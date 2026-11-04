# -*- coding: utf-8 -*-
"""审计回收站：每条记录的原始路径、删除时间、实际数据大小。"""
import datetime
import os
import re
import struct

RB = "C:\\$Recycle.Bin"
I = "$I"
R = "$R"


def parse_i(path):
    b = open(path, "rb").read()
    if len(b) < 24:
        return None
    size = struct.unpack("<q", b[8:16])[0]
    ft = struct.unpack("<q", b[16:24])[0]
    if ft <= 0:
        return None
    ts = (datetime.datetime(1601, 1, 1) +
          datetime.timedelta(microseconds=ft // 10) +
          datetime.timedelta(hours=8))
    txt = b[24:].decode("utf-16-le", "ignore")
    cands = re.findall(r"[A-Za-z]:\\[^\x00-\x1f]{2,260}", txt)
    return ts, size, (max(cands, key=len) if cands else "?")


def dir_size(p):
    if os.path.isfile(p):
        return os.path.getsize(p)
    t = 0
    for dp, _, fn in os.walk(p):
        for f in fn:
            try:
                t += os.path.getsize(os.path.join(dp, f))
            except Exception:
                pass
    return t


def main():
    entries = []
    orphans = []
    for sid in os.listdir(RB):
        d = os.path.join(RB, sid)
        if not os.path.isdir(d):
            continue
        try:
            names = os.listdir(d)
        except PermissionError:
            continue
        ibase = set()
        for n in names:
            if not n.startswith(I):
                continue
            ibase.add(n[2:])
            try:
                r = parse_i(os.path.join(d, n))
            except Exception:
                continue
            if not r:
                continue
            rp = os.path.join(d, R + n[2:])
            real = dir_size(rp) if os.path.exists(rp) else 0
            entries.append((r[0], r[2], r[1], real))
        for n in names:
            if n.startswith(R) and n[2:] not in ibase:
                p = os.path.join(d, n)
                orphans.append((dir_size(p), n))

    entries.sort(reverse=True)
    tot = sum(e[3] for e in entries)
    orph = sum(o[0] for o in orphans)

    print("有记录的条目 %d 个，数据合计 %.1f MB" % (len(entries), tot / 1048576))
    print("孤儿数据   %d 个，合计 %.1f MB" % (len(orphans), orph / 1048576))
    print("总计 %.2f GB" % ((tot + orph) / 1073741824))
    print()
    print("按来源目录归类：")
    buckets = {}
    for ts, path, size, real in entries:
        key = os.path.dirname(path)
        b = buckets.setdefault(key, [0, 0])
        b[0] += 1
        b[1] += real
    for k, (c, s) in sorted(buckets.items(), key=lambda x: -x[1][1])[:12]:
        print("  %6.1f MB  %3d 项  %s" % (s / 1048576, c, k[:80]))
    print()
    print("最大的 10 条：")
    for ts, path, size, real in entries[:10]:
        print("  %s  %8.1f MB  %s" % (ts.strftime("%m-%d %H:%M"),
                                      real / 1048576, path[:80]))


if __name__ == "__main__":
    main()
