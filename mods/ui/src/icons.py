#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Rasterise Material Design Icons (from Symbols Nerd Font) for the camera OSD.

Icons are rendered large, squeezed to the OSD pixel shape (a pixel is 2/3 as wide as
tall, so widths are multiplied by 1.5) and thresholded to a 1-bit mask. masks become
index images: fill colour + a 1-pixel dark outline so they stay readable on live view.
"""
import functools

import numpy as np
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

from pathlib import Path
NERD = str(Path(__file__).resolve().parents[3] / "assets/fonts/ModernShareMaterialIcons.ttf")
ASPECT = 1.5
SS = 12


@functools.lru_cache(None)
def _names():
    return {n: cp for cp, n in TTFont(NERD, lazy=True).getBestCmap().items()}


@functools.lru_cache(None)
def _font(px):
    return ImageFont.truetype(NERD, px)


def has(name):
    return "md-" + name in _names()


def mask(name, rows, threshold=0.45):
    """1-bit mask of icon `name`, `rows` tall (its em box), tightly cropped."""
    ch = chr(_names()["md-" + name])
    em = rows * SS
    f = _font(em)
    im = Image.new("L", (em * 3, em * 3), 0)
    ImageDraw.Draw(im).text((em * 1.5, em * 1.5), ch, font=f, fill=255, anchor="mm")
    box = im.getbbox()
    im = im.crop(box)
    w = max(1, round(im.width / SS * ASPECT))
    h = max(1, round(im.height / SS))
    a = np.asarray(im.resize((w, h), Image.BOX), dtype=float) / 255
    return a >= threshold


def dilate(m, r=1):
    out = m.copy()
    p = np.pad(m, r)
    h, w = m.shape
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out |= p[r + dy:r + dy + h, r + dx:r + dx + w]
    return out


def place(canvas, m, cx=None, cy=None):
    """OR mask m into bool canvas centred at (cx, cy) (default: canvas centre)."""
    H, W = canvas.shape
    h, w = m.shape
    x = round((W - w) / 2 if cx is None else cx - w / 2)
    y = round((H - h) / 2 if cy is None else cy - h / 2)
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, W), min(y + h, H)
    canvas[y0:y1, x0:x1] |= m[y0 - y:y1 - y, x0 - x:x1 - x]
    return canvas


def outlined(m, fill, edge):
    """Index image: fill where m, edge on the 1-px ring around it, else 0."""
    out = np.zeros(m.shape, np.uint8)
    out[dilate(m)] = edge
    out[m] = fill
    return out
