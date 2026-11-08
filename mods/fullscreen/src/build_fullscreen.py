#!/usr/bin/env python3
"""Full-screen boot image for Kodak C713/CD703 fw 1.30.

Usage: build_fullscreen.py BASE_FW IMAGE OUT_FW [preview.png]
(needs hook.bin / entry.bin assembled from hook.s / entry.s in this folder)

How it works (see NOTES.md "Graphics" / "Full-screen boot image"):
  * Boot screen = screen struct 0x15eedc (id 0x73): u32 0x402, u16 id, u16 count,
    ptr widget list, ptr handler. Stock list: 2 text widgets, logo (id 93 at 20,10),
    Share (id 92 at 170,90).
  * Images decode whole into a buffer at 0x18fad8 below the main stack, so one image
    must not decode to more than the stock logo (25800 px): 5 tiles of 480x48.
  * New image ids 246..250: the id table (0x1ccf50) is followed directly by image
    data, so the first data block (225 bytes) moves to the code zero run and the
    table grows into its place; the registered count (mov_s r1,0xf6 x2) -> 0xfb.
  * Space: the language section is NOT resident in RAM. The selected language block
    is copied from flash into a 0xba00-byte buffer at 0x183330; English uses only
    0x5c00 of it. We build "English + CLOS magic + tile streams" (<= 0xba00) in the
    flash space of language 17 (the 47 KB block) and point English (0) and 17 at it.
    The tile data then sits in RAM at 0x188f34+ whenever English is loaded.
  * Guard hook at 0x789f8 (UI DrawImage): tile ids draw nothing unless the magic is
    present, so other languages get a plain boot screen instead of garbage/hangs.
  * Widgets/list/records/moved block live in the unused code zero run 0x125420.
"""
import importlib.util
import os
import struct
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "../../.."))
sys.path.insert(0, os.path.join(ROOT, "mods/bootlogo/src"))
import make_logo as m  # noqa: E402

spec = importlib.util.spec_from_file_location("kodakfw", os.path.join(ROOT, "tools/kodakfw.py"))
kfw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kfw)

SW, SH, TH = 480, 240, 48
NT = SH // TH
PAL = 0x1CB83C
TABLE, NIDS = 0x1CCF50, 246
COUNT_IMMS = (0x90390, 0x90398)           # mov_s r1,0xf6
LANG_TAB = 0x14FCA4                        # 19 u32 offsets (from file 0x194800), 19 u32 sizes
REC3_FILE = 0x194800
LANG_BUF, LANG_MAX = 0x183330, 0xBA00
ENGLISH, VICTIM = 0, 17
MAGIC = b"CLOS"
SCREEN = 0x15EEDC
W_TEXT1, W_TEXT2, W_LOGO, W_SHARE = 0x15EE58, 0x15EE78, 0x15EE94, 0x15EEB0
ZRUN, ZRUN_LEN = 0x125420, 0x8D0
HOOK, ENTRY = 0x12FF00, 0x789F8
FLATTEN = float(os.environ.get("FLATTEN", "8"))   # Lab distance; 0 = off
FLATTEN_N = int(os.environ.get("FLATTEN_N", "1"))  # how many dominant colours to snap to


class FW:
    def __init__(self, path):
        self.d = bytearray(open(path, "rb").read())

    def off(self, a):
        return kfw.ram_to_file(self.d, a)

    def get(self, a, n):
        o = self.off(a)
        return bytes(self.d[o:o + n])

    def put(self, a, b, expect=None):
        o = self.off(a)
        if expect is not None:
            assert self.d[o:o + len(b)] == expect, f"unexpected bytes at {a:#x}: {self.d[o:o+len(b)].hex()}"
        self.d[o:o + len(b)] = b

    def u32(self, a):
        return struct.unpack("<I", self.get(a, 4))[0]


def decode_at(get, dat, n):
    out, a = bytearray(), dat
    while len(out) < n:
        c = get(a, 1)[0]; a += 1; L = c >> 1
        if c & 1:
            out += get(a, L); a += L
        else:
            out += get(a, 1) * L; a += 1
    return bytes(out[:n]), a - dat


def quantize(path, fw):
    g = fw.get(0x1A0000, 0x4FC00)
    P = np.frombuffer(g[PAL - 0x1A0000:PAL - 0x1A0000 + 1024], np.uint8).reshape(256, 4)[:, :3]
    lp = m.srgb_to_lab(P.astype(float))
    lp[0] = 1e9          # transparent
    lp[252:] = 1e9       # reserved, render wrong on the LCD
    im = np.asarray(Image.open(path).convert("RGB").resize((SW, SH), Image.LANCZOS))
    lab = m.srgb_to_lab(im.astype(float))
    if FLATTEN:
        # pull near-background pixels onto the most common colour: subtle gradients
        # otherwise turn into many palette steps and cost a lot of RLE bytes
        # (FLATTEN_N > 1: also the next most common, clearly different colours, e.g. rays)
        cols, counts = np.unique(im.reshape(-1, 3) // 4 * 4, axis=0, return_counts=True)
        cl = m.srgb_to_lab(cols.astype(float))
        bgs = []
        for k in np.argsort(-counts):
            if len(bgs) == FLATTEN_N:
                break
            if all(np.sqrt(((cl[k] - b) ** 2).sum()) >= 2 * FLATTEN for b in bgs):
                bgs.append(cl[k])
        bgs = np.array(bgs)
        dist = np.sqrt(((lab[..., None, :] - bgs) ** 2).sum(-1))       # H x W x N
        near = dist.argmin(-1)
        hit = dist.min(-1) < FLATTEN
        lab[hit] = bgs[near[hit]]
    idx = np.empty((SH, SW), np.uint8)
    for r in range(0, SH, 16):
        blk = lab[r:r + 16].reshape(-1, 1, 3)
        idx[r:r + 16] = np.argmin(((blk - lp[None]) ** 2).sum(-1), 1).reshape(-1, SW)
    return idx, P


def main():
    base, img, out = sys.argv[1:4]
    fw = FW(base)
    old = FW(base)
    assert not kfw.check(fw.d), "base image does not verify"
    hook = open(os.path.join(HERE, "hook.bin"), "rb").read()
    entry = open(os.path.join(HERE, "entry.bin"), "rb").read()

    # --- sanity: stock structures are what we expect ----------------------------------
    assert fw.get(SCREEN, 16) == struct.pack("<IHHII", 0x402, 0x73, 4, 0x15EECC, 0xDB5A4)
    assert fw.get(0x15EECC, 16) == struct.pack("<4I", W_TEXT1, W_TEXT2, W_LOGO, W_SHARE)
    assert fw.get(W_LOGO, 0x1C) == struct.pack("<IIIhhhhIHH", 7, 0x14802, 0, 20, 10, 0, 0, 0, 93, 0)
    assert fw.get(W_SHARE, 0x1C) == struct.pack("<IIIhhhhIHH", 7, 0x14803, 0, 170, 90, 0, 0, 0, 92, 0)
    for a in COUNT_IMMS:
        assert fw.get(a, 2) == bytes([0xF6, 0xD9]), f"count imm at {a:#x}"
    assert fw.get(ENTRY, 4) == bytes.fromhex("a2c1f1c0"), "DrawImage prologue"
    assert fw.get(HOOK, 0x100) == bytes(0x100), "hook area not empty"
    assert fw.get(ZRUN, ZRUN_LEN) == bytes(ZRUN_LEN), "code zero run not empty"
    offs = list(struct.unpack("<19I", fw.get(LANG_TAB, 76)))
    sizes = list(struct.unpack("<19I", fw.get(LANG_TAB + 76, 76)))
    assert (offs[ENGLISH], sizes[ENGLISH]) == (0, 0x5C00)
    assert (offs[VICTIM], sizes[VICTIM]) == (0x6BA00, 0xBA00)
    d = fw.d
    english = bytes(d[REC3_FILE + offs[ENGLISH]:REC3_FILE + offs[ENGLISH] + sizes[ENGLISH]])

    # first data block after the id table, and its owner record
    first = TABLE + 4 * NIDS
    owners = [a for a in range(0x1A0000, 0x1EFC00 - 20, 4)
              if struct.unpack("<HHHH", fw.get(a, 8))[3] == 8 and fw.u32(a + 16) == first]
    assert len(owners) == 1, owners
    ow, oh = struct.unpack("<HH", fw.get(owners[0], 4))
    first_px, first_len = decode_at(fw.get, first, ow * oh)
    moved = fw.get(first, first_len + 1)

    # --- tiles in the combined English block -----------------------------------------
    idx, P = quantize(img, fw)
    streams = [m.encode(idx[y:y + TH].tobytes()) + b"\0" for y in range(0, SH, TH)]
    combo = bytearray(english) + MAGIC
    data_ptrs = []
    for s in streams:
        data_ptrs.append(LANG_BUF + len(combo))
        combo += s
    assert LANG_BUF + len(english) == 0x188F30  # matches MAGICP in hook.s
    print(f"tiles {[len(s) - 1 for s in streams]} bytes; combined English block {len(combo)} of {LANG_MAX}")
    assert len(combo) <= LANG_MAX
    combo += bytes(LANG_MAX - len(combo))

    # --- code zero-run layout ---------------------------------------------------------
    LIST, NEWW, RECS, MOVED = ZRUN, ZRUN + 0x20, ZRUN + 0x80, ZRUN + 0x100
    ids = list(range(NIDS, NIDS + NT))             # 246..250
    widgets = [W_LOGO, W_SHARE] + [NEWW + 0x1C * i for i in range(NT - 2)]
    wl = struct.pack("<7I", W_TEXT1, W_TEXT2, *widgets)
    neww = b"".join(struct.pack("<IIIhhhhIHH", 7, 0x14804 + i, 0, 0, TH * (i + 2), 0, 0, 0, ids[i + 2], 0)
                    for i in range(NT - 2))
    recs = b"".join(struct.pack("<HHHHIII", SW, TH, SW, 8, 1, PAL, p) for p in data_ptrs)
    assert MOVED + len(moved) <= ZRUN + ZRUN_LEN

    # --- apply --------------------------------------------------------------------------
    vo = REC3_FILE + offs[VICTIM]
    d[vo:vo + LANG_MAX] = combo                     # language 17's text is gone
    for lang in (ENGLISH, VICTIM):
        fw.put(LANG_TAB + 4 * lang, struct.pack("<I", offs[VICTIM]))
        fw.put(LANG_TAB + 76 + 4 * lang, struct.pack("<I", LANG_MAX))
    fw.put(MOVED, moved)
    fw.put(owners[0] + 16, struct.pack("<I", MOVED), struct.pack("<I", first))
    fw.put(first, struct.pack("<5I", *[RECS + 20 * i for i in range(NT)]))
    for a in COUNT_IMMS:
        fw.put(a, bytes([NIDS + NT, 0xD9]), bytes([0xF6, 0xD9]))
    fw.put(LIST, wl)
    fw.put(NEWW, neww)
    fw.put(RECS, recs)
    fw.put(W_LOGO + 0xC, struct.pack("<hh", 0, 0))
    fw.put(W_LOGO + 0x18, struct.pack("<H", ids[0]))
    fw.put(W_SHARE + 0xC, struct.pack("<hh", 0, TH))
    fw.put(W_SHARE + 0x18, struct.pack("<H", ids[1]))
    fw.put(SCREEN + 6, struct.pack("<HI", len(wl) // 4, LIST))
    fw.put(HOOK, hook)
    fw.put(ENTRY, entry, bytes.fromhex("a2c1f1c0"))

    kfw.fix(fw.d)
    probs = kfw.check(fw.d)
    assert not probs, probs

    # --- verify by walking the structures like the camera does ------------------------
    # simulated RAM: firmware sections + the language buffer as the loader fills it
    o2, s2 = struct.unpack("<II", fw.get(LANG_TAB + 4 * ENGLISH, 4) + fw.get(LANG_TAB + 76 + 4 * ENGLISH, 4))
    assert s2 <= LANG_MAX
    langbuf = bytes(fw.d[REC3_FILE + o2:REC3_FILE + o2 + s2])
    assert langbuf[:len(english)] == english, "English strings changed"

    def ram(a, n):
        if LANG_BUF <= a < LANG_BUF + LANG_MAX:
            return langbuf[a - LANG_BUF:a - LANG_BUF + n]
        return fw.get(a, n)

    assert ram(0x188F30, 4) == MAGIC
    _, _, cnt, lst, _ = struct.unpack("<IHHII", ram(SCREEN, 16))
    shot = np.zeros((SH, SW), np.uint8)
    drawn = 0
    for i in range(cnt):
        w = struct.unpack("<I", ram(lst + 4 * i, 4))[0]
        typ, wid, _, x, y, _, _, _, iid, _ = struct.unpack("<IIIhhhhIHH", ram(w, 0x1C))
        if typ != 7:
            continue
        assert iid < NIDS + NT
        rec = struct.unpack("<I", ram(TABLE + 4 * iid, 4))[0]
        rw, rh, _, bpp, fl, pal, dat = struct.unpack("<HHHHIII", ram(rec, 20))
        assert (bpp, fl, pal) == (8, 1, PAL) and rw * rh <= 25800 and x + rw <= SW and y + rh <= SH
        px, _ = decode_at(ram, dat, rw * rh)
        shot[y:y + rh, x:x + rw] = np.frombuffer(px, np.uint8).reshape(rh, rw)
        drawn += 1
    assert drawn == NT and (shot == idx).all(), "tiles do not reassemble the image"
    for i in range(1, NIDS):                        # every stock image still decodes the same
        ra, rb = old.u32(TABLE + 4 * i), fw.u32(TABLE + 4 * i)
        assert ra == rb
        wa, ha, _, bpp, fl = struct.unpack("<HHHHI", old.get(ra, 12))
        if bpp == 8 and fl == 1:
            assert decode_at(old.get, old.u32(ra + 16), wa * ha)[0] == decode_at(fw.get, fw.u32(rb + 16), wa * ha)[0], i
    open(out, "wb").write(fw.d)
    print(f"wrote {out}; verifies OK; boot screen reassembles exactly; all stock images unchanged")
    if len(sys.argv) > 4:
        Image.fromarray(P[shot].astype(np.uint8)).resize((640, 480), Image.NEAREST).save(sys.argv[4])


if __name__ == "__main__":
    main()
