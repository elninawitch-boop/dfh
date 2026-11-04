# -*- coding: utf-8 -*-
"""截取指定窗口的截图，用于验证 GUI 外观"""
import sys
import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

# 找到标题匹配的窗口
target = sys.argv[1] if len(sys.argv) > 1 else "PSD"
out = sys.argv[2] if len(sys.argv) > 2 else r"C:\Users\123\1\gui_shot.png"

EnumWindows = user32.EnumWindows
EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

found = []


def cb(hwnd, lparam):
    if not user32.IsWindowVisible(hwnd):
        return True
    n = user32.GetWindowTextLengthW(hwnd)
    if n == 0:
        return True
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    title = buf.value
    if target in title:
        found.append((hwnd, title))
    return True


EnumWindows(EnumWindowsProc(cb), 0)
if not found:
    print("未找到窗口:", target)
    sys.exit(1)

hwnd, title = found[0]
print("窗口:", title, "hwnd=", hwnd)

# 置前
user32.SetForegroundWindow(hwnd)
user32.BringWindowToTop(hwnd)
import time
time.sleep(0.6)

rect = wintypes.RECT()
user32.GetWindowRect(hwnd, ctypes.byref(rect))
w = rect.right - rect.left
h = rect.bottom - rect.top
print("尺寸:", w, "x", h)

hdc = user32.GetWindowDC(hwnd)
mfc = gdi32.CreateCompatibleDC(hdc)
bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
gdi32.SelectObject(mfc, bmp)

# PW_RENDERFULLCONTENT = 2，可抓取 DirectComposition 内容
ok = user32.PrintWindow(hwnd, mfc, 2)
print("PrintWindow:", ok)

from PIL import Image
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

buf_len = w * h * 4
buf = ctypes.create_string_buffer(buf_len)
got = gdi32.GetDIBits(mfc, bmp, 0, h, buf, ctypes.byref(bi), 0)
print("GetDIBits 行数:", got)

img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1)
img.convert("RGB").save(out)
print("已保存:", out)

gdi32.DeleteObject(bmp)
gdi32.DeleteDC(mfc)
user32.ReleaseDC(hwnd, hdc)
