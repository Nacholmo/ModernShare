#!/usr/bin/env python3
"""Convert Kodak C713 / CD703 sensor RAW files (CCDInnnn.RAW) to DNG.

Usage:
  ccdi2dng.py FILE_OR_FOLDER... [-o OUTDIR] [--wb R,G,B | --wb grey] [--no-jpg]

Writes 100_nnnn.DNG (same base name as the camera's JPG, so editors can pair them) next to
the input, or into OUTDIR. A folder converts every CCDI*.RAW in it.

What a CCDI file is (measured on photos 0293-0296, firmware mod raw_plus_jpeg):
  * headerless, 3072 x 2310 pixels, 1 byte each, Bayer RGGB ((0,0) = red, (1,1) = blue)
  * saved before any colour processing (a B&W-mode shot's RAW is in colour, no date stamp)
  * black already removed by the camera (the darkest pixels read 0)
  * not linear: 10-bit sensor values squeezed into 8 bits with a fixed curve. The stock
    firmware's "companion" table (0x16bec8, 256 x u16) undoes it exactly, whatever look the
    installed firmware has (our film curves don't change it), so it is built in here (DECODE)
  * the JPG is the RAW cropped by 8 columns / 10 rows at the top left, to 3056 x 2292
DNG written: uncompressed 16-bit CFA, values 0..1023 (already linear: BlackLevel 0,
WhiteLevel 1023), crop to the JPG frame, the camera's daylight colour matrix (stock CCM
0x16cb28, which fits daylight shots best) as ForwardMatrix1 + ColorMatrix1, and the white
balance the camera used (fitted by undoing the firmware's colour pipeline on the matching JPG,
--fw; else the JPG's neutral areas; else the camera's typical daylight setting; or --wb).
If a black frame (BLACnnnn.RAW, saved with long exposures) exists, it is subtracted.
"""
import argparse
import glob
import os
import re
import struct
import sys

import numpy as np

W, H = 3072, 2310
CROP_X, CROP_Y, CROP_W, CROP_H = 8, 10, 3056, 2292
WHITE = 1023
DEFAULT_FW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../mods/date_fix/stock_color_neopan/KC713.FW")

# stock firmware 1.30, 0x16bec8: 8-bit RAW code -> 10-bit linear value
DECODE = np.array([
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30,
    31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59,
    60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 77, 78, 79, 80, 81, 82, 83, 85, 86, 87, 88, 90,
    91, 92, 94, 95, 96, 98, 99, 100, 102, 103, 105, 106, 108, 109, 111, 113, 114, 116, 118, 119, 121, 123, 125, 126,
    128, 130, 132, 134, 136, 138, 140, 142, 144, 146, 148, 150, 152, 154, 157, 159, 161, 164, 166, 168, 171, 173,
    176, 178, 181, 183, 186, 189, 191, 194, 197, 200, 203, 206, 209, 212, 215, 218, 221, 224, 227, 231, 234, 237,
    241, 244, 248, 251, 255, 259, 262, 266, 270, 274, 278, 282, 286, 290, 294, 298, 303, 307, 312, 316, 321, 325,
    330, 335, 339, 344, 349, 354, 360, 365, 370, 375, 381, 386, 392, 397, 403, 409, 415, 421, 427, 433, 439, 446,
    452, 459, 465, 472, 479, 486, 493, 500, 507, 514, 522, 529, 537, 545, 553, 560, 569, 577, 585, 594, 602, 611,
    620, 629, 638, 647, 656, 666, 675, 685, 695, 705, 715, 725, 736, 746, 757, 768, 779, 790, 802, 813, 825, 837,
    849, 861, 874, 886, 899, 912, 925, 939, 952, 966, 980, 994, 1008, 1023], np.uint16)

# stock daylight CCM (0x16cb28, Q16): white-balanced camera RGB -> linear sRGB; rows sum to 1
CCM = np.array([[150592, -88384, 3328], [-27776, 143360, -50048], [3008, -52352, 114880]]) / 65536
SRGB_XYZ_D65 = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750],
                         [0.0193339, 0.1191920, 0.9503041]])
SRGB_XYZ_D50 = np.array([[0.4360747, 0.3850649, 0.1430804], [0.2225045, 0.7168786, 0.0606169],
                         [0.0139322, 0.0971045, 0.7141733]])       # Bradford-adapted
DAYLIGHT_NEUTRAL = np.array([0.42, 1.0, 0.73])                     # camera's WB, mean of daylight shots 0293/0294/0296


def read_ccdi(path):
    a = np.fromfile(path, np.uint8)
    if a.size != W * H:
        sys.exit(f"{path}: {a.size} bytes, expected {W * H} (3072 x 2310) - not a C713 CCDI RAW")
    return DECODE[a.reshape(H, W)]


def half_rgb(lin):
    l = lin.astype(np.float64)
    return np.stack([l[0::2, 0::2], (l[0::2, 1::2] + l[1::2, 0::2]) / 2, l[1::2, 1::2]], -1)


def neutral_from_jpg(lin, jpg_path):
    """Camera RGB of white, from the parts of the camera's JPG that came out neutral grey."""
    from PIL import Image
    j = Image.open(jpg_path).convert("RGB")
    if j.size != (CROP_W, CROP_H):
        return None, "JPG has a different size"
    hw, hh = CROP_W // 2, CROP_H // 2
    jh = np.asarray(j.resize((hw, hh), Image.BILINEAR), np.float64)
    r = half_rgb(lin)[CROP_Y // 2:CROP_Y // 2 + hh, CROP_X // 2:CROP_X // 2 + hw]
    b = 8                                                            # average 8x8 blocks (alignment, noise)
    bh, bw = hh // b, hw // b
    blk = lambda x: x[:bh * b, :bw * b].reshape(bh, b, bw, b, 3)
    jb, rb = blk(jh), blk(r)
    jm, js, rm = jb.mean((1, 3)), jb.std((1, 3)).mean(-1), rb.mean((1, 3))
    chroma = jm.max(-1) - jm.min(-1)
    if (chroma < 3).mean() > 0.97:
        return None, "JPG is black and white"
    ok = (chroma < 8) & (js < 6) & (jm.mean(-1) > 50) & (jm.max(-1) < 235) & (rb.max((1, 3, 4)) < WHITE * 0.95)
    if ok.sum() < 30:
        return None, f"only {ok.sum()} neutral areas in the JPG"
    s = rm[ok].sum(0)
    return s / s[1], f"{ok.sum()} neutral areas of the JPG"


def neutral_from_camera(lin, jpg_path, fw_path):
    """The camera's own white balance: undo the firmware's colour pipeline on the JPG
    (JPEG YCbCr -> YCbCr matrix -> tone curves -> CCM) and fit per-channel gains to the RAW."""
    from PIL import Image
    fw = open(fw_path, "rb").read()
    dat = lambda a: a - 0x130000 + 0x100200
    mat = lambda a: np.array(struct.unpack_from("<12i", fw, dat(a)), float).reshape(3, 4)
    curve = lambda a: np.frombuffer(fw[dat(a):dat(a) + 1024], np.uint8) / 255
    ymat = mat(0x16CB58)
    tA, tB = curve(0x16BAC8), curve(0x16C0C8)
    j = Image.open(jpg_path).convert("RGB")
    hw, hh = CROP_W // 2, CROP_H // 2
    jh = np.asarray(j.resize((hw, hh), Image.BILINEAR), np.float64)
    ystd = np.array([[0.299, 0.587, 0.114], [-0.168736, -0.331264, 0.5], [0.5, -0.418688, -0.081312]])
    cp = ((jh @ ystd.T + [0, 128, 128]) - ymat[:, 3] / 4) @ np.linalg.inv(ymat[:, :3] / 65536).T / 255
    inv = lambda t, y: np.interp(y, np.maximum.accumulate(t) + np.arange(1024) * 1e-9, np.arange(1024) / 1023)
    x = np.stack([inv(tB, cp[..., 0]), inv(tA, cp[..., 1]), inv(tB, cp[..., 2])], -1) * WHITE
    r = half_rgb(lin)[CROP_Y // 2:CROP_Y // 2 + hh, CROP_X // 2:CROP_X // 2 + hw]
    b = 8
    bh, bw = hh // b, hw // b
    blk = lambda v: v[:bh * b, :bw * b].reshape(bh, b, bw, b, 3)
    jb, rb, xb = blk(jh), blk(r), blk(x)
    ok = (jb.std((1, 3)).mean(-1) < 4) & (jb.mean((1, 3)).max(-1) < 245) & (jb.mean((1, 3)).min(-1) > 4) \
        & (rb.max((1, 3, 4)) < WHITE * 0.95)
    if ok.sum() < 200:
        return None, f"only {ok.sum()} usable areas"
    rm, xm = rb.mean((1, 3))[ok], xb.mean((1, 3))[ok]
    best = None
    for a in (0x16CAC8, 0x16CAF8, 0x16CB28):                       # the 3 illuminant CCMs
        c = xm @ np.linalg.inv(mat(a)[:, :3] / 65536).T             # what entered the CCM
        g = (c * rm).sum(0) / (rm * rm).sum(0)                      # per-channel gain, least squares
        e = ((c - rm * g) ** 2).sum()
        if best is None or e < best[0]:
            best = (e, g)
    return 1 / best[1], f"the camera (fitted against the JPG with {os.path.relpath(fw_path)})"


def neutral_grey_world(lin):
    r = half_rgb(lin)
    ok = r.max(-1) < WHITE * 0.95
    s = r[ok].sum(0)
    return s / s[1]


# ------------------------------------------------------------------ DNG (TIFF) writer
SHORT, LONG, RATIONAL, SRATIONAL, BYTE, ASCII = 3, 4, 5, 10, 1, 2


def rat(x, den=1000000):
    return (int(round(x * den)), den)


def write_dng(path, data, tags):
    """data: uint16 HxW CFA. tags: {tag: (type, values)}; strip offsets are filled in here."""
    img = data.astype("<u2").tobytes()
    entries = dict(tags)
    entries[273] = (LONG, [0])                       # StripOffsets (patched below)
    entries[279] = (LONG, [len(img)])
    blobs, ifd = [], []
    n = len(entries)
    ifd_size = 2 + n * 12 + 4
    extra_off = 8 + ifd_size

    def pack_vals(t, v):
        if t == ASCII:
            b = v.encode("ascii") + b"\0"
            return b, len(b)
        if t == BYTE:
            return bytes(v), len(v)
        if t == SHORT:
            return struct.pack(f"<{len(v)}H", *v), len(v)
        if t == LONG:
            return struct.pack(f"<{len(v)}I", *v), len(v)
        if t == RATIONAL:
            return b"".join(struct.pack("<II", *p) for p in v), len(v)
        if t == SRATIONAL:
            return b"".join(struct.pack("<ii", *p) for p in v), len(v)
        raise ValueError(t)

    packed = {}
    for tag in sorted(entries):
        t, v = entries[tag]
        b, count = pack_vals(t, v)
        packed[tag] = (t, b, count)
    off = extra_off
    placed = {}
    for tag, (t, b, count) in packed.items():
        if len(b) > 4:
            placed[tag] = off
            blobs.append(b + (b"\0" if len(b) % 2 else b""))
            off += len(blobs[-1])
    img_off = off
    t, _, count = packed[273]
    packed[273] = (t, struct.pack("<I", img_off), count)
    out = bytearray(b"II*\0" + struct.pack("<I", 8) + struct.pack("<H", n))
    for tag, (t, b, count) in packed.items():
        if tag in placed:
            out += struct.pack("<HHII", tag, t, count, placed[tag])
        else:
            out += struct.pack("<HHI", tag, t, count) + b.ljust(4, b"\0")
    out += struct.pack("<I", 0)
    for b in blobs:
        out += b
    assert len(out) == img_off
    out += img
    with open(path, "wb") as f:
        f.write(out)


def exif_from_jpg(jpg_path):
    from PIL import Image
    e = Image.open(jpg_path).getexif()
    x = e.get_ifd(0x8769)
    return dict(make=e.get(271), model=e.get(272), date=x.get(36867), exposure=x.get(33434), fnumber=x.get(33437),
                iso=x.get(34855), focal=x.get(37386))


def convert(raw_path, outdir, wb, use_jpg, fw=None):
    folder, name = os.path.split(raw_path)
    m = re.match(r"(?i)ccdi(\d{4})\.raw$", name)
    num = m.group(1) if m else os.path.splitext(name)[0]
    jpgs = [p for p in glob.glob(os.path.join(folder, "*.JPG")) + glob.glob(os.path.join(folder, "*.jpg"))
            if re.search(rf"_{num}\.jpe?g$", p, re.I)] if m else []
    jpg = jpgs[0] if jpgs else None
    base = os.path.splitext(os.path.basename(jpg))[0] if jpg else f"100_{num}"
    lin = read_ccdi(raw_path).astype(np.int32)

    notes = []
    blacks = [p for p in glob.glob(os.path.join(folder, "*")) if re.fullmatch(rf"(?i)blac{num}\.raw", os.path.basename(p))]
    if blacks:
        lin = np.clip(lin - read_ccdi(blacks[0]).astype(np.int32), 0, WHITE)
        notes.append(f"black frame {os.path.basename(blacks[0])} subtracted")
    lin = lin.astype(np.uint16)

    if wb is not None and wb != "grey":
        neutral, why = 1 / np.asarray(wb, float), "--wb gains"
    else:
        neutral, why = (None, "")
        if wb is None and use_jpg and jpg:
            neutral, why = neutral_from_jpg(lin, jpg)
            if why == "JPG is black and white":
                neutral = None
            elif fw and os.path.exists(fw):
                n2, why2 = neutral_from_camera(lin, jpg, fw)
                if n2 is not None:
                    neutral, why = n2, why2
        if neutral is None and wb == "grey":
            why = "grey world (--wb grey)"
            neutral = neutral_grey_world(lin)
        elif neutral is None:
            why = f"the camera's typical daylight setting ({why or 'no JPG'})"
            neutral = DAYLIGHT_NEUTRAL.copy()
    neutral = neutral / neutral[1]
    notes.append(f"white balance from {why}: neutral R {neutral[0]:.3f} B {neutral[2]:.3f}")

    fm = SRGB_XYZ_D50 @ CCM
    cm = np.linalg.inv(SRGB_XYZ_D65 @ CCM @ np.diag(1 / DAYLIGHT_NEUTRAL))
    cm = cm / (cm @ SRGB_XYZ_D65 @ np.ones(3)).max()                 # DNG convention: brightest channel of white = 1
    ex = exif_from_jpg(jpg) if jpg else {}
    tags = {
        254: (LONG, [0]), 256: (LONG, [W]), 257: (LONG, [H]), 258: (SHORT, [16]), 259: (SHORT, [1]),
        262: (SHORT, [32803]), 271: (ASCII, ex.get("make") or "EASTMAN KODAK COMPANY"),
        272: (ASCII, ex.get("model") or "KODAK EASYSHARE C713 ZOOM DIGITAL CAMERA"),
        274: (SHORT, [1]), 277: (SHORT, [1]), 278: (LONG, [H]), 284: (SHORT, [1]),
        305: (ASCII, "ccdi2dng (kodak C713 mods)"),
        33421: (SHORT, [2, 2]), 33422: (BYTE, [0, 1, 1, 2]),
        50706: (BYTE, [1, 4, 0, 0]), 50707: (BYTE, [1, 1, 0, 0]),
        50708: (ASCII, "Kodak EasyShare C713 (CCDI)"),
        50710: (BYTE, [0, 1, 2]), 50711: (SHORT, [1]),
        50713: (SHORT, [1, 1]), 50714: (LONG, [0]), 50717: (LONG, [WHITE]),
        50719: (LONG, [CROP_X, CROP_Y]), 50720: (LONG, [CROP_W, CROP_H]),
        50721: (SRATIONAL, [rat(v) for v in cm.reshape(-1)]),
        50728: (RATIONAL, [rat(v) for v in neutral]),
        50778: (SHORT, [21]),                                          # D65
        50964: (SRATIONAL, [rat(v) for v in fm.reshape(-1)]),
    }
    if ex.get("date"):
        tags[306] = (ASCII, ex["date"]); tags[36867] = (ASCII, ex["date"])
    for tag, key in ((33434, "exposure"), (33437, "fnumber"), (37386, "focal")):
        if ex.get(key):
            tags[tag] = (RATIONAL, [rat(float(ex[key]), 1000000 if float(ex[key]) < 1 else 1000)])
    if ex.get("iso"):
        tags[34855] = (SHORT, [int(ex["iso"])])
    out = os.path.join(outdir or folder, base + ".DNG")
    write_dng(out, lin, tags)
    print(f"{raw_path} -> {out}" + "".join(f"\n    {n}" for n in notes))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--outdir")
    ap.add_argument("--wb", help="R,G,B white-balance gains, or 'grey' for grey-world (default: from the JPG)")
    ap.add_argument("--no-jpg", action="store_true", help="don't read the matching JPG (WB, exposure info)")
    ap.add_argument("--fw", default=DEFAULT_FW,
                    help="firmware the photos were taken with, to read the camera's white balance "
                         "(default: %(default)s)")
    a = ap.parse_args()
    wb = None if a.wb is None else ("grey" if a.wb == "grey" else [float(x) for x in a.wb.split(",")])
    files = []
    for p in a.inputs:
        files += sorted(f for f in glob.glob(os.path.join(p, "*")) if re.fullmatch(r"(?i)ccdi\d{4}\.raw", os.path.basename(f))) \
            if os.path.isdir(p) else [p]
    if not files:
        sys.exit("no CCDInnnn.RAW files found")
    if a.outdir:
        os.makedirs(a.outdir, exist_ok=True)
    for f in files:
        convert(f, a.outdir, wb, not a.no_jpg, a.fw)


if __name__ == "__main__":
    main()
