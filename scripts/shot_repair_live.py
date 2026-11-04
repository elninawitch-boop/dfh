# -*- coding: utf-8 -*-
"""修复过程中连续抓帧，验证进度条是否真的在推进。"""
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
    "--high-dpi-support=1 --disable-features=NetworkService "
    "--disable-background-networking --no-pings --disable-sync"
)

from PySide6.QtCore import QTimer, Qt            # noqa: E402
from PySide6.QtWidgets import QApplication      # noqa: E402

import psd_repair_qt as app_mod                 # noqa: E402

SAMPLE = r"E:/zh/1111_CORRUPTED_bak.psd"
OUT = os.path.join(HERE, "_bootshots")


def main():
    os.makedirs(OUT, exist_ok=True)
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv[:1])
    win = app_mod.Win()
    win.show()

    frames = []
    seq = {"i": 0}

    def start():
        win.bridge.load_path(SAMPLE)

    def begin():
        if win.bridge.probe is None:
            QTimer.singleShot(300, begin)
            return
        print("[live] 开始修复")
        win.bridge.start_fix('{"trim": true}')
        QTimer.singleShot(900, grab)

    def grab():
        seq["i"] += 1
        p = os.path.join(OUT, "live_%02d.png" % seq["i"])
        win.view.grab().save(p)
        frames.append(p)
        # 顺带把当前进度打出来
        win.view.page().runJavaScript(
            "(function(){try{return JSON.stringify({"
            "vis:document.visibilityState,"
            "s:+(S.progress||0).toFixed(3),"
            "t:+(PV.target||0).toFixed(3),"
            "sh:+(PV.shown||0).toFixed(3),"
            "raf:PV.raf?1:0,"
            "done:S.layers.filter(function(L){return L.state==='done'}).length,"
            "n:S.layers.length})}catch(e){return 'ERR '+e}})()",
            lambda v: print("[live] %02d  %s" % (seq["i"], v)))
        if win.bridge.busy and seq["i"] < 20:
            QTimer.singleShot(1500, grab)
        else:
            QTimer.singleShot(1200, grab)   # 完成后补一帧
            QTimer.singleShot(2500, app.quit)

    QTimer.singleShot(2500, start)
    QTimer.singleShot(4000, begin)
    QTimer.singleShot(120000, app.quit)
    app.exec()
    print("[live] 帧数", len(frames))


if __name__ == "__main__":
    main()
