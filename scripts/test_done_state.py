# -*- coding: utf-8 -*-
"""测试修复完成后的界面反馈"""
import json
import os
import sys
import threading

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QMainWindow

import psd_repair_core as core

UI = r"C:\Users\123\1\qt_ui\index.html"
TARGET = r"E:\zh\PFA_Velcro_Patch_2126x1417_Layered.psd"


class Win(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("完成状态测试")
        self.resize(1200, 880)
        self.view = QWebEngineView(self)
        self.setCentralWidget(self.view)
        self.view.page().javaScriptConsoleMessage = \
            lambda l, m, ln, s: print("  [JS]", m)
        self.view.load(QUrl.fromLocalFile(UI))
        self.view.loadFinished.connect(self.start)
        self.msgs = []
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.drain)
        self.timer.start(60)

    def send(self, func, obj):
        self.msgs.append((func, obj))

    def drain(self):
        import base64
        for _ in range(20):
            if not self.msgs:
                break
            func, obj = self.msgs.pop(0)
            payload = json.dumps(obj, ensure_ascii=False)
            b64 = base64.b64encode(payload.encode()).decode()
            code = (
                "if(window.%s){try{"
                "var r=atob('%s');var a=[];"
                "for(var i=0;i<r.length;i++)a.push(r.charCodeAt(i));"
                "var t=new TextDecoder('utf-8').decode(new Uint8Array(a));"
                "window.%s(JSON.parse(t));"
                "}catch(e){console.error('[drain]',e);}}" % (func, b64, func)
            )
            self.view.page().runJavaScript(code)

    def start(self, ok):
        print("页面加载:", ok)
        if not os.path.exists(TARGET):
            print("测试文件不存在:", TARGET)
            QApplication.instance().quit()
            return
        QTimer.singleShot(800, self.step_load)

    def step_load(self):
        print("\n[1] 载入文件")
        probe = core.PsdProbe(TARGET).parse()
        data = {
            "filename": os.path.basename(TARGET),
            "width": probe.width,
            "height": probe.height,
            "size": probe.size,
            "layers": [L["name"] for L in probe.layers],
            "issues": [{"sev": i.severity, "title": i.title,
                        "detail": i.detail} for i in probe.issues],
        }
        self.send("APP.setProbe", data)
        print("  %d 图层, %d 问题" % (len(data["layers"]),
                                      len(data["issues"])))
        self.file = TARGET
        QTimer.singleShot(1500, self.step_fix)

    def step_fix(self):
        print("\n[2] 修复")
        threading.Thread(target=self._fix, daemon=True).start()

    def _fix(self):
        base, ext = os.path.splitext(self.file)
        out = base + "_DONETEST" + (ext or ".psd")
        probe, out_path, check = core.repair(
            self.file, out_path=out, trim=True,
            on_stage=lambda t: self.send("APP.setStage", t),
            on_progress=lambda i, t, n, d:
                self.send("APP.setProgress", [i, t, n, d]))
        mb = os.path.getsize(out_path) / 1024 / 1024
        print("  修复完成: %.2f MB" % mb)
        self.send("APP.setDone", {
            "filename": os.path.basename(out_path),
            "mb": mb,
            "hasIssues": len(check.issues) > 0,
            "count": len(check.issues),
        })
        QTimer.singleShot(2500, self.step_check)

    def step_check(self):
        print("\n[3] 检查界面变化")
        js = """
        JSON.stringify({
          diagSummary: document.getElementById('diag-summary').innerText,
          hasBanner: !!document.querySelector('.done-banner'),
          bannerText: (document.querySelector('.done-banner-text')||{}).innerText || '',
          rightHasOutFile: !!document.querySelector('.out-file'),
          outFileText: (document.querySelector('.out-file')||{}).innerText || '',
          sizeCompare: (document.querySelector('.size-compare')||{}).innerText || '',
          fixBtnText: document.getElementById('btn-fix').innerText,
          openBtnDisabled: document.getElementById('btn-open').disabled,
          dropMain: document.getElementById('drop-main').innerText,
          status: document.getElementById('status').innerText
        }, null, 1)
        """
        self.view.page().runJavaScript(js, self.report)

    def report(self, r):
        print(r)
        pix = self.grab()
        dpr = self.devicePixelRatio()
        pix.scaled(int(pix.width() / dpr),
                   int(pix.height() / dpr)).save(
            r"C:\Users\123\1\done_state.png")
        print("\n已保存 done_state.png")
        QApplication.instance().quit()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = Win()
    w.show()
    QTimer.singleShot(120000, app.quit)
    app.exec()
