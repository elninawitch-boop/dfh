
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
