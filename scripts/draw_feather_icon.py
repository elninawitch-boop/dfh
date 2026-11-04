# -*- coding: utf-8 -*-
"""绘制羽毛图标（模仿用户提供的样式：蓝色羽毛 + 深色描边 + 白底圆角 + 底部蓝点）"""
import os
from PIL import Image, ImageDraw, ImageFilter

S = 256
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# ---------- 1. 白色圆角底 ----------
margin = 18
radius = 46
d.rounded_rectangle(
    [margin, margin, S - margin, S - margin],
    radius=radius, fill=(252, 253, 255, 255))

# 轻微阴影（让图标有立体感）
shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
sd = ImageDraw.Draw(shadow)
sd.rounded_rectangle(
    [margin + 2, margin + 4, S - margin + 2, S - margin + 4],
    radius=radius, fill=(60, 90, 150, 40))
shadow = shadow.filter(ImageFilter.GaussianBlur(6))
img = Image.alpha_composite(shadow, img)
d = ImageDraw.Draw(img)

# ---------- 2. 羽毛 ----------
# 羽毛中心线（从左下到右上，略微弯曲）
cx, cy = S // 2, S // 2

# 羽毛主体路径：一个细长的柳叶形
feather_pts = [
    (108, 196),   # 底部尖端
    (104, 180),
    (100, 160),
    (98, 140),
    (99, 120),
    (103, 100),
    (110, 82),
    (120, 68),
    (133, 58),
    (148, 54),    # 顶部尖端
    (158, 58),
    (152, 70),
    (142, 84),
    (133, 100),
    (126, 118),
    (121, 138),
    (118, 158),
    (116, 178),
    (114, 194),
]

# 深色描边层（略大）
outline_pts = [(x + 2, y + 2) for (x, y) in feather_pts]
d.polygon(outline_pts, fill=(25, 30, 45, 255))
d.polygon(feather_pts, fill=(58, 128, 228, 255))

# ---------- 3. 羽毛中脊（高光） ----------
spine = [(108, 192), (112, 160), (117, 128), (124, 100), (133, 76), (145, 60)]
d.line(spine, fill=(150, 200, 255, 220), width=3, joint="curve")

# 细描边加强
d.line([(108, 196), (120, 132), (148, 54)],
       fill=(20, 25, 40, 255), width=1)

# ---------- 4. 羽枝纹理 ----------
import math
for i in range(7):
    t = i / 7.0
    # 沿中脊取点
    px = 110 + (145 - 110) * t
    py = 190 - (190 - 62) * t
    length = 16 * (1 - t) + 6
    # 左侧羽枝
    d.line([(px, py), (px - length, py + length * 0.55)],
           fill=(35, 80, 160, 200), width=2)
    # 右侧羽枝
    d.line([(px + 4, py), (px + 4 + length * 0.8, py + length * 0.5)],
           fill=(35, 80, 160, 200), width=2)

# ---------- 5. 底部蓝色圆点（进度条效果） ----------
dot_y = 218
d.rounded_rectangle([104, dot_y - 5, 152, dot_y + 5],
                    radius=5, fill=(30, 110, 220, 255))

# ---------- 6. 圆角裁剪（整体） ----------
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle(
    [margin, margin, S - margin, S - margin],
    radius=radius, fill=255)
img.putalpha(mask)

out_png = r"C:\Users\123\1\feather_icon.png"
img.save(out_png)
print("已保存 PNG:", out_png)

out_ico = r"C:\Users\123\1\feather_icon.ico"
img.save(out_ico, sizes=[
    (16, 16), (24, 24), (32, 32), (48, 48),
    (64, 64), (128, 128), (256, 256)])
print("已保存 ICO:", out_ico)
print("ICO 大小: %.1f KB" % (os.path.getsize(out_ico) / 1024))
