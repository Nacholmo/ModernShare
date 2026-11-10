#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Read the graphics section (rec2, RAM 0x1a0000) of a KC713 firmware.

Shared by the UI-overhaul tools. See NOTES.md "Graphics".
"""
import struct

GFX_FILE, GFX_RAM, GFX_SIZE = 0x144C00, 0x1A0000, 0x4FC00
PAL = 0x1CB83C
ID_TABLE = 0x1CCF50
FONT_TABLE = GFX_RAM + 0x90


class Gfx:
    def __init__(self, fw):
        self.fw = fw if isinstance(fw, (bytes, bytearray)) else open(fw, "rb").read()
        self.g = self.fw[GFX_FILE:GFX_FILE + GFX_SIZE]

    def inside(self, a, n=1):
        return GFX_RAM <= a and a + n <= GFX_RAM + GFX_SIZE

    def u32(self, a):
        return struct.unpack_from("<I", self.g, a - GFX_RAM)[0]

    def rec(self, a):
        w, h, stride, bpp, flags, pal, data = struct.unpack_from("<HHHHIII", self.g, a - GFX_RAM)
        return dict(addr=a, w=w, h=h, stride=stride, bpp=bpp, flags=flags, pal=pal, data=data)

    def palette(self, a=PAL):
        o = a - GFX_RAM
        return [tuple(self.g[o + 4 * i:o + 4 * i + 4]) for i in range(256)]

    def file_off(self, a):
        """RAM address -> firmware file offset (code, data or graphics section)."""
        if a >= GFX_RAM:
            return a - GFX_RAM + GFX_FILE
        return a - 0x130000 + 0x100200 if a >= 0x130000 else a - 0x30000 + 0x200

    def rle(self, dat, n):
        """Decode n pixels; returns (pixels, stream length).

        The stream may live outside the graphics section (the fullscreen mod moved
        image 1's data to the code zero run), so read through the whole file.
        """
        g, p, out = self.fw, self.file_off(dat), bytearray()
        start = p
        while len(out) < n:
            c = g[p]; p += 1; L = c >> 1
            if c & 1:
                out += g[p:p + L]; p += L
            else:
                out += bytes([g[p]]) * L; p += 1
        return bytes(out[:n]), p - start

    def pixels(self, r):
        """8-bit index pixels (row-major, w*h) and stored byte length."""
        n = r["w"] * r["h"]
        if r["bpp"] == 8:
            if r["flags"] & 1:
                return self.rle(r["data"], n)
            o = r["data"] - GFX_RAM
            rows = [self.g[o + y * r["stride"]:o + y * r["stride"] + r["w"]] for y in range(r["h"])]
            return b"".join(rows), r["stride"] * r["h"]
        if r["bpp"] == 1:
            o = r["data"] - GFX_RAM
            out = bytearray()
            for y in range(r["h"]):
                row = self.g[o + y * r["stride"]:o + (y + 1) * r["stride"]]
                out += bytes((row[x >> 3] >> (7 - (x & 7))) & 1 for x in range(r["w"]))
            return bytes(out), r["stride"] * r["h"]
        raise ValueError(f"bpp {r['bpp']}")

    def ids(self, count):
        return [self.u32(ID_TABLE + 4 * i) for i in range(count)]

    def glyph(self, code):
        """(record, xoff, yoff, rows) of a Latin glyph; rows = list of 0/1 lists."""
        a = self.u32(GFX_RAM + 0x10 + 4 * code)
        if not a:
            return None
        r = self.rec(a)
        o = self.file_off(r["data"])
        xo, yo, w, h = self.fw[o:o + 4]
        st = (w + 7) // 8
        rows = [[(self.fw[o + 4 + y * st + (x >> 3)] >> (7 - (x & 7))) & 1 for x in range(w)]
                for y in range(h)]
        return r, xo, yo, rows
