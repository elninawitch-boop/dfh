# -*- coding: utf-8 -*-
"""绘制羽毛图标 v2：羽枝收在羽毛内部，更干净"""
import os
from PIL import Image, ImageDraw, ImageFilter

S = 256
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# ---------- 1. 阴影 ----------
margin = 18
radius = 46
shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
ImageDraw.Draw(shadow).rounded_rectangle(
    [margin + 2, margin + 5, S - margin + 2, S - margin + 5],
    radius=radius, fill=(50, 80, 140, 45))
img = Image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(7)), img)

# ---------- 2. 白色圆角底 ----------
d = ImageDraw.Draw(img)
d.rounded_rectangle([margin, margin, S - margin, S - margin],
                    radius=radius, fill=(251, 252, 255, 255))

# ---------- 3. 羽毛主体（更修长的柳叶形） ----------
# 用贝塞尔近似：从底部尖端到顶部尖端
def bezier(p0, p1, p2, p3, n=40):
    pts = []
    for i in range(n + 1):
        t = i / n
        mt = 1 - t
        x = (mt**3 * p0[0] + 3 * mt**2 * t * p1[0] +
             3 * mt * t**2 * p2[0] + t**3 * p3[0])
        y = (mt**3 * p0[1] + 3 * mt**2 * t * p1[1] +
             3 * mt * t**2 * p2[1] + t**3 * p3[1])
        pts.append((x, y))
    return pts

# 左边缘
left_edge = bezier((116, 200), (96, 170), (94, 110), (140, 52))
# 右边缘（反向）
right_edge = bezier((140, 52), (168, 96), (150, 165), (116, 200))
feather = left_edge + right_edge[1:]

# 深色外描边
d.polygon([(x + 2.5, y + 2.5) for (x, y) in feather],
          fill=(22, 28, 42, 255))
# 主体蓝
d.polygon(feather, fill=(62, 132, 230, 255))

# ---------- 4. 内部羽枝（裁剪在羽毛内） ----------
# 用羽毛形状做遮罩
feather_mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(feather_mask).polygon(feather, fill=255)

branch = Image.new("RGBA", (S, S), (0, 0, 0, 0))
bd = ImageDraw.Draw(branch)
for i in range(8):
    t = i / 8.0
    # 中脊上的点
    px = 118 + (138 - 118) * t
    py = 196 - (196 - 58) * t
    ln = 14 * (1 - t * 0.7) + 5
    # 左右羽枝，方向朝下外
    bd.line([(px, py), (px - ln * 0.9, py + ln * 0.7)],
            fill=(220, 238, 255, 130), width=2)
    bd.line([(px + 3, py), (px + 3 + ln * 0.75, py + ln * 0.65)],
            fill=(220, 238, 255, 130), width=2)

# 裁到羽毛内部
branch_cropped = Image.new("RGBA", (S, S), (0, 0, 0, 0))
branch_cropped.paste(branch, (0, 0), feather_mask)
img = Image.alpha_composite(img, branch_cropped)

# ---------- 5. 中脊高光 ----------
d = ImageDraw.Draw(img)
spine = bezier((116, 198), (108, 150), (108, 100), (139, 54), 30)
d.line(spine, fill=(180, 215, 255, 235), width=3, joint="curve")

# ---------- 6. 底部蓝点 ----------
d.rounded_rectangle([108, 213, 148, 223], radius=5,
                    fill=(30, 108, 220, 255))

# ---------- 7. 圆角裁剪 ----------
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle(
    [margin, margin, S - margin, S - margin], radius=radius, fill=255)
img.putalpha(mask)

img.save(r"C:\Users\123\1\feather_icon.png")
img.save(r"C:\Users\123\1\feather_icon.ico", sizes=[
    (16, 16), (24, 24), (32, 32), (48, 48),
    (64, 64), (128, 128), (256, 256)])
print("图标已生成")
print("PNG:", r"C:\Users\123\1\feather_icon.png")
print("ICO:", r"C:\Users\123\1\feather_icon.ico",
      "%.1f KB" % (os.path.getsize(r"C:\Users\123\1\feather_icon.ico") / 1024))
