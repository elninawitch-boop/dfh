# -*- coding: utf-8 -*-
"""只清理回收站里 psd-tool 的构建产物，保留其它条目。

用法：
    python rb_purge_build.py --dry        只统计
    python rb_purge_build.py --limit 5    只处理 5 条（试跑）
    python rb_purge_build.py              全量
"""
import argparse
import os
import re
import struct
import subprocess

RB = os.path.join("E:\\$Recycle.Bin",
                  "S-1-5-21-958826740-2857449033-2112264982-1001")
PREFIX = "E:\\workbuddy-en\\111\\psd-tool"


def orig_path(i_path):
    try:
        b = open(i_path, "rb").read()
        txt = b[24:].decode("utf-16-le", "ignore")
    except Exception:
        return ""
    c = re.findall(r"[A-Za-z]:\\[^\x00-\x1f]{2,260}", txt)
    return max(c, key=len) if c else ""


def size_of(p):
    if os.path.isfile(p):
        try:
            return os.path.getsize(p)
        except Exception:
            return 0
    t = 0
    for dp, _, fn in os.walk(p):
        for f in fn:
            try:
                t += os.path.getsize(os.path.join(dp, f))
            except Exception:
                pass
    return t


def rm(p):
    """目录用 rd（快），文件用 os.remove。"""
    if os.path.isdir(p):
        parent, name = os.path.split(p)
        subprocess.run('rd /s /q "%s"' % name, shell=True, cwd=parent,
                       capture_output=True)
    elif os.path.isfile(p):
        try:
            os.chmod(p, 0o666)
        except Exception:
            pass
        try:
            os.remove(p)
        except Exception as e:
            print("   删除失败:", e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    targets = []
    for n in os.listdir(RB):
        if not n.startswith("$I"):
            continue
        ip = os.path.join(RB, n)
        op = orig_path(ip)
        if not op.startswith(PREFIX):
            continue
        rp = os.path.join(RB, "$R" + n[2:])
        targets.append((size_of(rp) if os.path.exists(rp) else 0, ip, rp))

    targets.sort(reverse=True)
    total = sum(t[0] for t in targets)
    print("命中 %d 条，合计 %.2f GB" % (len(targets), total / 1073741824))
    if a.dry:
        for s, ip, rp in targets[:8]:
            print("   %7.1f MB  %s" % (s / 1048576, os.path.basename(rp)))
        return

    todo = targets[:a.limit] if a.limit else targets
    done = 0
    for s, ip, rp in todo:
        if os.path.exists(rp):
            rm(rp)
        rm(ip)
        if not os.path.exists(rp) and not os.path.exists(ip):
            done += 1

    left = sum(size_of(rp) for _, _, rp in targets if os.path.exists(rp))
    print("已清 %d / %d 条" % (done, len(todo)))
    print("剩余占用 %.2f GB" % (left / 1073741824))


if __name__ == "__main__":
    main()
