#!/usr/bin/env python3
"""Generate placeholder icon files for the Tauri project."""
import struct
import zlib
import os

base = os.path.dirname(os.path.abspath(__file__))


def make_png(width: int, height: int) -> bytes:
    def chunk(name: bytes, data: bytes) -> bytes:
        c = name + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    signature = b"\x89PNG\r\n\x1a\n"
    # Color type 6 = RGBA (8 bits per channel)
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    ihdr = chunk(b"IHDR", ihdr_data)

    # Simple orange pixel rows with full alpha
    raw = b""
    for _ in range(height):
        raw += b"\x00" + b"\xff\x8c\x00\xff" * width

    idat = chunk(b"IDAT", zlib.compress(raw))
    iend = chunk(b"IEND", b"")
    return signature + ihdr + idat + iend


for name, w, h in [
    ("32x32.png", 32, 32),
    ("128x128.png", 128, 128),
    ("128x128@2x.png", 256, 256),
]:
    path = os.path.join(base, name)
    with open(path, "wb") as f:
        f.write(make_png(w, h))
    print(f"Created {name} ({w}x{h})")
