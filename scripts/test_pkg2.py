# -*- coding: utf-8 -*-
"""用打包环境测试导入（UTF-8 输出）"""
import os
import subprocess
import sys

DIST = r"C:\Users\123\Desktop\PSD修复工具·Qt版"
INTERNAL = os.path.join(DIST, "_internal")
PD = os.path.join(INTERNAL, "PySide6")

TEST = """# -*- coding: utf-8 -*-
import sys, os
internal = sys.argv[1]
pd = os.path.join(internal, "PySide6")
sys.path.insert(0, internal)
sys.path.insert(0, pd)
os.add_dll_directory(pd)
os.add_dll_directory(internal)

mods = [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtNetwork",
    "PySide6.QtWebChannel",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
]
for m in mods:
    try:
        __import__(m)
        print("OK   " + m, flush=True)
    except Exception as e:
        print("FAIL " + m + " -> " + str(e)[:300], flush=True)
        sys.exit(1)
print("ALL_OK", flush=True)
"""


def main():
    p = r"C:\Users\123\1\_pkgtest2.py"
    with open(p, "w", encoding="utf-8") as f:
        f.write(TEST)

    env = os.environ.copy()
    env["PATH"] = PD + os.pathsep + INTERNAL + os.pathsep + env.get("PATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    r = subprocess.run(
        [sys.executable, p, INTERNAL],
        capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=120, env=env)
    print("=" * 62)
    print("导入测试")
    print("=" * 62)
    print(r.stdout)
    if r.stderr.strip():
        print("--- stderr ---")
        print(r.stderr[-800:])


if __name__ == "__main__":
    main()
