# -*- coding: utf-8 -*-
"""直接调用 APP.setDone 验证完成状态显示（跳过真实修复）"""
import json
import sys

from PySide6.QtCore import QUrl, QTimer
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QMainWindow

UI = r"C:\Users\123\1\qt_ui\index.html"


class Win(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("完成状态验证")
        self.resize(1200, 880)
        self.view = QWebEngineView(self)
        self.setCentralWidget(self.view)
        self.view.page().javaScriptConsoleMessage = \
            lambda l, m, ln, s: print("  [JS]", m)
        self.view.load(QUrl.fromLocalFile(UI))
        self.view.loadFinished.connect(self.run)

    def run(self, ok):
        print("页面加载:", ok)
        QTimer.singleShot(1200, self.fake_probe)

    def js(self, code, cb=None):
        self.view.page().runJavaScript(code, cb or (lambda r: None))

    def fake_probe(self):
        print("\n[1] 模拟载入文件")
        data = {
            "filename": "PFA_Velcro_Patch_2126x1417_Layered.psd",
            "width": 2126,
            "height": 1417,
            "size": 61231174,
            "layers": ["01_bg_red", "02_stripes_black", "02_stripe_01",
                       "02_stripe_02", "03_stripes_dither", "04_pfa_base",
                       "05_pfa_slice_01", "05_pfa_slice_02", "06_pfa_shadow",
                       "07_corner_block", "08_bottom_text", "10_asset_teamlogo"],
            "issues": [
                {"sev": "warn", "title": "有 17 个图层是满画布尺寸",
                 "detail": "每层约占 11.5 MB 内存。若内容不多，裁切后能大幅降低 PS 压力。"},
            ],
        }
        payload = json.dumps(data, ensure_ascii=False)
        import base64
        b64 = base64.b64encode(payload.encode()).decode()
        code = (
            "try{var r=atob('%s');var a=[];"
            "for(var i=0;i<r.length;i++)a.push(r.charCodeAt(i));"
            "var t=new TextDecoder('utf-8').decode(new Uint8Array(a));"
            "window.APP.setProbe(JSON.parse(t));}catch(e){console.error(e);}"
            % b64)
        self.js(code)
        QTimer.singleShot(1200, self.fake_done)

    def fake_done(self):
        print("[2] 模拟修复完成")
        data = {
            "filename": "PFA_Velcro_Patch_2126x1417_Layered_FIXED.psd",
            "mb": 58.21,
            "hasIssues": True,
            "count": 1,
        }
        payload = json.dumps(data, ensure_ascii=False)
        import base64
        b64 = base64.b64encode(payload.encode()).decode()
        code = (
            "try{var r=atob('%s');var a=[];"
            "for(var i=0;i<r.length;i++)a.push(r.charCodeAt(i));"
            "var t=new TextDecoder('utf-8').decode(new Uint8Array(a));"
            "window.APP.setDone(JSON.parse(t));}catch(e){console.error(e);}"
            % b64)
        self.js(code)
        QTimer.singleShot(1500, self.check)

    def check(self):
        print("\n[3] 检查界面变化")
        js = r"""
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
        self.js(js, self.report)

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
    QTimer.singleShot(30000, app.quit)
    app.exec()
