#!/usr/bin/env python3
"""Save RAW files next to every JPEG by turning on hidden debug save flags at power-on.

Usage: build_raw_plus_jpeg.py BASE_FW OUT_FW [--cfa] [--yrgb]

The hidden menu's save options are RAM bytes initialised from the data section at boot; only
the menu toggles (0xd6c68, 0xd6dfc, 0xd6e3c) and a debug command (0x1072e8) ever change them,
and the save code tests each independently, so JPEG keeps being written:
  --cfa   SaveCFAonTake 0x13358c (getter 0x67888, writer 0x67898 via 0x33c2c): the sensor's
          colour-filter-array data = true RAW (main frame, plus a "black" frame when taken)
  --yrgb  SaveFullYRGB 0x133184 (getter 0x54ec0): processed, uncompressed YCbCr 4:2:0 image
          (YRGBnnnn.RAW, 3056x2292x1.5 bytes), after the colour pipeline
SaveFullJPEG 0x133185 stays 1 (stock).
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "../../../tools"))
import kodakfw               # noqa: E402

DATA = lambda a: a - 0x130000 + 0x100200
FLAGS = {"cfa": 0x13358C, "yrgb": 0x133184}
JPEG = 0x133185


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("base"); ap.add_argument("out")
    for k in FLAGS:
        ap.add_argument("--" + k, action="store_true")
    a = ap.parse_args()
    d = bytearray(open(a.base, "rb").read())
    assert d[DATA(JPEG)] == 1, "JPEG saving is not on in the base"
    for k, addr in FLAGS.items():
        assert d[DATA(addr)] == 0, f"{k} flag {addr:#x} is not stock"
        if getattr(a, k):
            d[DATA(addr)] = 1
            print(f"{k}: {addr:#x} = 1")
    kodakfw.fix(d)
    assert not kodakfw.check(d)
    open(a.out, "wb").write(d)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
