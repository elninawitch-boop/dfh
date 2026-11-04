# -*- coding: utf-8 -*-
"""在真实 Qt WebEngine 里截一张静态页面，验证 backdrop-filter 与 opacity 动画的关系。"""
import os
import sys

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtWebEngineWidgets import QWebEngineView

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI = os.path.join(HERE, "_bootshots", "stacktest.html")
OUT = os.path.join(HERE, "_bootshots", "stacktest.png")


def main():
    app = QApplication(sys.argv[:1])
    win = QMainWindow()
    win.resize(1200, 620)
    view = QWebEngineView(win)
    win.setCentralWidget(view)
    win.show()
    view.load(QUrl.fromLocalFile(UI))

    def grab():
        pm = view.grab()
        pm.save(OUT)
        print("saved", OUT, pm.size())
        app.quit()

    QTimer.singleShot(4000, grab)
    app.exec()


if __name__ == "__main__":
    main()
