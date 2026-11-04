# -*- coding: utf-8 -*-
"""把程序图标合成为一张整体图：圆角白块 + 羽毛 + 柔和投影 + 边缘微溶解。

目的：不再依赖 CSS 的 drop-shadow，图标本身就是一个完整对象，
和底色之间是柔和的过渡，不是一张贴纸。
"""
import os

from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(HERE, "qt_ui", "feather_icon.png")
DST = os.path.join(HERE, "qt_ui", "boot_icon.png")

SCALE = 2           # 输出 2 倍图，缩放到 236px 显示依然锐利
PAD = 46            # 四周留给投影的边距


def main():
    src = Image.open(SRC).convert("RGBA")
    w, h = src.size
    W, H = (w + PAD * 2) * SCALE, (h + PAD * 2) * SCALE
    src = src.resize((w * SCALE, h * SCALE), Image.LANCZOS)
    w, h = src.size

    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ox, oy = (W - w) // 2, (H - h) // 2

    # 1) 投影：取图标 alpha 做形状，往下偏移后高斯模糊
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    alpha = src.split()[3]
    tint = Image.new("RGBA", (w, h), (38, 64, 120, 255))
    tint.putalpha(alpha)
    shadow.paste(tint, (ox, oy + 14 * SCALE), tint)
    shadow = shadow.filter(ImageFilter.GaussianBlur(18 * SCALE))
    # 压暗投影浓度
    px = shadow.load()
    for y in range(H):
        for x in range(0, W, 1):
            r, g, b, a = px[x, y]
            if a:
                px[x, y] = (r, g, b, int(a * 0.30))
    canvas = Image.alpha_composite(canvas, shadow)

    # 2) 第二层更紧的接触阴影，让图标"落"在面上
    contact = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    tint2 = Image.new("RGBA", (w, h), (30, 52, 96, 255))
    tint2.putalpha(alpha)
    contact.paste(tint2, (ox, oy + 5 * SCALE), tint2)
    contact = contact.filter(ImageFilter.GaussianBlur(5 * SCALE))
    px = contact.load()
    for y in range(H):
        for x in range(W):
            r, g, b, a = px[x, y]
            if a:
                px[x, y] = (r, g, b, int(a * 0.22))
    canvas = Image.alpha_composite(canvas, contact)

    # 3) 图标本体
    canvas.paste(src, (ox, oy), src)

    canvas.save(DST)
    print("已生成 %s  %dx%d  %.1f KB" % (DST, W, H, os.path.getsize(DST) / 1024))

    # 预览：放到开机底色上
    bg = Image.new("RGB", (W, H), (233, 238, 246))
    bg.paste(canvas, (0, 0), canvas)
    prev = os.path.join(HERE, "_bootshots", "icon_composite_preview.png")
    bg.save(prev)
    print("预览", prev)


if __name__ == "__main__":
    main()
