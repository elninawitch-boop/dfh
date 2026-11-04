# -*- coding: utf-8 -*-
"""对比中文字体在实际字号下的可读性"""
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import os

LOCAL = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Windows\Fonts")
WIN = r"C:\Windows\Fonts"

FONTS = [
    ("NotoSansSC-VF (当前)", os.path.join(WIN, "NotoSansSC-VF.ttf")),
    ("MiSans-Regular", os.path.join(WIN, "MiSans-Regular.otf")),
    ("msyh 微软雅黑", os.path.join(WIN, "msyh.ttc")),
    ("Deng 等线", os.path.join(WIN, "Deng.ttf")),
    ("SourceHan-Light", os.path.join(LOCAL, "SourceHanSansSC-Light.otf")),
    ("simhei 黑体", os.path.join(WIN, "simhei.ttf")),
]

SAMPLE = "拖入 PSD 文件，或点击选择"
SIZE = 13
W, H = 460, len(FONTS) * 46 + 10
img = Image.new("RGB", (W, H), (250, 251, 253))
d = ImageDraw.Draw(img)

print("字体可读性对比（字号 %d，中文样本）" % SIZE)
print("%-22s %-12s %-12s" % ("字体", "暗像素占比", "平均笔画浓度"))
for i, (name, path) in enumerate(FONTS):
    if not os.path.exists(path):
        print("%-22s 缺失" % name)
        continue
    f = ImageFont.truetype(path, SIZE)
    y = 8 + i * 46
    d.text((10, y), name[:14], font=ImageFont.truetype(path, 11),
           fill=(120, 130, 145))
    d.text((10, y + 20), SAMPLE, font=f, fill=(0, 0, 0))
    crop = np.array(img.crop((0, y + 18, W, y + 40)))
    mask = crop.mean(axis=2) < 128
    ratio = mask.mean() * 100
    # 笔画浓度：暗像素的平均灰度（越低越实）
    ink = crop.mean(axis=2)[mask].mean() if mask.any() else 255
    print("%-22s %8.1f%%   %8.1f" % (name, ratio, ink))

img.resize((W * 2, H * 2), Image.Resampling.NEAREST).save(
    r"C:\Users\123\1\font_compare.png")
print("\n已保存 font_compare.png")
