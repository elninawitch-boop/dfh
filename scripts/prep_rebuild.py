# -*- coding: utf-8 -*-
"""准备 Qt 版重新打包

包含：
  · 最新 UI（主题配色修复）
  · 羽毛图标
  · 精简后的依赖（打包后再删无用模块）
"""
import os
import shutil

SRC = r"C:\Users\123\1"
ARCHIVE = r"E:\1\psd-tool-20261101"
BUILD = r"C:\Users\123\1\qt_rebuild"

# ---------- 清理旧构建目录 ----------
if os.path.exists(BUILD):
    shutil.rmtree(BUILD)
os.makedirs(BUILD)

print("=" * 60)
print("准备构建目录")
print("=" * 60)

# ---------- 1. 复制源码 ----------
FILES = [
    "psd_repair_qt.py",
    "psd_repair_core.py",
    "js_bridge.py",
    "js_safe.py",
    "net_guard.py",
]
print("\n[1] 复制源码")
for f in FILES:
    src = os.path.join(SRC, f)
    if os.path.exists(src):
        shutil.copy2(src, BUILD)
        print("    %-24s %6.1f KB" % (f, os.path.getsize(src) / 1024))
    else:
        print("    %-24s 缺失!" % f)

# ---------- 2. 复制 UI ----------
print("\n[2] 复制界面")
ui_src = os.path.join(SRC, "qt_ui")
ui_dst = os.path.join(BUILD, "qt_ui")
if os.path.exists(ui_src):
    shutil.copytree(ui_src, ui_dst)
    for f in os.listdir(ui_dst):
        p = os.path.join(ui_dst, f)
        print("    %-24s %6.1f KB" % (f, os.path.getsize(p) / 1024))

# ---------- 3. 复制图标 ----------
print("\n[3] 复制图标")
icon_src = os.path.join(SRC, "feather_icon.ico")
if os.path.exists(icon_src):
    shutil.copy2(icon_src, BUILD)
    print("    feather_icon.ico       %6.1f KB"
          % (os.path.getsize(icon_src) / 1024))
else:
    print("    !! 图标不存在，需要先生成")

# ---------- 4. 校验关键文件 ----------
print("\n[4] 校验界面文件")
ui_file = os.path.join(BUILD, "qt_ui", "index.html")
if os.path.exists(ui_file):
    content = open(ui_file, encoding="utf-8").read()
    checks = [
        ("THEME_COLORS 配色表", "THEME_COLORS"),
        ("紫蓝粉主题", "紫蓝粉"),
        ("粉色光斑", "e868c8"),
        ("石墨主题", "石墨"),
        ("进度面板空状态", "prog-empty"),
        ("禁用按钮样式", "not-allowed"),
    ]
    for name, kw in checks:
        print("    %-24s %s" % (name, "OK" if kw in content else "缺失"))

print()
print("构建目录:", BUILD)
total = sum(os.path.getsize(os.path.join(dp, f))
            for dp, dn, fn in os.walk(BUILD) for f in fn)
print("大小: %.1f KB" % (total / 1024))
