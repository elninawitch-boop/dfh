# -*- coding: utf-8 -*-
"""启动真实主窗口，在指定时刻截图，用来核对真实渲染效果。

用法：python scripts/shot_app.py [毫秒,...]
默认在 1200/2000/2600/4000 ms 各截一张。
"""
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

# 可以用环境变量指定另一份 index.html 做新旧对照
if os.environ.get("UI_OVERRIDE"):
    app_mod.UI_PATH = os.environ["UI_OVERRIDE"]

OUT = os.path.join(HERE, "_bootshots")
TIMES = [int(x) for x in sys.argv[1].split(",")] if len(sys.argv) > 1 else [1200, 2000, 2600, 4000]


def main():
    os.makedirs(OUT, exist_ok=True)
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv[:1])
    win = app_mod.Win()
    win.show()

    def shot(i):
        def _do():
            p = os.path.join(OUT, "app_%04d.png" % TIMES[i])
            win.view.grab().save(p)
            print("saved", p)
            if i + 1 < len(TIMES):
                QTimer.singleShot(TIMES[i + 1] - TIMES[i], shot(i + 1))
            else:
                QTimer.singleShot(200, app.quit)
        return _do

    QTimer.singleShot(TIMES[0], shot(0))
    app.exec()


if __name__ == "__main__":
    main()
