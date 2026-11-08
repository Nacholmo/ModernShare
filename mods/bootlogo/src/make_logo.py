#!/usr/bin/env python3
"""Build a replacement for the "Kodak EasyShare system" startup logo.

Usage: make_logo.py STOCK_FW SOURCE_IMAGE OUTDIR [crop_top]

Graphics format (rec2, RAM 0x1a0000):
  record (20 bytes): u16 w, u16 h, u16 stride, u16 bpp, u32 flags, u32 palette, u32 data
  flags 1 = RLE. Stream of: byte c; L = c >> 1
      c odd  -> L literal bytes follow
      c even -> one byte follows, repeated L times
  Runs continue across rows; decoding stops after w*h pixels.
  All 8-bit images share the 256-colour RGBA palette at 0x1cb83c (index 0 = transparent).

The logo is image record 0x1cc35c (430x60, data 0x1d8127, 6554 bytes).
We keep its size and position, so the drawing code needs no changes.
"""
import struct
import sys

import numpy as np
from PIL import Image

GFX_FILE, GFX_RAM, GFX_SIZE = 0x144C00, 0x1A0000, 0x4FC00
REC = 0x1CC35C
PAL = 0x1CB83C


def decode(g, dat, n):
    p, out = dat - GFX_RAM, bytearray()
    while len(out) < n:
        c = g[p]; p += 1; L = c >> 1
        if c & 1:
            out += g[p:p + L]; p += L
        else:
            out += bytes([g[p]]) * L; p += 1
    return bytes(out[:n]), p - (dat - GFX_RAM)


def encode(px):
    out, i, n = bytearray(), 0, len(px)
    lit = bytearray()

    def flush():
        nonlocal lit
        while lit:
            chunk = lit[:127]; lit = lit[127:]
            out.append((len(chunk) << 1) | 1); out.extend(chunk)
    while i < n:
        j = i
        while j < n and j - i < 127 and px[j] == px[i]:
            j += 1
        run = j - i
        if run >= 3 or (run == 2 and not lit):
            flush()
            out += bytes([run << 1, px[i]])
        else:
            lit += px[i:j]
        i = j
    flush()
    return bytes(out)


def srgb_to_lab(rgb):
    c = rgb / 255.0
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ M.T / np.array([0.9505, 1.0, 1.089])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def main():
    fw, src, outdir = sys.argv[1:4]
    top = int(sys.argv[4]) if len(sys.argv) > 4 else 260
    d = open(fw, "rb").read()
    g = d[GFX_FILE:GFX_FILE + GFX_SIZE]
    w, h, stride, bpp, flags, pal, dat = struct.unpack_from("<HHHHIII", g, REC - GFX_RAM)
    assert (w, h, bpp, flags, pal) == (430, 60, 8, 1, PAL), (w, h, bpp, flags, hex(pal))
    old_px, old_len = decode(g, dat, w * h)

    P = np.frombuffer(g[PAL - GFX_RAM:PAL - GFX_RAM + 1024], np.uint8).reshape(256, 4)[:, :3].astype(float)
    lab_pal = srgb_to_lab(P)
    lab_pal[0] = 1e9  # never use the transparent index
    lab_pal[252:] = 1e9  # 252-255 are never used by stock art and show wrong on the LCD

    im = Image.open(src)
    if im.mode == "P" and im.size == (w, h):
        # already in camera palette indices (from compose_*.py)
        px = im.tobytes()
        assert 0 not in px and max(px) < 252, "index 0 is transparent, 252-255 are reserved"
    else:
        im = im.convert("RGB")
        W = im.width
        ch = round(W * h / w)
        im = im.crop((0, top, W, top + ch)).resize((w, h), Image.LANCZOS)
        lab = srgb_to_lab(np.asarray(im, float)).reshape(-1, 1, 3)
        idx = np.argmin(((lab - lab_pal[None]) ** 2).sum(-1), axis=1).astype(np.uint8)
        px = idx.tobytes()

    enc = encode(px)
    # verify by decoding from a scratch buffer
    chk, used = decode(enc + b"\0" * 4, GFX_RAM, w * h)
    assert chk == px and used == len(enc), "encoder round-trip failed"
    print(f"logo {w}x{h}: stock data {old_len} bytes at {dat:#x}, new data {len(enc)} bytes")
    if len(enc) > old_len:
        sys.exit("new image does not fit in the old slot")

    new = enc + g[dat - GFX_RAM + len(enc):dat - GFX_RAM + old_len]  # keep stock tail bytes (unused)
    old = g[dat - GFX_RAM:dat - GFX_RAM + old_len]
    open(f"{outdir}/patch.txt", "w").write(f"{dat:x}:{old.hex()}:{new.hex()}\n")
    prev = Image.new("RGB", (w, h))
    prev.putdata([tuple(int(v) for v in P[i]) for i in px])
    prev.save(f"{outdir}/preview.png")
    prev.resize((w * 2, h * 2), Image.NEAREST).save(f"{outdir}/preview_2x.png")
    print(f"wrote {outdir}/patch.txt and preview.png")


if __name__ == "__main__":
    main()
