# -*- coding: utf-8 -*-
"""精简新打包的 Qt 版（这次保留 Qt6Positioning）"""
import os
import shutil

# 从脚本位置推导 dist（脚本在 psd-tool/scripts/ 下）
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "qt_rebuild", "dist", "PSD修复工具")
INTERNAL = os.path.join(DIST, "_internal")
PD = os.path.join(INTERNAL, "PySide6")
OLD = r"E:\1\psd-tool-20261101\qt_backup_full\_internal\PySide6"


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
        except Exception:
            pass
    return total


print("=" * 64)
before = size_of(DIST)
print("精简前: %.1f MB" % (before / 1024 / 1024))
print("=" * 64)

total = 0

# 1. 调试资源（保留非 debug 的 .pak）
saved = remove([
    os.path.join(PD, "resources", "qtwebengine_devtools_resources.debug.pak"),
    os.path.join(PD, "resources", "qtwebengine_devtools_resources.pak"),
    os.path.join(PD, "resources", "qtwebengine_resources.debug.pak"),
    os.path.join(PD, "resources", "qtwebengine_resources_100p.debug.pak"),
    os.path.join(PD, "resources", "qtwebengine_resources_200p.debug.pak"),
])
total += saved
print("[1] 调试资源           %6.1f MB" % (saved / 1024 / 1024))

# 2. 软件 OpenGL
saved = remove([os.path.join(PD, "opengl32sw.dll")])
total += saved
print("[2] opengl32sw         %6.1f MB" % (saved / 1024 / 1024))

# 3. 翻译（保留 zh/en）
saved = remove([
    os.path.join(PD, "translations"),
    os.path.join(INTERNAL, "translations"),
])
total += saved
print("[3] translations       %6.1f MB" % (saved / 1024 / 1024))

# 4. qml 目录（界面不用 QML）
saved = remove([
    os.path.join(PD, "qml"),
    os.path.join(INTERNAL, "qml"),
])
total += saved
print("[4] qml 目录            %6.1f MB" % (saved / 1024 / 1024))

# 5. 开发工具
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
print("[5] 开发工具            %6.1f MB" % (saved / 1024 / 1024))

# 6. 无关模块（注意：不删 Qt6Positioning、Qt6Quick、Qt6Qml、Qt6Network）
misc = []
KEEP_PREFIXES = (
    "Qt6WebEngine", "Qt6WebChannel", "Qt6Quick.dll", "Qt6Qml.dll",
    "Qt6Network", "Qt6Core", "Qt6Gui", "Qt6Widgets", "Qt6Positioning",
    "Qt6OpenGL", "Qt6Svg", "Qt6PrintSupport",
)
if os.path.isdir(PD):
    for f in os.listdir(PD):
        if not f.startswith("Qt6"):
            continue
        # 保留白名单
        if any(f.startswith(k.split(".")[0]) for k in KEEP_PREFIXES):
            continue
        # 删除这些
        if f.startswith(("Qt6Designer", "Qt6Pdf", "Qt6UiTools",
                         "Qt6Charts", "Qt6DataVisualization",
                         "Qt6Graphs", "Qt6Multimedia", "Qt6SpatialAudio",
                         "Qt63D", "Qt6Quick3D", "Qt6Bluetooth",
                         "Qt6Nfc", "Qt6Location", "Qt6Sensors",
                         "Qt6SerialPort", "Qt6SerialBus",
                         "Qt6RemoteObjects", "Qt6Scxml",
                         "Qt6StateMachine", "Qt6Test", "Qt6Help",
                         "Qt6Sql", "Qt6Xml", "Qt6VirtualKeyboard",
                         "Qt6Labs")):
            misc.append(os.path.join(PD, f))
# 视频编解码
if os.path.isdir(PD):
    for f in os.listdir(PD):
        if f.startswith(("avcodec", "avformat", "avutil",
                         "swresample", "swscale")):
            misc.append(os.path.join(PD, f))
saved = remove(misc)
total += saved
print("[6] 无关模块 (%d 项)    %6.1f MB" % (len(misc), saved / 1024 / 1024))

# 7. 无关 pyd
pyds = []
if os.path.isdir(PD):
    for f in os.listdir(PD):
        if not f.endswith(".pyd"):
            continue
        if f.startswith(("QtQuick", "QtQml", "QtDesigner", "QtCharts",
                         "QtDataVisualization", "QtGraphs",
                         "QtBluetooth", "QtNfc", "QtPositioning",
                         "QtLocation", "QtSensors", "QtSerialPort",
                         "QtSerialBus", "QtRemoteObjects", "QtScxml",
                         "QtStateMachine", "QtTest", "QtHelp",
                         "QtUiTools", "QtSql", "QtXml", "QtPdf",
                         "QtMultimedia", "QtSpatialAudio")):
            pyds.append(os.path.join(PD, f))
saved = remove(pyds)
total += saved
print("[7] 无关 pyd (%d 项)    %6.1f MB" % (len(pyds), saved / 1024 / 1024))

after = size_of(DIST)
print()
print("=" * 64)
print("精简后: %.1f MB  (释放 %.1f MB)"
      % (after / 1024 / 1024, total / 1024 / 1024))
print("=" * 64)

# ---- 关键检查 ----
print("\n关键文件:")
REQUIRED = [
    "Qt6WebEngineCore.dll", "Qt6WebChannel.dll", "Qt6Network.dll",
    "Qt6Quick.dll", "Qt6Qml.dll", "Qt6Core.dll", "Qt6Gui.dll",
    "Qt6Widgets.dll", "Qt6Positioning.dll",
    "resources/icudtl.dat",
    "resources/qtwebengine_resources.pak",
    "resources/v8_context_snapshot.bin",
]
all_ok = True
for f in REQUIRED:
    p = os.path.join(PD, f.replace("/", os.sep))
    ok = os.path.exists(p)
    if not ok:
        all_ok = False
    print("  %-42s %s" % (f, "OK" if ok else "缺失!"))

# 图标
print()
for f in ("feather_icon.ico",):
    for base in (DIST, INTERNAL):
        p = os.path.join(base, f)
        if os.path.exists(p):
            print("  图标: %s" % p)

print()
print("全部关键文件: %s" % ("OK" if all_ok else "有缺失!"))
