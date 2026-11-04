# -*- coding: utf-8 -*-
"""精确对比：找出 QtWebEngineCore 需要的、但精简版缺失的文件"""
import os

OLD = r"E:\1\psd-tool-20261101\qt_backup_full\_internal"
NEW = r"C:\Users\123\Desktop\PSD修复工具·Qt版\_internal"

# 重点看 PySide6 根目录和 resources
def collect(root):
    out = {}
    for dp, dn, fn in os.walk(root):
        rel = os.path.relpath(dp, root)
        # 只看 PySide6 相关
        if not (rel == "PySide6" or rel.startswith("PySide6\\")
                or rel.startswith("PySide6/")):
            continue
        for f in fn:
            out[os.path.join(rel, f)] = os.path.getsize(os.path.join(dp, f))
    return out


old = collect(OLD)
new = collect(NEW)

missing = {k: v for k, v in old.items() if k not in new}
print("=" * 74)
print("PySide6 目录对比")
print("=" * 74)
print("可运行版: %d 个文件" % len(old))
print("精简版:   %d 个文件" % len(new))
print("缺失:     %d 个文件" % len(missing))
print()

# 按大小排序，只显示 > 100KB 的（小文件太多）
big = {k: v for k, v in missing.items() if v > 100 * 1024}
print("缺失的较大文件 (>100KB): %d 个" % len(big))
total = 0
for k, v in sorted(big.items(), key=lambda x: -x[1]):
    total += v
    print("  %-58s %8.2f MB" % (k, v / 1024 / 1024))
print()
print("大文件缺失总计: %.1f MB" % (total / 1024 / 1024))

# 特别关注这些可能影响 WebEngine 的
print()
print("可能影响 WebEngine 的缺失项:")
KEYWORDS = ("Qt6WebEngine", "Qt6Quick", "Qt6Qml", "Qt6Network",
            "Qt6Core", "Qt6Gui", "Qt6Widgets", "Qt6Positioning",
            "Qt6WebChannel", "icudtl", "v8_", "resources")
for k, v in sorted(missing.items()):
    if any(kw in k for kw in KEYWORDS):
        print("  %-58s %8.2f MB" % (k, v / 1024 / 1024))
