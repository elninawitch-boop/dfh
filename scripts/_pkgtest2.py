# -*- coding: utf-8 -*-
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
