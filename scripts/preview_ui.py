# -*- coding: utf-8 -*-
"""界面预览：把动画冻结在指定时刻再抓图，避免抓图延迟导致取帧不准。

用法：
  python scripts/preview_ui.py boot        # 开机动画 6 帧
  python scripts/preview_ui.py progress    # 进度条 4 种状态
输出目录：_bootshots/
"""
import json
import os
import sys

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtWebEngineWidgets import QWebEngineView

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI = os.path.join(HERE, "qt_ui", "index.html")
OUT = os.path.join(HERE, "_bootshots")
os.makedirs(OUT, exist_ok=True)

# 冻结所有 CSS 动画到指定毫秒
FREEZE_JS = """
(function(t){
  var anims = document.getAnimations ? document.getAnimations() : [];
  anims.forEach(function(a){
    try { a.pause(); a.currentTime = t; } catch(e){}
  });
  return anims.length;
})(%d)
"""

# 读某个元素的位置（CSS 像素）
RECT_JS = """
(function(sel){
  var e = document.querySelector(sel);
  if(!e) return null;
  var r = e.getBoundingClientRect();
  return JSON.stringify({x:r.x,y:r.y,w:r.width,h:r.height});
})(%s)
"""

BOOT_TIMES = [200, 500, 800, 1100, 1500, 2000, 2450, 2800]

PROGRESS_STATES = [
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


class Cap:
    def __init__(self, app):
        self.app = app
        self.win = QMainWindow()
        self.win.resize(1200, 880)
        self.view = QWebEngineView(self.win)
        self.win.setCentralWidget(self.view)
        self.win.show()
        self.loaded = False
        self.view.load(QUrl.fromLocalFile(UI))
        self.view.loadFinished.connect(self._on_load)

    def _on_load(self, ok):
        self.loaded = ok

    def run(self, fn):
        self._queue = fn
        QTimer.singleShot(1200, self._step)

    def _step(self):
        if not self.loaded:
            QTimer.singleShot(200, self._step)
            return
        self._queue(self)

    def js(self, code, cb=None):
        self.view.page().runJavaScript(code, cb or (lambda r: None))

    def grab(self, path):
        pm = self.win.grab()
        pm.save(path)
        return pm


def do_boot(cap):
    results = []

    def step(i):
        if i >= len(BOOT_TIMES):
            compose_boot(results)
            cap.app.quit()
            return
        t = BOOT_TIMES[i]

        def after_freeze(_):
            def after_paint(_=None):
                p = os.path.join(OUT, "boot_%04d.png" % t)
                cap.grab(p)
                results.append((t, p))
                print("saved", p)
                QTimer.singleShot(60, lambda: step(i + 1))
            QTimer.singleShot(90, after_paint)

        cap.js(FREEZE_JS % t, after_freeze)

    step(0)


def compose_boot(results):
    from PIL import Image, ImageDraw, ImageFont
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc", 20)
    except Exception:
        font = ImageFont.load_default()

    ims = [(t, Image.open(p).convert("RGB")) for t, p in results]
    scale = 0.42
    th = int(ims[0][1].size[1] * scale)
    tw = int(ims[0][1].size[0] * scale)
    ims = [(t, im.resize((tw, th), Image.LANCZOS)) for t, im in ims]

    cols = 4
    rows = (len(ims) + cols - 1) // cols
    pad, lab = 14, 30
    W = cols * tw + (cols + 1) * pad
    H = rows * (th + lab) + (rows + 1) * pad
    out = Image.new("RGB", (W, H), (236, 239, 245))
    d = ImageDraw.Draw(out)
    for k, (t, im) in enumerate(ims):
        r, c = divmod(k, cols)
        x = pad + c * (tw + pad)
        y = pad + r * (th + lab + pad)
        out.paste(im, (x, y))
        d.text((x + 2, y + th + 6), "%.2fs" % (t / 1000.0), font=font, fill=(30, 38, 52))
    dst = os.path.join(OUT, "boot_storyboard.png")
    out.save(dst)
    print("composed ->", dst)


def do_progress(cap):
    results = []

    def step(i):
        if i >= len(PROGRESS_STATES):
            compose_progress(results)
            cap.app.quit()
            return
        label, js = PROGRESS_STATES[i]

        def after_state(_):
            def after_freeze(_=None):
                def after_rect(rect):
                    def after_paint(_=None):
                        p = os.path.join(OUT, "prog_%d.png" % i)
                        cap.grab(p)
                        results.append((label, p, json.loads(rect) if rect else None))
                        print("saved", p)
                        QTimer.singleShot(60, lambda: step(i + 1))
                    QTimer.singleShot(90, after_paint)
                cap.js(RECT_JS % json.dumps(".foot"), after_rect)
            # 冻结在 3000ms：开机动画已结束，进度条过渡已走完
            cap.js(FREEZE_JS % 3000, after_freeze)

        cap.js(js, after_state)

    step(0)


def compose_progress(results):
    from PIL import Image, ImageDraw, ImageFont
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc", 24)
    except Exception:
        font = ImageFont.load_default()

    crops = []
    for label, p, rect in results:
        im = Image.open(p).convert("RGB")
        W, H = im.size
        # 用 CSS 坐标换算到像素，crop 出底部区域（含左右留白）
        if rect:
            sx = W / 1200.0
            sy = H / 880.0
            top = int((rect["y"] - 26) * sy)
            bot = int((rect["y"] + rect["h"] + 14) * sy)
            left = int((rect["x"] - 10) * sx)
            right = int((rect["x"] + rect["w"] + 10) * sx)
        else:
            top, bot, left, right = int(H * 0.94), H, 0, W
        crops.append((label, im.crop((max(0, left), max(0, top), min(W, right), min(H, bot)))))

    pad, labw = 18, 210
    cw = max(c.size[0] for _, c in crops)
    ch = max(c.size[1] for _, c in crops)
    W = labw + cw + pad * 2
    H = (ch + pad) * len(crops) + pad
    out = Image.new("RGB", (W, H), (247, 249, 252))
    d = ImageDraw.Draw(out)
    y = pad
    for label, c in crops:
        d.text((pad, y + ch // 2 - 15), label, font=font, fill=(22, 28, 40))
        out.paste(c, (labw + pad, y))
        y += ch + pad
    dst = os.path.join(OUT, "progress_states.png")
    out.save(dst)
    print("composed ->", dst)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "progress"
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
    app = QApplication(sys.argv[:1])
    cap = Cap(app)
    cap.run(do_boot if mode == "boot" else do_progress)
    app.exec()


if __name__ == "__main__":
    main()
