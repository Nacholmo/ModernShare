#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""ModernShare UI skin: what every image ID becomes.

Every image keeps its stock width and height, so no screen layout or code changes.
`build(G)` returns {id: 2-D uint8 index array}; IDs that are not listed keep their
stock pixels. Colours are indices into the shared palette (see NOTES "UI theme").
"""
import collections

import numpy as np
from PIL import Image, ImageDraw

import icons as I
from font import Face, draw_text

from pathlib import Path
NOTO = str(Path(__file__).resolve().parents[3] / "assets/fonts/NotoSans-")
WHITE, EDGE, BLACK = 2, 3, 4
TILE, ACCENT, GREEN, GREY = 6, 10, 8, 71

# Roles. "coral" (stage 1) is the default; theme("mono") switches to black and white.
# The mono greys are new palette entries that build_ui2.py writes (free slots).
G1, G2, G3, G4, G5 = 247, 248, 249, 250, 251
MONO_PALETTE = {G1: (18, 18, 20), G2: (40, 40, 44), G3: (72, 72, 78), G4: (124, 124, 130), G5: (190, 190, 196)}
EMBER_PALETTE = {G1: (36, 40, 43), G2: (54, 61, 65), G3: (241, 237, 228),
                 G4: (242, 187, 96), G5: (196, 189, 177)}
R = dict(name="coral", bar=ACCENT, arrow=ACCENT, tile=TILE, tile_edge=EDGE, tile_sel=ACCENT,
         glyph_sel=WHITE, check=ACCENT, check_fg=WHITE, tick=None, track=GREY, idle=GREY,
         play=ACCENT, chip=False)


def theme(name):
    global EDGE
    if name == "mono":
        EDGE = BLACK
        R.update(name="mono", bar=WHITE, arrow=WHITE, tile=G1, tile_edge=G3, tile_sel=WHITE,
                 glyph_sel=BLACK, check=WHITE, check_fg=BLACK, tick=G4, track=G3, idle=WHITE,
                 play=WHITE, chip=True)
    elif name == "ember":
        EDGE = BLACK
        R.update(name="ember", bar=G2, arrow=G5, tile=G1, tile_edge=G2, tile_sel=G4,
                 glyph_sel=G1, check=G4, check_fg=G1, tick=G4, track=G2, idle=WHITE,
                 play=G4, chip=False)
    else:
        assert name == "coral"
ASPECT = 1.5
SS = 8

BOLD = lambda cap: Face(NOTO + "CondensedBold.ttf", cap, 1.5)   # noqa: E731
_faces = {}


def face(cap):
    if cap not in _faces:
        _faces[cap] = BOLD(cap)
    return _faces[cap]


# ---------------------------------------------------------------- primitives
def shape(w, h, draw):
    """Supersampled 1-bit shape; draw(d, sx, sy) paints on a (w*SS, h*SS) canvas."""
    im = Image.new("L", (w * SS, h * SS), 0)
    draw(ImageDraw.Draw(im), SS, SS)
    return np.asarray(im.resize((w, h), Image.BOX), dtype=float) / 255 >= 0.5


def rrect(w, h, ry, x0=0, y0=0, x1=None, y1=None):
    """Rounded rectangle mask; ry = corner radius in rows (x radius is 1.5x)."""
    x1, y1 = w if x1 is None else x1, h if y1 is None else y1
    ry = min(ry, (y1 - y0) / 2)
    rx = min(ry * ASPECT, (x1 - x0) / 2)

    def draw(d, s, _):
        X0, Y0, X1, Y1 = x0 * s, y0 * s, x1 * s - 1, y1 * s - 1
        RX, RY = rx * s, ry * s
        if X1 - RX >= X0 + RX:
            d.rectangle((X0 + RX, Y0, X1 - RX, Y1), fill=255)
        if Y1 - RY >= Y0 + RY:
            d.rectangle((X0, Y0 + RY, X1, Y1 - RY), fill=255)
        for cx, cy in ((X0 + RX, Y0 + RY), (X1 - RX, Y0 + RY), (X0 + RX, Y1 - RY), (X1 - RX, Y1 - RY)):
            d.ellipse((cx - RX, cy - RY, cx + RX, cy + RY), fill=255)
    return shape(w, h, draw)


def poly(w, h, pts):
    return shape(w, h, lambda d, s, _: d.polygon([(x * s, y * s) for x, y in pts], fill=255))


def text_mask(w, h, parts):
    """parts: [(string, cap_rows)] set on one baseline, centred in w x h.

    Cap heights shrink together until the text leaves a 1-pixel border for its outline.
    """
    shrink = 0
    while True:
        big = np.zeros((40, 400), bool)
        x = 4
        for s, cap in parts:
            x = draw_text(big, x, 7, s, face(max(5, cap - shrink)))   # baseline on row 30
        ys, xs = np.nonzero(big)
        m = big[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        if (m.shape[1] <= w - 2 and m.shape[0] <= h - 2) or shrink > 8:
            return I.place(np.zeros((h, w), bool), m)
        shrink += 1


def paint(m, fill=WHITE, edge=-1):
    edge = EDGE if edge == -1 else edge
    return I.outlined(m, fill, edge) if edge is not None else np.where(m, fill, 0).astype(np.uint8)


def md(w, h, name, em=None, fill=WHITE, edge=-1, cx=None, cy=None):
    em = em or round(h * 1.25)        # the drawing fills about 80% of its em box
    m = I.mask(name, em)
    while m.shape[1] > w - 2 or m.shape[0] > h - 2:
        em -= 1
        m = I.mask(name, em)
    return paint(I.place(np.zeros((h, w), bool), m, cx, cy), fill, edge)


def dominant(a):
    c = collections.Counter(a[a > 0].tolist())
    return c.most_common(1)[0][0]


# ---------------------------------------------------------------- components
MENU = {1: "information", 2: "sd", 3: "power", 5: "cancel", 6: "circle_half_full",
        9: "music_note", 11: "calendar_clock", 12: "trash_can", 14: "email_fast",
        16: "camera_metering_center", 18: "heart", 19: "crop_free", 22: "translate",
        26: "magnify_plus", 27: "account_box", 30: "view_grid", 31: "printer",
        32: "content_copy", 33: "resize", 34: "lock", 35: "star", 37: "heart_off",
        38: "keyboard_return", 39: "timer_outline", 40: "wrench", 41: "camera_burst",
        42: "television", 46: "white_balance_sunny"}
STATUS = {76: "white_balance_sunny", 77: "white_balance_iridescent",
          79: "white_balance_incandescent", 106: "trash_can", 171: "flash_auto",
          174: "email_fast", 175: "heart", 176: "flash", 179: "flash_off", 180: "printer",
          181: "lock", 182: "eye", 88: "timer_sand"}
DIM = {202: "information", 205: "printer", 206: "printer", 207: "content_copy"}
ISO = {60: "100", 62: "200", 64: "400", 66: "80", 68: "800", 70: "1250", 72: "Auto"}
MP = {191: "1.2", 192: "2.1", 193: "2.2", 194: "3.1", 195: "4.4", 196: "5.0",
      197: "5.3", 198: "6.2", 199: "7.0"}
SELECTED = {122, 123, 124, 125, 128, 130, 132, 134, 136, 139, 141, 143, 145, 147, 148,
            151, 153, 155, 157, 159, 161, 163, 165}
BADGE_MD = {120: "image_multiple", 122: "image_multiple", 123: "play", 126: "play",
            131: "beach", 132: "beach", 133: "candle", 134: "candle",
            124: "wrench", 166: "wrench", 125: "share_variant", 167: "share_variant",
            168: "camera", 170: "video"}
ARROWS = {96: "l", 99: "r", 102: "l", 103: "r", 104: "d", 105: "u", 97: "d", 98: "u",
          116: "d", 117: "u", 118: "d", 119: "u"}


def arrow(w, h, d):
    m = 1.5
    e = 4 if w > 24 else 0.5
    pts = {"l": [(w - m - 3, 1), (w - m - 3, h - 1), (m + 2, h / 2)],
           "r": [(m + 3, 1), (m + 3, h - 1), (w - m - 2, h / 2)],
           "u": [(m + e, h - 2), (w - m - e, h - 2), (w / 2, 2)],
           "d": [(m + e, 2), (w - m - e, 2), (w / 2, h - 2)]}[d]
    return paint(poly(w, h, pts), R["arrow"])


def bar(w, h, inset, chip=False):
    """Selection pill. chip: keep a dark rounded cell at the left for the row's white icon."""
    if R["name"] == "ember":
        out = np.zeros((h, w), np.uint8)
        out[1:h-1, :] = R["bar"]
        out[4:h-4, 3:8] = G4
        return out
    out = paint(rrect(w, h, 99 if not R["chip"] else 9, 0, inset, w, h - inset), R["bar"], None)
    if chip and R["chip"]:
        out[rrect(w, h, 7, 5, inset + 2, 62, h - inset - 2)] = BLACK
    return out


def checkbox(w, h, on):
    box = rrect(w, h, 3, 3, 1, w - 3, h - 1)
    if on:
        out = paint(box, R["check"], None)
        tick = shape(w, h, lambda d, s, _: d.line(
            [(8.5 * s, 8.5 * s), (11.5 * s, 11.5 * s), (18.5 * s, 4.5 * s)], fill=255, width=int(2.2 * s)))
        out[tick & box] = R["check_fg"]
        return out
    inner = rrect(w, h, 2, 6, 3, w - 6, h - 3)
    return paint(box & ~inner, WHITE, None)


def tick(w, h, colour):
    m = shape(w, h, lambda d, s, _: d.line(
        [(7 * s, 14 * s), (14 * s, 21 * s), (29 * s, 6 * s)], fill=255, width=int(3.4 * s), joint="curve"))
    return paint(m, colour, None)


def brackets(w, h, colour):
    """Focus frame: four thin corner marks instead of two heavy square brackets."""
    arm_x, arm_y, t = 18, 12, 2
    m = np.zeros((h, w), bool)
    for sx in (0, 1):
        for sy in (0, 1):
            xs = slice(1, 1 + arm_x) if not sx else slice(w - 1 - arm_x, w - 1)
            ys = slice(1, 1 + arm_y) if not sy else slice(h - 1 - arm_y, h - 1)
            xt = slice(1, 1 + t + 1) if not sx else slice(w - 2 - t, w - 1)
            yt = slice(1, 1 + t) if not sy else slice(h - 1 - t, h - 1)
            m[yt, xs] = True
            m[ys, xt] = True
    return paint(m, colour)


def spinner(w, h, frame):
    """Busy indicator: a ring with a quarter arc that turns one step per frame."""
    ry = h / 2 - 5
    rx = ry * ASPECT
    while rx > w / 2 - 3:
        ry -= 1
        rx = ry * ASPECT
    cx, cy, tk = w / 2, h / 2, 5

    def ring(d, s, _, a0=None):
        box = ((cx - rx) * s, (cy - ry) * s, (cx + rx) * s, (cy + ry) * s)
        inner = ((cx - rx + tk * ASPECT) * s, (cy - ry + tk) * s, (cx + rx - tk * ASPECT) * s, (cy + ry - tk) * s)
        if a0 is None:
            d.ellipse(box, fill=255)
        else:
            d.pieslice(box, a0, a0 + 100, fill=255)
        d.ellipse(inner, fill=0)
    track = shape(w, h, ring)
    arc = shape(w, h, lambda d, s, _: ring(d, s, _, -90 + 90 * frame)) & track
    out = paint(track, R["track"])
    out[arc] = WHITE
    return out


def stock_glyph(a):
    """Pictogram of a stock oval badge: what is drawn inside the ring."""
    inside = np.zeros(a.shape, bool)
    for y in range(a.shape[0]):
        xs = np.nonzero(a[y] == WHITE)[0]          # the white oval, row by row
        if len(xs):
            inside[y, xs[0]:xs[-1] + 1] = True
    return inside & (a != WHITE)


def badge(a, i):
    """Flat rounded tile: dark with a white pictogram, accent when selected."""
    h, w = a.shape
    tile = rrect(w, h, 8, 2, 1, w - 2, h - 1)
    sel = i in SELECTED
    out = paint(tile, R["tile_sel"] if sel else R["tile"], EDGE if sel else R["tile_edge"])
    if i in BADGE_MD:
        g = I.place(np.zeros(a.shape, bool), I.mask(BADGE_MD[i], 25))
    else:
        g = stock_glyph(a)
    out[g & rrect(w, h, 6, 5, 3, w - 5, h - 3)] = R["glyph_sel"] if sel else WHITE
    return out


def transport(w, h, kind):
    """Review play/pause button with its four direction hints."""
    out = paint(rrect(w, h, 6, 6, 4, w - 6, h - 4), R["tile"], R["tile_edge"])
    for pts in ([(1, h / 2), (4, h / 2 - 3), (4, h / 2 + 3)], [(w - 1, h / 2), (w - 4, h / 2 - 3), (w - 4, h / 2 + 3)],
                [(w / 2, 0), (w / 2 - 4, 3), (w / 2 + 4, 3)], [(w / 2, h), (w / 2 - 4, h - 3), (w / 2 + 4, h - 3)]):
        out[poly(w, h, pts)] = GREY
    g = I.place(np.zeros((h, w), bool), I.mask(kind, 21))
    out[g] = R["play"]
    return out


# ---------------------------------------------------------------- the skin
def build(stock, log=print):
    """stock: {id: index array}. Returns the redrawn subset."""
    new = {}
    size = lambda i: (stock[i].shape[1], stock[i].shape[0])   # noqa: E731

    def icon_set(table, **kw):
        for i, name in table.items():
            if not I.has(name):
                log(f"  id {i}: no icon '{name}', stock kept")
                continue
            new[i] = md(*size(i), name, **kw)

    icon_set(MENU, em=23 if R["name"] == "ember" else 27,
             fill=G3 if R["name"] == "ember" else WHITE)
    icon_set(STATUS)
    for i, name in DIM.items():
        new[i] = md(*size(i), name, fill=dominant(stock[i]), edge=None)

    for i, d in ARROWS.items():
        new[i] = arrow(*size(i), d)
    new[85] = bar(*size(85), 1 if R["chip"] else 4, chip=True)
    new[91] = bar(*size(91), 1)
    new[94] = checkbox(*size(94), True)
    new[95] = checkbox(*size(95), False)
    new[90] = tick(*size(90), R["tick"] or dominant(stock[90]))
    new[53] = paint(rrect(*size(53), 99, 2, 1, 12, 8), ACCENT, EDGE)
    new[54] = paint(rrect(*size(54), 99, 2, 1, 12, 8), GREEN, EDGE)
    for i, c in ((47, R["idle"]), (48, GREEN), (49, GREEN), (50, GREEN), (112, R["idle"]), (113, GREEN)):
        new[i] = brackets(*size(i), c)
    for k, i in enumerate((215, 216, 217, 218)):
        new[i] = spinner(*size(i), k)
    for i in range(120, 171):
        new[i] = badge(stock[i], i)
    if R["name"] in ("mono", "ember"):
        new[84] = np.zeros(stock[84].shape, np.uint8)      # no disc behind unselected menu icons
    new[228] = transport(*size(228), "pause")
    new[229] = transport(*size(229), "play")

    # text-based status labels
    for i, v in ISO.items():
        for j, colour in ((i, WHITE), (i + 1, ACCENT)):
            w, h = size(j)
            m = np.zeros((h, w), bool)
            top = text_mask(w, 9, [("ISO", 7)])
            m[1:10] |= top
            m[11:h - 1] |= text_mask(w, h - 12, [(v, 11)])
            new[j] = paint(m, colour, EDGE)
    for i, v in MP.items():
        new[i] = paint(text_mask(*size(i), [(v, 14), (" MP", 9)]), WHITE, EDGE)
    for i, v in ((244, "2x"), (245, "4x")):
        new[i] = paint(text_mask(*size(i), [(v, 12)]), WHITE, EDGE)
    new[75] = paint(text_mask(*size(75), [("AWB", 12)]), WHITE, EDGE)
    new[21] = paint(text_mask(*size(21), [("ISO", 15)]), WHITE, EDGE)
    new[25] = paint(text_mask(*size(25), [("LT", 15)]), WHITE, EDGE)
    new[51] = paint(text_mask(*size(51), [("AE", 13)]), ACCENT, EDGE)
    new[52] = paint(text_mask(*size(52), [("AF", 13)]), ACCENT, EDGE)
    for i, v in ((200, "320"), (201, "640")):
        w, h = size(i)
        m = text_mask(48, h, [(v, 14)])
        full = np.zeros((h, w), bool)
        full[:, :48] = m
        I.place(full, I.mask("video", 17), cx=60)
        new[i] = paint(full, WHITE, EDGE)
    for i, v in ((183, "10"), (184, "2"), (185, "2x")):
        w, h = size(i)
        full = np.zeros((h, w), bool)
        if i == 185:
            full[:, :36] = text_mask(36, h, [(v, 13)])
            I.place(full, I.mask("timer_outline", 20), cx=51)
        else:
            I.place(full, I.mask("timer_outline", 20), cx=16)
            full[:, 30:] = text_mask(w - 30, h, [(v, 14)])
        new[i] = paint(full, WHITE, EDGE)

    for i, a in new.items():
        assert a.shape == stock[i].shape and a.dtype == np.uint8, i
        assert a.max() < 252, i
    return new
