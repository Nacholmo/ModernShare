#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Generate ModernShare's Ember graphics from local stock and pinned font inputs.

Reskin only: every image keeps its size, every glyph keeps (or narrows) its advance,
so screen layouts and all code stay byte-identical. Changes are confined to the
graphics section: glyph records + glyph bitmaps, image data pointers + image streams.
"""
import hashlib
import json
import struct
import sys

import numpy as np

from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(HERE), str(ROOT/'tools'), str(ROOT/'mods/bootlogo/src')]
import design
from font import Face, pack, LINE_H
from gfx import Gfx, GFX_FILE, GFX_RAM, ID_TABLE
from make_logo import encode

NIMG = 246
IMG_LO, IMG_HI = 0x1CD409, 0x1E8C8E          # 8-bit stream area (ids 2..245 in stock order)
GLYPH_TABLE = GFX_RAM + 0x10                 # 256 record pointers, index = char code
FONT_LO, FONT_HI = 0x1AD738, 0x1AF0DB        # Latin glyph bitmaps
FONT_FILE = design.NOTO + "CondensedSemiBold.ttf"
FONT_CAP, FONT_XSCALE = 17, 1.3


def build_images(G, d, log):
    stock = {}
    for i, a in enumerate(G.ids(NIMG)):
        if a:
            r = G.rec(a)
            stock[i] = np.frombuffer(G.pixels(r)[0], np.uint8).reshape(r["h"], r["w"])
    new = design.build(stock, log)
    p = IMG_LO
    for i in sorted(stock):
        if i == 1 and 1 not in new:
            continue                         # its stream lives in the code zero run; untouched
        px = (new[i] if i in new else stock[i]).tobytes()
        s = encode(px) + b"\0"               # stock streams are followed by one pad byte
        assert p + len(s) <= IMG_HI, f"image data overflows at id {i}"
        o = p - GFX_RAM + GFX_FILE
        d[o:o + len(s)] = s
        ro = G.ids(NIMG)[i] - GFX_RAM + GFX_FILE
        struct.pack_into("<I", d, ro + 16, p)
        p += len(s)
    o = p - GFX_RAM + GFX_FILE
    d[o:IMG_HI - GFX_RAM + GFX_FILE] = bytes(IMG_HI - p)
    log(f"images: {len(new)} redrawn of {len(stock)}; {p - IMG_LO} / {IMG_HI - IMG_LO} bytes, {IMG_HI - p} free")
    return sorted(new), p


def build_font(G, d, spill, log):
    """Replace the Latin glyphs. Returns the end of any data spilled past FONT_HI."""
    f = Face(FONT_FILE, FONT_CAP, FONT_XSCALE)
    blobs, squeezed = {}, []
    for c in range(0x21, 0x100):
        a = G.u32(GLYPH_TABLE + 4 * c)
        if not a:
            continue
        ch = bytes([c]).decode("latin-1")
        r = G.rec(a)
        assert r["bpp"] == 1 and r["flags"] == 0x80
        face = f
        if f.advance(ch) > r["w"] + 0.6:     # never wider than stock: squeeze to its advance
            face = Face(FONT_FILE, FONT_CAP, FONT_XSCALE * r["w"] / f.advance(ch))
            squeezed.append(ch)
        adv, xo, yo, bits = face.bitmap(ch)
        adv = min(adv, r["w"])
        if bits is None:
            continue
        h, w = bits.shape
        xo = max(0, min(xo, max(0, adv - w)))
        assert yo + h <= r["h"] and w <= 255, (ch, yo, h)
        blobs[c] = (a, adv, pack(xo, yo, bits))
    # Only the bytes of the glyphs being replaced are reused; glyphs that are kept
    # (line feed, space, no-break space) stay where they are.
    free = []
    for c, (a, adv, blob) in blobs.items():
        r = G.rec(a)
        o = r["data"] - GFX_RAM
        w, h = G.g[o + 2], G.g[o + 3]
        free.append([r["data"], r["data"] + 4 + ((w + 7) // 8) * h + 1])   # + stock pad byte
    free.sort()
    merged = [free[0]]
    for lo, hi in free[1:]:
        assert lo >= merged[-1][1], "stock glyph bitmaps overlap"
        if lo == merged[-1][1]:
            merged[-1][1] = hi
        else:
            merged.append([lo, hi])
    assert merged[0][0] >= FONT_LO and merged[-1][1] <= FONT_HI + 1
    merged.append([spill, IMG_HI])           # then the space the smaller images freed
    spilled = 0
    for c, (a, adv, blob) in blobs.items():
        blob += b"\0"                         # every stock bitmap is followed by one zero byte
        k = next(k for k, (lo, hi) in enumerate(merged) if hi - lo >= len(blob))
        p = merged[k][0]
        merged[k][0] += len(blob)
        spilled += len(blob) if k == len(merged) - 1 else 0
        o = p - GFX_RAM + GFX_FILE
        d[o:o + len(blob)] = blob
        ro = a - GFX_RAM + GFX_FILE
        struct.pack_into("<HHH", d, ro, adv, G.rec(a)["h"], (adv + 7) // 8)
        struct.pack_into("<I", d, ro + 16, p)
    log(f"font: {len(blobs)} glyphs, {sum(len(b[2]) for b in blobs.values())} bytes "
        f"({spilled} spilled into freed image space), {len(squeezed)} squeezed: {''.join(squeezed)}")
    return len(blobs)


def apply(base, log=print):
    """Generate the Ember image/font layout from local vendor pixels and pinned fonts."""
    lock=json.loads((ROOT/'assets/fonts/manifest.json').read_text())
    for name, digest in lock['fonts'].items():
        if hashlib.sha256((ROOT/'assets/fonts'/name).read_bytes()).hexdigest()!=digest:
            raise ValueError('Pinned font changed: '+name)
    design.theme('ember')
    d=bytearray(base)
    images,end=build_images(Gfx(base),d,log)
    glyphs=build_font(Gfx(base),d,end,log)
    return d


def generated_spans(base):
    """File ranges regenerated by apply(); chooser arena is reserved for the recipe."""
    result=apply(base,lambda _:None);g=Gfx(result);spans=[]
    def add(a,n):spans.append((g.file_off(a),n))
    add(IMG_LO,0x1e6000-IMG_LO)
    add(0x1e6800,IMG_HI-0x1e6800)
    for i,p in enumerate(g.ids(NIMG)):
        if p and i!=1:add(p+16,4)
    for c in range(0x21,0x100):
        p=g.u32(GLYPH_TABLE+4*c)
        if not p:continue
        rec=g.rec(p);at=g.file_off(rec['data'])
        xo,yo,w,h=result[at:at+4]
        if not w or not h:continue
        add(p,6);add(p+16,4)
        add(rec['data'],4+((w+7)//8)*h+1)
    return spans
