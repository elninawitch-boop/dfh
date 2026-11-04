# -*- coding: utf-8 -*-
"""验证 Qt WebEngine 视图能否接收原生文件拖放，以及 JS 侧 f.path 是否可用。"""
import os, sys, json

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
    "--disable-features=NetworkService --disable-background-networking "
    "--disable-component-update --disable-domain-reliability --no-pings --disable-sync"
)

from PySide6.QtCore import Qt, QMimeData, QUrl, QPoint, QTimer
from PySide6.QtGui import QDropEvent, QDragEnterEvent
from PySide6.QtWidgets import QApplication

import psd_repair_qt as appmod

PSD = r"C:\Users\123\1\pfa\deliverables\PFA_record_vinyl.psd"
PSD = r"E:\1\pfa\deliverables\PFA_record_vinyl.psd"
if not os.path.exists(PSD):
    for root, dirs, files in os.walk(r"C:\Users\123\1\pfa"):
        for f in files:
            if f.lower().endswith(".psd"):
                PSD = os.path.join(root, f); break
        if os.path.exists(PSD) and PSD.lower().endswith(".psd"): break
print("测试文件:", PSD, os.path.exists(PSD))

log = []

appmod.QApplication.setHighDpiScaleFactorRoundingPolicy(
    Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
app = QApplication(sys.argv)
w = appmod.Win()
w.show()

orig_js_obj = w.js_obj
def patched(func, obj):
    log.append(func)
    print("[->JS]", func, str(obj)[:80])
    return orig_js_obj(func, obj)
w.js_obj = patched

def report():
    print("\n==== 结果 ====")
    print("js_obj 调用:", log)
    hit = any(x in ("APP.setLoading", "APP.setProbe") for x in log)
    print("拖放是否生效:", "是" if hit else "否")
    app.quit()

def do_drop():
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(PSD)])
    pos = QPoint(w.view.width() // 2, w.view.height() // 2)

    targets = [("view", w.view), ("window", w)]
    # 也尝试发给 view 内部的真实 widget
    inner = w.view.focusProxy()
    if inner:
        targets.append(("focusProxy", inner))

    for name, tgt in targets:
        enter = QDragEnterEvent(pos, Qt.DropActions(Qt.CopyAction),
                                mime, Qt.MouseButtons(Qt.LeftButton),
                                Qt.KeyboardModifiers(Qt.NoModifier))
        QApplication.sendEvent(tgt, enter)
        print("[%s] dragEnter accepted=%s" % (name, enter.isAccepted()))
        drop = QDropEvent(pos, Qt.DropActions(Qt.CopyAction), mime,
                          Qt.MouseButtons(Qt.LeftButton),
                          Qt.KeyboardModifiers(Qt.NoModifier))
        QApplication.sendEvent(tgt, drop)
        print("[%s] drop accepted=%s" % (name, drop.isAccepted()))

    # 另外查一下 JS 侧能否拿到 File.path
    w.view.page().runJavaScript(
        "(()=>{try{const dt=new DataTransfer();return 'ok';}catch(e){return 'err';}})()",
        lambda r: print("[JS] DataTransfer 可用:", r))

    QTimer.singleShot(4000, report)

def start():
    # 先查 JS 里 drop 监听是否注册
    def cb(v):
        print("[JS] drop listener 检查:", v)
        QTimer.singleShot(300, do_drop)
    w.view.page().runJavaScript(
        "typeof document.ondrop + '|' + (window.__calls?__calls.length:'no')", cb)

w.view.loadFinished.connect(lambda ok: QTimer.singleShot(1500, start))
QTimer.singleShot(25000, lambda: (print("超时"), app.quit()))
sys.exit(app.exec())
