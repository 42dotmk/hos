#!/usr/bin/env python3
# Render splash.png (640x480, the size mklive's boot menu expects) from
# overlay/usr/share/hos/logo.txt so the boot menu and fastfetch match.
# Only the full-block cells are drawn, in the accent colour over a dim
# drop shadow, on hbg's fallback background. No PIL: raw PNG via zlib.
import struct, sys, zlib

W, H = 640, 480
BG, FG, DIM = (0x1A, 0x1B, 0x26), (0x7A, 0xA2, 0xF7), (0x3B, 0x42, 0x61)
CW, CH = 24, 40  # pixels per logo cell
SHADOW = (8, 8)  # drop shadow offset

rows = [
    l.rstrip("\n").replace("$1", "").replace("$2", "")
    for l in open("overlay/usr/share/hos/logo.txt", encoding="utf-8")
]
rows = [r for r in rows if "█" in r or "╚" in r]  # drop the text tagline
cols = max(len(r) for r in rows)
ox, oy = (W - cols * CW) // 2, (H - len(rows) * CH) // 2

px = bytearray(bytes(BG) * W * H)
def cell(x, y, dx, dy, c):
    for yy in range(oy + y * CH + dy, oy + (y + 1) * CH + dy):
        for xx in range(ox + x * CW + dx, ox + (x + 1) * CW + dx):
            i = (yy * W + xx) * 3
            px[i : i + 3] = bytes(c)

blocks = [(x, y) for y, r in enumerate(rows) for x, ch in enumerate(r) if ch == "█"]
for x, y in blocks:
    cell(x, y, *SHADOW, DIM)
for x, y in blocks:
    cell(x, y, 0, 0, FG)

raw = b"".join(b"\0" + bytes(px[y * W * 3 : (y + 1) * W * 3]) for y in range(H))
def chunk(t, b):
    return struct.pack(">I", len(b)) + t + b + struct.pack(">I", zlib.crc32(t + b) & 0xFFFFFFFF)
with open(sys.argv[1] if len(sys.argv) > 1 else "splash.png", "wb") as f:
    f.write(b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
