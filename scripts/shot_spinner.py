# -*- coding: utf-8 -*-
"""抓 spinner 的连续帧，裁出按钮和标题栏两处，做成 GIF 预览。"""
import os
import sys
import json

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

geo = {}

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
    "--high-dpi-support=1 --disable-features=NetworkService"
)

from PySide6.QtCore import QTimer, Qt            # noqa: E402
from PySide6.QtWidgets import QApplication      # noqa: E402

import psd_repair_qt as m                       # noqa: E402

OUT = os.path.join(HERE, "_bootshots")
FRAMES = 14

JS = """(function(){
  S.busy = true; S.progress = 0.42; S.stage = '解码图层';
  S.layers.forEach(function(L,i){ L.state = i<6?'done':(i===6?'run':'wait');
    L.frac = i<6?1:(i===6?0.5:0); L.detail = i<6?'完成':(i===6?'解码中':'等待'); });
  setSpinning(true); setFixLabel('修复中…');
  document.getElementById('prog').classList.add('open');
  renderProgList(); renderProgress();
  var b = document.getElementById('btn-fix').getBoundingClientRect();
  var h = document.getElementById('prog-head').getBoundingClientRect();
  return JSON.stringify({dpr: window.devicePixelRatio,
    btn:[b.x,b.y,b.width,b.height], head:[h.x,h.y,h.width,h.height]});
})()"""


def main():
    os.makedirs(OUT, exist_ok=True)
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv[:1])
    w = m.Win()
    w.show()

    shots = []
    state = {"i": 0}

    def begin():
        w.bridge.load_path(r"E:/zh/1111_CORRUPTED_bak.psd")
        QTimer.singleShot(2600, inject)

    def inject():
        def got(v):
            try:
                geo.update(json.loads(v))
            except Exception:
                pass
            QTimer.singleShot(500, tick)
        w.view.page().runJavaScript(JS, got)

    def tick():
        state["i"] += 1
        p = os.path.join(OUT, "sp_%02d.png" % state["i"])
        w.view.grab().save(p)
        shots.append(p)
        if state["i"] < FRAMES:
            QTimer.singleShot(40, tick)
        else:
            build(shots)
            app.quit()

    QTimer.singleShot(1800, begin)
    app.exec()


def build(shots):
    from PIL import Image
    ims = [Image.open(p).convert("RGB") for p in shots]
    W, H = ims[0].size
    dpr = geo.get("dpr", 1.0) or 1.0

    def box(key, pad):
        x, y, w, h = geo.get(key, [0, 0, 100, 40])
        return (max(0, int((x - pad) * dpr)), max(0, int((y - pad) * dpr)),
                min(W, int((x + w + pad) * dpr)), min(H, int((y + h + pad) * dpr)))

    # 按钮整体放大；标题栏只裁「PROGRESS + spinner + 阶段文字」那一段
    regions = [("spin_btn", box("btn", 6), 5),
               ("spin_hdr", box("head", 4), 4)]

    for name, bx, scale in regions:
        crops = [im.crop(bx) for im in ims]
        w0, h0 = crops[0].size
        big = [c.resize((w0 * scale, h0 * scale), Image.LANCZOS) for c in crops]
        gif = os.path.join(OUT, name + ".gif")
        big[0].save(gif, save_all=True, append_images=big[1:],
                    duration=90, loop=0, optimize=True)
        print("GIF ->", gif)
        big[3].save(os.path.join(OUT, name + "_static.png"))
    print("静态图已存")


if __name__ == "__main__":
    main()
