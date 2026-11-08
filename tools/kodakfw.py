#!/usr/bin/env python3
"""Inspect, verify, patch and re-checksum Kodak EasyShare C713/C813 (Altek "RHIR") firmware images.

Format (reverse engineered from kc713.fw / kc813.fw v1.30 and the camera's own updater at 0xFE304):

  0x000  "RHIR"
  0x006  u8   number of section records
  0x008  u32  (value & 0xFFFF00) must equal 0x034200 for C713 (byte 9 = 0x42 model/MCU id; C813 = 0x43)
  0x00C  u16  MAIN version major, u16 minor  (1, 3000 -> "1.3000")
  0x010  records, 16 bytes each:
           u32 type   (1 = checked by the updater, 0 = not checked, 2 = special)
           u16 start  sector (512 B) in this file
           u16 count  sectors
           u32 dest   RAM load address
           u32 sum    32-bit little-endian word sum of the section bytes
  0x1F0  "KHIR"
  0x1F4  u32  sum32 of header bytes 0x000..0x1EF
  0x1F8  u32  bitwise NOT of the above
  0x1FC  u16  CamOS version major, u16 minor
  0x200  section data
"""
import argparse
import struct
import sys

MAGIC = b"RHIR"
KMAGIC = b"KHIR"


def sum32(b: bytes) -> int:
    n = len(b) // 4
    s = sum(struct.unpack_from("<%dI" % n, b)) if n else 0
    tail = b[n * 4:]
    if tail:
        s += struct.unpack("<I", tail.ljust(4, b"\0"))[0]
    return s & 0xFFFFFFFF


def records(d: bytes):
    out = []
    for i in range(d[6]):
        t, st, n, dest, ck = struct.unpack_from("<IHHII", d, 0x10 + 16 * i)
        out.append(dict(idx=i, type=t, start=st, count=n, dest=dest, sum=ck, off=st * 512, size=n * 512))
    return out


def check(d: bytes, model_word=0x034200):
    """Return a list of problems (empty == OK). Mirrors the camera's validator plus stricter extra checks."""
    p = []
    if d[:4] != MAGIC:
        p.append("bad RHIR magic")
    w8 = struct.unpack_from("<I", d, 8)[0]
    if (w8 & 0xFFFF00) != model_word:
        p.append(f"model word {w8 & 0xFFFF00:#x} != {model_word:#x} (camera rejects this)")
    for r in records(d):
        if r["type"] not in (0, 1):   # type 2 is not a checksummed data section; leave it untouched
            continue
        if r["off"] + r["size"] > len(d):
            p.append(f"record {r['idx']} runs past end of file")
            continue
        s = sum32(d[r["off"]:r["off"] + r["size"]])
        if s != r["sum"]:
            who = "camera rejects" if r["type"] == 1 else "not checked by updater, may be checked at boot"
            p.append(f"record {r['idx']} sum {r['sum']:#010x} != computed {s:#010x} ({who})")
    if d[0x1F0:0x1F4] != KMAGIC:
        p.append("bad KHIR magic")
    k1, k2 = struct.unpack_from("<II", d, 0x1F4)
    h = sum32(d[:0x1F0])
    if k1 != h or k2 != (~h & 0xFFFFFFFF):
        p.append(f"KHIR header sum {k1:#010x}/{k2:#010x} != {h:#010x}/{~h & 0xFFFFFFFF:#010x}")
    return p


def fix(d: bytearray):
    for r in records(d):
        if r["type"] not in (0, 1):
            continue
        s = sum32(bytes(d[r["off"]:r["off"] + r["size"]]))
        struct.pack_into("<I", d, 0x10 + 16 * r["idx"] + 12, s)
    h = sum32(bytes(d[:0x1F0]))
    struct.pack_into("<II", d, 0x1F4, h, ~h & 0xFFFFFFFF)


def cmd_info(a):
    d = open(a.fw, "rb").read()
    print(f"{a.fw}: {len(d)} bytes, model byte {d[9]:#04x}, MAIN {struct.unpack_from('<HH', d, 0xC)}, "
          f"CamOS {struct.unpack_from('<HH', d, 0x1FC)}")
    for r in records(d):
        print(f"  rec{r['idx']} type {r['type']} file {r['off']:#08x}+{r['size']:#08x} -> RAM {r['dest']:#08x} sum {r['sum']:#010x}")
    probs = check(d)
    print("  verify:", "OK" if not probs else "")
    for x in probs:
        print("   -", x)
    return 1 if probs else 0


def cmd_replace(a):
    d = bytearray(open(a.fw, "rb").read())
    if check(d):
        sys.exit("input image does not verify; refusing to patch")
    old, new = a.old.encode("latin1"), a.new.encode("latin1")
    if len(new) > len(old):
        sys.exit(f"new text is {len(new)} bytes, longer than old ({len(old)}); strings cannot grow in place")
    # only whole NUL-terminated strings, never substrings of longer text
    hits, i = [], 0
    while (i := d.find(old + b"\0", i)) != -1:
        if i == 0 or d[i - 1] == 0:
            hits.append(i)
        i += 1
    if not hits:
        sys.exit("text not found as a whole string")
    for h in hits:
        d[h:h + len(old)] = new + b"\0" * (len(old) - len(new))
        print(f"  patched {h:#08x}")
    fix(d)
    probs = check(d)
    if probs:
        sys.exit("output failed verification: " + "; ".join(probs))
    open(a.out, "wb").write(d)
    print(f"wrote {a.out} ({len(hits)} occurrence(s)); verifies OK")


def cmd_fix(a):
    d = bytearray(open(a.fw, "rb").read())
    fix(d)
    open(a.out, "wb").write(d)
    probs = check(d)
    print("verify:", "OK" if not probs else probs)


def ram_to_file(d: bytes, addr: int) -> int:
    for r in records(d):
        if r["type"] in (0, 1) and r["dest"] <= addr < r["dest"] + r["size"]:
            return r["off"] + addr - r["dest"]
    raise ValueError(f"RAM address {addr:#x} is not inside any loaded section")


def cmd_patch(a):
    """Apply one or more ADDR:EXPECTED:NEW byte patches (RAM addresses, hex bytes) and re-checksum."""
    d = bytearray(open(a.fw, "rb").read())
    if check(d):
        sys.exit("input image does not verify; refusing to patch")
    for spec in a.patches:
        addr_s, old_s, new_s = spec.split(":")
        addr, old, new = int(addr_s, 16), bytes.fromhex(old_s), bytes.fromhex(new_s)
        if len(old) != len(new):
            sys.exit(f"{spec}: expected and new bytes must be the same length")
        o = ram_to_file(d, addr)
        if bytes(d[o:o + len(old)]) != old:
            sys.exit(f"{spec}: found {bytes(d[o:o + len(old)]).hex()} at RAM {addr:#x} (file {o:#x}), expected {old.hex()}")
        d[o:o + len(new)] = new
        print(f"  RAM {addr:#08x} (file {o:#08x}): {old.hex()} -> {new.hex()}")
    fix(d)
    probs = check(d)
    if probs:
        sys.exit("output failed verification: " + "; ".join(probs))
    open(a.out, "wb").write(d)
    print(f"wrote {a.out}; verifies OK")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("patch", help="patch bytes at RAM addresses: ADDR:EXPECTEDHEX:NEWHEX ...")
    s.add_argument("fw"); s.add_argument("patches", nargs="+"); s.add_argument("-o", "--out", required=True)
    s.set_defaults(f=cmd_patch)
    s = sp.add_parser("info"); s.add_argument("fw"); s.set_defaults(f=cmd_info)
    s = sp.add_parser("replace", help="replace a whole NUL-terminated string (same length or shorter)")
    s.add_argument("fw"); s.add_argument("old"); s.add_argument("new"); s.add_argument("-o", "--out", required=True)
    s.set_defaults(f=cmd_replace)
    s = sp.add_parser("fix", help="recompute all section sums and the KHIR header sum")
    s.add_argument("fw"); s.add_argument("-o", "--out", required=True); s.set_defaults(f=cmd_fix)
    a = ap.parse_args()
    sys.exit(a.f(a) or 0)


if __name__ == "__main__":
    main()
