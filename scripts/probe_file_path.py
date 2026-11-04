# -*- coding: utf-8 -*-
"""探测 Qt WebEngine 的 File 对象是否有 path 属性（决定 HTML5 拖放能否拿到路径）"""
import os, sys, json
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-features=NetworkService --no-pings"
from PySide6.QtCore import QUrl, QTimer
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineWidgets import QWebEngineView

HERE = os.path.dirname(os.path.abspath(__file__))
app = QApplication(sys.argv)
v = QWebEngineView()
v.resize(600, 400)
v.show()
v.load(QUrl.fromLocalFile(os.path.join(HERE, "qt_ui", "index.html")))

JS = r"""
(function(){
  var out = {};
  out.hasPath = ('path' in File.prototype);
  out.fileKeys = Object.getOwnPropertyNames(File.prototype).join(',');
  out.hasEntry = ('webkitGetAsEntry' in DataTransferItem.prototype);
  out.hasDroppedFiles = ('files' in DataTransfer.prototype);
  out.ua = navigator.userAgent;
  // 尝试构造一个带路径的 File（测试构造器是否接受）
  try { var f = new File(['x'],'a.psd',{path:'C:/x/a.psd'}); out.ctorPath = (f.path===undefined?'undefined':f.path); } catch(e){ out.ctorPath='ERR '+e; }
  out.ondropExists = (typeof document.ondrop);
  return JSON.stringify(out);
})()
"""

def cb(r):
    print("JS 结果:", r)
    try:
        d = json.loads(r)
        print("\n判定: File.path 可用 =", d["hasPath"], "→ 拖放取路径", "可用" if d["hasPath"] else "不可用")
    except Exception as e:
        print("解析失败", e)
    app.quit()

v.loadFinished.connect(lambda ok: QTimer.singleShot(1200, lambda: v.page().runJavaScript(JS, cb)))
QTimer.singleShot(15000, app.quit)
sys.exit(app.exec())
