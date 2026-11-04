# -*- coding: utf-8 -*-
"""进度条状态预览：把 4 个状态渲染出来拼成一张对比图。

用法：python scripts/preview_progress.py
输出：_bootshots/progress_states.png
"""
import os
import sys

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtWebEngineWidgets import QWebEngineView

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI = os.path.join(HERE, "qt_ui", "index.html")
OUT = os.path.join(HERE, "_bootshots")
os.makedirs(OUT, exist_ok=True)

STATES = [
    ("空闲 · 0%", """
        S.busy=false; S.progress=0; S.stage='';
        document.getElementById('track').className='track';
        renderProgress(); setStatus('等待文件');
    """),
    ("处理中 · 12%", """
        S.busy=true; S.progress=0.12; S.stage='分析结构';
        document.getElementById('track').className='track';
        renderProgress(); setStatus('113.08 MB · 2126 × 1417 · 14 个图层');
    """),
    ("处理中 · 47%", """
        S.busy=true; S.progress=0.47; S.stage='解码通道 07/14';
        document.getElementById('track').className='track';
        renderProgress(); setStatus('正在重建合并图 · 剩余约 8 秒');
    """),
    ("完成 · 100%", """
        S.busy=false; S.progress=1; S.stage='完成 · 结构校验通过';
        document.getElementById('track').className='track done';
        renderProgress(); setStatus('已保存 1111_FIXED.psd · 51.80 MB');
    """),
]


def main():
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
    app = QApplication(sys.argv)
    win = QMainWindow()
    win.resize(1200, 880)
    view = QWebEngineView(win)
    win.setCentralWidget(view)
    win.show()
    view.load(QUrl.fromLocalFile(UI))

    shots = []

    def grab(i):
        def _do():
            js = STATES[i][1]
            view.page().runJavaScript(js, lambda _=None: _save(i))
        return _do

    def _save(i):
        def _after():
            pm = win.grab()
            p = os.path.join(OUT, "p%d.png" % i)
            pm.save(p)
            shots.append((STATES[i][0], p))
            print("saved", p)
            if i + 1 < len(STATES):
                QTimer.singleShot(420, grab(i + 1))
            else:
                QTimer.singleShot(200, lambda: (compose(shots), app.quit()))
        # 让 CSS 过渡走完再抓
        QTimer.singleShot(700, _after)

    QTimer.singleShot(3000, grab(0))
    app.exec()


def compose(shots):
    from PIL import Image, ImageDraw, ImageFont
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc", 22)
    except Exception:
        font = ImageFont.load_default()

    crops = []
    for label, p in shots:
        im = Image.open(p).convert("RGB")
        w, h = im.size
        crop = im.crop((0, int(h * 0.86), w, int(h * 0.975)))
        crops.append((label, crop))

    pad = 16
    lw = 190
    cw = max(c.size[0] for _, c in crops)
    ch = max(c.size[1] for _, c in crops)
    W = lw + cw + pad * 2
    H = (ch + pad) * len(crops) + pad
    out = Image.new("RGB", (W, H), (250, 251, 253))
    d = ImageDraw.Draw(out)
    y = pad
    for label, c in crops:
        d.text((pad, y + ch // 2 - 14), label, font=font, fill=(20, 26, 38))
        out.paste(c, (lw + pad, y))
        y += ch + pad
    dst = os.path.join(OUT, "progress_states.png")
    out.save(dst)
    print("composed ->", dst)


if __name__ == "__main__":
    main()
