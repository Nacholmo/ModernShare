#!/usr/bin/env python3
"""Approximate a film 3D LUT (.cube) with the camera's capture pipeline, and patch it in.

Usage:
  fit_lut.py BASE_FW COLOR.cube OUT_FW [--bw BW.cube] [--photo IN.JPG PREVIEW.png] [--matrix-only]

Capture pipeline of saved photos (confirmed with the mtest2 diagnostic, photos 0247-0255):
  camera RGB -> CCM_illum -> tone curves -> YCbCr matrix (+offsets) -> JPEG
  * CCM_illum: three 3x4 int32 Q16 matrices at 0x16cac8 / 0x16caf8 / 0x16cb28 (one per
    illuminant, chosen by white balance). We multiply all three by the same matrix R, so the
    change is the same whichever one is active.
  * tone curves: 1024 x u8, 10-bit linear in -> 8-bit out. A 0x16bac8 = green,
    B 0x16c0c8 = red AND blue (shared). Used by every mode.
  * YCbCr matrices, 3x4 int32 Q16, offsets in 1/4 units (514 = 128.5):
    0x16cb58 normal (COLOR and VIVID), 0x16cb88 B&W (Cb = Cr = 0), 0x16cbb8 sepia (unused).
    Writing Ymat = Ystd @ P turns it into a 3x3 matrix P + offset o on the curve output.
  VIVID = the COLOR look plus the camera's own extra saturation (colour level 2).

Model fitted (s = a stock photo's colour, v = what the stock curves were fed):
  v = curves_stock^-1(s)
  colour: out = P @ curves(clip(R @ v)) + o
  B&W:    out = grey(w . curves(clip(R @ v)) + oy) + chroma tint (cb, cr)
Everything is fitted together (CIE Lab error, everyday colours weighted up); the B&W look
shares R and the curves with the colour look.
"""
import argparse
import os
import struct
import sys

import numpy as np

DATA = lambda a: a - 0x130000 + 0x100200
CCM_ILLUM = (0x16CAC8, 0x16CAF8, 0x16CB28)
CURVE_A, CURVE_B = 0x16BAC8, 0x16C0C8          # green, red+blue
YMAT, YMAT_BW = 0x16CB58, 0x16CB88
K = 28                                          # curve knots (denser in the shadows)
XK = (np.arange(K + 1) / K) ** 2                # knot positions in linear 0..1
YSTD = np.array([[0.299, 0.587, 0.114], [-0.168736, -0.331264, 0.5], [0.5, -0.418688, -0.081312]])
BW_WEIGHT = 0.5
GREY_WEIGHT = 6.0                               # grey tone (greys are kept neutral by construction)
CCM_MAX = 3.9                                   # keep coefficients well inside the hardware range


# ---------------------------------------------------------------- colour helpers
def srgb_to_lab(c):
    c = np.clip(c, 0, 1)
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ M.T / np.array([0.9505, 1.0, 1.089])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def read_cube(path):
    n, rows, lo, hi = None, [], np.zeros(3), np.ones(3)
    for line in open(path, encoding="utf-8", errors="replace"):
        t = line.split()
        if not t or t[0].startswith("#") or t[0] == "TITLE":
            continue
        if t[0] == "LUT_3D_SIZE":
            n = int(t[1])
        elif t[0] == "DOMAIN_MIN":
            lo = np.array(t[1:4], float)
        elif t[0] == "DOMAIN_MAX":
            hi = np.array(t[1:4], float)
        elif t[0] == "LUT_1D_SIZE":
            sys.exit("1D LUTs are not supported, use a 3D .cube")
        elif t[0][0] in "-.0123456789":
            rows.append([float(v) for v in t[:3]])
    assert n and len(rows) == n ** 3, f"bad .cube: size {n}, {len(rows)} rows"
    return np.array(rows).reshape(n, n, n, 3), lo, hi      # indexed [b, g, r] (red fastest)


def apply_cube(cube, rgb):
    lut, lo, hi = cube
    n = lut.shape[0]
    p = np.clip((rgb - lo) / (hi - lo), 0, 1) * (n - 1)
    i0 = np.minimum(p.astype(int), n - 2)
    f = p - i0
    out = 0
    for db in (0, 1):
        for dg in (0, 1):
            for dr in (0, 1):
                w = ((f[..., 0] if dr else 1 - f[..., 0]) * (f[..., 1] if dg else 1 - f[..., 1])
                     * (f[..., 2] if db else 1 - f[..., 2]))
                out = out + w[..., None] * lut[i0[..., 2] + db, i0[..., 1] + dg, i0[..., 0] + dr]
    return np.clip(out, 0, 1)


def curve_eval(table, v):                       # table: 1024 values in 0..1, v linear 0..1
    return np.interp(v, np.arange(1024) / 1023, table)


def curve_inverse(table, y):
    t = np.maximum.accumulate(table) + np.arange(1024) * 1e-9
    return np.interp(y, t, np.arange(1024) / 1023)


def lm_fit(p, resid, iters=80):
    """Small Levenberg-Marquardt with a forward-difference Jacobian."""
    r = resid(p)
    lam = 1e-3
    for it in range(iters):
        J = np.empty((r.size, p.size))
        for j in range(p.size):
            q = p.copy(); q[j] += 1e-4
            J[:, j] = (resid(q) - r) / 1e-4
        g, H = J.T @ r, J.T @ J
        while True:
            step = np.linalg.solve(H + lam * (np.diag(np.diag(H)) + 1e-9 * np.eye(p.size)), -g)
            r2 = resid(p + step)
            if r2 @ r2 < r @ r:
                p, gain = p + step, (r @ r - r2 @ r2) / (r @ r)
                r, lam = r2, max(lam / 3, 1e-7)
                break
            lam *= 4
            if lam > 1e8:
                return p
        if gain < 1e-6:
            break
    return p


# ---------------------------------------------------------------- the camera
def load_camera(d):
    m = lambda a: np.array(struct.unpack_from("<12i", d, DATA(a)), float).reshape(3, 4)
    cam = dict(ccm=[m(a) for a in CCM_ILLUM], ymat=m(YMAT), ybw=m(YMAT_BW),
               tA=np.frombuffer(bytes(d[DATA(CURVE_A):DATA(CURVE_A) + 1024]), np.uint8) / 255,
               tB=np.frombuffer(bytes(d[DATA(CURVE_B):DATA(CURVE_B) + 1024]), np.uint8) / 255)
    cam["Ystd"] = cam["ymat"][:, :3] / 65536
    assert np.allclose(cam["Ystd"][0], [0.299, 0.587, 0.114], atol=1e-3), "normal YCbCr matrix is not stock"
    assert np.allclose(cam["ybw"][0, :3] / 65536, [0.299, 0.587, 0.114], atol=1e-3), "B&W matrix is not stock"
    return cam


def to_v(cam, s):
    """Stock photo colours -> the linear values the stock curves were fed."""
    tB, tA = cam["tB"], cam["tA"]
    return np.stack([curve_inverse(tB, s[..., 0]), curve_inverse(tA, s[..., 1]), curve_inverse(tB, s[..., 2])], -1)


def curves_out(R, b, a, v, knots=True):
    x = np.clip(v @ R.T, 0, 1)
    f = (lambda y, t: np.interp(t, XK, y)) if knots else (lambda y, t: curve_eval(y, t))
    return np.stack([f(b, x[..., 0]), f(a, x[..., 1]), f(b, x[..., 2])], -1)


def colour_out(R, b, a, P, o, v, knots=True):
    return np.clip(curves_out(R, b, a, v, knots) @ P.T + o, 0, 1)


def bw_out(R, b, a, w, oy, tint, v, cam, knots=True):
    y = curves_out(R, b, a, v, knots) @ w + oy
    Yi = np.linalg.inv(cam["Ystd"])               # decoder: rgb = Yi @ [y, cb, cr]
    return np.clip(y[..., None] * Yi[:, 0] + Yi[:, 1:] @ tint, 0, 1)


# ---------------------------------------------------------------- fitting
def _fill(p0, free, x):
    p = p0.copy(); p[free] = x
    return p


NC = 9 + 2 * (K + 1)                            # R + curves
NP = 12                                         # P + o
NB = 6                                          # w + oy + (cb, cr)


def unpack(p, has_bw):
    R = p[:9].reshape(3, 3)
    R = R + ((1 - R.sum(1)) / 3)[:, None]      # greys stay grey before the curves
    k = []
    for o in (9, 9 + K + 1):
        k.append(np.clip(p[o] + np.concatenate([[0], np.cumsum(p[o + 1:o + K + 1] ** 2)]), 0, 1))
    M = p[NC:NC + 9].reshape(3, 3).copy()      # the YCbCr matrix the firmware stores
    M[0] = M[0] ** 2                            # luma weights >= 0 (negative ones are untested)
    M[1:] -= M[1:].mean(1, keepdims=True)       # greys get no chroma: whites stay white
    P = np.linalg.solve(YSTD, M)
    o = np.linalg.solve(YSTD, [p[NC + 9] ** 2, 0, 0])   # firmware Y offset >= 0, no colour cast
    bw = (p[NC + 12:NC + 15] ** 2, p[NC + 15] ** 2, np.zeros(2)) if has_bw else None   # weights, offset >= 0, no tint
    return R, k[0], k[1], P, o, bw


def samples(cam):
    """Colours of a stock photo: an RGB grid + extra greys, with weights."""
    g = np.linspace(0, 1, 17)
    grid = np.stack(np.meshgrid(g, g, g, indexing="ij"), -1).reshape(-1, 3)
    grey = np.repeat(np.linspace(0, 1, 65)[:, None], 3, 1)
    s = np.concatenate([grid, grey])
    w = np.concatenate([1.5 - (grid.max(1) - grid.min(1)), np.full(len(grey), GREY_WEIGHT)])
    return s, to_v(cam, s), np.sqrt(w)[:, None]


def stats(out, target_lab):
    de = np.sqrt(((srgb_to_lab(out) - target_lab) ** 2).sum(-1))
    return de.mean(), np.percentile(de, 95), de.max()


def fit(cam, cube, bw_cube=None, matrix_only=False):
    """matrix_only: keep the stock tone curves, fit only R, P, o (and the B&W mix)."""
    s, v, sw = samples(cam)
    kn = not matrix_only
    tc = srgb_to_lab(apply_cube(cube, s))
    tb = srgb_to_lab(apply_cube(bw_cube, s)) if bw_cube is not None else None
    has_bw = tb is not None

    def resid(q):
        R, b, a, P, o, bw = unpack(q, has_bw)
        if matrix_only:
            b, a = cam["tB"], cam["tA"]
        r = [((srgb_to_lab(colour_out(R, b, a, P, o, v, kn)) - tc) * sw).reshape(-1)]
        if has_bw:
            # weighted down: R is shared, and the colour look matters more than a few dE of B&W
            r.append(((srgb_to_lab(bw_out(R, b, a, *bw, v, cam, kn)) - tb) * sw * BW_WEIGHT).reshape(-1))
        return np.concatenate(r)

    def start(R0):
        p = [R0.reshape(-1)]
        for t in (cam["tB"], cam["tA"]):
            y = curve_eval(t, XK)
            p += [[y[0]], np.sqrt(np.maximum(np.diff(y), 1e-6))]
        p += [np.vstack([np.sqrt(YSTD[0]), YSTD[1:]]).reshape(-1), [0.05, 0.0, 0.0]]
        if has_bw:
            p += [np.sqrt(YSTD[0]), [0.02], [0.0, 0.0]]
        return np.concatenate(p)

    # starting matrices: identity, and a least-squares solve with the stock curves undone
    tgt = apply_cube(cube, s)
    R_ls = np.linalg.lstsq(v * sw, to_v(cam, tgt) * sw, rcond=None)[0].T
    starts = [start(np.eye(3)), start(R_ls), start((np.eye(3) + R_ls) / 2)]
    if has_bw:       # also: the colour film fitted alone, then the B&W film added on top
        pc = fit(cam, cube, matrix_only=matrix_only)["p"]
        starts.append(np.concatenate([pc, start(np.eye(3))[-NB:]]))
    free = np.ones(starts[0].size, bool)
    if matrix_only:
        free[9:NC] = False                      # curve parameters stay at their start (unused)
    best = None
    for p0 in starts:
        x = lm_fit(p0[free], lambda x, p0=p0: resid(_fill(p0, free, x)))
        p = _fill(p0, free, x)
        e = resid(p) @ resid(p)
        if best is None or e < best[0]:
            best = (e, p)
    R, b, a, P, o, bw = unpack(best[1], has_bw)

    # quantise like the firmware stores it
    r = dict(R=R, P=P, o=o, bw=bw, p=best[1])
    xs = np.arange(1024) / 1023
    r["qB"] = np.round(np.interp(xs, XK, b) * 255) if not matrix_only else np.round(cam["tB"] * 255)
    r["qA"] = np.round(np.interp(xs, XK, a) * 255) if not matrix_only else np.round(cam["tA"] * 255)
    r["matrix_only"] = matrix_only
    out = lambda vv: colour_out(R, r["qB"] / 255, r["qA"] / 255, P, o, vv, knots=False)
    r["colour"] = dict(stock=stats(s, tc), fit=stats(out(v), tc))
    if has_bw:
        r["bw_look"] = dict(stock=stats(s, tb), fit=stats(bw_out(R, r["qB"] / 255, r["qA"] / 255, *bw, v, cam,
                                                                  knots=False), tb))
    return r


def fit_ccm(cam, cube, bw=False):
    """Colour matrix (CCM) only: stock curves and stock YCbCr matrix (P = I, o = 0).
    For per-scene looks, where only the CCM is fetched per photo. Colour: R keeps greys
    neutral up to one brightness gain. B&W: all three rows equal (R = G = B), sum 1."""
    s, v, sw = samples(cam)
    tc = srgb_to_lab(apply_cube(cube, s))
    I, z = np.eye(3), np.zeros(3)

    def R_of(q):
        if bw:
            w = q[:3] / q[:3].sum()
            return np.outer(np.ones(3), w)
        R = q[:9].reshape(3, 3)
        return (R + ((1 - R.sum(1)) / 3)[:, None]) * q[9]

    def resid(q):
        return ((srgb_to_lab(colour_out(R_of(q), cam["tB"], cam["tA"], I, z, v, knots=False)) - tc) * sw).reshape(-1)

    starts = [YSTD[0].copy()] if bw else [np.r_[np.eye(3).ravel(), g] for g in (0.8, 1.0, 1.2)]
    best = None
    for q0 in starts:
        q = lm_fit(q0, resid)
        e = resid(q) @ resid(q)
        if best is None or e < best[0]:
            best = (e, q)
    R = R_of(best[1])
    out = colour_out(R, cam["tB"], cam["tA"], I, z, v, knots=False)
    return dict(R=R, P=I, o=z, bw=None, qB=np.round(cam["tB"] * 255), qA=np.round(cam["tA"] * 255),
                matrix_only=True, colour=dict(stock=stats(s, tc), fit=stats(out, tc)))


# ---------------------------------------------------------------- firmware
def patch(d, cam, r):
    put = lambda a, M: struct.pack_into("<12i", d, DATA(a), *[int(round(x)) for x in M.reshape(-1)])
    for a, M in zip(CCM_ILLUM, cam["ccm"]):
        new = M.copy()
        new[:, :3] = np.round(r["R"] @ M[:, :3] / 64) * 64          # stock values are multiples of 64
        if np.abs(new[:, :3]).max() > CCM_MAX * 65536:
            print(f"warning: CCM at {a:#x} has a coefficient of {np.abs(new[:, :3]).max() / 65536:.2f}")
        put(a, new)
    if not r.get("matrix_only"):
        d[DATA(CURVE_B):DATA(CURVE_B) + 1024] = bytes(r["qB"].astype(np.uint8))
        d[DATA(CURVE_A):DATA(CURVE_A) + 1024] = bytes(r["qA"].astype(np.uint8))
    Y = cam["ymat"].copy()
    Y[:, :3] = cam["Ystd"] @ r["P"] * 65536
    Y[:, 3] += np.round(cam["Ystd"] @ r["o"] * 255 * 4)                # offsets in 1/4 units
    Y[0, 3] = max(Y[0, 3], 0)
    put(YMAT, Y)
    if r["bw"] is not None:
        w, oy, tint = r["bw"]
        B = cam["ybw"].copy()
        B[0, :3] = w * 65536
        B[0, 3] = max(B[0, 3] + round(oy * 255 * 4), 0)
        B[1:, 3] += np.round(np.asarray(tint) * 255 * 4)
        put(YMAT_BW, B)
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../tools"))
    import kodakfw
    kodakfw.fix(d)
    assert not kodakfw.check(d)


def photo_panels(cam, cube, r, path, size=(640, 480), bw=False):
    """[stock photo, LUT applied, camera approximation] as float arrays."""
    from PIL import Image
    im = Image.open(path).convert("RGB")
    im.thumbnail(size)
    s = np.asarray(im, float) / 255
    v = to_v(cam, s)
    qb, qa = r["qB"] / 255, r["qA"] / 255
    cam_px = (bw_out(r["R"], qb, qa, *r["bw"], v, cam, knots=False) if bw
              else colour_out(r["R"], qb, qa, r["P"], r["o"], v, knots=False))
    return [s, apply_cube(cube, s), cam_px]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("base"); ap.add_argument("cube"); ap.add_argument("out")
    ap.add_argument("--bw", metavar="BW.cube", help="B&W film for the BLACK & WHITE mode")
    ap.add_argument("--photo", nargs=2, metavar=("IN_JPG", "PREVIEW_PNG"),
                    help="preview: stock photo | LUT | camera approximation")
    ap.add_argument("--matrix-only", action="store_true",
                    help="keep the stock tone curves (fit only the colour matrices)")
    a = ap.parse_args()
    d = bytearray(open(a.base, "rb").read())
    cam, cube = load_camera(d), read_cube(a.cube)
    bw_cube = read_cube(a.bw) if a.bw else None
    r = fit(cam, cube, bw_cube, a.matrix_only)
    print("distance to the LUT look (CIE76 dE; under ~2 is hard to see, under ~5 is close):")
    looks = [("COLOR/VIVID", a.cube, r["colour"])] + ([("B&W", a.bw, r["bw_look"])] if a.bw else [])
    for slot, path, st in looks:
        print(f"{slot}: {os.path.basename(path)}")
        for name, (m, p95, mx) in (("stock camera", st["stock"]), ("camera approximation", st["fit"])):
            print(f"  {name:22s} mean dE {m:5.2f}   95% {p95:5.2f}   max {mx:5.1f}")
    fmt = lambda M: " | ".join(" ".join(f"{x:+.3f}" for x in row) for row in M)
    print(f"R (before curves): {fmt(r['R'])}\nP (after curves):  {fmt(r['P'])}   offset {np.round(r['o'] * 255, 1)}")
    if r["bw"] is not None:
        print(f"B&W mix {np.round(r['bw'][0], 3)} offset {r['bw'][1] * 255:+.1f} tint {np.round(np.asarray(r['bw'][2]) * 255, 1)}")
    patch(d, cam, r)
    open(a.out, "wb").write(d)
    print(f"wrote {a.out}")
    if a.photo:
        from PIL import Image
        strips = [np.concatenate(photo_panels(cam, cube, r, a.photo[0]), 1)]
        if a.bw:
            strips.append(np.concatenate(photo_panels(cam, bw_cube, r, a.photo[0], bw=True), 1))
        Image.fromarray((np.concatenate(strips, 0) * 255 + 0.5).astype(np.uint8)).save(a.photo[1])
        print(f"wrote {a.photo[1]} (rows: {', '.join(l[0] for l in looks)}; stock | LUT | camera)")


if __name__ == "__main__":
    main()
