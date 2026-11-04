# -*- coding: utf-8 -*-
"""在真实主窗口里切换进度条状态并截图，用来核对底部进度条的视觉。"""
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
    "--high-dpi-support=1 --disable-features=NetworkService "
    "--disable-background-networking --disable-component-update "
    "--disable-domain-reliability --no-pings --disable-sync"
)

from PySide6.QtCore import QTimer, Qt           # noqa: E402
from PySide6.QtWidgets import QApplication     # noqa: E402

import psd_repair_qt as app_mod                # noqa: E402

OUT = os.path.join(HERE, "_bootshots")

STATES = [
    ("0% 空闲", "S.busy=false;S.progress=0;S.stage='';"
                "S.layers=[];"
                "document.getElementById('track').className='track';"
                "renderProgress();setStatus('等待文件');"),
    ("12% 分析中", "S.busy=true;S.progress=0.12;S.stage='分析结构';"
                   "S.layers=Array.from({length:14},(_,i)=>({name:'L'+i,state:'wait',frac:0,detail:'等待'}));"
                   "document.getElementById('track').className='track';"
                   "renderProgress();setStatus('113.08 MB · 2126 × 1417 · 14 个图层');"),
    ("47% 解码中", "S.busy=true;S.progress=0.47;S.stage='解码通道 07/14';"
                   "S.layers=Array.from({length:14},(_,i)=>({name:'L'+i,"
                   "state:i<6?'done':(i===6?'run':'wait'),frac:i<6?1:(i===6?0.5:0),"
                   "detail:i<6?'完成':(i===6?'解码中':'等待')}));"
                   "document.getElementById('track').className='track';"
                   "renderProgress();setStatus('正在重建合并图 · 剩余约 8 秒');"),
    ("100% 完成", "S.busy=false;S.progress=1;S.stage='完成 · 结构校验通过';"
                  "S.layers=Array.from({length:14},(_,i)=>({name:'L'+i,state:'done',frac:1,detail:'完成'}));"
                  "document.getElementById('track').className='track done';"
                  "renderProgress();setStatus('已保存 1111_FIXED.psd · 51.80 MB');"),
]


def main():
    os.makedirs(OUT, exist_ok=True)
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv[:1])
    win = app_mod.Win()
    win.show()

    shots = []

    def step(i):
        if i >= len(STATES):
            compose(shots)
            app.quit()
            return
        label, js = STATES[i]

        def after(_=None):
            def grab():
                p = os.path.join(OUT, "pr_%d.png" % i)
                win.view.grab().save(p)
                shots.append((label, p))
                print("saved", p)
                QTimer.singleShot(120, lambda: step(i + 1))
            QTimer.singleShot(650, grab)

        win.view.page().runJavaScript(js, after)

    QTimer.singleShot(3000, lambda: step(0))
    app.exec()


def compose(shots):
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc", 26)
    crops = []
    for label, p in shots:
        im = Image.open(p).convert("RGB")
        W, H = im.size
        # 底部 130px（含进度条与状态行）
        crop = im.crop((0, H - int(130 * H / 800.0) - 10, W, H - 4))
        crops.append((label, crop))
    pad, labw = 18, 190
    cw = max(c.size[0] for _, c in crops)
    ch = max(c.size[1] for _, c in crops)
    out = Image.new("RGB", (labw + cw + pad * 2, (ch + pad) * len(crops) + pad), (246, 248, 251))
    d = ImageDraw.Draw(out)
    y = pad
    for label, c in crops:
        d.text((pad, y + ch // 2 - 16), label, font=font, fill=(20, 26, 38))
        out.paste(c, (labw + pad, y))
        y += ch + pad
    dst = os.path.join(OUT, "progress_states.png")
    out.save(dst)
    print("composed ->", dst)


if __name__ == "__main__":
    main()
