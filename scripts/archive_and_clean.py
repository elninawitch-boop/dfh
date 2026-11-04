# -*- coding: utf-8 -*-
"""把本轮的构建产物和备份移到 E:\1，然后清理 C 盘

E:\1 已存在大量历史内容，所以建独立子目录：E:\1\psd-tool-20261101
"""
import os
import shutil
import sys

SRC = r"C:\Users\123\1"
ARCHIVE = r"E:\1\psd-tool-20261101"


def size_of(p):
    if not os.path.exists(p):
        return 0
    if os.path.isfile(p):
        return os.path.getsize(p)
    t = 0
    for dp, dn, fn in os.walk(p):
        for f in fn:
            try:
                t += os.path.getsize(os.path.join(dp, f))
            except Exception:
                pass
    return t


def fmt(mb):
    return "%.1f MB" % (mb / 1024 / 1024)


# ---------- 1. 建归档目录 ----------
os.makedirs(ARCHIVE, exist_ok=True)
print("归档目录:", ARCHIVE)
print()

# ---------- 2. 要归档的项目 ----------
ITEMS = [
    # (源路径, 归档里的名字, 说明)
    ("qt_backup_full", "qt_backup_full",
     "Qt 版完整备份（710MB，精简前的原始状态）"),
    ("qt_build", "qt_build",
     "Qt 版打包中间产物（build/dist/spec）"),
    ("psd_tool_build", "psd_tool_build",
     "Tk 版打包目录"),
]

total_moved = 0
for src_name, dst_name, desc in ITEMS:
    src = os.path.join(SRC, src_name)
    if not os.path.exists(src):
        print("[跳过] %-22s 不存在" % src_name)
        continue
    sz = size_of(src)
    dst = os.path.join(ARCHIVE, dst_name)
    if os.path.exists(dst):
        print("[跳过] %-22s 归档已存在" % src_name)
        continue
    print("[移动] %-22s %10s  -> %s" % (src_name, fmt(sz), dst_name))
    try:
        shutil.move(src, dst)
        total_moved += sz
    except Exception as e:
        print("       失败: %s" % e)

# ---------- 3. 归档测试脚本 ----------
print()
SCRIPTS_ARCHIVE = os.path.join(ARCHIVE, "dev_scripts")
os.makedirs(SCRIPTS_ARCHIVE, exist_ok=True)

# 本轮产生的临时脚本前缀
PREFIXES = (
    "test_", "slim_", "bench_", "diag_", "fix_", "add_", "switch_",
    "verify_", "prep_", "measure_", "resolve_", "trace_", "profile_",
    "count_", "speedup", "opt_", "adjust_", "polish", "upgrade_",
    "rewrite_", "integrate_", "isolate_", "sharpen_", "boost_",
    "tune_", "kill_", "phase_", "restore_", "set_font", "unify_",
    "replace_", "_imp_test", "_simple", "_stress", "_stepwise",
    "_checkdata", "_scan", "_scan2", "fetch_gitee", "gitee_list",
    "glass_render", "js_bridge", "js_safe", "net_guard",
    "psd_repair_qt", "qt_glass", "qt_proto", "qt_test", "qt_web_test",
    "qt_screenshot", "ambient", "motion", "extract_444",
)

moved_scripts = 0
for f in os.listdir(SRC):
    if not f.endswith(".py"):
        continue
    if not f.startswith(PREFIXES):
        continue
    src = os.path.join(SRC, f)
    dst = os.path.join(SCRIPTS_ARCHIVE, f)
    try:
        shutil.move(src, dst)
        moved_scripts += 1
    except Exception as e:
        print("  脚本移动失败 %s: %s" % (f, e))

print("[归档] %d 个开发脚本 -> dev_scripts/" % moved_scripts)

# ---------- 4. 归档截图 ----------
print()
SHOTS_ARCHIVE = os.path.join(ARCHIVE, "screenshots")
os.makedirs(SHOTS_ARCHIVE, exist_ok=True)

SHOT_PREFIXES = (
    "v1", "v2", "v3", "v4", "v5", "v6", "v7", "v8", "v9", "v10",
    "g1", "g2", "g3", "g4", "g5", "g6", "g7", "g8", "g9", "g10",
    "g11", "g12", "check1", "check2", "final1", "new_gui", "gui_shot",
    "desktop_app", "qt1", "qt_shot", "qt_final", "qt_packaged",
    "bridge_test", "e2e_", "txt1", "txt2", "btn1", "btn2", "btn3",
    "glass_test", "glass_v2", "glass_v3", "gl_test", "gl_v2", "gl_v3",
    "zoom_", "sharp_test", "realtime_test", "scale_", "theme_",
    "bg_00", "bg_06", "bg_12", "bg_20", "bg_30", "bg_new",
    "mv_000", "mv_025", "mv_050", "mv_075",
    "p1", "p2", "p3", "font_test", "font_compare",
    "dbg_bg", "dbg_lens", "preview_a", "preview_b",
)

moved_shots = 0
for f in os.listdir(SRC):
    if not f.lower().endswith((".png", ".jpg", ".gif")):
        continue
    if not f.startswith(SHOT_PREFIXES):
        continue
    src = os.path.join(SRC, f)
    dst = os.path.join(SHOTS_ARCHIVE, f)
    try:
        shutil.move(src, dst)
        moved_shots += 1
    except Exception:
        pass

print("[归档] %d 张截图 -> screenshots/" % moved_shots)

# ---------- 5. 归档文档 ----------
DOCS_ARCHIVE = os.path.join(ARCHIVE, "docs")
os.makedirs(DOCS_ARCHIVE, exist_ok=True)
for f in ("明天待办.md", "交接状态-20261031.md", "项目上下文.md"):
    src = os.path.join(SRC, f)
    if os.path.exists(src):
        try:
            shutil.move(src, os.path.join(DOCS_ARCHIVE, f))
            print("[归档] %s" % f)
        except Exception:
            pass

# ---------- 6. 保留的核心文件 ----------
print()
print("=" * 66)
print("归档完成，共移动: %s" % fmt(total_moved))
print("=" * 66)
print()
print("C:\\Users\\123\\1 保留的文件:")
KEEP = [
    "psd_repair_gui.py",       # Tk 版主程序
    "psd_repair_core.py",      # 修复引擎
    "gl_glass.py",             # GPU 玻璃
    "bg_render.py",            # 背景动画
    "text_render.py",          # 文字渲染
    "psd_repair.py",           # 命令行版
    "qt_ui",                   # Qt 版界面
]
for k in KEEP:
    p = os.path.join(SRC, k)
    if os.path.exists(p):
        print("  %-24s %10s" % (k, fmt(size_of(p))))
    else:
        print("  %-24s (不存在)" % k)

print()
print("E:\\1\\psd-tool-20261101 内容:")
for d in sorted(os.listdir(ARCHIVE)):
    p = os.path.join(ARCHIVE, d)
    print("  %-24s %10s" % (d, fmt(size_of(p))))
print()
print("归档总大小: %s" % fmt(size_of(ARCHIVE)))
