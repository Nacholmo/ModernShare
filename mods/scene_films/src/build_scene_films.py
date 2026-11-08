#!/usr/bin/env python3
"""Film presets in SCN scenes, plus flash Off by default in every mode.

Usage: build_scene_films.py BASE_FW OUT_FW [--photo STOCK.JPG PREVIEW.png]

BASE_FW must have stock colour matrices (e.g. mods/theme/KC713.FW). Normal COLOR / B&W /
VIVID stay stock; only the scenes in SCENES get a film look.

How it works (see hook.s):
  * The capture loader 0x11e124 fetches the colour matrices for every photo through two
    getters, 0xaf508 GetCCM(illuminant) and 0xaf514 GetYmat(colour mode) (measured with the
    diag call log). Their first 4 bytes become branches to our hook at 0x125600, which reads
    the capture mode (0x1328ff): if FILMTAB[mode] names a film, the film's 3 CCMs / Ymat are
    returned instead of the stock ones.
  * Each scene's look is fitted either as CCM + Ymat ("full") or as a CCM alone ("ccm").
    A B&W film has a Ymat with Cb = Cr = 0 ("full") or a CCM with three equal rows ("ccm").
  * v1/v2 put the films on the wrong modes (help-string order without "High ISO"), so they
    never applied; they prove nothing about whether the Ymat is used.

SCN menu position -> capture mode (jump table 0x3c604, SetScene 0x3c5ec). The menu follows
the help strings starting at "High ISO" (0x1958a5); Museum = 17 was measured with the
diag build's call log, and the flash defaults per mode agree (Backlight = forced fill, Night /
Self Portrait = red-eye):
  High ISO 21, Portrait 5, Sport 4, Landscape 3, Night Portrait 6, Night Landscape 15, Snow 10,
  Beach 11, Text 13, Fireworks 16, Flower 12, Museum 17, Self Portrait 7, Children 9,
  Backlight 14, last item (Sunset / Candle Light) 22. Auto = 0.
The diag log also showed both getters called once per photo by the loader 0x11e124
(callers 0x11e134 CCM, 0x11e142 Ymat) plus 9 CCM calls from 0x98990.
"""
import argparse
import os
import struct
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "../../..")
sys.path[:0] = [os.path.join(ROOT, "mods/lut/src"), os.path.join(ROOT, "mods/flash_all_off/src"),
                os.path.join(ROOT, "tools")]
import fit_lut as F          # noqa: E402
import patch as flash        # noqa: E402  (mods/flash_all_off)
import kodakfw               # noqa: E402

LUTS = os.path.join(ROOT, "mods/lut/looks/filmluts")
# scene name, capture mode, film LUT, black-and-white?, method:
#   "full": CCM + YCbCr matrix (fit_lut matrix-only model, best match; needs GetYmat hooked)
#   "ccm":  CCM alone (fit_lut.fit_ccm); B&W = CCM with three equal rows
SCENES = [("Sunset", 22, "negative_color/agfa_vista_200", False, "full"),
          ("Children", 9, "colorslide/kodak_ektachrome_100_vs", False, "full"),
          ("Museum", 17, "bw/fuji_neopan_1600", True, "ccm")]

CODE = lambda a: a - 0x30000 + 0x200
HOOK, FILMTAB, FILMS = 0x125600, 0x125780, 0x1257A0
LOGCNT = 0x125A00                                   # diagnostic log (hook.s, DIAG)
FILM_SIZE = 0xC0
# stock first 4 bytes of each getter. Only GetCCM is hooked: GetYmat is called per photo only
# for B&W / sepia (0x9fec0 & co.); the normal Ymat is baked into tables at start-up, so a
# per-scene Ymat has no effect (scene_films v1, photo 0281: Museum stayed in colour).
ENTRIES = {0xAF508: ("ccm", (0xD13F, 0x2115)), 0xAF514: ("ymat", (0xD13D, 0xE083))}


def assemble(diag=False):
    """hook(_diag).bin + symbol offsets. Re-assembles if AS / OBJCOPY / NM are set (arc-elf32 binutils)."""
    name = "hook_diag" if diag else "hook"
    if os.environ.get("AS"):
        o = os.path.join(HERE, name + ".o")
        subprocess.check_call([os.environ["AS"], "-mcpu=arc700"] + (["--defsym", "DIAG=1"] if diag else [])
                              + [os.path.join(HERE, "hook.s"), "-o", o])
        subprocess.check_call([os.environ["OBJCOPY"], "-O", "binary", o, os.path.join(HERE, name + ".bin")])
        syms = subprocess.check_output([os.environ["NM"], o], text=True)
        with open(os.path.join(HERE, name + ".sym"), "w") as f:
            f.write(syms)
    syms = {l.split()[2]: int(l.split()[0], 16) for l in open(os.path.join(HERE, name + ".sym")) if len(l.split()) == 3}
    assert syms["FILMTAB"] == FILMTAB and syms["FILMS"] == FILMS and syms["LOGCNT"] == LOGCNT
    return open(os.path.join(HERE, name + ".bin"), "rb").read(), syms


def branch(at, target):
    """32-bit ARCompact 'b target' placed at address 'at', in firmware byte order."""
    off = (target - (at & ~3)) >> 1                       # s24 halfword offset (bits 1..24)
    assert -(1 << 23) <= off < (1 << 23) and not (target & 1)
    w = (1 << 16) | ((off & 0x3FF) << 17) | (((off >> 10) & 0x3FF) << 6) | ((off >> 20) & 0xF)   # bit 16 = 'far' b
    return struct.pack("<HH", w >> 16, w & 0xFFFF)


def film_matrices(cam, base, lut, bw, method):
    """3 CCMs + Ymat (0xC0 bytes) for one film."""
    cube = F.read_cube(os.path.join(LUTS, lut + ".cube"))
    if method == "ccm":
        r = F.fit_ccm(cam, cube, bw)
    else:
        # a B&W film goes through the colour path too: the fit drives the chroma rows to ~0
        # by itself, and they are then forced to exactly 0
        r = F.fit(cam, cube, matrix_only=True)
        if bw:
            r["P"] = np.linalg.solve(F.YSTD, np.vstack([(F.YSTD @ r["P"])[:1], np.zeros((2, 3))]))
            r["o"] = np.linalg.solve(F.YSTD, [(F.YSTD @ r["o"])[0], 0, 0])
    tmp = bytearray(base)
    F.patch(tmp, cam, r)                                  # writes the 3 CCMs and the Ymat
    out = b"".join(bytes(tmp[F.DATA(a):F.DATA(a) + 0x30]) for a in F.CCM_ILLUM)
    Y = bytes(tmp[F.DATA(F.YMAT):][:0x30])
    if bw:
        y = struct.unpack("<12i", Y)
        Y = struct.pack("<12i", *y[:4], 0, 0, 0, y[7], 0, 0, 0, y[11])
    s, v, _ = F.samples(cam)
    st = dict(stock=F.stats(s, F.srgb_to_lab(F.apply_cube(cube, s))),
              fit=F.stats(F.colour_out(r["R"], cam["tB"], cam["tA"], r["P"], r["o"], v, knots=False),
                          F.srgb_to_lab(F.apply_cube(cube, s))))
    return out + Y, r, cube, st


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("base"); ap.add_argument("out")
    ap.add_argument("--photo", nargs=2, metavar=("STOCK_JPG", "PREVIEW_PNG"))
    ap.add_argument("--diag", action="store_true",
                    help="log every getter call (caller, argument, mode) at 0x125a00 for MEMDUMP")
    a = ap.parse_args()
    entries = dict(ENTRIES)
    d = bytearray(open(a.base, "rb").read())
    cam = F.load_camera(d)                                 # asserts stock matrices
    hook, syms = assemble(a.diag)
    assert len(hook) <= FILMTAB - HOOK
    assert d[CODE(HOOK):CODE(HOOK + 0x6F0)] == bytes(0x6F0), "hook area 0x125600.. not empty"
    for at, (_, stock) in entries.items():
        assert d[CODE(at):CODE(at) + 4] == struct.pack("<HH", *stock), f"{at:#x} is not the stock getter"

    n = flash.apply(d)
    print(f"flash: {n} reset values changed, all 11 slots start Off")

    tab = bytearray(24)
    films = b""
    panels = []
    for i, (name, mode, lut, bw, method) in enumerate(SCENES):
        m, r, cube, st = film_matrices(cam, bytes(d), lut, bw, method)
        tab[mode] = i + 1
        films += m
        print(f"{name:9s} (mode {mode:2d}, {method:4s}) = {os.path.basename(lut):28s} mean dE {st['fit'][0]:4.1f} "
              f"(stock {st['stock'][0]:4.1f})")
        if a.photo:
            panels.append(np.concatenate(F.photo_panels(cam, cube, r, a.photo[0]), 1))
    assert FILMS + len(films) <= LOGCNT
    d[CODE(HOOK):CODE(HOOK) + len(hook)] = hook
    d[CODE(FILMTAB):CODE(FILMTAB) + 24] = tab
    d[CODE(FILMS):CODE(FILMS) + len(films)] = films
    for at, (sym, _) in entries.items():
        d[CODE(at):CODE(at) + 4] = branch(at, HOOK + syms[sym])
    kodakfw.fix(d)
    assert not kodakfw.check(d)
    open(a.out, "wb").write(d)
    print(f"wrote {a.out}")
    if a.photo:
        from PIL import Image
        Image.fromarray((np.concatenate(panels, 0) * 255 + 0.5).astype(np.uint8)).save(a.photo[1])
        print(f"wrote {a.photo[1]} (rows: {', '.join(s[0] for s in SCENES)}; stock | LUT | camera)")


if __name__ == "__main__":
    main()
