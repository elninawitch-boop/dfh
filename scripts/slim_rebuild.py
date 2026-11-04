# -*- coding: utf-8 -*-
"""对重新打包的 Qt 版做精简（已验证安全项）"""
import os
import shutil

DIST = r"C:\Users\123\1\qt_rebuild\dist\PSD修复工具"
INTERNAL = os.path.join(DIST, "_internal")
PD = os.path.join(INTERNAL, "PySide6")


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


def remove(paths):
    total = 0
    for p in paths:
        if not os.path.exists(p):
            continue
        sz = size_of(p)
        try:
            if os.path.isdir(p):
                shutil.rmtree(p)
            else:
                os.remove(p)
            total += sz
        except Exception as e:
            print("    失败 %s: %s" % (os.path.basename(p), e))
    return total


before = size_of(DIST)
print("=" * 62)
print("精简前: %.1f MB" % (before / 1024 / 1024))
print("=" * 62)

total = 0

# ---- 1. WebEngine 调试资源 ----
print("\n[1] WebEngine 调试资源")
saved = remove([
    os.path.join(PD, "resources", "qtwebengine_devtools_resources.debug.pak"),
    os.path.join(PD, "resources", "qtwebengine_devtools_resources.pak"),
    os.path.join(PD, "resources", "qtwebengine_resources.debug.pak"),
    os.path.join(PD, "resources", "qtwebengine_resources_100p.debug.pak"),
    os.path.join(PD, "resources", "qtwebengine_resources_200p.debug.pak"),
])
total += saved
print("    释放 %.1f MB" % (saved / 1024 / 1024))

# ---- 2. 软件 OpenGL ----
print("[2] 软件 OpenGL")
saved = remove([os.path.join(PD, "opengl32sw.dll")])
total += saved
print("    释放 %.1f MB" % (saved / 1024 / 1024))

# ---- 3. 翻译 ----
print("[3] 翻译文件")
saved = remove([
    os.path.join(PD, "translations"),
    os.path.join(INTERNAL, "translations"),
])
total += saved
print("    释放 %.1f MB" % (saved / 1024 / 1024))

# ---- 4. qml 目录 ----
print("[4] qml 目录")
saved = remove([
    os.path.join(PD, "qml"),
    os.path.join(INTERNAL, "qml"),
])
total += saved
print("    释放 %.1f MB" % (saved / 1024 / 1024))

# ---- 5. 开发工具 ----
print("[5] 开发工具")
tools = []
for d in (PD, INTERNAL):
    for f in ("qmlls.exe", "qml.exe", "qmlcachegen.exe", "qmllint.exe",
              "qmlformat.exe", "qmlimportscanner.exe", "designer.exe",
              "assistant.exe", "linguist.exe", "lrelease.exe",
              "lupdate.exe"):
        p = os.path.join(d, f)
        if os.path.exists(p):
            tools.append(p)
saved = remove(tools)
total += saved
print("    释放 %.1f MB" % (saved / 1024 / 1024))

# ---- 6. 无关模块 ----
print("[6] 无关 Qt 模块")
misc = []
if os.path.isdir(PD):
    for f in os.listdir(PD):
        if f.startswith(("Qt6Designer", "Qt6Pdf", "Qt6UiTools",
                         "Qt6Charts", "Qt6DataVisualization",
                         "Qt6Graphs", "Qt6Multimedia", "Qt6SpatialAudio",
                         "Qt63D", "Qt6Quick3D", "Qt6Bluetooth",
                         "Qt6Nfc", "Qt6Positioning", "Qt6Location",
                         "Qt6Sensors", "Qt6SerialPort", "Qt6SerialBus",
                         "Qt6RemoteObjects", "Qt6Scxml",
                         "Qt6StateMachine", "Qt6Test", "Qt6Help",
                         "Qt6Sql", "Qt6Xml", "Qt6VirtualKeyboard",
                         "Qt6Labs", "avcodec", "avformat", "avutil",
                         "swresample", "swscale")):
            misc.append(os.path.join(PD, f))
# 无关的 pyd
if os.path.isdir(PD):
    for f in os.listdir(PD):
        if f.endswith(".pyd") and f.startswith(
                ("QtQuick", "QtQml", "QtDesigner", "QtCharts",
                 "QtDataVisualization", "QtGraphs", "QtBluetooth",
                 "QtNfc", "QtPositioning", "QtLocation", "QtSensors",
                 "QtSerialPort", "QtSerialBus", "QtRemoteObjects",
                 "QtScxml", "QtStateMachine", "QtTest", "QtHelp",
                 "QtUiTools", "QtSql", "QtXml", "QtPdf",
                 "QtMultimedia", "QtSpatialAudio")):
            misc.append(os.path.join(PD, f))
saved = remove(misc)
total += saved
print("    释放 %.1f MB (%d 项)" % (saved / 1024 / 1024, len(misc)))

# ---- 7. 插件目录 ----
print("[7] 无关插件目录")
dirs = []
for d in ("sqldrivers", "sceneparsers", "assetimporters", "renderers",
          "qmltooling", "designer", "metatypes",
          "Pinyin", "OpenWNN", "GraphicalEffects", "images"):
    for base in (INTERNAL, PD):
        p = os.path.join(base, d)
        if os.path.exists(p):
            dirs.append(p)
saved = remove(dirs)
total += saved
print("    释放 %.1f MB (%d 项)" % (saved / 1024 / 1024, len(dirs)))

after = size_of(DIST)
print()
print("=" * 62)
print("精简后: %.1f MB" % (after / 1024 / 1024))
print("释放: %.1f MB (%.0f%%)"
      % (total / 1024 / 1024, total * 100.0 / max(before, 1)))
print("=" * 62)

# 验证关键文件仍在
print("\n关键文件检查:")
for f in ("Qt6WebEngineCore.dll", "Qt6WebChannel.dll", "Qt6Network.dll",
          "Qt6Quick.dll", "Qt6Qml.dll", "Qt6Core.dll", "Qt6Gui.dll",
          "Qt6Widgets.dll"):
    p = os.path.join(PD, f)
    print("  %-26s %s" % (f, "OK" if os.path.exists(p) else "缺失!"))
