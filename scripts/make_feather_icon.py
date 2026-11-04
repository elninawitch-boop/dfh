# -*- coding: utf-8 -*-
"""从用户提供的羽毛图片生成程序图标（ico）

原图特征：白底、蓝色羽毛、圆角方块、底部有蓝色圆点
需要提取羽毛主体，做成透明背景的图标
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SRC_CANDIDATES = [
    r"C:\Users\123\Desktop\image.png",
    r"C:\Users\123\1\image.png",
    r"C:\Users\123\Downloads\image.png",
]

src = None
for c in SRC_CANDIDATES:
    if os.path.exists(c):
        src = c
        break

if not src:
    print("未找到原图，请把图片放到 C:\\Users\\123\\1\\image.png")
    print("查过的路径:")
    for c in SRC_CANDIDATES:
        print("  ", c)
    raise SystemExit(1)

print("源图片:", src)
img = Image.open(src).convert("RGBA")
print("尺寸:", img.size)

# 放大到 256x256 基准（如果太小）
w, h = img.size
target = 256
if max(w, h) < target:
    scale = target / max(w, h)
    img = img.resize((int(w * scale), int(h * scale)),
                     Image.Resampling.LANCZOS)
    print("放大到:", img.size)

# 裁成正方形（居中）
w, h = img.size
side = min(w, h)
left = (w - side) // 2
top = (h - side) // 2
img = img.crop((left, top, left + side, top + side))
img = img.resize((256, 256), Image.Resampling.LANCZOS)
print("裁成方形: 256x256")

# 分析图片：找出羽毛区域（非白色且非背景）
arr = np.array(img)
r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]
luma = 0.299 * r + 0.587 * g + 0.114 * b

# 羽毛是蓝色的：B 通道明显高于 R
is_feather = (b.astype(int) - r.astype(int) > 25) & (b > 80)
# 深色描边也算羽毛的一部分
is_outline = (luma < 100) & (a > 128)
mask = is_feather | is_outline

print("羽毛像素占比: %.1f%%" % (mask.mean() * 100))

if mask.sum() < 100:
    print("警告：羽毛识别失败，直接用原图")
    icon = img
else:
    # 找羽毛的包围盒
    ys, xs = np.where(mask)
    y0, y1 = ys.min(), ys.max() + 1
    x0, x1 = xs.min(), xs.max() + 1
    print("羽毛区域: (%d,%d)-(%d,%d)  %dx%d"
          % (x0, y0, x1, y1, x1 - x0, y1 - y0))

    # 扩展一点边距
    pad = max(8, int((x1 - x0) * 0.12))
    x0 = max(0, x0 - pad)
    y0 = max(0, y0 - pad)
    x1 = min(256, x1 + pad)
    y1 = min(256, y1 + pad)

    # 提取羽毛
    feather = img.crop((x0, y0, x1, y1))
    fw, fh = feather.size

    # 做成正方形画布（保持比例）
    canvas_side = max(fw, fh)
    icon = Image.new("RGBA", (canvas_side, canvas_side), (0, 0, 0, 0))
    # 居中放置
    ox = (canvas_side - fw) // 2
    oy = (canvas_side - fh) // 2

    # 羽毛部分：白色背景变透明
    fa = np.array(feather)
    fr, fg, fb = fa[:, :, 0], fa[:, :, 1], fa[:, :, 2]
    fluma = 0.299 * fr + 0.587 * fg + 0.114 * fb

    # 白色背景 -> 透明（保留羽毛的蓝和黑描边）
    fa_mask = np.where(
        (fluma > 235) & (fb.astype(int) - fr.astype(int) < 20),
        0,      # 纯白 -> 全透明
        255     # 其余保留
    ).astype(np.uint8)

    # 边缘羽化
    alpha_img = Image.fromarray(fa_mask, "L").filter(
        ImageFilter.GaussianBlur(0.6))
    feather.putalpha(alpha_img)

    icon.paste(feather, (ox, oy), feather)

# 缩放到标准尺寸并保存
icon = icon.resize((256, 256), Image.Resampling.LANCZOS)

out_png = r"C:\Users\123\1\feather_icon.png"
icon.save(out_png)
print("已保存 PNG:", out_png)

# 生成多尺寸 ico
out_ico = r"C:\Users\123\1\feather_icon.ico"
icon.save(out_ico, sizes=[
    (16, 16), (24, 24), (32, 32), (48, 48),
    (64, 64), (128, 128), (256, 256)
])
print("已保存 ICO:", out_ico)
print("ICO 大小: %.1f KB" % (os.path.getsize(out_ico) / 1024))
