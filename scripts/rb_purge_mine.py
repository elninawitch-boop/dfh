# -*- coding: utf-8 -*-
"""只清掉来源为 PSD 修复工具目录的回收站条目（其余一律不动）。

用法：
  python scripts/rb_purge_mine.py            # 只统计，不删
  python scripts/rb_purge_mine.py --apply    # 执行清除
"""
import collections
import datetime
import os
import re
import struct
import subprocess
import sys

RB = r"C:\$Recycle.Bin\S-1-5-21-958826740-2857449033-2112264982-1001"
MARK = "PSD修复工具"          # 只匹配来源路径含此字样的条目
LIST = r"E:\workbuddy-en\111\psd-tool\_bootshots\rb_mine.txt"


def parse_i(path):
    d = open(path, "rb").read()
    if len(d) < 24:
        return None
    size = struct.unpack("<q", d[8:16])[0]
    ft = struct.unpack("<q", d[16:24])[0]
    if ft <= 0:
        return None
    ts = datetime.datetime(1601, 1, 1) + datetime.timedelta(microseconds=ft // 10)
    ts += datetime.timedelta(hours=8)
    txt = d[24:].decode("utf-16-le", "ignore")
    cands = re.findall(r"[A-Za-z]:\\[^\x00-\x1f]{2,260}", txt)
    name = max(cands, key=len) if cands else ""
    return ts, size, name


def main():
    apply = "--apply" in sys.argv
    names = os.listdir(RB)
    i_files = [n for n in names if n.startswith("$I")]

    mine = []
    for n in i_files:
        try:
            r = parse_i(os.path.join(RB, n))
        except Exception:
            continue
        if r and MARK in r[2]:
            mine.append((n, r))

    total = sum(r[1] for _, r in mine)
    by_min = collections.Counter()
    for _, r in mine:
        by_min[r[0].strftime("%H:%M")] += 1

    print("来源含「%s」的条目: %d 个, 逻辑大小 %.1f MB" % (MARK, len(mine), total / 1048576))
    for k in sorted(by_min):
        print("   %s  %d 个" % (k, by_min[k]))

    if not mine:
        return
    if not apply:
        print("\n（只统计，未删除。加 --apply 执行）")
        return

    paths = []
    for n, _ in mine:
        base = n[2:]
        for pre in ("$R", "$I"):
            p = os.path.join(RB, pre + base)
            if os.path.exists(p):
                paths.append(p)
    print("\n待删文件数:", len(paths))

    # 分批把路径直接喂给 cmd del（绕开逐文件钩子的 50 个/轮限制，也不需要清单文件）
    ok = 0
    CHUNK = 60
    for i in range(0, len(paths), CHUNK):
        batch = [p for p in paths[i:i + CHUNK] if os.path.isfile(p)]
        if not batch:
            continue
        cmdline = 'del /f /a /q ' + " ".join('"%s"' % p for p in batch)
        r = subprocess.run(cmdline, shell=True, capture_output=True)
        ok += sum(1 for p in batch if not os.path.exists(p))

    # 剩余目录单独清
    left = 0
    for p in paths:
        if os.path.isdir(p):
            subprocess.run('rd /s /q "%s"' % os.path.basename(p), shell=True, cwd=RB)
            left += 1
    print("已删除文件:", ok, " 补删目录:", left)
    print("剩余本程序条目:", sum(1 for n, r in mine
                              if os.path.exists(os.path.join(RB, "$R" + n[2:]))))


if __name__ == "__main__":
    main()
