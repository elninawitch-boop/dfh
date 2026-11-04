# -*- coding: utf-8 -*-
"""最近打开的文件记录

为什么放在 Python 侧而不是 localStorage：
  · Qt WebEngine 默认 profile 的 localStorage 不保证落盘（net_guard 把
    HttpCacheType 设成了 MemoryHttpCache，持久化行为不可依赖）；
  · JS 侧本来就拿不到完整路径（拖放由 Qt 层 DropCatcher 取值，
    load_path 只把 basename 传给 JS），要「再点一次就能重新打开」
    必须有完整路径，只能在 Python 侧存。

存储位置：%LOCALAPPDATA%\\PSD修复工具\\recent.json
  · 不写到程序目录（打包后是只读的 _internal）
  · 不写到用户文档目录（不污染）
  · 纯本地文件，不联网

只留最近 MAX_ITEMS 条，按打开时间倒序。
"""
import json
import os
import threading

MAX_ITEMS = 5
APP_DIR_NAME = "PSD修复工具"
FILE_NAME = "recent.json"


def _store_dir():
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        base = os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, APP_DIR_NAME)


def _store_path():
    return os.path.join(_store_dir(), FILE_NAME)


class RecentStore:
    """最近文件列表（线程安全；实际只会在主线程调用，锁是兜底）"""

    def __init__(self):
        self._lock = threading.Lock()
        self._items = self._load()

    # ------------------------------------------------------------ 读写
    def _load(self):
        try:
            with open(_store_path(), "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                return []
            out = []
            for it in data:
                if not isinstance(it, dict):
                    continue
                p = it.get("path")
                if not isinstance(p, str) or not p:
                    continue
                out.append({
                    "path": p,
                    "name": os.path.basename(p),
                    "size": float(it.get("size") or 0),
                    "time": float(it.get("time") or 0),
                })
            return out[:MAX_ITEMS]
        except Exception:
            return []

    def _save(self):
        try:
            d = _store_dir()
            os.makedirs(d, exist_ok=True)
            tmp = _store_path() + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._items, f, ensure_ascii=False, indent=1)
            os.replace(tmp, _store_path())
        except Exception as e:
            print("[recent] 保存失败:", e)

    # ------------------------------------------------------------ 对外
    def list(self):
        """给 JS 的列表：去掉 path（前端用索引，不需要真路径）"""
        with self._lock:
            return [{
                "name": it["name"],
                "size": it["size"],
                "time": it["time"],
                "exists": os.path.exists(it["path"]),
            } for it in self._items]

    def path_at(self, index):
        """按下标取真实路径（前端只回传下标，不回传路径）"""
        try:
            i = int(index)
        except Exception:
            return None
        with self._lock:
            if 0 <= i < len(self._items):
                return self._items[i]["path"]
        return None

    def remove_at(self, index):
        try:
            i = int(index)
        except Exception:
            return False
        with self._lock:
            if 0 <= i < len(self._items):
                self._items.pop(i)
                self._save()
                return True
        return False

    def touch(self, path):
        """打开一个文件：移到队首并更新大小/时间"""
        if not path:
            return
        path = os.path.abspath(path)
        try:
            size = os.path.getsize(path) / 1024 / 1024
        except Exception:
            size = 0.0
        import time as _t
        item = {"path": path, "name": os.path.basename(path),
                "size": size, "time": _t.time()}
        with self._lock:
            self._items = [it for it in self._items if it["path"] != path]
            self._items.insert(0, item)
            del self._items[MAX_ITEMS:]
            self._save()
