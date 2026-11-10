#!/usr/bin/env python3
"""Recolour the camera UI by remapping the shared 256-colour palette.

Usage: make_theme.py IN_FW OUT_FW [preview_dir]

Two identical palette tables must change together (entries 1-251):
  * 0x141c00 (data section): loaded at boot (0x3b5dc) into the hardware OSD palette
    (0x175420). Menu fills/text and everything else on screen use it.
  * 0x1cb83c (graphics section): the palette every 8-bit image record points to. The
    blitter maps each entry to a hardware index by EXACT colour match, unmatched
    colours become transparent (v1 of this theme changed only this table: the boot
    image vanished except black/grey, and menus stayed blue).
Index 0 = transparent and 252-255 = system colours are never touched.

UI code also uses 32-bit colours (0x00BBGGRR) for menu fills and text. 0x42040 turns
each into a hardware palette index by converting it like a palette entry (R and B
rounded to 6 bits) and taking the first exact match, else 0 = transparent. Theme v2
left them stock: the menu background (navy 3d4875) matched nothing and the live view
showed through. UI_COLOURS lists every such colour that hits a recoloured entry; each
is rewritten to its entry's new colour. KEEP lists entries also used as immediate
fill components (mov r4..r7), which are left stock instead.

Theme "Claude dark": Kodak navy -> neutral charcoal, Kodak red / yellow / orange
gradients -> one warm accent, light blue -> light grey, green -> modern green.
Lightness is preserved so contrast and readability stay the same.
"""
import colorsys
import os
import struct
import sys

TABLES = (0x144C00 + 0x1CB83C - 0x1A0000,       # graphics palette (file offset)
          0x100200 + 0x141C00 - 0x130000)       # hardware palette source (file offset)
ACCENT_H = 15 / 360          # warm orange-coral
GREEN_H = 140 / 360
KEEP = {167}                 # e2d7d1: immediate fill colour at 0x8771c
EMBER = {247: (36,40,43), 248: (54,61,65), 249: (241,237,228),
         250: (242,187,96), 251: (196,189,177)}
BG,FOCUS,IVORY,AMBER,SECONDARY = EMBER.values()
EMBER_WORDS = {
    0x14d334: BG, 0x14d398: BG, 0xd0c74: BG, 0xd15c8: BG, 0xe6f00: BG,
    0x14d39c: BG, 0x14d358: BG, 0x14d350: IVORY, 0x14d32c: IVORY,
    0x14d324: AMBER, 0x6f9e4: AMBER, 0xdd2b8: AMBER,
    0xc9ac0: AMBER, 0xe0d64: AMBER, 0xea5d4: AMBER, 0xea5c4: AMBER,
}
# RAM addresses of UI colour words: data-section colour table, then code literal pools
UI_COLOURS = (0x14d324, 0x14d330, 0x14d334, 0x14d350, 0x14d358, 0x14d398, 0x14d39c,
              0x6f9e4, 0x73ccc, 0x73cd8, 0xc9ac0, 0xd0c74, 0xd15c8, 0xdd2b8, 0xe0d64,
              0xe6f00, 0xe6f04, 0xea5c4, 0xea5c8, 0xea5cc, 0xea5d4)


def ram_to_file(a):
    return a - 0x130000 + 0x100200 if a >= 0x130000 else a - 0x30000 + 0x200


def hw_colour(r, g, b, a):
    """The conversion 0x42040 / the palette loader apply (checked against a RAM dump)."""
    q = lambda x: (x + 1 if x <= 0x53 else x - 1 if x >= 0xac else x) >> 2
    return q(r) | (g << 8) | (q(b) << 16) | (((30 * (255 - a) + 255) // 510) << 24)


def remap(r, g, b):
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    deg = h * 360
    if s < 0.12 or l < 0.04 or l > 0.97:
        return r, g, b                                   # neutrals stay
    if 185 <= deg <= 265:                                # Kodak navy / blues -> charcoal
        h2, s2 = 235 / 360, 0.07
        l2 = 0.08 + 0.38 * l                             # sky-blue menu bg -> dark grey
    elif deg >= 320 or deg <= 12:                        # Kodak red -> accent
        h2, s2, l2 = ACCENT_H, min(1.0, s) * 0.78, l * 0.95 + 0.04
    elif 12 < deg <= 65:                                 # yellow / orange gradients -> accent tints
        h2, s2, l2 = ACCENT_H + (deg - 40) / 360 * 0.25, s * 0.82, l
    elif 90 <= deg <= 160:                               # status greens -> modern green
        h2, s2, l2 = GREEN_H, s * 0.75, l * 0.9
    else:
        return r, g, b
    rr, gg, bb = colorsys.hls_to_rgb(h2 % 1, max(0, min(1, l2)), max(0, min(1, s2)))
    return round(rr * 255), round(gg * 255), round(bb * 255)


def main():
    src, dst = sys.argv[1:3]
    d = bytearray(open(src, "rb").read())
    old = bytes(d[TABLES[0]:TABLES[0] + 1024])
    assert old[4:1008] == d[TABLES[1] + 4:TABLES[1] + 1008], "palette tables differ"
    new = bytearray(old)
    for i in range(1, 252):
        if i in KEEP:
            continue
        r, g, b, a = old[4 * i:4 * i + 4]
        new[4 * i:4 * i + 3] = bytes(remap(r, g, b))
    for o in TABLES:
        d[o + 4:o + 1008] = new[4:1008]
    first = {}
    for i in range(255, -1, -1):
        first[hw_colour(*old[4 * i:4 * i + 4])] = i
    for a in UI_COLOURS:
        o = ram_to_file(a)
        r, g, b, al = d[o:o + 4]
        i = first.get(hw_colour(r, g, b, al))
        assert al == 0 and i and 0 < i < 252, f"{a:#x}: {d[o:o+4].hex()} is not a palette colour"
        d[o:o + 3] = new[4 * i:4 * i + 3]
    for i,rgb in EMBER.items():
        new[4*i:4*i+3]=bytes(rgb)
        for o in TABLES:d[o+4*i:o+4*i+3]=bytes(rgb)
    for a,rgb in EMBER_WORDS.items():
        o=ram_to_file(a);d[o:o+3]=bytes(rgb)
    now = {}
    for i in range(255, -1, -1):
        now[hw_colour(*new[4 * i:4 * i + 4])] = i
    for a in UI_COLOURS:
        o = ram_to_file(a)
        assert now.get(hw_colour(*d[o:o + 4])), f"{a:#x} would be transparent"
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../tools"))
    import kodakfw
    kodakfw.fix(d)
    assert not kodakfw.check(d)
    open(dst, "wb").write(d)
    changed = sum(old[4 * i:4 * i + 3] != new[4 * i:4 * i + 3] for i in range(256))
    print(f"wrote {dst}: {changed} palette entries recoloured, {len(UI_COLOURS)} UI colours updated")


if __name__ == "__main__":
    main()
