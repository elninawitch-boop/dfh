# -*- coding: utf-8 -*-
"""连接已运行的 Qt 版，检查主题切换是否真的改变背景

因为已打包的程序无法直接注入 JS，这里启动源码版做验证，
同时截图对比四个主题。
"""
import sys

from PySide6.QtCore import QUrl, QTimer
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QMainWindow

UI = r"C:\Users\123\1\qt_ui\index.html"
THEMES = ['冰蓝青', '紫蓝粉', '红黑', '石墨']


class Win(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("主题验证")
        self.resize(1200, 880)
        self.view = QWebEngineView(self)
        self.setCentralWidget(self.view)
        self.logs = []
        self.view.page().javaScriptConsoleMessage = \
            lambda l, m, ln, s: self.logs.append(m)
        self.view.load(QUrl.fromLocalFile(UI))
        self.view.loadFinished.connect(self.start)
        self.i = 0

    def start(self, ok):
        print("页面加载:", ok)
        QTimer.singleShot(1500, self.step)

    def step(self):
        if self.i >= len(THEMES):
            print("\n完成")
            QApplication.instance().quit()
            return
        name = THEMES[self.i]
        print("\n[%d] %s" % (self.i + 1, name))
        self.view.page().runJavaScript(
            "setTheme('%s'); 'ok'" % name, self.after)

    def after(self, r):
        QTimer.singleShot(1000, self.capture)

    def capture(self):
        name = THEMES[self.i]
        pix = self.grab()
        dpr = self.devicePixelRatio()
        out = r"C:\Users\123\1\theme_%d.png" % self.i
        pix.scaled(int(pix.width() / dpr), int(pix.height() / dpr)).save(out)

        # 读取真实渲染的背景像素
        js = """
        (function(){
          var a = document.getElementById('aurora');
          var cs = getComputedStyle(a);
          var b1 = document.querySelector('.b1');
          return JSON.stringify({
            base: cs.getPropertyValue('--bg-base').trim(),
            b1: getComputedStyle(b1).backgroundColor,
            dark: document.body.classList.contains('dark'),
            label: document.getElementById('theme-label').textContent
          });
        })();
        """
        self.view.page().runJavaScript(js, self.report)

    def report(self, r):
        print("   ", r)
        self.i += 1
        QTimer.singleShot(300, self.step)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = Win()
    w.show()
    QTimer.singleShot(30000, app.quit)
    app.exec()
