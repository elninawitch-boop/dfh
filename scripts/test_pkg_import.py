# -*- coding: utf-8 -*-
"""用打包目录的环境测试 PySide6 导入，定位缺失的 DLL"""
import os
import subprocess
import sys

DIST = r"C:\Users\123\Desktop\PSD修复工具·Qt版"
INTERNAL = os.path.join(DIST, "_internal")
PD = os.path.join(INTERNAL, "PySide6")

SCRIPT = r'''
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
]
for m in mods:
    try:
        __import__(m)
        print("OK  ", m)
    except Exception as e:
        print("FAIL", m, "->", e)
        sys.exit(1)

# 关键：WebEngine
for m in ["PySide6.QtWebChannel",
          "PySide6.QtWebEngineCore",
          "PySide6.QtWebEngineWidgets"]:
    try:
        __import__(m)
        print("OK  ", m)
    except Exception as e:
        print("FAIL", m, "->", e)
        sys.exit(2)

print("ALL_OK")
'''


def main():
    path = r"C:\Users\123\1\_pkgtest.py"
    with open(path, "w", encoding="utf-8") as f:
        f.write(SCRIPT)

    env = os.environ.copy()
    env["PATH"] = PD + os.pathsep + INTERNAL + os.pathsep + env.get("PATH", "")

    r = subprocess.run(
        [sys.executable, path, INTERNAL],
        capture_output=True, text=True, timeout=120, env=env)
    print("=" * 62)
    print("导入测试结果")
    print("=" * 62)
    print(r.stdout)
    if r.stderr:
        print("--- stderr ---")
        print(r.stderr[-1500:])


if __name__ == "__main__":
    main()
