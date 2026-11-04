# -*- coding: utf-8 -*-
"""不依赖 qwebchannel.js 的桥接方案

原理：
  · JS 侧把请求写进一个数组 window.__calls
  · Python 定时轮询这个数组，取走后调用对应函数
  · Python 通过 runJavaScript 调用 JS 的 window.APP.xxx

优点：完全不需要 qwebchannel.js，稳定可靠。
代价：有约 50ms 的轮询延迟（对 UI 交互无感）。
"""
import json

from PySide6.QtCore import QTimer

# 注入到页面的桥接代码（在页面加载前注入）
BRIDGE_JS = r"""
(function(){
  if (window.__BRIDGE_READY__) return;
  window.__BRIDGE_READY__ = true;

  // JS 调用 Python 的队列
  window.__calls = [];

  window.pyCall = function(fn, arg){
    window.__calls.push([fn, arg === undefined ? null : arg]);
  };

  // 供 Python 取走队列
  window.__drainCalls = function(){
    const out = window.__calls.slice();
    window.__calls.length = 0;
    return JSON.stringify(out);
  };

  console.log('[bridge] 注入完成');
})();
"""


class JsBridge:
    """JS -> Python 的轮询桥"""

    def __init__(self, view, handlers, interval_ms=40):
        self.view = view
        self.handlers = handlers
        self.timer = QTimer(view)
        self.timer.timeout.connect(self._poll)
        self.timer.start(interval_ms)
        self._busy = False

    def _poll(self):
        if self._busy:
            return
        self._busy = True

        def done(result):
            self._busy = False
            if not result:
                return
            try:
                calls = json.loads(result)
            except Exception:
                return
            for fn, arg in calls:
                h = self.handlers.get(fn)
                if h:
                    try:
                        h(arg)
                    except Exception as e:
                        print("[bridge] 处理 %s 出错: %s" % (fn, e))

        try:
            self.view.page().runJavaScript("window.__drainCalls()", done)
        except Exception:
            self._busy = False
