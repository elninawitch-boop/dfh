# -*- coding: utf-8 -*-
"""测开机动画的时间偏移：背景（CSS）与图标（图片）各自什么时候到位。

在页面里读 performance 资源计时 + 图片解码状态，输出相对导航开始的毫秒数。
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
    "--high-dpi-support=1 --disable-features=NetworkService "
    "--disable-background-networking --no-pings --disable-sync"
)

from PySide6.QtCore import QTimer, QUrl          # noqa: E402
from PySide6.QtWidgets import QApplication, QMainWindow   # noqa: E402
from PySide6.QtWebEngineWidgets import QWebEngineView     # noqa: E402

UI = os.path.join(HERE, "qt_ui", "index.html")

PROBE = r"""
(function(){
  var out = {t: performance.now()};
  // 图标资源加载情况
  var im = document.getElementById('boot-icon');
  out.imgComplete = !!(im && im.complete);
  out.imgNatural = im ? im.naturalWidth : -1;
  var res = performance.getEntriesByType('resource') || [];
  out.res = res.map(function(r){
    return {name: r.name.split('/').pop(), start: Math.round(r.startTime),
            dur: Math.round(r.duration), size: r.transferSize};
  });
  // 导航计时
  var nav = performance.getEntriesByType('navigation')[0];
  if (nav) {
    out.domReady = Math.round(nav.domContentLoadedEventEnd);
    out.loadEnd  = Math.round(nav.loadEventEnd);
    out.firstPaint = -1;
  }
  var fp = performance.getEntriesByName('first-paint')[0];
  if (fp) out.firstPaint = Math.round(fp.startTime);
  // 动画当前进度
  try {
    var a = im && im.getAnimations ? im.getAnimations() : [];
    out.iconAnims = a.map(function(x){ return {name:x.animationName, t: Math.round(x.currentTime||0)}; });
  } catch(e){}
  return JSON.stringify(out);
})()
"""


def main():
    app = QApplication(sys.argv[:1])
    win = QMainWindow()
    win.resize(1200, 880)
    view = QWebEngineView(win)
    win.setCentralWidget(view)
    win.show()
    view.load(QUrl.fromLocalFile(UI))

    marks = []

    def poll(i=0):
        if i > 25:
            report()
            return

        def done(v):
            try:
                d = json.loads(v)
            except Exception:
                d = {"raw": v}
            marks.append(d)
            QTimer.singleShot(20, lambda: poll(i + 1))

        view.page().runJavaScript(PROBE, done)

    def report():
        print("=" * 60)
        first = marks[0] if marks else {}
        print("首次采样 t=%.0fms" % first.get("t", -1))
        print("firstPaint=%s domReady=%s loadEnd=%s"
              % (first.get("firstPaint"), first.get("domReady"), first.get("loadEnd")))
        print("\n资源加载:")
        for r in first.get("res", []):
            print("  %-24s start=%4dms dur=%4dms size=%s"
                  % (r["name"], r["start"], r["dur"], r["size"]))
        print("\n图标就绪时刻:")
        for m in marks:
            if m.get("imgComplete"):
                print("  第一次 img.complete 在 t=%.0fms（naturalWidth=%d）"
                      % (m.get("t", 0), m.get("imgNatural", 0)))
                break
        else:
            print("  采样期间始终未就绪")
        print("\n图标动画时间轴:")
        for m in marks[:8]:
            print("  t=%4.0f  anims=%s" % (m.get("t", 0), m.get("iconAnims")))
        app.quit()

    QTimer.singleShot(0, poll)
    app.exec()


if __name__ == "__main__":
    main()
