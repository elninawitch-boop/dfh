# -*- coding: utf-8 -*-
"""验证 Qt 层拖放拦截：合成一个带本地文件 URL 的 QDropEvent，看能不能取到路径。

注意：合成事件不走 Chromium 原生拖放路径，只验证 Qt 层的过滤器与回调链路。
"""
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
    "--high-dpi-support=1 --disable-features=NetworkService "
    "--disable-background-networking --no-pings --disable-sync"
)

from PySide6.QtCore import QMimeData, QPoint, QTimer, QUrl, Qt      # noqa: E402
from PySide6.QtGui import QDropEvent, QDragEnterEvent               # noqa: E402
from PySide6.QtWidgets import QApplication                          # noqa: E402

import psd_repair_qt as app_mod                                     # noqa: E402

SAMPLE = r"E:/1/pfa/deliverables/PFA_record_vinyl.psd"


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv[:1])
    win = app_mod.Win()
    win.show()

    def fire():
        target = win.view.focusProxy() or win.view
        md = QMimeData()
        md.setUrls([QUrl.fromLocalFile(SAMPLE)])

        pos = QPoint(60, 60)
        enter = QDragEnterEvent(pos, Qt.CopyAction, md, Qt.LeftButton, Qt.NoModifier)
        QApplication.sendEvent(target, enter)
        print("DragEnter 被接受:", enter.isAccepted())

        drop = QDropEvent(pos, Qt.CopyAction, md, Qt.LeftButton, Qt.NoModifier)
        QApplication.sendEvent(target, drop)
        print("Drop 被接受:", drop.isAccepted())
        print("bridge.file_path =", win.bridge.file_path)

        def check():
            p = win.bridge.probe
            if p is None:
                print("结果: 失败 —— 没有解析出 probe")
            else:
                print("结果: 成功 —— %dx%d, %d 层, %d 个问题"
                      % (p.width, p.height, len(p.layers), len(p.issues)))
            app.quit()

        QTimer.singleShot(2500, check)

    QTimer.singleShot(2500, fire)
    app.exec()


if __name__ == "__main__":
    main()
