# -*- coding: utf-8 -*-
"""
_make_icon.py —— 生成程序图标 app.ico（纯标准库，不依赖 Pillow）。

设计：深红圆角底 + 金色五角星（民国档案风格）。
输出：app.ico（含 16/24/32/48/64/128/256 七种尺寸；
      256 用 PNG 压缩存储，小尺寸用 32 位 BMP 存储，兼容各版本 Windows）。

用法：py _make_icon.py
"""
from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "app.ico"

BG = (142, 27, 34)       # 深红
GOLD = (212, 175, 55)    # 金
SIZES = (16, 24, 32, 48, 64, 128, 256)
SAMPLES = ((0.25, 0.25), (0.75, 0.25), (0.25, 0.75), (0.75, 0.75))


def star_points(size: float) -> list[tuple[float, float]]:
    """正立五角星顶点（外半径 0.40、内半径 0.16，按画布尺寸缩放）。"""
    cx = cy = size / 2.0
    r_out, r_in = size * 0.34, size * 0.14
    pts = []
    for i in range(10):
        r = r_out if i % 2 == 0 else r_in
        a = math.radians(-90 + i * 36)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def in_poly(x: float, y: float, poly: list[tuple[float, float]]) -> bool:
    """射线法判断点是否在多边形内。"""
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xin = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < xin:
                inside = not inside
    return inside


def in_rounded(x: float, y: float, size: float, inset: float) -> bool:
    """圆角方形（squircle）命中测试。"""
    r = size * 0.20
    lo, hi = inset, size - inset
    if x < lo or x > hi or y < lo or y > hi:
        return False
    cx = min(max(x, lo + r), hi - r)
    cy = min(max(y, lo + r), hi - r)
    if x == cx and y == cy:
        return True
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def render_rgba(size: int) -> bytes:
    """渲染一张 size×size 的 RGBA 位图（每像素 4 样本超采样抗锯齿）。"""
    star = star_points(size)
    rows = []
    for y in range(size):
        row = bytearray()
        for x in range(size):
            ar = ag = ab = aa = 0
            for sx, sy in SAMPLES:
                px, py = x + sx, y + sy
                if not in_rounded(px, py, size, 0.5):
                    continue
                aa += 255
                if in_poly(px, py, star):
                    ar, ag, ab = ar + GOLD[0], ag + GOLD[1], ab + GOLD[2]
                else:
                    ar, ag, ab = ar + BG[0], ag + BG[1], ab + BG[2]
            n = len(SAMPLES)
            if aa == 0:
                row += b"\x00\x00\x00\x00"
            else:
                hit = aa // 255
                row += bytes((ar // hit, ag // hit, ab // hit, aa // n))
        rows.append(b"\x00" + bytes(row))          # 每行前缀 filter=0
    return b"".join(rows)


def to_png(size: int, raw: bytes) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)   # 8bit RGBA
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def to_bmp(size: int, raw: bytes) -> bytes:
    """ICO 内嵌的 32 位 BMP：BITMAPINFOHEADER + 自下而上的 BGRA + AND 掩码。"""
    header = struct.pack("<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0,
                         size * size * 4, 0, 0, 0, 0)
    xor = bytearray()
    for y in range(size - 1, -1, -1):
        off = y * (size * 4 + 1) + 1
        line = raw[off:off + size * 4]
        for i in range(0, len(line), 4):           # RGBA → BGRA
            r, g, b, a = line[i:i + 4]
            xor += bytes((b, g, r, a))
    mask_row = ((size + 31) // 32) * 4             # 1bpp，行按 4 字节对齐
    return header + bytes(xor) + b"\x00" * (mask_row * size)


def build_ico() -> bytes:
    images = []
    for size in SIZES:
        raw = render_rgba(size)
        blob = to_png(size, raw) if size >= 256 else to_bmp(size, raw)
        images.append((size, blob))
        print(f"  {size:>3}×{size:<3} {'PNG' if size >= 256 else 'BMP'} {len(blob):>6} 字节")

    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries, data = b"", b""
    for size, blob in images:
        w = 0 if size >= 256 else size          # 256 在 ICO 里记作 0
        entries += struct.pack("<BBBBHHII", w, w, 0, 0, 1, 32, len(blob), offset)
        offset += len(blob)
        data += blob
    return header + entries + data


if __name__ == "__main__":
    print("生成 app.ico：")
    OUT.write_bytes(build_ico())
    print(f"完成：{OUT}（{OUT.stat().st_size} 字节）")
