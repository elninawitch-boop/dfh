# -*- coding: utf-8 -*-
"""逐条核对：$I（记录）对应的 $R（数据）是否还在，实际占多少盘。

$I 只有几十字节，$R 才是真数据。$R 不存在 = 只剩一条历史记录，不占空间。
"""
import datetime
import os
import re
import struct

RB = r"C:\$Recycle.Bin\S-1-5-21-958826740-2857449033-2112264982-1001"


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
    return ts, size, (max(cands, key=len) if cands else "?")


def real_size(p):
    try:
        if os.path.isfile(p):
            return os.path.getsize(p)
        if os.path.isdir(p):
            t = 0
            for dp, _, fn in os.walk(p):
                for f in fn:
                    try:
                        t += os.path.getsize(os.path.join(dp, f))
                    except Exception:
                        pass
            return t
    except Exception:
        pass
    return 0


def main():
    names = os.listdir(RB)
    rows = []
    for n in names:
        if not n.startswith("$I"):
            continue
        try:
            r = parse_i(os.path.join(RB, n))
        except Exception:
            continue
        if not r:
            continue
        rpath = os.path.join(RB, "$R" + n[2:])
        exists = os.path.exists(rpath)
        rows.append((r[0], r[2], r[1], exists, real_size(rpath) if exists else 0))

    rows.sort()
    print("%-16s %-52s %10s %8s" % ("删除时间", "原始路径", "逻辑大小", "数据在?"))
    print("-" * 92)
    tot_log = tot_real = 0
    for ts, path, size, exists, real in rows:
        short = path if len(path) <= 50 else path[:24] + "…" + path[-24:]
        print("%-16s %-52s %8.1fMB %8s" % (
            ts.strftime("%Y-%m-%d %H:%M"), short, size / 1048576,
            ("是 %.1fMB" % (real / 1048576)) if exists else "否（仅记录）"))
        tot_log += size
        tot_real += real
    print("-" * 92)
    print("合计：逻辑 %.1f MB，实际占盘 %.1f MB" % (tot_log / 1048576, tot_real / 1048576))

    # 孤儿数据：有 $R 没有对应 $I（之前批量删除中断留下的）
    i_bases = {n[2:] for n in names if n.startswith("$I")}
    orphans = []
    for n in names:
        if not n.startswith("$R"):
            continue
        if n[2:] in i_bases:
            continue
        orphans.append((real_size(os.path.join(RB, n)), n))
    if orphans:
        print()
        print("孤儿数据（有文件无记录）: %d 项, 合计 %.1f MB"
              % (len(orphans), sum(s for s, _ in orphans) / 1048576))
        for s, n in sorted(orphans, reverse=True)[:8]:
            print("   %8.1f MB  %s" % (s / 1048576, n))
    else:
        print("\n无孤儿数据文件。")


if __name__ == "__main__":
    main()
