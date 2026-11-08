#!/usr/bin/env python3
"""Allow years up to 2037 when setting the clock, and start with the date stamp Off.

Usage: build_date_fix.py BASE_FW OUT_FW

Years are stored as year - 1900. Stock limits are 2007..2025 (found with the decompiler project):
  * 0xdc604 and 0xeb020 (the two date-setting screens): year < 2007 wraps to 125 (2025),
    year > 2025 wraps to 107 (2007). -> limit 2037, wrap to 137.
  * 0x7166c (date validator): rejects years outside 2006..2025. -> 2006..2037.
  2037 keeps clear of the 2038 rollover of 32-bit second counters.
Date stamp: setting byte 0x135235 (getter 0x89e90, setter 0x89e98; 0 = Off, 1..3 = formats;
the stamp icon is shown when != 0). It is saved with the other settings and restored at power-on
by 0x3e7a8 (`ldb r0,[r13,0x39]` in the delay slot of `bl.d SetDateStamp`). That load becomes
`mov r0,0`, so every power-on starts with the stamp Off; the menu can still turn it on.
Encodings were checked with the GNU ARC assembler against the stock bytes.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "../../../tools"))
import kodakfw               # noqa: E402

CODE = lambda a: a - 0x30000 + 0x200
PATCHES = [  # address, stock bytes, new bytes, what
    (0x71688, "8c265f9a", "8c265f9d", "validator: cmp r14,2025 -> 2037"),
    (0xdc664, "8c215f8a", "8c215f8d", "date screen 1: cmp r1,2025 -> 2037"),
    (0xdc65e, "7dd8", "89d8", "date screen 1: wrap below 2007 to 2037"),
    (0xeb080, "8c215f8a", "8c215f8d", "date screen 2: cmp r1,2025 -> 2037"),
    (0xeb07a, "7dd8", "89d8", "date screen 2: wrap below 2007 to 2037"),
    (0x3e7dc, "39158010", "4a200000", "power-on: date stamp = 0 (Off) instead of the saved value"),
]


def apply(d):
    for at, old, new, what in PATCHES:
        o, n = bytes.fromhex(old), bytes.fromhex(new)
        assert d[CODE(at):CODE(at) + len(o)] == o, f"{at:#x}: not the stock bytes ({what})"
        d[CODE(at):CODE(at) + len(n)] = n
        print(f"{at:#x}: {what}")


def main():
    base, out = sys.argv[1:3]
    d = bytearray(open(base, "rb").read())
    apply(d)
    kodakfw.fix(d)
    assert not kodakfw.check(d)
    open(out, "wb").write(d)
    print("wrote", out)


if __name__ == "__main__":
    main()
