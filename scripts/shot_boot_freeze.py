# -*- coding: utf-8 -*-
"""把开机动画冻结到指定毫秒再抓帧，逐 20ms 检查背景与图标是否同时出现。

grab() 本身慢，但动画是冻结的，所以抓帧耗时不影响到画面时刻。
"""
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
    "--high-dpi-support=1 --disable-features=NetworkService "
    "--disable-background-networking --no-pings --disable-sync"
)

from PySide6.QtCore import QTimer, QUrl, Qt       # noqa: E402
from PySide6.QtWidgets import QApplication, QMainWindow  # noqa: E402
from PySide6.QtWebEngineWidgets import QWebEngineView    # noqa: E402

UI = os.path.join(HERE, "qt_ui", "index.html")
OUT = os.path.join(HERE, "_bootshots")
TIMES = [0, 20, 40, 60, 80, 100, 120, 160, 220, 320, 500]

FREEZE = """
(function(t){
  var n = 0;
  (document.getAnimations ? document.getAnimations() : []).forEach(function(a){
    try { a.pause(); a.currentTime = t; n++; } catch(e){}
  });
  return n;
})(%d)
"""


def main():
    app = QApplication(sys.argv[:1])
    win = QMainWindow()
    win.resize(1200, 880)
    view = QWebEngineView(win)
    win.setCentralWidget(view)
    win.show()
    view.load(QUrl.fromLocalFile(UI))

    shots = []
    state = {"loaded": False}
    view.loadFinished.connect(lambda ok: state.update(loaded=ok))

    def step(i=0):
        if i >= len(TIMES):
            compose(shots)
            app.quit()
            return
        t = TIMES[i]

        def after(_=None):
            def grab(_=None):
                p = os.path.join(OUT, "fz_%04d.png" % t)
                view.grab().save(p)
                shots.append((t, p))
                print("[freeze] %dms 已抓" % t)
                QTimer.singleShot(40, lambda: step(i + 1))
            QTimer.singleShot(120, grab)

        view.page().runJavaScript(FREEZE % t, after)

    def start():
        if not state["loaded"]:
            QTimer.singleShot(200, start)
            return
        QTimer.singleShot(600, lambda: step(0))

    QTimer.singleShot(300, start)
    app.exec()


def compose(shots):
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc", 15)
    ims = []
    for t, p in shots:
        im = Image.open(p).convert("RGB")
        im = im.resize((im.width // 6, im.height // 6), Image.LANCZOS)
        ims.append((t, im))
    w, h = ims[0][1].size
    cols, pad, lab = 6, 6, 18
    rows = (len(ims) + cols - 1) // cols
    out = Image.new("RGB", (cols * w + (cols + 1) * pad,
                            rows * (h + lab) + (rows + 1) * pad), (222, 226, 233))
    d = ImageDraw.Draw(out)
    for i, (t, im) in enumerate(ims):
        r, c = divmod(i, cols)
        x = pad + c * (w + pad)
        y = pad + r * (h + lab + pad)
        out.paste(im, (x, y))
        d.text((x + 2, y + h + 1), "%dms" % t, font=font, fill=(20, 26, 38))
    dst = os.path.join(OUT, "boot_freeze.png")
    out.save(dst)
    print("composed ->", dst)


if __name__ == "__main__":
    main()
