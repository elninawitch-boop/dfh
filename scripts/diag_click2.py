# -*- coding: utf-8 -*-
"""诊断进度面板：等过渡动画结束再测"""
import sys

from PySide6.QtCore import QUrl, QTimer
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QMainWindow

UI = r"C:\Users\123\1\qt_ui\index.html"


class Win(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("交互诊断2")
        self.resize(1200, 880)
        self.view = QWebEngineView(self)
        self.setCentralWidget(self.view)
        self.view.page().javaScriptConsoleMessage = \
            lambda l, m, ln, s: print("  [JS]", m)
        self.view.load(QUrl.fromLocalFile(UI))
        self.view.loadFinished.connect(self.step1)

    def step1(self, ok):
        print("页面加载:", ok)
        print("\n[1] 点击前状态")
        js = """
        (function(){
          var l = document.getElementById('prog-list');
          var p = document.getElementById('prog');
          return JSON.stringify({
            progClass: p.className,
            listMaxH: getComputedStyle(l).maxHeight,
            listH: l.offsetHeight,
            listOpacity: getComputedStyle(l).opacity,
            transition: getComputedStyle(l).transition
          });
        })();
        """
        self.view.page().runJavaScript(js, self.after_before)

    def after_before(self, r):
        print("   ", r)
        print("\n[2] 执行点击")
        js = """
        (function(){
          document.getElementById('prog-head').click();
          return document.getElementById('prog').className;
        })();
        """
        self.view.page().runJavaScript(js, self.after_click)

    def after_click(self, r):
        print("   点击后 class:", r)
        print("\n[3] 等待 1.5 秒过渡完成...")
        QTimer.singleShot(1500, self.check_final)

    def check_final(self):
        js = """
        (function(){
          var l = document.getElementById('prog-list');
          var p = document.getElementById('prog');
          return JSON.stringify({
            progClass: p.className,
            listMaxH: getComputedStyle(l).maxHeight,
            listH: l.offsetHeight,
            listOpacity: getComputedStyle(l).opacity,
            rowCount: l.querySelectorAll('.row').length
          });
        })();
        """
        self.view.page().runJavaScript(js, self.report)

    def report(self, r):
        print("   ", r)
        import json
        try:
            d = json.loads(r)
            print()
            print("=" * 56)
            if d["listH"] > 0:
                print("结论: 展开正常，高度 %d px" % d["listH"])
            else:
                print("结论: 高度仍为 0，展开失败")
                print("  maxHeight:", d["listMaxH"])
                print("  opacity:", d["listOpacity"])
                print("  行数:", d["rowCount"])
            print("=" * 56)
        except Exception as e:
            print("解析失败:", e)
        QApplication.instance().quit()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = Win()
    w.show()
    QTimer.singleShot(25000, app.quit)
    app.exec()
