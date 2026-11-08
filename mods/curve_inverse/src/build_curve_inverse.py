#!/usr/bin/env python3
"""Rewrite the two curve "companion" tables as the inverse of the current curve B.

Usage: build_curve_inverse.py BASE_FW OUT_FW [--no-flash]

The decompiler workspace showed that 0x16bec8 / 0x16c4c8 (pipeline struct +4 / +0xc, 256 x u16)
are both the inverse of stock curve B 0x16c0c8 (8-bit -> 10-bit; the midpoint of each output
level's input range reproduces stock to 0.2 on average). Builds that rewrote the curves left
these stale, which is the current hypothesis for the lavender whites. This rebuilds them from
the base firmware's own curve B, and (unless --no-flash) also sets flash Off in every mode.
"""
import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "../../..")
sys.path[:0] = [os.path.join(ROOT, "tools"), os.path.join(ROOT, "mods/flash_all_off/src")]
import kodakfw               # noqa: E402

DATA = lambda a: a - 0x130000 + 0x100200
CURVE_B, COMP_A, COMP_B = 0x16C0C8, 0x16BEC8, 0x16C4C8


def inverse(curve):
    """256 x u16: for each 8-bit output level, the middle 10-bit input that produces it."""
    c = np.maximum.accumulate(curve)                     # guard against non-monotonic curves
    lo = np.searchsorted(c, np.arange(256), "left")
    hi = np.searchsorted(c, np.arange(256), "right") - 1
    inv = (lo + hi) // 2
    inv[hi < lo] = lo[hi < lo]                           # level never produced: next input up
    return np.clip(inv, 0, 1023).astype("<u2")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("base"); ap.add_argument("out")
    ap.add_argument("--no-flash", action="store_true")
    a = ap.parse_args()
    d = bytearray(open(a.base, "rb").read())
    stock = open(os.path.join(ROOT, "firmware/stock/kc713.fw"), "rb").read()
    sB = np.frombuffer(stock[DATA(CURVE_B):DATA(CURVE_B) + 1024], np.uint8).astype(int)
    sK = np.frombuffer(stock[DATA(COMP_A):DATA(COMP_A) + 512], "<u2").astype(int)
    assert np.abs(inverse(sB).astype(int) - sK).mean() < 0.5, "inverse rule does not reproduce stock"
    for t in (COMP_A, COMP_B):
        assert d[DATA(t):DATA(t) + 512] == stock[DATA(t):DATA(t) + 512], f"{t:#x} already modified"
    B = np.frombuffer(bytes(d[DATA(CURVE_B):DATA(CURVE_B) + 1024]), np.uint8).astype(int)
    inv = inverse(B)
    for t in (COMP_A, COMP_B):
        d[DATA(t):DATA(t) + 512] = inv.tobytes()
    print("companions rewritten; inverse at levels 64/128/200/250:", inv[[64, 128, 200, 250]].tolist(),
          "(stock", sK[[64, 128, 200, 250]].tolist(), ")")
    if not a.no_flash:
        import patch as flash
        print(f"flash: {flash.apply(d)} reset values changed")
    kodakfw.fix(d)
    assert not kodakfw.check(d)
    open(a.out, "wb").write(d)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
