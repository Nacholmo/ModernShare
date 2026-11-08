#!/usr/bin/env python3
"""Film look with film tone curves in COLOR/VIVID + a B&W film, plus SCN film presets and flash Off.

Usage: build_film_color.py BASE_FW OUT_FW [--color LUT|none] [--bw LUT] [--raw] [--photo STOCK.JPG PREVIEW.png]

--color none: COLOR/VIVID stay stock (stock curves and matrices); only the B&W mode's own
YCbCr matrix (0x16cb88) gets the B&W film (luma weights + offset, fitted through the stock
curves). COLOR and VIVID share the CCMs, curves and normal YCbCr matrix, so they can't differ.
--raw: also save the sensor RAW next to every JPG (mods/raw_plus_jpeg, SaveCFAonTake).

BASE_FW must be stock-coloured (mods/theme/KC713.FW). Steps:
  1. fit_lut full fit (tone curves + matrices) of the COLOR film, with the B&W film.
  2. Write the new curves and rebuild both curve companions as the inverse of curve B
     (mods/curve_inverse: stale companions caused the lavender whites).
  3. Build the SCN film presets (mods/scene_films) on top, so their matrices are fitted
     through the NEW curves (the curves are shared by every mode). This also sets flash Off.
  4. Write the COLOR/VIVID and B&W matrices.
"""
import argparse
import os
import struct
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "../../.."))
sys.path[:0] = [os.path.join(ROOT, "mods/lut/src"), os.path.join(ROOT, "mods/curve_inverse/src"),
                os.path.join(ROOT, "mods/raw_plus_jpeg/src"),
                os.path.join(ROOT, "tools")]
import fit_lut as F                          # noqa: E402
import build_curve_inverse as CI             # noqa: E402
import build_raw_plus_jpeg as RAW            # noqa: E402
import kodakfw                               # noqa: E402

LUTS = os.path.join(ROOT, "mods/lut/looks/filmluts")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("base"); ap.add_argument("out")
    ap.add_argument("--color", default="negative_color/agfa_vista_200")
    ap.add_argument("--bw", default="bw/fuji_neopan_1600")
    ap.add_argument("--photo", nargs=2, metavar=("STOCK_JPG", "PREVIEW_PNG"))
    ap.add_argument("--raw", action="store_true", help="also save the sensor RAW (CCDInnnn.RAW)")
    a = ap.parse_args()
    d = bytearray(open(a.base, "rb").read())
    cam = F.load_camera(d)
    bw_cube = F.read_cube(os.path.join(LUTS, a.bw + ".cube"))
    if a.color == "none":
        return bw_only(a, d, cam, bw_cube)
    cube = F.read_cube(os.path.join(LUTS, a.color + ".cube"))

    # 1. full fit
    r = F.fit(cam, cube, bw_cube)
    print(f"COLOR {os.path.basename(a.color)}: mean dE {r['colour']['fit'][0]:.1f} (stock {r['colour']['stock'][0]:.1f}); "
          f"B&W {os.path.basename(a.bw)}: {r['bw_look']['fit'][0]:.1f} (stock {r['bw_look']['stock'][0]:.1f})")
    g = np.repeat(np.linspace(0, 1, 33)[:, None], 3, 1)
    out = F.colour_out(r["R"], r["qB"] / 255, r["qA"] / 255, r["P"], r["o"], F.to_v(cam, g), knots=False) * 255
    print("predicted greys (R,G,B) at 25/50/75/100%:", [tuple(out[i].round().astype(int)) for i in (8, 16, 24, 32)],
          f"worst channel spread {np.ptp(out, 1).max():.1f}")

    # 2. curves + companions, stock matrices
    d1 = bytearray(d)
    d1[F.DATA(F.CURVE_B):F.DATA(F.CURVE_B) + 1024] = bytes(r["qB"].astype(np.uint8))
    d1[F.DATA(F.CURVE_A):F.DATA(F.CURVE_A) + 1024] = bytes(r["qA"].astype(np.uint8))
    inv = CI.inverse(r["qB"].astype(int)).tobytes()
    for t in (CI.COMP_A, CI.COMP_B):
        d1[CI.DATA(t):CI.DATA(t) + 512] = inv
    kodakfw.fix(d1)

    # 3. SCN presets through the new curves (+ flash Off)
    with tempfile.TemporaryDirectory() as tmp:
        p1, p2 = os.path.join(tmp, "curves.fw"), os.path.join(tmp, "scenes.fw")
        open(p1, "wb").write(d1)
        subprocess.check_call([sys.executable, os.path.join(ROOT, "mods/scene_films/src/build_scene_films.py"), p1, p2])
        d2 = bytearray(open(p2, "rb").read())

    # 4. COLOR/VIVID + B&W matrices (cam = stock matrices; also rewrites the same curves)
    F.patch(d2, cam, r)
    assert d2[CI.DATA(CI.COMP_A):CI.DATA(CI.COMP_A) + 512] == inv
    if a.raw:
        set_raw(d2)
    kodakfw.fix(d2)
    assert not kodakfw.check(d2)
    open(a.out, "wb").write(d2)
    print("wrote", a.out)
    if a.photo:
        from PIL import Image
        rows = [np.concatenate(F.photo_panels(cam, cube, r, a.photo[0]), 1),
                np.concatenate(F.photo_panels(cam, bw_cube, r, a.photo[0], bw=True), 1)]
        Image.fromarray((np.concatenate(rows, 0) * 255 + 0.5).astype(np.uint8)).save(a.photo[1])
        print("wrote", a.photo[1], "(rows: COLOR, B&W; stock | LUT | camera)")


def set_raw(d):
    assert d[RAW.DATA(RAW.JPEG)] == 1 and d[RAW.DATA(RAW.FLAGS["cfa"])] == 0
    d[RAW.DATA(RAW.FLAGS["cfa"])] = 1
    print("sensor RAW saving on (SaveCFAonTake 0x13358c = 1)")


def fit_bw_ymat(cam, bw_cube):
    """B&W luma weights w >= 0 and offset oy >= 0 through the stock CCM and curves."""
    s, v, sw = F.samples(cam)
    tb = F.srgb_to_lab(F.apply_cube(bw_cube, s))
    I, z = np.eye(3), np.zeros(2)
    out = lambda p: F.bw_out(I, cam["tB"], cam["tA"], p[:3] ** 2, p[3] ** 2, z, v, cam, knots=False)
    resid = lambda p: ((F.srgb_to_lab(out(p)) - tb) * sw).reshape(-1)
    p = F.lm_fit(np.concatenate([np.sqrt(F.YSTD[0]), [0.02]]), resid)
    return p[:3] ** 2, p[3] ** 2, F.stats(out(p), tb), F.stats(s, tb)


def bw_only(a, d, cam, bw_cube):
    w, oy, st, st0 = fit_bw_ymat(cam, bw_cube)
    print(f"COLOR/VIVID: stock. B&W {os.path.basename(a.bw)}: mean dE {st[0]:.1f} (stock {st0[0]:.1f}); "
          f"luma weights {np.round(w, 3)} offset {oy * 255:+.1f}")
    with tempfile.TemporaryDirectory() as tmp:        # SCN presets (fitted through the stock curves) + flash Off
        p1, p2 = os.path.join(tmp, "base.fw"), os.path.join(tmp, "scenes.fw")
        open(p1, "wb").write(d)
        subprocess.check_call([sys.executable, os.path.join(ROOT, "mods/scene_films/src/build_scene_films.py"), p1, p2])
        d2 = bytearray(open(p2, "rb").read())
    B = cam["ybw"].copy()
    B[0, :3] = w * 65536
    B[0, 3] = max(B[0, 3] + round(oy * 255 * 4), 0)
    struct.pack_into("<12i", d2, F.DATA(F.YMAT_BW), *[int(round(x)) for x in B.reshape(-1)])
    if a.raw:
        set_raw(d2)
    kodakfw.fix(d2)
    assert not kodakfw.check(d2)
    open(a.out, "wb").write(d2)
    print("wrote", a.out)
    if a.photo:
        from PIL import Image
        r = dict(R=np.eye(3), qB=cam["tB"] * 255, qA=cam["tA"] * 255, bw=(w, oy, np.zeros(2)))
        row = np.concatenate(F.photo_panels(cam, bw_cube, r, a.photo[0], bw=True), 1)
        Image.fromarray((row * 255 + 0.5).astype(np.uint8)).save(a.photo[1])
        print("wrote", a.photo[1], "(B&W: stock | LUT | camera)")


if __name__ == "__main__":
    main()
