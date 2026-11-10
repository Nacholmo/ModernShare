#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Rasterise a TrueType font into the camera's 1-bit glyph format.

The OSD is 480x240 on a 4:3 panel, so one OSD pixel is 2/3 as wide as it is tall.
Glyphs are rendered large, squeezed to (XSCALE x natural width) and thresholded, so
they look normally proportioned on the LCD.

Camera glyph record: u16 advance, u16 line height, u16 stride, u16 bpp=1, u32 flags=0x80,
u32 palette, u32 data; data = u8 xoff, yoff, w, h then h rows of ceil(w/8) bytes, MSB left.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFont

SS = 16                 # supersampling factor
LINE_H, BASELINE = 28, 23   # stock: line 28 rows, baseline below row 22


class Face:
    def __init__(self, path, cap_rows=17, xscale=1.5, threshold=0.5, embolden=0.0):
        self.xscale, self.threshold = xscale, threshold
        probe = ImageFont.truetype(path, 1000)
        cap = -probe.getbbox("H", anchor="ls")[1]
        self.size = cap_rows * SS * 1000 / cap
        self.font = ImageFont.truetype(path, round(self.size))
        self.embolden = embolden

    def advance(self, ch):
        return self.font.getlength(ch) / SS * self.xscale

    def bitmap(self, ch, adv=None):
        """Returns (advance, xoff, yoff, 2-D bool array or None)."""
        natural = self.advance(ch)
        adv = round(natural) if adv is None else adv
        W, H = int(natural / self.xscale * SS) + 8 * SS, LINE_H * SS
        im = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(im)
        sw = round(self.embolden * SS)
        d.text((4 * SS, BASELINE * SS), ch, font=self.font, fill=255, anchor="ls",
               stroke_width=sw, stroke_fill=255)
        tw = round(W / SS * self.xscale)
        small = np.asarray(im.resize((tw, LINE_H), Image.BOX), dtype=float) / 255
        bits = small >= self.threshold
        left = round(4 * self.xscale + (adv - natural) / 2)   # where the pen origin lands
        ys, xs = np.nonzero(bits)
        if not len(xs):
            return adv, 0, 0, None
        x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
        return adv, int(x0 - left), int(y0), bits[y0:y1, x0:x1]


def pack(xoff, yoff, bits):
    h, w = bits.shape
    rows = np.packbits(bits, axis=1)
    return bytes([xoff, yoff, w, h]) + rows.tobytes()


def draw_text(canvas, x, y, text, face, advs=None):
    """Draw into a 2-D bool canvas; returns the pen x after the text."""
    for ch in text:
        adv, xo, yo, bits = face.bitmap(ch, None if advs is None else advs.get(ch))
        if bits is not None:
            h, w = bits.shape
            xs, ys = x + xo, y + yo
            x0, y0 = max(xs, 0), max(ys, 0)
            x1, y1 = min(xs + w, canvas.shape[1]), min(ys + h, canvas.shape[0])
            if x1 > x0 and y1 > y0:
                canvas[y0:y1, x0:x1] |= bits[y0 - ys:y1 - ys, x0 - xs:x1 - xs]
        x += adv
    return x
