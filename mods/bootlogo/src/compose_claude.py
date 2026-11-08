#!/usr/bin/env python3
"""Compose the 430x60 "Claude OS" startup banner from claude_os.png.

Usage: compose_claude.py STOCK_FW claude_os.png OUT.png

Writes an 8-bit indexed PNG that already uses the camera's UI palette, so
make_logo.py stores its indices unchanged.

Layout: flower + "Claude OS" wordmark on the left, the character's head on the
right, on white like the stock logo. The wordmark is limited to 4 colours: the
anti-aliased edges otherwise cost too many RLE bytes for the 6554-byte slot.
"""
import sys

import numpy as np
from PIL import Image

from make_logo import GFX_FILE, GFX_RAM, GFX_SIZE, PAL, srgb_to_lab

W, H = 430, 60
SRC_BG = np.array([252, 236, 222])
WHITE, DARK, ORANGE, GREY = 0x02, 0x04, 0x79, 0x83  # palette indices (252-255 are reserved: never use)
SPLIT = 330  # x where the wordmark area ends and the head area begins


def fit_h(im, box, h):
    c = im.crop(box)
    return c.resize((max(1, round(c.width * h / c.height)), h), Image.LANCZOS)


def main():
    fw, src_path, out_path = sys.argv[1:4]
    g = open(fw, "rb").read()[GFX_FILE:GFX_FILE + GFX_SIZE]
    P = np.frombuffer(g[PAL - GFX_RAM:PAL - GFX_RAM + 1024], np.uint8).reshape(256, 4)[:, :3]
    lab_pal = srgb_to_lab(P.astype(float))

    src = Image.open(src_path).convert("RGB")
    canvas = Image.new("RGB", (W, H), tuple(SRC_BG))
    flower = fit_h(src, (68, 265, 158, 342), 26)
    title = fit_h(src, (62, 342, 628, 462), 44)
    head = fit_h(src, (690, 110, 1075, 445), 60)
    x = 14
    canvas.paste(flower, (x, 4)); x += flower.width + 4
    canvas.paste(title, (x, 9))
    canvas.paste(head, (W - head.width - 10, 0))

    a = np.asarray(canvas, float)
    bg = np.abs(a - SRC_BG).sum(-1) < 24  # peach background and its faint rays
    lab = srgb_to_lab(a)

    def quant(region, allowed):
        L = np.full_like(lab_pal, 1e9)
        L[allowed] = lab_pal[allowed]
        d = ((region[..., None, :] - L) ** 2).sum(-1)
        return np.argmin(d, -1).astype(np.uint8)

    idx = np.empty((H, W), np.uint8)
    idx[:, :SPLIT] = quant(lab[:, :SPLIT], [WHITE, DARK, ORANGE, GREY])
    idx[:, SPLIT:] = quant(lab[:, SPLIT:], list(range(1, 252)))
    idx[bg] = WHITE

    out = Image.fromarray(idx, "P")
    out.putpalette(P.reshape(-1).tolist())
    out.save(out_path)


if __name__ == "__main__":
    main()
