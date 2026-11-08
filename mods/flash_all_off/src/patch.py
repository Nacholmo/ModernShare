#!/usr/bin/env python3
"""Flash defaults to Off in EVERY capture mode (normal mode and all scene slots).

Usage: patch.py IN_FW OUT_FW

The flash setting has 11 slots, bytes 0x132928..0x132932 (struct 0x1328fc + 0x2c..0x36),
one per capture mode. Values are one-hot: 1 = Off, 2 = Red-eye, 4 = Auto, 8 = Fill.
The mode switch (0x3c66a, jump table 0x3c682 indexed by the capture mode 0x1328ff) runs
the mode's reset function; modes without a slot force a value (1, or 4 for Landscape, 8 for
Candle Light). Each slot has a reset function (run at power-on and on mode switches) of the form
    v = slot; slot = (v == KEEP) ? KEEP : DEFAULT        (mov_s r0,2 / mov_s r0,4)
flash_off only changed the first one (0x3bd92). Here both immediates of every reset become
1 (mov_s r0,1 = 0xd801), and the initial slot values in the data section become 1.
You can still turn the flash on by hand; it goes back to Off on the next mode switch or
power-on.
"""
import os
import sys

CODE = lambda a: a - 0x30000 + 0x200
DATA = lambda a: a - 0x130000 + 0x100200
# (address of the two mov_s r0,imm in each reset function); slot in the comment
RESETS = [(0x3bd8e, 0x3bd92),   # +0x2c 0x132928 (normal mode)
          (0x3bda6, 0x3bdaa),   # +0x35 0x132931
          (0x3bdbe, 0x3bdc2),   # +0x2d
          (0x3bdd6, 0x3bdda),   # +0x2e
          (0x3bdee, 0x3bdf2),   # +0x2f (default red-eye)
          (0x3be06, 0x3be0a),   # +0x30 (default red-eye)
          (0x3be1e, 0x3be22),   # +0x31
          (0x3be36, 0x3be3a),   # +0x32
          (0x3be4e, 0x3be52),   # +0x33 (default red-eye)
          (0x3be66, 0x3be6a),   # +0x34
          (0x3cadc, 0x3cae0),   # +0x36 0x132932
          (0x3c6a6, 0x3c6c8)]   # modes with no slot that force a value (mode switch at 0x3c66a):
                                # mode 4 = Landscape (forced 4) and mode 14 = Candle Light (forced 8)
OFF = bytes([0x01, 0xd8])       # mov_s r0,1


def apply(d):
    """Patch bytearray d in place (checksums not fixed). Returns the number of changes."""
    n = 0
    for pair in RESETS:
        for a in pair:
            o = CODE(a)
            old = bytes(d[o:o + 2])
            assert old in (b"\x02\xd8", b"\x04\xd8", b"\x08\xd8", OFF), f"{a:#x}: unexpected {old.hex()}"
            n += old != OFF
            d[o:o + 2] = OFF
    o = DATA(0x132928)
    assert all(v in (1, 2, 4, 8) for v in d[o:o + 11]), "flash slots not where expected"
    d[o:o + 11] = bytes([1] * 11)
    return n


def main():
    src, dst = sys.argv[1:3]
    d = bytearray(open(src, "rb").read())
    n = apply(d)
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../tools"))
    import kodakfw
    kodakfw.fix(d)
    assert not kodakfw.check(d)
    open(dst, "wb").write(d)
    print(f"wrote {dst}: {n} reset immediates changed, 11 flash slots start Off")


if __name__ == "__main__":
    main()
