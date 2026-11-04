# -*- coding: utf-8 -*-
"""诊断进度面板交互：检查 JS 是否报错、变量是否就绪"""
import sys

from PySide6.QtCore import QUrl, QTimer
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QMainWindow

UI = r"C:\Users\123\1\qt_ui\index.html"

errors = []


class Win(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("交互诊断")
        self.resize(1200, 880)
        self.view = QWebEngineView(self)
        self.setCentralWidget(self.view)

        def console(level, msg, line, src):
            print("  [JS %s] %s" % (level, msg))
            if level >= 2:      # error
                errors.append(msg)

        self.view.page().javaScriptConsoleMessage = console
        self.view.load(QUrl.fromLocalFile(UI))
        self.view.loadFinished.connect(self.check)

    def check(self, ok):
        print("页面加载:", ok)
        js = r"""
        (function(){
          var r = {};
          r.progExists = !!document.getElementById('prog');
          r.headExists = !!document.getElementById('prog-head');
          r.listExists = !!document.getElementById('prog-list');
          r.elProgDefined = (typeof elProg !== 'undefined');
          r.onclickSet = !!(document.getElementById('prog-head') &&
                            document.getElementById('prog-head').onclick);
          r.classBefore = document.getElementById('prog').className;

          // 模拟点击
          try {
            var h = document.getElementById('prog-head');
            h.click();
            r.classAfter = document.getElementById('prog').className;
            r.toggled = (r.classAfter !== r.classBefore);
          } catch(e) {
            r.clickError = e.message;
          }

          // 检查 list 高度
          var list = document.getElementById('prog-list');
          r.listHeight = list ? list.offsetHeight : -1;
          r.listMaxHeight = list ? getComputedStyle(list).maxHeight : '';

          return JSON.stringify(r, null, 1);
        })();
        """
        QTimer.singleShot(2000, lambda: self.view.page().runJavaScript(
            js, self.report))

    def report(self, r):
        print()
        print("=" * 60)
        print("交互诊断结果")
        print("=" * 60)
        print(r)
        print()
        print("JS 错误数:", len(errors))
        for e in errors[:5]:
            print("  -", e)
        QApplication.instance().quit()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = Win()
    w.show()
    QTimer.singleShot(20000, app.quit)
    app.exec()
