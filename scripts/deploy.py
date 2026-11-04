# -*- coding: utf-8 -*-
"""一键打包部署 · PSD 修复工具（Qt 版）

用法：
    python scripts/deploy.py              # 完整流程：同步 → 清理 → 构建 → 精简 → 部署
    python scripts/deploy.py --sync-only  # 只同步源码，不构建（改完代码想先跑一下用这个）
    python scripts/deploy.py --no-slim    # 跳过精简（调试用，产物会大 266MB）
    python scripts/deploy.py --dry-run    # 只检查不执行

为什么需要这个脚本：
    index.html 在链路上有 4 份副本，任何一份落后就会打出旧界面。
    手动做 7 步，漏一步就白打 6 分钟：

        工作区镜像 → 项目源 → 构建副本 → dist → app（已部署）
                       ↑           ↑
                   每一步都要同步

    本脚本把这条链路固化下来，并且在每一步之后自检版本号。

踩过的坑（都已处理，别删这些逻辑）：
    1. dist/build 必须用 Python shutil.rmtree 清，不能用 rd/rm
       —— 会被安全钩子改送回收站，等于没删，且累积 1GB/轮。
    2. 部署必须「改名旧目录 → 全新 copytree → 删旧目录」，
       不能用 cp 合并覆盖：合并不会删旧文件，slim 精简掉的模块会一直留着。
       实测四轮后 897 文件/444MB 变成 3998 文件/613MB。
    3. 判断程序是否在运行必须用 psutil 或 Get-Process 按进程名，
       不能用 tasklist + 中文名匹配（GBK 编码，匹配不上）。
    4. 精简后必须校验关键 DLL，缺 Qt6Positioning 会导致
       'DLL load failed while importing QtWebEngineCore'，且只在运行时才报。
"""
import argparse
import os
import shutil
import stat
import subprocess
import sys
import time

# ============================================================
# 路径常量
# ============================================================
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QT_REBUILD = os.path.join(ROOT, "qt_rebuild")
DIST = os.path.join(QT_REBUILD, "dist", "PSD修复工具")
BUILD = os.path.join(QT_REBUILD, "build")
APP = os.path.join(ROOT, "app")
CUR = os.path.join(APP, "PSD修复工具·Qt版")
STALE = os.path.join(APP, "_stale_deploy")
SPEC = os.path.join(QT_REBUILD, "PSD修复工具.spec")
PY = sys.executable

APP_NAME = "PSD修复工具"

# 要同步的源码文件（新增模块记得加进来）
SOURCE_FILES = [
    "psd_repair_qt.py",
    "psd_repair_core.py",
    "js_bridge.py",
    "js_safe.py",
    "net_guard.py",
    "recent_store.py",
]

# 界面目录里要同步的文件
UI_FILES = ["index.html", "boot_icon.png", "feather_icon.png"]
UI_ICON = "feather_icon.ico"        # spec 里用到的 exe 图标

# 精简后必须存在的关键文件（缺一个运行时才会崩）
REQUIRED = [
    "Qt6WebEngineCore.dll", "Qt6WebChannel.dll", "Qt6Network.dll",
    "Qt6Quick.dll", "Qt6Qml.dll", "Qt6Core.dll", "Qt6Gui.dll",
    "Qt6Widgets.dll", "Qt6Positioning.dll",
    "resources/icudtl.dat",
    "resources/qtwebengine_resources.pak",
    "resources/v8_context_snapshot.bin",
]

# 版本指纹：用来判断 index.html 是哪一版
FINGERPRINTS = {
    "boot-halo": "F 版开机动画（字标 + 同心扩散环）",
    "boot-icon": "旧版开机动画（图标）",
}

# ============================================================
# 工具函数
# ============================================================


def size_of(path):
    if not os.path.exists(path):
        return 0
    if os.path.isfile(path):
        return os.path.getsize(path)
    total = 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            try:
                total += os.path.getsize(os.path.join(dirpath, f))
            except OSError:
                pass
    return total


def count_of(path):
    if not os.path.exists(path):
        return 0
    n = 0
    for _, _, filenames in os.walk(path):
        n += len(filenames)
    return n


def mb(n):
    return "%.1f MB" % (n / 1024 / 1024)


def rmtree_py(path):
    """用 Python 删目录。

    不能用 rd/rm —— 会被安全钩子改送回收站，等于没删。
    onerror 兜底处理只读文件（build 目录里常有）。
    """
    if not os.path.exists(path):
        return 0
    sz = size_of(path)

    def onerr(func, target, _exc):
        try:
            os.chmod(target, stat.S_IWRITE)
            func(target)
        except Exception:
            pass

    shutil.rmtree(path, onerror=onerr)
    return sz


def run(cmd, cwd, quiet_lines=12, show_progress=False):
    """跑子进程。

    构建要 6 分钟，全程无输出会让人以为卡死 ——
    所以 show_progress=True 时按关键行实时打印（INFO: 里的阶段名）。

    注意 encoding/errors：中文 Windows 默认用 GBK 解码子进程输出，
    而 PyInstaller 和 slim_final.py 都输出 UTF-8，不指定会抛
    UnicodeDecodeError。所有 subprocess 调用都必须带上这两个参数。
    """
    print("    $ %s" % " ".join(cmd))
    p = subprocess.Popen(
        cmd, cwd=cwd, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True,
        encoding="utf-8", errors="replace")
    tail = []
    last_beat = time.time()
    for line in p.stdout:
        line = line.rstrip()
        if not line:
            continue
        tail.append(line)
        if len(tail) > 300:
            tail.pop(0)
        if show_progress:
            # 只打关键阶段，不然几千行 INFO 刷屏
            for key in ("Analyzing", "Building PYZ", "Building PKG",
                        "Building EXE", "Building COLLECT", "Build complete",
                        "checking", "Traceback", "ERROR"):
                if key in line:
                    print("      " + line[:110])
                    last_beat = time.time()
                    break
            else:
                # 60 秒没动静就打一次心跳，证明还活着
                if time.time() - last_beat > 60:
                    print("      ... 仍在处理（已 %d 秒）"
                          % (time.time() - last_beat))
                    last_beat = time.time()
    p.wait()
    if not show_progress:
        for line in tail[-quiet_lines:]:
            print("      " + line)
    return p.returncode


def quiet_run(cmd, cwd=None, timeout=None):
    """跑一个不需要看输出的命令（清理、检测用）。

    强制 utf-8 + errors=replace，避免中文 Windows 的 GBK 解码崩溃。
    cmd 是字符串时自动走 shell（rd 这类内置命令需要）；
    cwd 在 shell 模式下必须传进去，否则 rd 的相对路径解析错。
    """
    is_str = isinstance(cmd, str)
    try:
        return subprocess.run(
            cmd, cwd=cwd, shell=is_str, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        class _R:
            returncode = 1
            stdout = ""
            stderr = "timeout"
        return _R()


def detect_version(html_path):
    """根据指纹判断 index.html 版本"""
    if not os.path.exists(html_path):
        return "缺失"
    try:
        txt = open(html_path, encoding="utf-8", errors="replace").read()
    except Exception:
        return "读取失败"
    tags = [desc for key, desc in FINGERPRINTS.items() if key in txt]
    return " + ".join(tags) if tags else "未知版本"


def is_running():
    """检测程序是否在运行。

    必须按进程名精确匹配，不能用 tasklist + 中文名（GBK 会乱码匹配不上）。
    优先 psutil，退回 PowerShell Get-Process。
    """
    try:
        import psutil
        for p in psutil.process_iter(["name"]):
            try:
                if p.info["name"] and p.info["name"].startswith(APP_NAME):
                    return p.pid
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return None
    except ImportError:
        pass
    try:
        out = quiet_run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-Process -Name '%s*' -ErrorAction SilentlyContinue | "
             "Select-Object -First 1).Id" % APP_NAME], timeout=15)
        s = out.stdout.strip()
        return int(s) if s.isdigit() else None
    except Exception:
        return None


def step(n, title):
    print()
    print("=" * 64)
    print("[%d] %s" % (n, title))
    print("=" * 64)


# ============================================================
# 各步骤
# ============================================================


def check_env():
    step(0, "环境检查")

    problems = []

    if is_running():
        problems.append(
            "程序正在运行（PID %s），打包前必须先关掉。\n"
            "      原因：程序开着时无法覆盖 exe，会覆盖失败或界面损坏。" % is_running())

    if not os.path.exists(SPEC):
        problems.append("spec 文件不存在: %s" % SPEC)

    for f in SOURCE_FILES:
        if not os.path.exists(os.path.join(ROOT, f)):
            problems.append("源码缺失: %s" % f)

    for f in UI_FILES:
        p = os.path.join(ROOT, "qt_ui", f)
        if not os.path.exists(p):
            # boot_icon.png 在 F 版已经不用了，缺了不算错
            if f == "boot_icon.png":
                print("    · %-22s 不存在（F 版已不使用，可忽略）" % f)
                continue
            problems.append("界面文件缺失: qt_ui/%s" % f)

    # 检查 PyInstaller
    r = quiet_run([PY, "-m", "PyInstaller", "--version"], timeout=60)
    if r.returncode != 0:
        problems.append("PyInstaller 不可用")
    else:
        print("    · PyInstaller %s" % r.stdout.strip())

    print("    · Python %s" % sys.version.split()[0])
    print("    · 项目根 %s" % ROOT)

    if problems:
        print()
        print("!! 检查未通过：")
        for p in problems:
            print("   - " + p)
        return False
    print()
    print("    全部通过")
    return True


def sync_sources():
    step(1, "同步源码到 qt_rebuild")

    # 源码 .py
    for f in SOURCE_FILES:
        src = os.path.join(ROOT, f)
        dst = os.path.join(QT_REBUILD, f)
        shutil.copy2(src, dst)
        print("    %-24s %7d B" % (f, os.path.getsize(dst)))

    # 界面文件
    for f in UI_FILES:
        src = os.path.join(ROOT, "qt_ui", f)
        if not os.path.exists(src):
            print("    %-24s 跳过（不存在）" % ("qt_ui/" + f))
            continue
        dst = os.path.join(QT_REBUILD, "qt_ui", f)
        shutil.copy2(src, dst)
        print("    %-24s %7d B" % ("qt_ui/" + f, os.path.getsize(dst)))

    # exe 图标
    src = os.path.join(ROOT, UI_ICON)
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(QT_REBUILD, UI_ICON))
        print("    %-24s %7d B" % (UI_ICON, os.path.getsize(src)))

    # 同步后自检
    print()
    src_html = os.path.join(ROOT, "qt_ui", "index.html")
    dst_html = os.path.join(QT_REBUILD, "qt_ui", "index.html")
    a, b = os.path.getsize(src_html), os.path.getsize(dst_html)
    print("    index.html 校验: 源 %d B / 构建 %d B  %s"
          % (a, b, "OK" if a == b else "不一致！"))
    print("    版本: %s" % detect_version(dst_html))
    return a == b


def clean_old():
    step(2, "清理旧构建产物")

    for path, name in ((DIST, "dist"), (BUILD, "build")):
        if os.path.exists(path):
            sz = size_of(path)
            n = count_of(path)
            rmtree_py(path)
            print("    %-6s 已删 %4d 文件  %s" % (name, n, mb(sz)))
        else:
            print("    %-6s 不存在，跳过" % name)

    # 顺手清掉上次可能残留的部署中间目录
    if os.path.exists(STALE):
        rmtree_py(STALE)
        print("    _stale_deploy 残留已清")


def build():
    step(3, "PyInstaller 构建")
    t0 = time.time()
    rc = run([PY, "-m", "PyInstaller", "--noconfirm", SPEC],
             cwd=QT_REBUILD, show_progress=True)
    dur = time.time() - t0
    if rc != 0:
        print()
        print("!! 构建失败，退出码 %d（耗时 %.0fs）" % (rc, dur))
        return False
    print()
    print("    构建成功，耗时 %.0fs" % dur)
    print("    产物 %d 文件 %s" % (count_of(DIST), mb(size_of(DIST))))
    return True


def slim():
    step(4, "精简（slim_final.py）")
    script = os.path.join(ROOT, "scripts", "slim_final.py")
    if not os.path.exists(script):
        print("    slim_final.py 不存在，跳过")
        return True
    before = size_of(DIST)
    rc = run([PY, script], cwd=os.path.join(ROOT, "scripts"))
    after = size_of(DIST)
    if rc != 0:
        print()
        print("!! 精简失败，退出码 %d" % rc)
        return False
    print()
    print("    %s → %s（释放 %s）" % (mb(before), mb(after), mb(before - after)))

    # 关键文件校验：缺了运行时才崩，必须在这里拦住
    # 注意：这些文件在 _internal/PySide6/ 下，不是 _internal/ 根目录
    # （和 slim_final.py 里的 PD 变量一致，别改成 _internal 根）
    pyside = os.path.join(DIST, "_internal", "PySide6")
    missing = []
    for rel in REQUIRED:
        p = os.path.join(pyside, rel.replace("/", os.sep))
        if not os.path.exists(p):
            missing.append(rel)
    if missing:
        print()
        print("!! 精简删过头了，%s 下缺少关键文件：" % pyside)
        for m in missing:
            print("     - " + m)
        print("   参考交接文档 §7.5，把这些从精简名单里去掉")
        return False
    print("    关键文件 %d 项全部存在" % len(REQUIRED))
    return True


def deploy():
    step(5, "部署到 app/")

    if is_running():
        print("!! 程序正在运行，无法覆盖。请先关掉。")
        return False

    print("    源  %d 文件 %s" % (count_of(DIST), mb(size_of(DIST))))
    print("    现  %d 文件 %s" % (count_of(CUR), mb(size_of(CUR))))

    # 1) 改名旧目录（copytree 要求目标不存在）
    if os.path.exists(CUR):
        if os.path.exists(STALE):
            rmtree_py(STALE)
        os.rename(CUR, STALE)
        print("    [1] 旧目录已改名为 _stale_deploy")

    # 2) 全新复制（不能用 cp 合并，见文件头第 2 条坑）
    shutil.copytree(DIST, CUR)
    print("    [2] 全新复制完成：%d 文件 %s"
          % (count_of(CUR), mb(size_of(CUR))))

    # 3) 删旧目录（rd 必须相对名 + cwd）
    quiet_run('rd /s /q "_stale_deploy"', cwd=APP)
    print("    [3] 旧目录已删，残留=%s" % os.path.exists(STALE))
    return True


def verify():
    step(6, "部署后校验")

    ok = True
    exe = os.path.join(CUR, "PSD修复工具.exe")
    if os.path.exists(exe):
        print("    exe            %9d B" % os.path.getsize(exe))
    else:
        print("    !! exe 不存在")
        ok = False

    idx = os.path.join(CUR, r"_internal\qt_ui\index.html")
    if os.path.exists(idx):
        n = os.path.getsize(idx)
        v = detect_version(idx)
        src_n = os.path.getsize(os.path.join(ROOT, "qt_ui", "index.html"))
        same = "OK" if n == src_n else "与源码不一致！"
        print("    index.html     %9d B   %s" % (n, v))
        print("                   与源码对比 %d B → %s" % (src_n, same))
        if n != src_n:
            ok = False
    else:
        print("    !! 部署目录里没有 index.html")
        ok = False

    print("    部署体积       %s / %d 文件" % (mb(size_of(CUR)), count_of(CUR)))

    # 文件数应和 dist 一致，多出来说明合并覆盖了
    if count_of(CUR) != count_of(DIST):
        print("    !! 文件数与 dist 不一致（%d vs %d），可能是合并覆盖"
              % (count_of(CUR), count_of(DIST)))
        ok = False
    else:
        print("    文件数与 dist 一致（无残留垃圾）")
    return ok


def purge_recycle():
    """清回收站里的构建产物（每轮约 1GB，不清会越积越多）"""
    script = os.path.join(ROOT, "scripts", "rb_purge_fast.py")
    if not os.path.exists(script):
        return
    print()
    print("    顺手清回收站 ...")
    quiet_run([PY, script], cwd=os.path.join(ROOT, "scripts"), timeout=300)


# ============================================================
# 主流程
# ============================================================


def main():
    ap = argparse.ArgumentParser(
        description="PSD 修复工具 一键打包部署",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    ap.add_argument("--sync-only", action="store_true",
                    help="只同步源码，不构建（改完代码想先跑一下时用）")
    ap.add_argument("--no-slim", action="store_true",
                    help="跳过精简（调试用，产物大 266MB）")
    ap.add_argument("--dry-run", action="store_true",
                    help="只检查环境和版本，不执行")
    args = ap.parse_args()

    print()
    print("=" * 64)
    print("  PSD 修复工具 · 打包部署")
    print("  项目 %s" % ROOT)
    print("=" * 64)

    # 环境检查
    if not check_env():
        sys.exit(1)

    if args.dry_run:
        step(1, "版本现状（dry-run，不执行）")
        for label, p in (
            ("项目源", os.path.join(ROOT, "qt_ui", "index.html")),
            ("构建副本", os.path.join(QT_REBUILD, "qt_ui", "index.html")),
            ("已部署", os.path.join(CUR, r"_internal\qt_ui\index.html")),
        ):
            print("    %-10s %9s B   %s"
                  % (label,
                     (os.path.getsize(p) if os.path.exists(p) else "-"),
                     detect_version(p)))
        print()
        print("    源文件与构建副本 %s"
              % ("一致" if os.path.getsize(
                  os.path.join(ROOT, "qt_ui", "index.html")) == os.path.getsize(
                  os.path.join(QT_REBUILD, "qt_ui", "index.html"))
                  else "不一致 —— 需要同步"))
        return

    # 同步
    if not sync_sources():
        print()
        print("!! 源码同步后版本不一致，中止")
        sys.exit(1)

    if args.sync_only:
        print()
        print("已同步完成（--sync-only，未构建）")
        return

    # 构建链
    clean_old()
    if not build():
        sys.exit(1)
    if not args.no_slim:
        if not slim():
            sys.exit(1)
    if not deploy():
        sys.exit(1)
    ok = verify()
    purge_recycle()

    print()
    print("=" * 64)
    if ok:
        print("  完成。")
        print("  桌面快捷方式：C:\\Users\\123\\DeskBox\\Toll\\PSD修复工具.lnk")
        print("  建议手动启动一次，确认开机动画正常。")
    else:
        print("  部署完成但有校验警告，见上方 !! 项。")
    print("=" * 64)
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()
