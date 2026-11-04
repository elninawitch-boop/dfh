#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
psd_repair_qt.py —— PSD 修复工具（Qt WebEngine 版）

架构：
  · 界面：HTML/CSS/JS（内嵌 Qt WebEngine，完全本地，零联网）
  · 后端：Python 负责 PSD 解析与修复
  · 桥接：QWebChannel 双向调用

安全：
  · 启动前安装网络硬阻断（net_guard）
  · 页面内注入 fetch/XHR/WebSocket 拦截
  · 运行时监控，检测到外连立即记录
"""

import json
import os
import queue
import sys
import threading
import traceback

# ---- 必须在 QApplication 之前 ----
from PySide6.QtCore import QUrl, QTimer, QObject, Signal, Slot, Qt, QEvent
from PySide6.QtGui import QColor
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QMainWindow, QFileDialog

import psd_repair_core as core
import net_guard
from js_bridge import JsBridge
from recent_store import RecentStore

HERE = os.path.dirname(os.path.abspath(__file__))
UI_PATH = os.path.join(HERE, "qt_ui", "index.html")

# 修复线程是 CPU 密集的纯 Python/numpy 循环，默认 5ms 的 GIL 切换间隔
# 会让主线程（Qt 事件循环）长时间拿不到执行权 —— 实测最长卡 688ms，
# 20 秒修复里累计 8.4 秒不响应。降到 1ms 后主线程能及时刷 UI。
try:
    sys.setswitchinterval(0.0005)
except Exception:
    pass

# 拖放高亮（JS 侧只负责视觉反馈，路径一律由 Qt 层取）
_JS_DROP_ON = ("(function(){var d=document.getElementById('drop');"
               "if(d)d.classList.add('over');})()")
_JS_DROP_OFF = ("(function(){var d=document.getElementById('drop');"
                "if(d)d.classList.remove('over');})()")


class DropCatcher(QObject):
    """在 Qt 层截获原生拖放，绕开 Chromium 的 File 对象。

    背景：Qt WebEngine 没有 Electron 的私有扩展 File.path，
    File.prototype 只有 name/lastModified/lastModifiedDate/
    webkitRelativePath/constructor，所以 JS 侧拿不到本地路径。
    必须在 Qt 层用 mimeData().urls() -> toLocalFile() 取真实路径。

    事件过滤器要装在真正接收拖放的子控件上，也就是
    view.focusProxy()（RenderWidgetHostViewQtDelegateWidget），
    同时用 findChildren 兜底，避免版本差异导致装错。
    """

    def __init__(self, view, on_file):
        super().__init__(view)
        self.view = view
        self.on_file = on_file
        self.installed = 0
        self.install()

    def install(self):
        """把过滤器挂到所有可能接收拖放的控件上（可重复调用）"""
        targets = [self.view]
        try:
            fp = self.view.focusProxy()
            if fp is not None:
                targets.append(fp)
        except Exception:
            pass
        try:
            targets.extend(self.view.findChildren(QObject))
        except Exception:
            pass

        n = 0
        for w in targets:
            if w is self:
                continue
            try:
                w.installEventFilter(self)
                n += 1
            except Exception:
                pass
        self.installed = n
        return n

    # ------------------------------------------------------------------
    @staticmethod
    def _psd_path(ev):
        """从拖放数据里取第一个本地 .psd 路径，没有则返回 None"""
        try:
            md = ev.mimeData()
        except Exception:
            return None
        if md is None or not md.hasUrls():
            return None
        for u in md.urls():
            try:
                if not u.isLocalFile():
                    continue
                p = u.toLocalFile()
                if p and p.lower().endswith(".psd"):
                    return p
            except Exception:
                continue
        return None

    def _highlight(self, on):
        try:
            self.view.page().runJavaScript(_JS_DROP_ON if on else _JS_DROP_OFF)
        except Exception:
            pass

    def eventFilter(self, obj, ev):
        t = ev.type()

        if t in (QEvent.DragEnter, QEvent.DragMove):
            if self._psd_path(ev):
                self._highlight(True)
                ev.acceptProposedAction()
                return True
            return False

        if t == QEvent.DragLeave:
            self._highlight(False)
            return False

        if t == QEvent.Drop:
            self._highlight(False)
            p = self._psd_path(ev)
            if p:
                ev.acceptProposedAction()
                try:
                    self.on_file(p)
                except Exception as e:
                    print("[drop] 载入失败:", e)
                return True
            return False

        return False


class Bridge:
    """Python 与 JS 的桥（轮询模式）"""

    def __init__(self, win):
        self.win = win
        self.probe = None
        self.file_path = None
        self.last_out = None
        self.busy = False
        # 最近打开的文件（Python 侧持久化，见 recent_store.py）
        self.recent = RecentStore()
        # 后台线程 -> 主线程 的消息队列（避免跨线程调用 Qt）
        self.msg_queue = queue.Queue()

    def post(self, func, obj):
        """后台线程调用此方法，把消息排入队列"""
        self.msg_queue.put((func, obj))

    # ---------------------------------------------- JS 调用 Python
    def pick_file(self, arg=None):
        path, _ = QFileDialog.getOpenFileName(
            self.win, "选择 PSD 文件", "",
            "Photoshop 文件 (*.psd);;所有文件 (*.*)")
        if path:
            self.load_path(path)

    def load_path(self, path):
        if not path or not os.path.exists(path):
            return
        self.file_path = path
        self.last_out = None          # 换文件后「打开文件夹」要跟着换目标
        self.probe = None
        # 记进最近列表，并立刻把新列表推给前端（右栏空状态要跟着变）
        try:
            self.recent.touch(path)
            self.win.js_obj("APP.setRecent", self.recent.list())
        except Exception as e:
            print("[recent] 更新失败:", e)
        self.win.js("APP.setLoading", json.dumps(os.path.basename(path)))
        threading.Thread(target=self._detect, args=(path,), daemon=True).start()

    # ---------------------------------------------- 最近文件
    def open_recent(self, index):
        """点右栏的最近文件条目：按下标取真实路径再走正常加载流程"""
        p = self.recent.path_at(index)
        if not p:
            return
        if not os.path.exists(p):
            # 文件被删/被移动，直接从列表里移除并刷新
            self.recent.remove_at(index)
            self.win.js_obj("APP.setRecent", self.recent.list())
            return
        self.load_path(p)

    def remove_recent(self, index):
        """点行尾的 × ：只删记录，不碰文件"""
        if self.recent.remove_at(index):
            self.win.js_obj("APP.setRecent", self.recent.list())

    def push_recent(self):
        """页面就绪后把已有列表推给前端"""
        self.win.js_obj("APP.setRecent", self.recent.list())

    def _detect(self, path):
        try:
            probe = core.PsdProbe(path).parse()
            self.probe = probe
            data = {
                "filename": os.path.basename(path),
                "width": probe.width,
                "height": probe.height,
                "size": probe.size,
                "layers": [L["name"] for L in probe.layers],
                "issues": [{"sev": i.severity, "title": i.title,
                            "detail": i.detail} for i in probe.issues],
            }
            self.post("APP.setProbe", data)
        except Exception as e:
            self.post("APP.setFailed", "解析失败: %s" % e)

    def start_fix(self, arg):
        if not self.file_path or self.probe or self.busy:
            if not self.file_path:
                return
        try:
            opts = json.loads(arg) if arg else {}
        except Exception:
            opts = {}
        trim = opts.get("trim", True)
        self.busy = True
        base, ext = os.path.splitext(self.file_path)
        out = base + "_FIXED" + (ext or ".psd")
        threading.Thread(target=self._fix,
                         args=(self.file_path, out, trim),
                         daemon=True).start()

    def _fix(self, path, out, trim):
        try:
            def on_stage(t):
                self.post("APP.setStage", t)

            def on_progress(i, total, name, detail):
                self.post("APP.setProgress", [i, total, name, detail])

            probe, out_path, check = core.repair(
                path, out_path=out, trim=trim,
                on_stage=on_stage, on_progress=on_progress)
            self.last_out = out_path
            self.busy = False
            self.post("APP.setDone", {
                "filename": os.path.basename(out_path),
                "mb": os.path.getsize(out_path) / 1024 / 1024,
                "hasIssues": len(check.issues) > 0,
                "count": len(check.issues),
            })
        except Exception:
            self.busy = False
            self.post("APP.setFailed", traceback.format_exc(limit=1))

    def open_folder(self, arg=None):
        """在资源管理器中定位文件：有输出就定位输出，否则定位源文件"""
        target = self.last_out or self.file_path
        if not target or not os.path.exists(target):
            return
        import subprocess
        try:
            subprocess.Popen(["explorer", "/select,",
                              os.path.normpath(target)])
        except Exception:
            pass

    def cancel(self, arg=None):
        self.busy = False
        self.win.js("APP.setStage", json.dumps("已取消", ensure_ascii=False))


class Win(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PSD 修复工具")
        self.resize(1200, 880)
        self.setMinimumSize(980, 720)

        # ---- 窗口图标（任务栏显示用）----
        self._set_app_icon()

        self.view = QWebEngineView(self)
        self.setCentralWidget(self.view)

        # 页面底色 = 开机动画的底色（#e9eef6）。
        # WebEngine 首帧要 200ms 左右才出来，这段空白期如果底色不一致
        # 就会看到"先白一下、再出现背景、图标最后才淡入"的时差感。
        try:
            self.view.page().setBackgroundColor(QColor("#e9eef6"))
            pal = self.view.palette()
            pal.setColor(pal.ColorRole.Window, QColor("#e9eef6"))
            self.view.setPalette(pal)
            self.view.setStyleSheet("background:#e9eef6;")
            self.setStyleSheet("QMainWindow{background:#e9eef6;}")
        except Exception:
            pass

        # ---- 网络防护 ----
        self.profile = net_guard.configure_profile(self.view)

        # ---- JS 桥（轮询模式，不依赖 qwebchannel.js）----
        self.bridge = Bridge(self)
        self._js_bridge = None
        self._drop = None

        # 打印 JS 控制台，便于排错
        self.view.page().javaScriptConsoleMessage = \
            lambda level, msg, line, src: print("[JS]", msg)

        # ---- 加载本地页面 ----
        self.view.load(QUrl.fromLocalFile(UI_PATH))
        self.view.loadFinished.connect(self._on_loaded)

        # ---- 运行时网络监控 ----
        self.monitor = net_guard.NetMonitor()
        self.monitor.start()

        # ---- 消息队列消费（主线程安全）----
        self._msg_timer = QTimer(self)
        self._msg_timer.timeout.connect(self._drain_messages)
        self._msg_timer.start(60)

    def _set_app_icon(self):
        """设置窗口图标（标题栏 + 任务栏）"""
        from PySide6.QtGui import QIcon

        # 打包后资源在 sys._MEIPASS 下；源码运行时在脚本目录
        bases = []
        if hasattr(sys, "_MEIPASS"):
            bases.append(sys._MEIPASS)
        bases.append(HERE)
        bases.append(os.path.dirname(sys.executable))
        bases.append(os.path.join(os.path.dirname(sys.executable), "_internal"))

        candidates = []
        for b in bases:
            candidates.append(os.path.join(b, "feather_icon.ico"))
            candidates.append(os.path.join(b, "_internal", "feather_icon.ico"))

        for p in candidates:
            if not os.path.exists(p):
                continue
            icon = QIcon(p)
            if icon.isNull():
                continue
            # 多尺寸都塞进去，任务栏/标题栏/Alt+Tab 都会用
            ico = QIcon()
            for sz in (16, 24, 32, 48, 64, 128, 256):
                pm = icon.pixmap(sz, sz)
                if not pm.isNull():
                    ico.addPixmap(pm)
            if ico.isNull():
                ico = icon
            self.setWindowIcon(ico)
            app = QApplication.instance()
            if app:
                app.setWindowIcon(ico)
            print("[icon] 已加载:", p)
            return

        print("[icon] 未找到图标文件，尝试的路径:")
        for p in candidates:
            print("       ", p, os.path.exists(p))

    def _drain_messages(self):
        """在主线程里消费后台线程的消息"""
        b = getattr(self, "bridge", None)
        if b is None:
            return
        import queue as _q
        for _ in range(20):     # 每次最多处理 20 条，避免卡死
            try:
                func, obj = b.msg_queue.get_nowait()
            except _q.Empty:
                break
            try:
                self.js_obj(func, obj)
            except Exception as e:
                print("[msg] 处理 %s 失败: %s" % (func, e))

    def js_obj(self, func, obj):
        """安全地把 Python 对象传给 JS（base64 编码，避免转义问题）"""
        import base64
        payload = json.dumps(obj, ensure_ascii=False)
        b64 = base64.b64encode(payload.encode("utf-8")).decode("ascii")
        code = (
            "if(window.%s){try{"
            "var r=atob('%s');var a=[];"
            "for(var i=0;i<r.length;i++)a.push(r.charCodeAt(i));"
            "var t=new TextDecoder('utf-8').decode(new Uint8Array(a));"
            "window.%s(JSON.parse(t));"
            "}catch(e){console.error('[js_obj]',e);}}"
            % (func, b64, func)
        )
        self.view.page().runJavaScript(code)

    def _on_loaded(self, ok):
        if ok:
            # 注意：block_all_requests 会移除 http(s) 资源，但 qrc:// 必须保留
            net_guard.block_all_requests(self.view)
            # 建立轮询桥（延迟 400ms 等页面脚本就绪）
            QTimer.singleShot(400, self._start_bridge)
            # 装拖放拦截：focusProxy 要等页面渲染出来才存在，分几次补装
            QTimer.singleShot(200, self._install_drop)
            QTimer.singleShot(900, self._install_drop)
            QTimer.singleShot(2000, self._install_drop)

    def _install_drop(self):
        """安装/补装拖放事件过滤器（focusProxy 出现时机不稳定）"""
        try:
            if self._drop is None:
                self._drop = DropCatcher(self.view, self.bridge.load_path)
                print("[drop] 事件过滤器已安装，挂载点 %d 个" % self._drop.installed)
            else:
                n = self._drop.install()
                print("[drop] 补装完成，挂载点 %d 个" % n)
        except Exception as e:
            print("[drop] 安装失败:", e)

    def _start_bridge(self):
        handlers = {
            "pick_file": self.bridge.pick_file,
            "load_path": self.bridge.load_path,
            "start_fix": self.bridge.start_fix,
            "open_folder": self.bridge.open_folder,
            "cancel": self.bridge.cancel,
            "open_recent": self.bridge.open_recent,
            "remove_recent": self.bridge.remove_recent,
        }
        self._js_bridge = JsBridge(self.view, handlers)
        # 桥就绪后再推最近列表，否则 APP.setRecent 还不存在
        QTimer.singleShot(150, self.bridge.push_recent)
        print("[bridge] 轮询桥已启动")

    def js(self, func, arg_json):
        """调用前端函数（仅限主线程）"""
        try:
            obj = json.loads(arg_json) if arg_json else None
        except Exception:
            obj = arg_json
        self.js_obj(func, obj)

    def closeEvent(self, e):
        conns = self.monitor.report()
        if conns:
            print("警告：检测到外连！", conns, file=sys.stderr)
        else:
            print("网络监控：全程零外连", file=sys.stderr)
        self.monitor.stop()
        super().closeEvent(e)


def main():
    # 保留系统 DPI 缩放（150%），让字形走原生清晰渲染
    # 不能强制 scale=1，否则高端屏上字会糊
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
        "--high-dpi-support=1 "
        "--disable-features=NetworkService "
        "--disable-background-networking "
        "--disable-component-update "
        "--disable-domain-reliability "
        "--no-pings "
        "--disable-sync"
    )
    # PassThrough 保留系统给的小数缩放（1.5）
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)
    w = Win()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
