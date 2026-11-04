# -*- coding: utf-8 -*-
"""清掉回收站里没有 $I 记录的孤儿数据文件（资源管理器看不见，无法还原）。

用法：python rb_purge_orphans.py [盘符]   默认 E
"""
import os
import subprocess
import sys

SID = "S-1-5-21-958826740-2857449033-2112264982-1001"
DRIVE = (sys.argv[1] if len(sys.argv) > 1 else "E").rstrip(":")
RB = os.path.join("%s:\\$Recycle.Bin" % DRIVE, SID)
TMP = os.path.join(RB, "_purge_tmp2")


def main():
    if os.path.isdir(TMP):
        subprocess.run('rd /s /q "_purge_tmp2"', shell=True, cwd=RB)
    os.makedirs(TMP, exist_ok=True)

    moved = 0
    for n in os.listdir(RB):
        if n.startswith("."):
            try:
                os.rename(os.path.join(RB, n), os.path.join(TMP, n))
                moved += 1
            except Exception:
                pass
    print("搬入 %d 项" % moved)

    r = subprocess.run('rd /s /q "_purge_tmp2"', shell=True, cwd=RB,
                       capture_output=True)
    print("rd 返回码 %d，临时目录还在: %s" % (r.returncode, os.path.isdir(TMP)))


if __name__ == "__main__":
    main()
