# -*- coding: utf-8 -*-
"""审计回收站：按删除时间与来源路径统计，判断哪些是本次误删产生的。"""
import collections
import datetime
import os
import re
import struct
import sys

SID_DIRS = [
    r"C:\$Recycle.Bin\S-1-5-21-958826740-2857449033-2112264982-1001",
]


def parse_i(path):
    d = open(path, "rb").read()
    if len(d) < 24:
        return None
    size = struct.unpack("<q", d[8:16])[0]
    ft = struct.unpack("<q", d[16:24])[0]
    if ft <= 0:
        return None
    ts = datetime.datetime(1601, 1, 1) + datetime.timedelta(microseconds=ft // 10)
    ts = ts + datetime.timedelta(hours=8)      # FILETIME 是 UTC，转本地时间
    txt = d[24:].decode("utf-16-le", "ignore")
    # 从解码串里挑出最长的盘符路径（不同版本偏移不一样，用正则更稳）
    cands = re.findall(r"[A-Za-z]:\\[^\x00-\x1f]{2,260}", txt)
    name = max(cands, key=len) if cands else txt.split("\x00")[0]
    return ts, size, name


def main():
    for rb in SID_DIRS:
        if not os.path.isdir(rb):
            print("目录不存在:", rb)
            continue
        names = os.listdir(rb)
        i_files = [n for n in names if n.startswith("$I")]
        print("回收站:", rb)
        print("$I 元数据条目:", len(i_files))

        rows = []
        for n in i_files:
            try:
                r = parse_i(os.path.join(rb, n))
                if r:
                    rows.append(r)
            except Exception:
                pass
        print("成功解析:", len(rows))
        print()

        by_min = collections.Counter()
        size_min = collections.Counter()
        for ts, size, name in rows:
            k = ts.strftime("%m-%d %H:%M")
            by_min[k] += 1
            size_min[k] += size

        print("=== 按删除时间（分钟）===")
        for k in sorted(by_min, reverse=True)[:15]:
            print("  %s   %5d 个  %9.1f MB" % (k, by_min[k], size_min[k] / 1048576))

        print()
        print("=== 按来源顶层目录 ===")
        by_src = collections.Counter()
        sz_src = collections.Counter()
        for ts, size, name in rows:
            parts = name.split("\\")
            key = "\\".join(parts[:5]) if len(parts) >= 5 else name
            by_src[key] += 1
            sz_src[key] += size
        for k in sorted(by_src, key=lambda x: -sz_src[x])[:10]:
            print("  %5d 个  %9.1f MB   %s" % (by_src[k], sz_src[k] / 1048576, k))

        # 本次会话（今天 20:20 之后）产生的条目
        cut = datetime.datetime(2026, 11, 1, 20, 20)
        mine = [r for r in rows if r[0] >= cut]
        theirs = [r for r in rows if r[0] < cut]
        print()
        print("=== 分界：今天 20:20 ===")
        print("  20:20 之后（本次操作产生）: %5d 个  %8.1f MB"
              % (len(mine), sum(r[1] for r in mine) / 1048576))
        print("  20:20 之前（历史遗留）    : %5d 个  %8.1f MB"
              % (len(theirs), sum(r[1] for r in theirs) / 1048576))
        if theirs:
            print("  历史条目最早: %s   最晚: %s"
                  % (min(r[0] for r in theirs).strftime("%Y-%m-%d %H:%M"),
                     max(r[0] for r in theirs).strftime("%Y-%m-%d %H:%M")))

        # 实际还占着磁盘的 $R 数据
        r_names = [n for n in names if n.startswith("$R")]
        real = 0
        for n in r_names:
            p = os.path.join(rb, n)
            try:
                if os.path.isfile(p):
                    real += os.path.getsize(p)
                elif os.path.isdir(p):
                    for dp, dn, fn in os.walk(p):
                        for f in fn:
                            real += os.path.getsize(os.path.join(dp, f))
            except Exception:
                pass
        print("  回收站实际占用: %.1f MB（$R 数据文件）" % (real / 1048576))


if __name__ == "__main__":
    main()
