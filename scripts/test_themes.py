# -*- coding: utf-8 -*-
"""验证四个主题的背景色确实不同"""
import sys

from PySide6.QtCore import QUrl, QTimer
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QMainWindow

UI = r"C:\Users\123\1\qt_ui\index.html"
OUT = r"C:\Users\123\1\theme_check"


class Win(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("主题测试")
        self.resize(1200, 880)
        self.view = QWebEngineView(self)
        self.setCentralWidget(self.view)
        self.view.page().javaScriptConsoleMessage = \
            lambda l, m, ln, s: print("  [JS]", m)
        self.view.load(QUrl.fromLocalFile(UI))
        self.view.loadFinished.connect(self.run)
        self.themes = ['冰蓝青', '紫蓝粉', '红黑', '石墨']
        self.idx = 0

    def run(self, ok):
        print("页面加载:", ok)
        QTimer.singleShot(1500, self.next_theme)

    def next_theme(self):
        if self.idx >= len(self.themes):
            print("\n全部主题截图完成")
            QApplication.instance().quit()
            return
        name = self.themes[self.idx]
        print("\n[%d/%d] 切换主题: %s" % (self.idx + 1, len(self.themes), name))
        js = "setTheme('%s'); 'done'" % name
        self.view.page().runJavaScript(js, self.after_set)

    def after_set(self, r):
        name = self.themes[self.idx]
        QTimer.singleShot(1200, lambda: self.shot(name))

    def shot(self, name):
        pix = self.grab()
        dpr = self.devicePixelRatio()
        out = "%s_%d.png" % (OUT, self.idx)
        pix.scaled(int(pix.width() / dpr), int(pix.height() / dpr)).save(out)
        print("  已保存:", out)
        # 读取实际背景色
        js = """
        (function(){
          var a = document.getElementById('aurora');
          var b1 = document.querySelector('.b1');
          var b2 = document.querySelector('.b2');
          return JSON.stringify({
            base: a.style.getPropertyValue('--bg-base') ||
                  getComputedStyle(a).getPropertyValue('--bg-base'),
            b1: b1.style.background,
            b2: b2.style.background,
            dark: document.body.classList.contains('dark')
          });
        })();
        """
        self.view.page().runJavaScript(js, self.report)

    def report(self, r):
        print("  配色:", r)
        self.idx += 1
        QTimer.singleShot(300, self.next_theme)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = Win()
    w.show()
    QTimer.singleShot(30000, app.quit)
    app.exec()
