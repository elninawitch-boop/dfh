# -*- coding: utf-8 -*-
"""检查运行中窗口的实际图标（从窗口句柄抓取）"""
import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
shell32 = ctypes.windll.shell32

# 找 PSD 修复工具窗口
found = []


def cb(hwnd, lp):
    if not user32.IsWindowVisible(hwnd):
        return True
    n = user32.GetWindowTextLengthW(hwnd)
    if n == 0:
        return True
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    if "PSD" in buf.value:
        found.append((hwnd, buf.value))
    return True


WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows(WNDENUMPROC(cb), 0)

print("找到窗口:", found)
if not found:
    print("没有运行中的窗口")
    raise SystemExit

hwnd, title = found[0]

# WM_GETICON
WM_GETICON = 0x007F
ICON_SMALL = 0
ICON_BIG = 1
ICON_SMALL2 = 2

for name, kind in (("ICON_SMALL", ICON_SMALL),
                   ("ICON_BIG", ICON_BIG),
                   ("ICON_SMALL2", ICON_SMALL2)):
    hicon = user32.SendMessageW(hwnd, WM_GETICON, kind, 0)
    print("%-12s hIcon = %s" % (name, hicon))

# 也要试 GetClassLongPtr
GCLP_HICON = -14
GCLP_HICONSM = -34
cls_big = user32.GetClassLongPtrW(hwnd, GCLP_HICON)
cls_small = user32.GetClassLongPtrW(hwnd, GCLP_HICONSM)
print("类图标 BIG   =", cls_big)
print("类图标 SMALL =", cls_small)

# 提取图标存成图片
hicon = user32.SendMessageW(hwnd, WM_GETICON, ICON_BIG, 0)
if not hicon:
    hicon = cls_big
if not hicon:
    print("\n窗口没有设置图标！")
else:
    print("\n提取图标...")
    # 用 GetIconInfo + DrawIconEx 转成位图
    class ICONINFO(ctypes.Structure):
        _fields_ = [("fIcon", wintypes.BOOL),
                    ("xHotspot", wintypes.DWORD),
                    ("yHotspot", wintypes.DWORD),
                    ("hbmMask", wintypes.HBITMAP),
                    ("hbmColor", wintypes.HBITMAP)]

    from PIL import Image
    import struct

    ii = ICONINFO()
    if user32.GetIconInfo(hicon, ctypes.byref(ii)):
        # 从 hbmColor 读像素
        class BITMAP(ctypes.Structure):
            _fields_ = [("bmType", wintypes.LONG),
                        ("bmWidth", wintypes.LONG),
                        ("bmHeight", wintypes.LONG),
                        ("bmWidthBytes", wintypes.LONG),
                        ("bmPlanes", wintypes.WORD),
                        ("bmBitsPixel", wintypes.WORD),
                        ("bmBits", ctypes.c_void_p)]

        bm = BITMAP()
        gdi32.GetObjectW(ii.hbmColor, ctypes.sizeof(BITMAP), ctypes.byref(bm))
        w, h = bm.bmWidth, bm.bmHeight
        print("图标尺寸: %dx%d" % (w, h))

        hdc = user32.GetDC(0)
        mfc = gdi32.CreateCompatibleDC(hdc)
        gdi32.SelectObject(mfc, ii.hbmColor)

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [("biSize", wintypes.DWORD),
                        ("biWidth", wintypes.LONG),
                        ("biHeight", wintypes.LONG),
                        ("biPlanes", wintypes.WORD),
                        ("biBitCount", wintypes.WORD),
                        ("biCompression", wintypes.DWORD),
                        ("biSizeImage", wintypes.DWORD),
                        ("biXPelsPerMeter", wintypes.LONG),
                        ("biYPelsPerMeter", wintypes.LONG),
                        ("biClrUsed", wintypes.DWORD),
                        ("biClrImportant", wintypes.DWORD)]

        bi = BITMAPINFOHEADER()
        bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bi.biWidth = w
        bi.biHeight = -h
        bi.biPlanes = 1
        bi.biBitCount = 32
        bi.biCompression = 0

        buf = ctypes.create_string_buffer(w * h * 4)
        gdi32.GetDIBits(mfc, ii.hbmColor, 0, h, buf,
                        ctypes.byref(bi), 0)
        img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1)
        img = img.resize((w * 8, h * 8), Image.Resampling.NEAREST)
        img.save(r"C:\Users\123\1\window_icon_actual.png")
        print("已保存: window_icon_actual.png")

        gdi32.DeleteDC(mfc)
        user32.ReleaseDC(0, hdc)
