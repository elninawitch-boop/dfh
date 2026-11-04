#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
psd_repair.py —— AI 生成 PSD 的通用诊断 / 修复工具

针对 AI（Gemini 等）用自写编码器生成 PSD 时常犯的几类结构性错误：

  1. 图层数写成正数（规范要求有透明通道时写负数），导致 PS 走错误解析分支 → 爆栈
  2. 图层 bbox 没加上区域/画布原点偏移，整层被放成满画布，内存虚胖
  3. 文件尾部被截断（合并图数据不完整）
  4. 段落长度与实际数据不闭合（缺偶数对齐填充、多写附加块）
  5. 通道压缩标记与真实数据不一致（compression=2 的 zlib / RLE / RAW）
  6. 图层记录里缺 blend mode、多写或漏写 extra data

支持读入：RAW(0) / RLE PackBits(1) / ZIP+预测器(2) 三种通道压缩。
输出：一律用 RLE(1) 重写，兼容性最好、体积也小。

用法：
    python psd_repair.py 文件.psd                    # 诊断 + 修复，输出 *_FIXED.psd
    python psd_repair.py 文件.psd --check            # 只诊断，不写文件
    python psd_repair.py 文件.psd --no-trim          # 只修结构，不裁图层
    python psd_repair.py 文件.psd -o 输出.psd        # 指定输出路径
    python psd_repair.py 目录/ --check               # 批量诊断整个目录
    python psd_repair.py 目录/ --recursive           # 批量修复（递归）

依赖：numpy, pillow
"""

import argparse
import os
import struct
import sys
import zlib

import numpy as np
from PIL import Image

# ---------------------------------------------------------------- 常量

SIG = b"8BPS"
COMPRESSION_NAMES = {0: "RAW", 1: "RLE", 2: "ZIP", 3: "ZIP+预测器"}


# ---------------------------------------------------------------- 解压

def _unpackbits_rows(seg, w, h):
    """解 PackBits 行压缩数据 -> (h, w) uint8"""
    counts = np.frombuffer(seg[:h * 2], dtype=">u2").astype(np.int64)
    out = np.zeros((h, w), dtype=np.uint8)
    src = np.frombuffer(seg, dtype=np.uint8)
    total = len(src)
    p = h * 2
    for row in range(h):
        clen = int(counts[row])
        end = p + clen
        buf = np.zeros(w, dtype=np.uint8)
        o = 0
        while o < w and p < end and p < total:
            b = int(np.int8(src[p])); p += 1
            if 0 <= b <= 127:
                cnt = b + 1
                buf[o:o + cnt] = src[p:p + cnt]
                p += cnt
                o += cnt
            elif -127 <= b <= -1:
                cnt = 1 - b
                buf[o:o + cnt] = src[p]
                p += 1
                o += cnt
            else:      # -128: no-op
                pass
        out[row] = buf
        p = end
    return out


def _unzip_channel(body, w, h, has_predictor):
    """解 ZIP 压缩通道，返回 (h, w) uint8"""
    raw = zlib.decompress(body)
    if has_predictor:
        # 逐行做 delta 还原
        arr = np.frombuffer(raw, dtype=np.uint8)
        if arr.size != (w + 1) * h:
            # 有些实现不写预测器标记字节，退化为直接还原
            rowlen = w
            arr = arr.reshape(h, rowlen).astype(np.int32)
            arr = np.cumsum(arr, axis=1) & 0xFF
            return arr.astype(np.uint8)
    # 无预测器：直接 reshape
    if raw.__len__() != w * h:
        raise ValueError("ZIP 解压后大小 %d != %d" % (len(raw), w * h))
    return np.frombuffer(raw, dtype=np.uint8).reshape(h, w)


def decode_channel(body, comp, w, h):
    """把一段通道 body 解码成 (h, w) uint8"""
    if comp == 0:
        arr = np.frombuffer(body, dtype=np.uint8)
        if arr.size < w * h:
            arr = np.pad(arr, (0, w * h - arr.size))
        return arr[:w * h].reshape(h, w)
    if comp == 1:
        return _unpackbits_rows(body, w, h)
    if comp == 2:
        return _unzip_channel(body, w, h, False)
    if comp == 3:
        return _unzip_channel(body, w, h, True)
    raise ValueError("未知压缩标记 %d" % comp)


# ---------------------------------------------------------------- 读取

class PsdReader:
    def __init__(self, path):
        self.path = path
        with open(path, "rb") as f:
            self.data = f.read()
        self.n = len(self.data)
        self.problems = []

    def parse(self):
        d, n = self.data, self.n
        if d[:4] != SIG:
            raise ValueError("不是 PSD 文件（签名 %r）" % d[:4])

        self.version = struct.unpack(">H", d[4:6])[0]
        self.channels = struct.unpack(">H", d[12:14])[0]
        self.height = struct.unpack(">I", d[14:18])[0]
        self.width = struct.unpack(">I", d[18:22])[0]
        self.depth = struct.unpack(">H", d[22:24])[0]
        self.color_mode = struct.unpack(">H", d[24:26])[0]

        o = 26
        cml = struct.unpack(">I", d[o:o + 4])[0]
        self.color_mode_data = d[o + 4:o + 4 + cml]
        o += 4 + cml

        resl = struct.unpack(">I", d[o:o + 4])[0]
        self.image_resources = d[o + 4:o + 4 + resl]
        o += 4 + resl

        lm_len = struct.unpack(">I", d[o:o + 4])[0]
        lm_start = o
        self.lm_end = o + 4 + lm_len
        o += 4

        li_len = struct.unpack(">I", d[o:o + 4])[0]
        self.li_len = li_len
        self.li_end = o + 4 + li_len
        o += 4

        nraw = struct.unpack(">h", d[o:o + 2])[0]
        o += 2
        self.layer_count_raw = nraw
        self.layer_count = abs(nraw)
        if nraw > 0:
            self.problems.append(
                "图层数写作正数 %d（规范要求负数 -%d），PS 会走错误解析分支"
                % (nraw, abs(nraw)))

        layers = []
        for i in range(self.layer_count):
            top, left, bot, right = struct.unpack(">iiii", d[o:o + 16]); o += 16
            nch = struct.unpack(">H", d[o:o + 2])[0]; o += 2
            chans = []
            for _ in range(nch):
                cid, clen = struct.unpack(">hI", d[o:o + 6]); o += 6
                chans.append([cid, clen])

            blend_sig = d[o:o + 4]
            blend_key = d[o + 4:o + 8]
            o += 8
            if blend_sig != b"8BIM":
                self.problems.append("图层%d: 混合模式签名异常 %r" % (i, blend_sig))

            op, clip, flags = d[o], d[o + 1], d[o + 2]
            o += 4
            extra = struct.unpack(">I", d[o:o + 4])[0]; o += 4
            ex_end = o + extra
            ml = struct.unpack(">I", d[o:o + 4])[0]; o += 4 + ml
            bl = struct.unpack(">I", d[o:o + 4])[0]; o += 4 + bl
            pl = d[o]
            name = d[o + 1:o + 1 + pl].decode("ascii", "replace")
            o = ex_end

            layers.append({
                "i": i, "name": name,
                "left": left, "top": top, "right": right, "bottom": bot,
                "w": right - left, "h": bot - top,
                "chans": chans, "opacity": op,
                "clip": clip, "flags": flags,
                "blend": blend_key,
            })

        self.record_end = o

        # 通道像素
        for L in layers:
            w, h = L["w"], L["h"]
            if w <= 0 or h <= 0:
                self.problems.append(
                    "图层%d(%s): 尺寸异常 %dx%d" % (L["i"], L["name"], w, h))
                L["rgba"] = np.zeros((max(1, h), max(1, w), 4), np.uint8)
                continue
            buf = {}
            for c in L["chans"]:
                cid, clen = c[0], c[1]
                if o + 2 > n:
                    self.problems.append(
                        "图层%d(%s) 通道%d: 头部越过文件末尾，文件被截断"
                        % (L["i"], L["name"], cid))
                    c.append(0)
                    continue
                comp = struct.unpack(">H", d[o:o + 2])[0]
                o += 2
                body_len = clen - 2
                if o + body_len > n:
                    self.problems.append(
                        "图层%d(%s) 通道%d: 数据越过文件末尾（需 %d 字节，仅剩 %d），文件被截断"
                        % (L["i"], L["name"], cid, body_len, n - o))
                    body = d[o:]
                    o = n
                else:
                    body = d[o:o + body_len]
                    o += body_len
                c.append(comp)
                try:
                    buf[cid] = decode_channel(body, comp, w, h)
                except Exception as e:
                    self.problems.append(
                        "图层%d(%s) 通道%d: 解压失败（compression=%d）: %s"
                        % (L["i"], L["name"], cid, comp, e))
                    buf[cid] = np.zeros((h, w), np.uint8)
            rgba = np.zeros((h, w, 4), np.uint8)
            rgba[:, :, 0] = buf.get(0, np.zeros((h, w), np.uint8))
            rgba[:, :, 1] = buf.get(1, np.zeros((h, w), np.uint8))
            rgba[:, :, 2] = buf.get(2, np.zeros((h, w), np.uint8))
            rgba[:, :, 3] = buf.get(-1, np.full((h, w), 255, np.uint8))
            L["rgba"] = rgba

        self.channel_end = o

        # 段落闭合检查
        if o != self.li_end:
            diff = self.li_end - o
            if 0 <= diff <= 1 and all(b == 0 for b in d[o:self.li_end]):
                pass      # 合法偶数对齐
            else:
                self.problems.append(
                    "图层信息段未闭合：通道数据止于 %d，声明结束 %d（差 %d）"
                    % (o, self.li_end, diff))

        o = self.li_end
        gm_len = struct.unpack(">I", d[o:o + 4])[0]
        self.global_mask = d[o + 4:o + 4 + gm_len]
        o += 4 + gm_len

        self.after_mask = o
        if o != self.lm_end:
            diff = self.lm_end - o
            # 段尾可能有合法的附加信息块，尝试解析
            ok_extra = self._probe_extra_blocks(o)
            if not ok_extra:
                self.problems.append(
                    "图层与蒙版段未闭合：%d != %d（差 %d）"
                    % (o, self.lm_end, diff))

        # 合并图
        o = self.lm_end
        if o + 2 > n:
            self.problems.append("合并图区缺失，文件被截断")
            self.merged = None
            self.merged_comp = None
        else:
            self.merged_comp = struct.unpack(">H", d[o:o + 2])[0]
            o += 2
            self.merged_body = d[o:]
            expect = self.channels * self.width * self.height
            actual = len(self.merged_body)
            if self.merged_comp == 0 and actual != expect:
                self.problems.append(
                    "合并图数据不完整：有 %d 字节，需 %d 字节，缺 %d"
                    % (actual, expect, expect - actual))
            self.merged = None

        self.layers = layers
        # bbox 越界检查
        for L in layers:
            if (L["left"] < 0 or L["top"] < 0 or
                    L["right"] > self.width or L["bottom"] > self.height):
                self.problems.append(
                    "图层%d(%s): bbox 超出画布 (%d,%d)-(%d,%d) 画布 %dx%d"
                    % (L["i"], L["name"], L["left"], L["top"],
                       L["right"], L["bottom"], self.width, self.height))
        return self

    def _probe_extra_blocks(self, start):
        """检查从 start 到 lm_end 是否为合法的附加信息块序列"""
        d, p, end = self.data, start, self.lm_end
        while p + 12 <= end:
            sig = d[p:p + 4]
            key = d[p + 4:p + 8]
            ln = struct.unpack(">I", d[p + 8:p + 12])[0]
            if sig not in (b"8BIM", b"8B64"):
                return False
            p += 12 + ln + (ln & 1)
            if p > end:
                return False
            if p == end:
                return True
        return p == end


# ---------------------------------------------------------------- 修复

def trim_layers(layers, log=print):
    """把每个图层裁到 alpha 的非透明外接矩形"""
    before = after = 0
    for L in layers:
        before += L["w"] * L["h"]
        alpha = L["rgba"][:, :, 3]
        ys, xs = np.nonzero(alpha)
        if len(ys) == 0:
            L["crop"] = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
            L["new_left"], L["new_top"] = L["left"], L["top"]
            after += 1
            log("    %-24s 全透明 → 1x1 占位" % L["name"])
            continue
        y0, y1 = int(ys.min()), int(ys.max()) + 1
        x0, x1 = int(xs.min()), int(xs.max()) + 1
        L["crop"] = Image.fromarray(L["rgba"][y0:y1, x0:x1], "RGBA")
        L["new_left"] = L["left"] + x0
        L["new_top"] = L["top"] + y0
        after += (x1 - x0) * (y1 - y0)
        if (x1 - x0) != L["w"] or (y1 - y0) != L["h"]:
            log("    %-24s %4dx%-4d → %4dx%-4d  @ (%d,%d)"
                % (L["name"], L["w"], L["h"], x1 - x0, y1 - y0,
                   L["new_left"], L["new_top"]))
    return before, after


def rle_encode_channel(arr):
    """PackBits 行压缩，返回 (行长度表 bytes, 数据 bytes)"""
    h, w = arr.shape
    counts = []
    chunks = []
    for row in range(h):
        line = arr[row]
        out = bytearray()
        i = 0
        while i < w:
            # 找连续相同
            j = i + 1
            while j < w and line[j] == line[i] and (j - i) < 128:
                j += 1
            run = j - i
            if run >= 3:
                out.append((257 - run) & 0xFF)
                out.append(int(line[i]))
                i = j
            else:
                start = i
                while i < w and (i - start) < 128:
                    if i + 2 < w and line[i] == line[i + 1] == line[i + 2]:
                        break
                    i += 1
                cnt = i - start
                out.append(cnt - 1)
                out.extend(line[start:i].tobytes())
        counts.append(len(out))
        chunks.append(bytes(out))
    return struct.pack(">%dH" % h, *counts), b"".join(chunks)


def write_psd(path, width, height, layers, dpi=600,
              color_mode_data=b"", image_resources=None, global_mask=b""):
    """用规范格式写 PSD（负图层数 + RLE 压缩 + 完整合并图）"""
    with open(path, "wb") as f:
        f.write(SIG)
        f.write(struct.pack(">H", 1))
        f.write(b"\x00" * 6)
        f.write(struct.pack(">H", 4))
        f.write(struct.pack(">I", height))
        f.write(struct.pack(">I", width))
        f.write(struct.pack(">H", 8))
        f.write(struct.pack(">H", 3))

        f.write(struct.pack(">I", len(color_mode_data)))
        f.write(color_mode_data)

        # 分辨率资源，保留原有资源并替换 1005
        res_data = struct.pack(">IHHIHH", dpi << 16, 1, 2, dpi << 16, 1, 2)
        res_block = (b"8BIM" + struct.pack(">H", 1005) + b"\x00\x00" +
                     struct.pack(">I", len(res_data)) + res_data)
        if image_resources:
            keep = _strip_resource(image_resources, 1005)
            res_block = keep + res_block
        f.write(struct.pack(">I", len(res_block)))
        f.write(res_block)

        records = bytearray()
        chdata = bytearray()

        for L in layers:
            img = L["crop"]
            lw, lh = img.size
            left = L.get("new_left", L["left"])
            top = L.get("new_top", L["top"])

            records.extend(struct.pack(">iiii", top, left, top + lh, left + lw))
            records.extend(struct.pack(">H", 4))

            enc = []
            for ch in ("R", "G", "B", "A"):
                arr = np.array(img.getchannel(ch))
                table, data = rle_encode_channel(arr)
                enc.append(table + data)

            for cid, body in zip((0, 1, 2, -1), enc):
                records.extend(struct.pack(">hI", cid, len(body) + 2))

            records.extend(b"8BIM")
            blend = L.get("blend") or b"norm"
            if len(blend) != 4:
                blend = b"norm"
            records.extend(blend)
            records.extend(struct.pack(">BBBB", L["opacity"], L.get("clip", 0),
                                       L["flags"] & 0xFF, 0))

            nb = L["name"].encode("ascii", "replace")[:255]
            pad = (4 - ((1 + len(nb)) % 4)) % 4
            pname = struct.pack(">B", len(nb)) + nb + b"\x00" * pad
            extra = struct.pack(">II", 0, 0) + pname
            records.extend(struct.pack(">I", len(extra)))
            records.extend(extra)

            for body in enc:
                chdata.extend(struct.pack(">H", 1))
                chdata.extend(body)

        body = struct.pack(">h", -len(layers)) + records + chdata
        if len(body) % 2:
            body += b"\x00"
        sec = struct.pack(">I", len(body)) + body
        # 全局蒙版段
        gbody = struct.pack(">I", len(global_mask)) + global_mask
        sec_len = len(sec) + len(gbody)
        f.write(struct.pack(">I", sec_len))
        f.write(sec)
        f.write(gbody)

        # 合并图
        comp = composite(layers, width, height)
        f.write(struct.pack(">H", 0))
        for ch in ("R", "G", "B", "A"):
            f.write(comp.getchannel(ch).tobytes())
    return comp


def _strip_resource(res_bytes, res_id):
    """从图像资源块里移除指定 ID 的资源，其余原样保留"""
    out = bytearray()
    p = 0
    n = len(res_bytes)
    while p + 12 <= n:
        sig = res_bytes[p:p + 4]
        if sig not in (b"8BIM", b"8B64"):
            break
        rid = struct.unpack(">H", res_bytes[p + 4:p + 6])[0]
        name_len = res_bytes[p + 6]
        name_total = 2 + name_len
        name_total += name_total % 2
        size_pos = p + 6 + name_total
        if size_pos + 4 > n:
            break
        size = struct.unpack(">I", res_bytes[size_pos:size_pos + 4])[0]
        block_end = size_pos + 4 + size
        block_end += block_end % 2
        if block_end > n:
            break
        if rid != res_id:
            out.extend(res_bytes[p:block_end])
        p = block_end
    return bytes(out)


def composite(layers, width, height):
    """按可见性和不透明度合成预览图"""
    comp = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    for L in layers:
        if L["flags"] & 2:          # 隐藏层
            continue
        im = L["crop"].copy()
        if L["opacity"] < 255:
            im.putalpha(im.getchannel("A").point(
                lambda p: int(p * L["opacity"] / 255.0)))
        tmp = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        tmp.paste(im, (L.get("new_left", L["left"]),
                       L.get("new_top", L["top"])))
        comp = Image.alpha_composite(comp, tmp)
    return comp


# ---------------------------------------------------------------- 报告

def report(reader):
    print("=" * 72)
    print("文件: %s" % reader.path)
    size = reader.n
    print("大小: %d 字节 (%.2f MB)" % (size, size / 1024 / 1024))
    print("画布: %dx%d, %d 通道, %d 位, 色彩模式 %d"
          % (reader.width, reader.height, reader.channels,
             reader.depth, reader.color_mode))
    print("图层数: %d (原始值 %d, %s)"
          % (reader.layer_count, reader.layer_count_raw,
             "规范" if reader.layer_count_raw < 0 else "应为负数"))

    full = sum(1 for L in reader.layers
               if L["w"] == reader.width and L["h"] == reader.height)
    wasted = sum(1 for L in reader.layers
                 if L["w"] * L["h"] > 0 and
                 (np.count_nonzero(L["rgba"][:, :, 3]) /
                  float(L["w"] * L["h"])) < 0.5)
    print("满画布图层: %d / %d" % (full, len(reader.layers)))
    print()

    if reader.problems:
        print("发现 %d 处问题:" % len(reader.problems))
        for p in reader.problems:
            print("  !!", p)
    else:
        print("结构完全自洽，未发现问题。")
    print()
    return len(reader.problems)


# ---------------------------------------------------------------- 主流程

def repair_one(path, out=None, trim=True, check_only=False):
    reader = PsdReader(path).parse()
    nprob = report(reader)

    if check_only:
        return nprob, None

    layers = reader.layers
    if trim:
        print("裁剪图层到内容范围:")
        before, after = trim_layers(layers)
        if before:
            print("  总像素: %.1fM → %.1fM (省 %.1f%%)"
                  % (before / 1e6, after / 1e6,
                     (1 - after / float(before)) * 100))
    else:
        for L in layers:
            L["crop"] = Image.fromarray(L["rgba"], "RGBA")
            L["new_left"], L["new_top"] = L["left"], L["top"]
        print("保持原图层尺寸（未裁剪）")

    if out is None:
        base, ext = os.path.splitext(path)
        out = base + "_FIXED" + (ext or ".psd")

    print("\n写出: %s" % out)
    write_psd(out, reader.width, reader.height, layers,
              color_mode_data=reader.color_mode_data,
              image_resources=reader.image_resources,
              global_mask=reader.global_mask)

    # 复核
    print("复核输出文件:")
    chk = PsdReader(out).parse()
    if chk.problems:
        print("  !! 输出仍有 %d 处问题:" % len(chk.problems))
        for p in chk.problems:
            print("    ", p)
    else:
        print("  OK 结构自洽")
    print("  大小: %.2f MB" % (os.path.getsize(out) / 1024 / 1024))
    return nprob, out


def collect(paths, recursive):
    files = []
    for p in paths:
        if os.path.isdir(p):
            for root, _, names in os.walk(p):
                for nm in names:
                    if nm.lower().endswith(".psd"):
                        files.append(os.path.join(root, nm))
                if not recursive:
                    break
        elif os.path.isfile(p):
            files.append(p)
    return files


def main():
    ap = argparse.ArgumentParser(
        description="诊断并修复 AI 生成的 PSD 结构问题")
    ap.add_argument("paths", nargs="+", help="PSD 文件或目录")
    ap.add_argument("-o", "--out", help="输出路径（单文件时有效）")
    ap.add_argument("--check", action="store_true", help="只诊断，不修改")
    ap.add_argument("--no-trim", action="store_true",
                    help="不裁剪图层，只修结构")
    ap.add_argument("--recursive", action="store_true", help="递归处理子目录")
    args = ap.parse_args()

    files = collect(args.paths, args.recursive)
    if not files:
        print("没有找到 .psd 文件")
        return 1

    summary = []
    for i, f in enumerate(files, 1):
        print("\n[%d/%d] %s" % (i, len(files), f))
        out = args.out if (len(files) == 1 and args.out) else None
        try:
            n, o = repair_one(f, out=out, trim=not args.no_trim,
                              check_only=args.check)
            summary.append((f, n, "已修复 → %s" % o if o else "仅诊断"))
        except Exception as e:
            print("  !! 处理失败: %s" % e)
            summary.append((f, -1, "失败: %s" % e))

    print("\n" + "=" * 72)
    print("汇总:")
    for f, n, s in summary:
        print("  %-50s %s" % (os.path.basename(f), s))
    bad = sum(1 for _, n, _ in summary if n > 0)
    print("共 %d 个文件，%d 个存在结构问题。" % (len(summary), bad))
    return 0


if __name__ == "__main__":
    sys.exit(main())
