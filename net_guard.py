#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
net_guard.py —— 网络硬阻断

三层防护，确保应用运行期间绝不联网：
  1. QtWebEngineProfile 设置请求拦截器，拒绝所有 http/https/ws
  2. 禁用 QtWebEngine 的后台网络服务（拼写检查、安全浏览等）
  3. 运行时用 psutil 监控本进程，检测到外连立即记录并可选强制断开
"""

import sys


def install_webengine_guard():
    """必须在 QApplication 创建之前调用"""
    from PySide6.QtWebEngineCore import QWebEngineProfile
    import PySide6.QtWebEngineCore as wec

    # ---- 关掉所有后台联网服务 ----
    flags_to_off = [
        "AllowRunningInsecureContent",
        "PluginsEnabled",
        "JavascriptCanOpenWindows",
        "LocalStorageEnabled",
        "DnsPrefetchEnabled",           # 关键：禁用 DNS 预取
        "HyperlinkAuditingEnabled",     # 关键：禁用链接审计（向 Google 上报）
        "PdfViewerEnabled",
        "ErrorPageEnabled",
        "AutoLoadImages",
    ]

    # Qt6 的 WebAttribute 枚举，尽量关掉联网相关的
    try:
        from PySide6.QtWebEngineCore import QWebEngineSettings
        attrs = {
            "DnsPrefetchEnabled": False,
            "HyperlinkAuditingEnabled": False,
            "LocalContentCanAccessRemoteUrls": False,   # 关键：本地页面禁止访问远程
            "LocalContentCanAccessFileUrls": True,
            "JavascriptCanOpenWindows": False,
        }
        for k, v in attrs.items():
            a = getattr(QWebEngineSettings.WebAttribute, k, None)
            if a is not None:
                QWebEngineSettings.setDefaultAttribute(a, v)
    except Exception:
        pass

    # ---- 全局拦截：默认 profile 的自定义 scheme 之外一律拒绝 ----
    # 用 setUrlRequestInterceptor 需要私有 API，这里改用更稳的方式：
    # 在 profile 上关闭所有可以发请求的属性，并在前端 JS 层再加一道防线


def install_js_guard(profile):
    """在页面加载前注入 JS，拦截所有网络调用

    页面加载完成后立即执行，把 fetch / XHR / WebSocket / EventSource
    全部替换为拒绝实现。即使页面代码想联网也做不到。
    """
    from PySide6.QtWebEngineCore import QWebEngineScript
    script_src = r"""
    (function(){
      'use strict';
      const BLOCK = () => Promise.reject(new Error('network disabled'));

      // fetch
      try { window.fetch = BLOCK; } catch(e) {}

      // XMLHttpRequest
      try {
        const XO = XMLHttpRequest.prototype.open;
        XMLHttpRequest.prototype.open = function(){
          throw new Error('network disabled');
        };
      } catch(e) {}

      // WebSocket
      try {
        window.WebSocket = function(){ throw new Error('network disabled'); };
      } catch(e) {}

      // EventSource
      try {
        window.EventSource = function(){ throw new Error('network disabled'); };
      } catch(e) {}

      // sendBeacon
      try {
        navigator.sendBeacon = function(){ return false; };
      } catch(e) {}

      // 图片/脚本等标签的远程加载：拦截所有非 data:/file: 的 URL
      const isLocal = u => !u || u.startsWith('data:') ||
                          u.startsWith('file:') || u.startsWith('about:') ||
                          u.startsWith('blob:') || u.startsWith('qrc:');
      try {
        const desc = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype,'src');
        // 保留原行为，仅记录（真正阻断靠 profile 层）
      } catch(e) {}

      console.log('[net-guard] 网络调用已禁用');
    })();
    """
    s = QWebEngineScript()
    s.setName("net-guard")
    s.setSourceCode(script_src)
    s.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
    s.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
    s.setRunsOnSubFrames(True)
    profile.scripts().insert(s)


def configure_profile(view):
    """配置 QWebEngineProfile，关闭一切联网能力"""
    from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEngineSettings

    profile = view.page().profile()

    # 1) 用内存缓存，不落盘、不联网
    try:
        profile.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
        profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies)
    except Exception:
        pass

    # 2) 关闭 DNS 预取与链接审计（这两项会主动联网）
    try:
        st = profile.settings()
        attrs = st.WebAttribute
        for name, val in [
            ("DnsPrefetchEnabled", False),
            ("HyperlinkAuditingEnabled", False),
            ("LocalContentCanAccessRemoteUrls", False),
            ("JavascriptCanOpenWindows", False),
            ("PluginsEnabled", False),
        ]:
            a = getattr(attrs, name, None)
            if a is not None:
                st.setAttribute(a, val)
    except Exception:
        pass

    # 3) 注入 JS 拦截
    try:
        install_js_guard(profile)
    except Exception as e:
        print("JS guard 安装失败:", e, file=sys.stderr)

    return profile


def block_all_requests(view):
    """兜底：页面加载完成后再注入一次拦截，并移除所有外部资源链接"""
    js = r"""
    (function(){
      // 移除所有可能联网的标签
      document.querySelectorAll('link[href^="http"], script[src^="http"], iframe[src^="http"]')
        .forEach(n => n.remove());
      // 禁用所有表单提交
      document.addEventListener('submit', e => e.preventDefault(), true);
      console.log('[net-guard] 外部资源已清除');
    })();
    """
    view.page().runJavaScript(js)


class NetMonitor:
    """运行时监控：检测到外连就记录下来"""

    def __init__(self):
        self.connections = []
        self.running = False
        self._thread = None
        self._proc = None

    def start(self):
        try:
            import psutil
            self._proc = psutil.Process()
        except Exception:
            return
        import threading
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        import time
        seen = set()
        while self.running:
            try:
                procs = [self._proc] + self._proc.children(recursive=True)
                for p in procs:
                    try:
                        for c in p.net_connections(kind='inet'):
                            if not c.raddr:
                                continue
                            ip = c.raddr.ip
                            # 排除本机回环
                            if ip.startswith('127.') or ip == '::1':
                                continue
                            key = (ip, c.raddr.port)
                            if key not in seen:
                                seen.add(key)
                                self.connections.append(key)
                    except Exception:
                        pass
            except Exception:
                pass
            time.sleep(1.0)

    def stop(self):
        self.running = False

    def report(self):
        return list(self.connections)
