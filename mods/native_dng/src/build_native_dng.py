#!/usr/bin/env python3
"""Build an asserted, isolated direct-DNG experiment from the confirmed firmware."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

from make_dng import ROOT, make_header
sys.path.insert(0, str(ROOT / 'tools'))
import kodakfw

BASE_SHA = '4765fbbbc64c4fb3db63c3ee4c5227ebe023a3678f9c9c81ea009642ce3a2630'
ENTRY, HEADER, HOOK, LOG = 0x67898, 0x1241A0, 0x125A00, 0x125CC0
TOOLS = ROOT / 'decompiler-project/tools/binutils'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def branch(at, target):
    delta = target - (at & ~3)
    if delta & 1 or not -(1 << 24) <= delta < (1 << 24):
        raise ValueError('invalid branch displacement')
    off = delta >> 1
    word = (1 << 16) | ((off & 0x3ff) << 17) | (((off >> 10) & 0x3ff) << 6) | ((off >> 20) & 0xf)
    return struct.pack('<HH', word >> 16, word & 0xffff)


def build(base, outdir):
    original = base.read_bytes()
    if sha(original) != BASE_SHA or kodakfw.check(original):
        raise ValueError('base is not the confirmed, checksum-valid 4765fbbb firmware')
    outdir.mkdir(parents=True, exist_ok=True)
    target = outdir / 'KC713.FW'
    if target.exists():
        raise FileExistsError(f'{target}: use a fresh build directory')
    src = Path(__file__).with_name('hook.s')
    obj, binary = outdir / 'hook.o', outdir / 'hook.bin'
    subprocess.run([str(TOOLS / 'arc-elf32-as'), '-mcpu=arc700', str(src), '-o', str(obj)], check=True)
    subprocess.run([str(TOOLS / 'arc-elf32-objcopy'), '-O', 'binary', str(obj), str(binary)], check=True)
    asm = subprocess.check_output([str(TOOLS / 'arc-elf32-objdump'), '-d', '-M', 'cpu=arc700',
                  '--adjust-vma=0x125a00', str(obj)], text=True)
    (outdir / 'hook.asm').write_text(asm)
    relocs = subprocess.check_output([str(TOOLS / 'arc-elf32-objdump'), '-r', str(obj)], text=True)
    if 'R_ARC_' in relocs:
        raise ValueError('unresolved assembly relocations')
    code, header = binary.read_bytes(), make_header()
    assert len(header) == 1536 and HEADER + len(header) <= 0x124800
    assert HOOK + len(code) <= LOG and LOG + 40 <= 0x125CF0
    image = bytearray(original)
    patches = []

    def put(address, expected, value, reason):
        offset = kodakfw.ram_to_file(image, address)
        if image[offset:offset + len(expected)] != expected:
            raise ValueError(f'{address:#x}: expected bytes differ')
        assert len(expected) == len(value)
        image[offset:offset + len(value)] = value
        patches.append({'address': hex(address), 'file_offset': offset, 'length': len(value),
                        'reason': reason, 'old_sha256': sha(expected), 'new_sha256': sha(value)})

    # Require the entire candidate allocation to be zero, including safety margins and log.
    for start, end in ((HEADER, 0x124800), (HOOK, 0x125CF0)):
        offset = kodakfw.ram_to_file(image, start)
        assert image[offset:offset + end - start] == bytes(end - start), f'{start:#x}: cave occupied'
    put(HEADER, bytes(len(header)), header, 'Fixed DNG header; original sensor buffer follows on disk')
    put(HOOK, bytes(len(code)), code, 'Conditional DNG writer and stock fallback')
    put(ENTRY, bytes.fromhex('f1c0460d8059'), branch(ENTRY, HOOK) + bytes.fromhex('e078'),
        'Replace push/call prologue with branch and nop; fallback replays prologue')
    before_checksum = bytes(image)
    kodakfw.fix(image)
    assert not kodakfw.check(image)
    allowed = set()
    for p in patches:
        allowed.update(range(p['file_offset'], p['file_offset'] + p['length']))
    # Only the checked code-section sum and header checksum pair may differ outside patches.
    for record in kodakfw.records(original):
        if record['dest'] == 0x30000:
            allowed.update(range(0x10 + record['idx'] * 16 + 12, 0x10 + record['idx'] * 16 + 16))
    allowed.update(range(0x1F4, 0x1FC))
    changes = [i for i, (a, b) in enumerate(zip(original, image)) if a != b]
    assert all(i in allowed for i in changes) and len(image) == len(original)
    with target.open('xb') as f:
        f.write(image)
    (outdir / 'header.bin').write_bytes(header)
    (outdir / 'code.bin').write_bytes(image[0x200:0x100200])
    manifest = {'status': 'experimental; not camera-tested', 'base': str(base.relative_to(ROOT)),
        'base_sha256': BASE_SHA, 'firmware_sha256': sha(image), 'firmware_bytes': len(image),
        'source_sha256': sha(src.read_bytes()), 'hook_sha256': sha(code), 'hook_bytes': len(code),
        'header_sha256': sha(header), 'header_bytes': len(header), 'dng_bytes': 7096320 + len(header),
        'patches': patches, 'changed_bytes': len(changes), 'checksums': kodakfw.check(image),
        'diagnostics': {'address': hex(LOG), 'u32_fields': ['magic', 'attempts', 'phase', 'first_error',
            'input_bytes', 'header_written', 'payload_written', 'close_error', 'buffer_pointer', 'reserved']},
        'limitations': ['fixed daylight WB', 'no dynamic EXIF or embedded preview',
                        'separate black-frame RAW retained; no subtraction in camera',
                        'non-main or non-7096320-byte calls use original RAW writer']}
    (outdir / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (outdir / 'SHA256SUMS').write_text(f'{sha(image)}  KC713.FW\n')
    print(f'{target}: {sha(image)}; {len(code)} hook bytes; checksums OK')
    return manifest


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base', type=Path, default=ROOT / 'mods/date_fix/stock_color_neopan/KC713.FW')
    ap.add_argument('--outdir', type=Path, required=True)
    a = ap.parse_args()
    build(a.base.resolve(), a.outdir.resolve())
