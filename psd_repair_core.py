#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
psd_repair_core.py —— PSD 结构诊断与修复引擎（可被 GUI / CLI 复用）

设计要点：
- 所有耗时步骤通过 progress 回调上报，GUI 可实时显示逐层进度
- 修复流程分阶段：解析 -> 解码各层 -> 诊断 -> 裁切 -> 写盘 -> 复核
- 任何单层失败不会中断整体流程，会记录为警告
"""

import os
import struct
import zlib

import numpy as np
from PIL import Image

SIG = b"8BPS"

# 问题严重程度
SEV_ERROR = "error"
SEV_WARN = "warn"


class Issue:
    """一条诊断问题"""

    def __init__(self, code, severity, title, detail=""):
        self.code = code
        self.severity = severity
        self.title = title
        self.detail = detail

    def __repr__(self):
        return "<Issue %s %s %s>" % (self.severity, self.code, self.title)


# --------------------------------------------------------------- 解压

def _unpackbits_rows(seg, w, h):
    counts = np.frombuffer(seg[:h * 2], dtype=">u2").astype(np.int64)
    out = np.zeros((h, w), dtype=np.uint8)
    src = np.frombuffer(seg, dtype=np.uint8)
    total = len(src)
    p = h * 2
    for row in range(h):
        clen = int(counts[row]) if row < len(counts) else 0
        end = min(p + clen, total)
        buf = np.zeros(w, dtype=np.uint8)
        o = 0
        while o < w and p < end:
            b = int(np.int8(src[p])); p += 1
            if 0 <= b <= 127:
                cnt = min(b + 1, w - o)
                buf[o:o + cnt] = src[p:p + cnt]
                p += cnt
                o += cnt
            elif -127 <= b <= -1:
                cnt = min(1 - b, w - o)
                buf[o:o + cnt] = src[p]
                p += 1
                o += cnt
        out[row] = buf
        p = end
    return out


def decode_channel(body, comp, w, h):
    """把通道 body 解码为 (h, w) uint8"""
    if comp == 0:
        arr = np.frombuffer(body, dtype=np.uint8)
        if arr.size < w * h:
            arr = np.pad(arr, (0, w * h - arr.size))
        return arr[:w * h].reshape(h, w)
    if comp == 1:
        return _unpackbits_rows(body, w, h)
    if comp == 2:
        raw = zlib.decompress(body)
        if len(raw) != w * h:
            raise ValueError("ZIP 解压后 %d != %d" % (len(raw), w * h))
        return np.frombuffer(raw, dtype=np.uint8).reshape(h, w)
    if comp == 3:
        # ZIP + 预测器：每行首字节为 predictor 标记，随后为差分值
        raw = zlib.decompress(body)
        stride = w + 1
        if len(raw) == stride * h:
            arr = np.frombuffer(raw, dtype=np.uint8).reshape(h, stride)
            data = arr[:, 1:].astype(np.int32)
            data = np.cumsum(data, axis=1) & 0xFF
            return data.astype(np.uint8)
        if len(raw) == w * h:
            data = np.frombuffer(raw, dtype=np.uint8).reshape(h, w).astype(np.int32)
            data = np.cumsum(data, axis=1) & 0xFF
            return data.astype(np.uint8)
        raise ValueError("ZIP 预测器数据长度异常 %d" % len(raw))
    raise ValueError("未知压缩标记 %d" % comp)


# --------------------------------------------------------------- 图层名解码

def _decode_name(raw):
    """Pascal 串是本地代码页编码的，中文 PSD 通常是 GBK。

    依次尝试常见编码，全部失败才退 latin-1（至少不丢字节）。
    """
    if not raw:
        return ""
    for enc in ("utf-8", "gbk", "big5", "shift_jis"):
        try:
            s = raw.decode(enc)
        except Exception:
            continue
        if "\ufffd" not in s:
            return s
    return raw.decode("latin-1", "replace")


def _find_luni(d, p, end):
    """在附加图层信息块里找 luni（Unicode 图层名，UTF-16BE）。

    块结构：签名(4) + 键(4) + 长度(4) + 数据(长度，奇数补一字节)
    luni 数据：字符数(4) + UTF-16BE 字符串
    """
    end = min(end, len(d))
    while p + 12 <= end:
        if d[p:p + 4] not in (b"8BIM", b"8B64"):
            break
        key = d[p + 4:p + 8]
        ln, = struct.unpack(">I", d[p + 8:p + 12])
        ds = p + 12
        if key == b"luni" and ds + 4 <= len(d):
            cnt, = struct.unpack(">I", d[ds:ds + 4])
            body = d[ds + 4: ds + 4 + cnt * 2]
            try:
                return body.decode("utf-16-be", "ignore").rstrip("\x00")
            except Exception:
                return ""
        p = ds + ln + (ln % 2)
    return ""


def _luni_block(name):
    """生成 luni 块，写回时用它保住中文名（Pascal 串只能放 ASCII）。"""
    if not name:
        return b""
    ub = name.encode("utf-16-be")
    return (b"8BIM" + b"luni" + struct.pack(">I", 4 + len(ub)) +
            struct.pack(">I", len(name)) + ub)


# --------------------------------------------------------------- 读取/诊断

class PsdProbe:
    """解析 PSD 头部与图层表，并给出问题清单"""

    def __init__(self, path):
        self.path = path
        self.issues = []
        self.layers = []
        self.complete = True
        with open(path, "rb") as f:
            self.data = f.read()
        self.size = len(self.data)

    def _add(self, code, sev, title, detail=""):
        self.issues.append(Issue(code, sev, title, detail))

    def parse(self, progress=None):
        d, n = self.data, self.size
        if d[:4] != SIG:
            raise ValueError("不是 PSD 文件")

        self.version, = struct.unpack(">H", d[4:6])
        self.channels, = struct.unpack(">H", d[12:14])
        self.height, = struct.unpack(">I", d[14:18])
        self.width, = struct.unpack(">I", d[18:22])
        self.depth, = struct.unpack(">H", d[22:24])
        self.color_mode, = struct.unpack(">H", d[24:26])

        o = 26
        cml, = struct.unpack(">I", d[o:o + 4])
        self.color_mode_data = d[o + 4:o + 4 + cml]
        o += 4 + cml

        if o + 4 > n:
            raise ValueError("文件在图像资源段就结束了，严重截断")
        resl, = struct.unpack(">I", d[o:o + 4])
        self.image_resources = d[o + 4:o + 4 + resl]
        o += 4 + resl

        if o + 4 > n:
            raise ValueError("文件缺少图层段")
        lm_len, = struct.unpack(">I", d[o:o + 4])
        self.lm_end = o + 4 + lm_len
        o += 4

        if o + 4 > n:
            raise ValueError("文件缺少图层信息长度字段")
        li_len, = struct.unpack(">I", d[o:o + 4])
        self.li_end = o + 4 + li_len
        o += 4

        if o + 2 > n:
            raise ValueError("文件缺少图层数字段")
        nraw, = struct.unpack(">h", d[o:o + 2])
        o += 2
        self.layer_count_raw = nraw
        self.layer_count = abs(nraw)
        if nraw > 0:
            self._add("layer_count_sign", SEV_ERROR,
                      "图层数写成正数 %d" % nraw,
                      "PSD 规范要求有透明通道时写负数（-%d）。"
                      "Photoshop 读到正数会走错误的解析分支，"
                      "是导致 PS 崩溃/爆栈的主要原因。" % abs(nraw))

        layers = []
        for i in range(self.layer_count):
            if o + 18 > n:
                self._add("truncated_record", SEV_ERROR,
                          "第 %d 层记录不完整" % i, "文件在此处被截断")
                self.complete = False
                break
            top, left, bot, right = struct.unpack(">iiii", d[o:o + 16]); o += 16
            nch, = struct.unpack(">H", d[o:o + 2]); o += 2
            chans = []
            for _ in range(nch):
                if o + 6 > n:
                    self.complete = False
                    break
                cid, clen = struct.unpack(">hI", d[o:o + 6]); o += 6
                chans.append([cid, clen])
            if o + 12 > n:
                self.complete = False
                break
            blend_sig = d[o:o + 4]
            blend_key = d[o + 4:o + 8]
            o += 8
            if blend_sig != b"8BIM":
                self._add("blend_sig", SEV_WARN,
                          "第 %d 层混合模式签名异常" % i,
                          "期望 8BIM，实际 %r" % blend_sig)
            op, clip, flags = d[o], d[o + 1], d[o + 2]
            o += 4
            extra, = struct.unpack(">I", d[o:o + 4]); o += 4
            ex_end = o + extra
            if o + 4 <= n:
                ml, = struct.unpack(">I", d[o:o + 4]); o += 4 + ml
            if o + 4 <= n:
                bl, = struct.unpack(">I", d[o:o + 4]); o += 4 + bl
            name = ""
            if o < n:
                pl = d[o]
                raw = d[o + 1:o + 1 + pl]
                name = _decode_name(raw)
                # 图层名有两份：Pascal 串（本地代码页）和 luni 块（UTF-16BE）。
                # 中文名只有 luni 是准的，优先用它。
                # 注意 Pascal 串按 4 字节对齐（Photoshop 的做法），
                # 个别工具按 2 字节，所以两种都试一次。
                uni = ""
                nlen = 1 + pl                       # 长度字节 + 名字
                for align in (4, 2):
                    p = o + nlen + ((-nlen) % align)   # 相对名字起点补齐
                    uni = _find_luni(d, p, ex_end)
                    if uni:
                        break
                if uni:
                    name = uni
            o = min(ex_end, n)
            layers.append({
                "i": i, "name": name or ("图层%d" % i),
                "left": left, "top": top, "right": right, "bottom": bot,
                "w": max(0, right - left), "h": max(0, bot - top),
                "chans": chans, "opacity": op, "clip": clip, "flags": flags,
                "blend": blend_key, "rgba": None, "decoded": False,
            })

        self.record_end = o
        self.layers = layers

        # 注：此处的 o 只是图层记录的末尾，通道数据还没读，
        # 所以不能拿它判断"段落闭合"。真正的闭合校验放在 decode_layers 里。

        # 图层尺寸检查
        for L in layers:
            if L["w"] <= 0 or L["h"] <= 0:
                self._add("bad_size", SEV_ERROR,
                          "图层「%s」尺寸异常 %dx%d" % (L["name"], L["w"], L["h"]))
            elif (L["left"] < 0 or L["top"] < 0 or
                  L["right"] > self.width or L["bottom"] > self.height):
                self._add("bbox_outside", SEV_WARN,
                          "图层「%s」超出画布范围" % L["name"],
                          "位置 (%d,%d)-(%d,%d)，画布 %dx%d。"
                          % (L["left"], L["top"], L["right"], L["bottom"],
                             self.width, self.height))

        # 满画布统计
        full = [L for L in layers
                if L["w"] == self.width and L["h"] == self.height]
        if len(full) > 1:
            self._add("full_canvas", SEV_WARN,
                      "有 %d 个图层是满画布尺寸" % len(full),
                      "每层约占 %.1f MB 内存。若内容不多，裁切后能大幅降低 PS 压力。"
                      % (self.width * self.height * 4 / 1024 / 1024))

        # 截断检查（合并图）
        # 合并图开头有 2 字节压缩标记：0=原始 / 1=RLE / 2,3=ZIP。
        # 不能一律按 channels*w*h 比字节数 —— Photoshop 默认存 RLE，
        # 压缩后远小于未压缩尺寸，那样比会把正常的 PS 文件全判成"被截断"。
        w, h = self.width, self.height
        ch = self.channels
        if self.lm_end + 2 > n:
            self._add("merged_missing", SEV_ERROR, "文件缺少合并图数据")
        else:
            comp, = struct.unpack(">H", d[self.lm_end:self.lm_end + 2])
            avail = n - (self.lm_end + 2)
            need = None
            if comp == 0:                       # 原始像素
                need = ch * w * h
            elif comp == 1:                     # RLE：行计数表 + 各行数据
                tbl = ch * h * 2
                if avail < tbl:
                    need = tbl
                else:
                    counts = struct.unpack(">%dH" % (ch * h),
                                           d[self.lm_end + 2:self.lm_end + 2 + tbl])
                    need = tbl + sum(counts)
            else:                               # ZIP：无法预估，只要求有数据
                need = 1
            if avail < need:
                self._add("merged_truncated", SEV_ERROR,
                          "合并图数据不完整（文件被截断）",
                          "压缩方式 %d，只有 %d 字节，需要 %d 字节，缺 %d 字节。"
                          % (comp, avail, need, need - avail))

        # 全局图层蒙版与合并图（读回以便原样写出）
        try:
            o = self.lm_end
            gm_len = struct.unpack(">I", d[o:o + 4])[0]
            self.global_mask = d[o + 4:o + 4 + gm_len]
        except Exception:
            self.global_mask = b""
        return self

    def decode_layers(self, progress=None):
        """解码所有图层像素，progress(i, total, name, status)"""
        d, n = self.data, self.size
        o = self.record_end
        total = len(self.layers)
        for idx, L in enumerate(self.layers):
            if progress:
                progress(idx, total, L["name"], "解码中")
            w, h = L["w"], L["h"]
            if w <= 0 or h <= 0:
                L["rgba"] = np.zeros((1, 1, 4), np.uint8)
                L["decoded"] = True
                continue
            buf = {}
            for c in L["chans"]:
                cid, clen = c[0], c[1]
                if o + 2 > n:
                    self.complete = False
                    self._add("channel_truncated", SEV_ERROR,
                              "图层「%s」通道数据缺失" % L["name"],
                              "文件在此处被截断")
                    break
                comp, = struct.unpack(">H", d[o:o + 2]); o += 2
                body_len = max(0, clen - 2)
                if o + body_len > n:
                    self._add("channel_truncated", SEV_ERROR,
                              "图层「%s」通道数据不完整" % L["name"],
                              "需要 %d 字节，实际只剩 %d 字节"
                              % (body_len, n - o))
                    body = d[o:]
                    o = n
                    self.complete = False
                else:
                    body = d[o:o + body_len]
                    o += body_len
                try:
                    buf[cid] = decode_channel(body, comp, w, h)
                except Exception as e:
                    self._add("decode_failed", SEV_WARN,
                              "图层「%s」通道解压失败" % L["name"], str(e))
                    buf[cid] = np.zeros((h, w), np.uint8)
            rgba = np.zeros((h, w, 4), np.uint8)
            for k, cid in enumerate((0, 1, 2, -1)):
                if cid in buf:
                    rgba[:, :, k] = buf[cid]
                elif cid == -1:
                    rgba[:, :, 3] = 255
            L["rgba"] = rgba
            L["decoded"] = True
        self.channel_end = o

        # 现在通道数据读完了，才做真正的段落闭合校验
        if o != self.li_end:
            diff = self.li_end - o
            if 0 <= diff <= 1 and all(b == 0 for b in self.data[o:self.li_end]):
                pass      # 合法偶数对齐填充
            else:
                self._add("section_not_closed", SEV_ERROR,
                          "图层信息段长度不闭合",
                          "通道数据止于 %d，声明结束于 %d，相差 %d 字节。"
                          % (o, self.li_end, diff))

        if progress:
            progress(total, total, "", "解码完成")


# --------------------------------------------------------------- 写盘

def rle_encode_channel(arr):
    h, w = arr.shape
    counts = []
    chunks = []
    for row in range(h):
        line = arr[row]
        out = bytearray()
        i = 0
        while i < w:
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


def _strip_resource(res_bytes, res_id):
    out = bytearray()
    p, n = 0, len(res_bytes)
    while p + 12 <= n:
        sig = res_bytes[p:p + 4]
        if sig not in (b"8BIM", b"8B64"):
            break
        rid, = struct.unpack(">H", res_bytes[p + 4:p + 6])
        name_len = res_bytes[p + 6]
        name_total = 2 + name_len
        name_total += name_total % 2
        size_pos = p + 6 + name_total
        if size_pos + 4 > n:
            break
        size, = struct.unpack(">I", res_bytes[size_pos:size_pos + 4])
        block_end = size_pos + 4 + size
        block_end += block_end % 2
        if block_end > n:
            break
        if rid != res_id:
            out.extend(res_bytes[p:block_end])
        p = block_end
    return bytes(out)


def write_psd(path, probe, layers, dpi=600, progress=None):
    """按规范重写 PSD：负图层数 + RLE + 完整合并图"""
    width, height = probe.width, probe.height
    nlayer = len(layers)
    with open(path, "wb") as f:
        f.write(SIG)
        f.write(struct.pack(">H", 1))
        f.write(b"\x00" * 6)
        f.write(struct.pack(">H", 4))
        f.write(struct.pack(">I", height))
        f.write(struct.pack(">I", width))
        f.write(struct.pack(">H", 8))
        f.write(struct.pack(">H", 3))

        cmd = probe.color_mode_data
        f.write(struct.pack(">I", len(cmd)))
        f.write(cmd)

        res_data = struct.pack(">IHHIHH", dpi << 16, 1, 2, dpi << 16, 1, 2)
        new_res = (b"8BIM" + struct.pack(">H", 1005) + b"\x00\x00" +
                   struct.pack(">I", len(res_data)) + res_data)
        keep = _strip_resource(probe.image_resources or b"", 1005)
        res_block = keep + new_res
        f.write(struct.pack(">I", len(res_block)))
        f.write(res_block)

        records = bytearray()
        chdata = bytearray()

        for idx, L in enumerate(layers):
            if progress:
                progress(idx, nlayer, L["name"], "写入中")
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
            records.extend(struct.pack(">BBBB", L["opacity"],
                                       L.get("clip", 0), L["flags"] & 0xFF, 0))

            # Pascal 串只能放 ASCII（超出的会变 ?），真正的中文名写进 luni 块，
            # 否则修复后的文件在 Photoshop 里名字会变成问号。
            lname = L.get("name") or ""
            nb = lname.encode("ascii", "replace")[:255]
            pad = (4 - ((1 + len(nb)) % 4)) % 4
            pname = struct.pack(">B", len(nb)) + nb + b"\x00" * pad
            extra = struct.pack(">II", 0, 0) + pname + _luni_block(lname)
            records.extend(struct.pack(">I", len(extra)))
            records.extend(extra)
            for body in enc:
                chdata.extend(struct.pack(">H", 1))
                chdata.extend(body)

        body = struct.pack(">h", -nlayer) + records + chdata
        if len(body) % 2:
            body += b"\x00"

        gm = probe.global_mask or b""
        sec = (struct.pack(">I", len(body)) + body +
               struct.pack(">I", len(gm)) + gm)
        f.write(struct.pack(">I", len(sec)))
        f.write(sec)

        if progress:
            progress(nlayer, nlayer, "", "合成预览")
        comp = composite(layers, width, height)
        f.write(struct.pack(">H", 0))
        for ch in ("R", "G", "B", "A"):
            f.write(comp.getchannel(ch).tobytes())
    return comp


def composite(layers, width, height):
    comp = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    for L in layers:
        if L["flags"] & 2:
            continue
        im = L["crop"].copy() if "crop" in L else Image.fromarray(L["rgba"], "RGBA")
        if L["opacity"] < 255:
            im.putalpha(im.getchannel("A").point(
                lambda p: int(p * L["opacity"] / 255.0)))
        tmp = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        tmp.paste(im, (L.get("new_left", L["left"]),
                       L.get("new_top", L["top"])))
        comp = Image.alpha_composite(comp, tmp)
    return comp


# --------------------------------------------------------------- 高层流程

def trim_layers(layers, progress=None):
    """裁到 alpha 外接矩形，progress(i, total, name, detail)"""
    total = len(layers)
    saved = 0
    for idx, L in enumerate(layers):
        before = L["w"] * L["h"]
        alpha = L["rgba"][:, :, 3]
        ys, xs = np.nonzero(alpha)
        if len(ys) == 0:
            L["crop"] = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
            L["new_left"], L["new_top"] = L["left"], L["top"]
            detail = "全透明，保留占位"
            saved += before - 1
        else:
            y0, y1 = int(ys.min()), int(ys.max()) + 1
            x0, x1 = int(xs.min()), int(xs.max()) + 1
            L["crop"] = Image.fromarray(L["rgba"][y0:y1, x0:x1], "RGBA")
            L["new_left"] = L["left"] + x0
            L["new_top"] = L["top"] + y0
            nw, nh = x1 - x0, y1 - y0
            saved += before - nw * nh
            if nw != L["w"] or nh != L["h"]:
                detail = "%dx%d → %dx%d" % (L["w"], L["h"], nw, nh)
            else:
                detail = "已是紧凑尺寸"
        if progress:
            progress(idx, total, L["name"], detail)
    if progress:
        progress(total, total, "", "裁切完成")
    return saved


def repair(path, out_path=None, trim=True,
           on_issue=None, on_stage=None, on_progress=None):
    """
    完整修复流程。

    on_stage(text)                      阶段提示
    on_issue(Issue)                     每发现一个问题
    on_progress(i, total, name, detail) 逐层进度
    """
    def stage(t):
        if on_stage:
            on_stage(t)

    stage("解析文件")
    probe = PsdProbe(path).parse()

    stage("解码图层")
    probe.decode_layers(progress=on_progress)

    # 补充：解码后统计真正“内容稀疏”的满画布层
    if trim:
        sparse = 0
        for L in probe.layers:
            if not L["decoded"] or L["w"] <= 0:
                continue
            area = L["w"] * L["h"]
            used = int(np.count_nonzero(L["rgba"][:, :, 3]))
            if area and used < area * 0.85:
                sparse += 1
        if sparse:
            probe._add("sparse_canvas", SEV_WARN,
                       "有 %d 个图层内容远小于画幅" % sparse,
                       "裁切到实际内容范围可显著减少 PS 内存占用。")

    if on_issue:
        for it in probe.issues:
            on_issue(it)

    layers = probe.layers
    if trim:
        stage("裁切图层")
        saved = trim_layers(layers, progress=on_progress)
    else:
        stage("准备图层")
        total = len(layers)
        for idx, L in enumerate(layers):
            L["crop"] = Image.fromarray(L["rgba"], "RGBA")
            L["new_left"], L["new_top"] = L["left"], L["top"]
            if on_progress:
                on_progress(idx, total, L["name"], "保持原尺寸")
        if on_progress:
            on_progress(total, total, "", "就绪")

    if out_path is None:
        base, ext = os.path.splitext(path)
        out_path = base + "_FIXED" + (ext or ".psd")

    stage("写入文件")
    write_psd(out_path, probe, layers, progress=on_progress)

    stage("复核")
    check = PsdProbe(out_path).parse()
    return probe, out_path, check
