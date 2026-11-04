# -*- coding: utf-8 -*-
"""开机动画逐帧抓图：验证白场 -> 图标 -> 变暗 -> 弥散 -> 面板 的时间轴。

用法：python scripts/preview_boot.py [输出目录]
抓取时间点：0.30s / 0.60s / 1.00s / 1.20s / 1.60s / 2.00s / 2.30s / 2.90s
"""
import os
import sys

from PySide6.QtCore import QTimer, QUrl, Qt
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtWebEngineWidgets import QWebEngineView

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI = os.path.join(HERE, "qt_ui", "index.html")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "_bootshots")

SHOTS = [300, 600, 1000, 1200, 1600, 2000, 2300, 2900]


def main():
    os.makedirs(OUT, exist_ok=True)
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"
    app = QApplication(sys.argv)

    win = QMainWindow()
    win.resize(1200, 880)
    view = QWebEngineView(win)
    win.setCentralWidget(view)
    win.show()
    view.load(QUrl.fromLocalFile(UI))

    def shot(i):
        def _do():
            pm = win.grab()
            p = os.path.join(OUT, "f%d_%04dms.png" % (i, SHOTS[i]))
            pm.save(p)
            print("saved", p)
            if i + 1 < len(SHOTS):
                QTimer.singleShot(SHOTS[i + 1] - SHOTS[i], shot(i + 1))
            else:
                QTimer.singleShot(300, app.quit)
        return _do

    QTimer.singleShot(SHOTS[0], shot(0))
    app.exec()


if __name__ == "__main__":
    main()
