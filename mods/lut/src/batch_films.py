#!/usr/bin/env python3
"""Fit every film LUT in looks/filmluts/films.tsv and rank how well the camera can match it.

Usage: batch_films.py BASE_FW PHOTO.JPG OUTDIR [--matrix-only]

Writes OUTDIR/ranking.md (stock and fitted distance per film) and OUTDIR/sheet_*.jpg
contact sheets: for each film, the LUT applied to PHOTO (top) and the camera's
approximation (bottom). Build a firmware for a chosen film with fit_lut.py.
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fit_lut as F

LOOKS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../looks/filmluts")
TW, TH, COLS = 240, 180, 6


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base"); ap.add_argument("photo"); ap.add_argument("outdir")
    ap.add_argument("--matrix-only", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    cam = F.load_camera(bytearray(open(a.base, "rb").read()))
    rows = [l.rstrip("\n").split("\t") for l in open(os.path.join(LOOKS, "films.tsv"))][1:]
    results = []
    for key, path, name, iso, kind in rows:
        cube = F.read_cube(os.path.join(LOOKS, path + ".cube"))
        r = F.fit(cam, cube, matrix_only=a.matrix_only)
        lut_px, cam_px = F.photo_panels(cam, cube, r, a.photo, (TW, TH))[1:]
        r["fit"], r["stock"] = r["colour"]["fit"], r["colour"]["stock"]
        r["photo"] = np.sqrt(((F.srgb_to_lab(lut_px) - F.srgb_to_lab(cam_px)) ** 2).sum(-1)).mean()
        results.append((key, name, kind, r, lut_px, cam_px))
        print(f"{name:28s} {kind:6s} stock {r['stock'][0]:5.2f} -> fit {r['fit'][0]:5.2f} "
              f"(95% {r['fit'][1]:5.2f}), on the photo {r['photo']:5.2f}", flush=True)

    with open(os.path.join(a.outdir, "ranking.md"), "w") as f:
        f.write("Ranked by the error on the test photo (CIE76 dE between the LUT and the camera's version).\n\n")
        f.write("| film | kind | photo dE | all colours dE (mean / 95%) | stock dE | match |\n|---|---|---|---|---|---|\n")
        for key, name, kind, r, *_ in sorted(results, key=lambda x: x[3]["photo"]):
            m = r["photo"]
            q = "very close" if m < 2.5 else "close" if m < 4.5 else "rough" if m < 7 else "poor"
            f.write(f"| {name} (`{key}`) | {kind} | {m:.1f} | {r['fit'][0]:.1f} / {r['fit'][1]:.1f} | {r['stock'][0]:.1f} | {q} |\n")

    # contact sheets: LUT on top, camera approximation below, 6 films per row
    per = COLS * 4
    for s in range(0, len(results), per):
        chunk = results[s:s + per]
        nrow = (len(chunk) + COLS - 1) // COLS
        sheet = Image.new("RGB", (COLS * (TW + 8), nrow * (2 * TH + 30)), (24, 24, 28))
        dr = ImageDraw.Draw(sheet)
        for i, (key, name, kind, r, lut_px, cam_px) in enumerate(chunk):
            x, y = (i % COLS) * (TW + 8), (i // COLS) * (2 * TH + 30)
            for k, px in enumerate((lut_px, cam_px)):
                sheet.paste(Image.fromarray((px * 255 + 0.5).astype(np.uint8)), (x, y + 16 + k * TH))
            dr.text((x + 2, y + 2), f"{name}  {r['photo']:.1f}", fill=(235, 235, 235))
        sheet.save(os.path.join(a.outdir, f"sheet_{s // per + 1}.jpg"), quality=88)
    print(f"wrote {a.outdir}/ranking.md and {len(range(0, len(results), per))} contact sheets")


if __name__ == "__main__":
    main()
