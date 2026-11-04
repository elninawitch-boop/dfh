# -*- coding: utf-8 -*-
"""诊断：修复过程中主线程是否被卡住（UI 冻结）。

做法：主线程挂一个 50ms 心跳定时器，记录每次触发的间隔。
如果修复期间出现远超 50ms 的空档，说明主线程被 GIL 或长任务饿死了。
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
    "--high-dpi-support=1 --disable-features=NetworkService "
    "--disable-background-networking --no-pings --disable-sync"
)

from PySide6.QtCore import QTimer, Qt            # noqa: E402
from PySide6.QtWidgets import QApplication      # noqa: E402

import psd_repair_qt as app_mod                 # noqa: E402

SAMPLE = sys.argv[1] if len(sys.argv) > 1 else r"E:/zh/1111_CORRUPTED_bak.psd"


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv[:1])
    win = app_mod.Win()
    win.show()

    beats = []
    last = [time.monotonic()]
    state = {"fixing": False, "done": False}

    hb = QTimer()
    hb.setInterval(50)

    def beat():
        now = time.monotonic()
        gap = now - last[0]
        last[0] = now
        if state["fixing"]:
            beats.append(gap)

    hb.timeout.connect(beat)
    hb.start(50)

    def start():
        print("[diag] 载入", SAMPLE)
        win.bridge.load_path(SAMPLE)

    def maybe_fix():
        if win.bridge.probe is None:
            QTimer.singleShot(300, maybe_fix)
            return
        print("[diag] 解析完成，开始修复")
        state["fixing"] = True
        last[0] = time.monotonic()
        win.bridge.start_fix('{"trim": true}')
        watch()

    def watch():
        if win.bridge.busy:
            QTimer.singleShot(300, watch)
            return
        state["fixing"] = False
        report()

    def report():
        if not beats:
            print("[diag] 没采到心跳")
        else:
            beats_sorted = sorted(beats, reverse=True)
            over200 = [b for b in beats if b > 0.2]
            print("[diag] 心跳样本 %d 个（约 %.1f 秒）" % (len(beats), sum(beats)))
            print("[diag] 最大空档 %.0f ms" % (beats_sorted[0] * 1000))
            print("[diag] 前 8 大空档: " + ", ".join("%.0fms" % (b * 1000) for b in beats_sorted[:8]))
            print("[diag] 超过 200ms 的卡顿次数: %d" % len(over200))
            print("[diag] 卡顿总时长 %.1f 秒" % sum(over200))
        app.quit()

    QTimer.singleShot(2500, start)
    QTimer.singleShot(4000, maybe_fix)
    QTimer.singleShot(600000, app.quit)
    app.exec()


if __name__ == "__main__":
    main()
