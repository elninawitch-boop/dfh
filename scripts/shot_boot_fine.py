# -*- coding: utf-8 -*-
"""以 20ms 间隔抓开机动画前 1.2 秒，检查背景与图标是否同时出现。

Qt 的 grab() 本身要几十毫秒，所以同时记录每帧的真实时刻，
用真实时间而不是名义间隔来判断。
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
    "--high-dpi-support=1 --disable-features=NetworkService "
    "--disable-background-networking --no-pings --disable-sync"
)

from PySide6.QtCore import QTimer, Qt            # noqa: E402
from PySide6.QtWidgets import QApplication      # noqa: E402

import psd_repair_qt as app_mod                 # noqa: E402

OUT = os.path.join(HERE, "_bootshots")
INTERVAL = 20
LIMIT_MS = 1200


def main():
    os.makedirs(OUT, exist_ok=True)
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv[:1])
    win = app_mod.Win()

    shots = []
    t0 = [0.0]

    def tick():
        now = time.monotonic() * 1000
        if t0[0] == 0:
            t0[0] = now
        el = now - t0[0]
        if el > LIMIT_MS:
            compose(shots)
            app.quit()
            return
        pm = win.view.grab()
        p = os.path.join(OUT, "fine_%04d.png" % int(el))
        pm.save(p)
        shots.append((el, p))
        QTimer.singleShot(INTERVAL, tick)

    win.show()
    QTimer.singleShot(0, tick)
    app.exec()
    print("[fine] 共 %d 帧" % len(shots))


def compose(shots):
    from PIL import Image, ImageDraw, ImageFont
    # 只取前 16 帧，2 行 8 列
    pick = shots[:16]
    if not pick:
        return
    font = ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc", 15)
    ims = []
    for t, p in pick:
        im = Image.open(p).convert("RGB")
        im = im.resize((im.width // 6, im.height // 6), Image.LANCZOS)
        ims.append((t, im))
    w, h = ims[0][1].size
    cols, pad, lab = 8, 6, 18
    rows = (len(ims) + cols - 1) // cols
    out = Image.new("RGB", (cols * w + (cols + 1) * pad,
                            rows * (h + lab) + (rows + 1) * pad), (225, 229, 235))
    d = ImageDraw.Draw(out)
    for i, (t, im) in enumerate(ims):
        r, c = divmod(i, cols)
        x = pad + c * (w + pad)
        y = pad + r * (h + lab + pad)
        out.paste(im, (x, y))
        d.text((x + 2, y + h + 1), "%.0fms" % t, font=font, fill=(20, 26, 38))
    dst = os.path.join(OUT, "boot_fine.png")
    out.save(dst)
    print("composed ->", dst)
    print("[fine] 时间点: " + ", ".join("%.0f" % t for t, _ in pick))


if __name__ == "__main__":
    main()
