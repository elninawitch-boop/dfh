# -*- coding: utf-8 -*-
"""找出精简后缺失的必需文件

方法：对比"能运行的备份"和"当前精简版"，只列出 DLL/PYD 差异
（qml/翻译是故意删的，排除）
"""
import os

OLD = r"E:\1\psd-tool-20261101\qt_backup_full\_internal"
NEW = r"C:\Users\123\Desktop\PSD修复工具·Qt版\_internal"

# 只关注这些扩展名（可执行/库文件）
EXTS = (".dll", ".pyd", ".exe", ".dat", ".pak")


def collect(root):
    out = {}
    for dp, dn, fn in os.walk(root):
        # 跳过故意删除的目录
        rel_dir = os.path.relpath(dp, root)
        if any(x in rel_dir for x in (
                "qml", "translations", "designer", "qmltooling",
                "metatypes", "sceneparsers", "assetimporters",
                "renderers", "sqldrivers", "images", "Pinyin",
                "OpenWNN", "GraphicalEffects")):
            continue
        for f in fn:
            if not f.lower().endswith(EXTS):
                continue
            full = os.path.join(dp, f)
            out[f] = {
                "rel": os.path.relpath(full, root),
                "size": os.path.getsize(full),
            }
    return out


old = collect(OLD)
new = collect(NEW)

print("=" * 70)
print("对比可运行版本 vs 当前精简版")
print("=" * 70)
print("可运行版本文件数: %d" % len(old))
print("当前版本文件数:   %d" % len(new))

missing = {k: v for k, v in old.items() if k not in new}
extra = {k: v for k, v in new.items() if k not in old}

print()
print("缺失的文件 (%d 个):" % len(missing))
total = 0
for name, info in sorted(missing.items(),
                         key=lambda x: -x[1]["size"]):
    total += info["size"]
    print("  %-46s %8.1f MB  %s"
          % (name[:46], info["size"] / 1024 / 1024, info["rel"]))

print()
print("缺失总计: %.1f MB" % (total / 1024 / 1024))

if extra:
    print()
    print("多出的文件: %d 个" % len(extra))
