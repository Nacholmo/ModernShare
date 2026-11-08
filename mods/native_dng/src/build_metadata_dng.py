#!/usr/bin/env python3
"""Add per-shot EXIF to the camera-confirmed direct-DNG firmware; preserve v1."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from make_dng import ROOT, make_header
from metadata_header import make_metadata_header, mutable_ranges
sys.path.insert(0, str(ROOT / 'tools'))
import kodakfw

BASE_SHA = '8dce21de78bf28f2a3c8a029f40dd8ae84a5ee0c517c28080d1a67148199fd5e'
HEADER, META, SITE = 0x1241A0, 0x12FF40, 0xA4290
TOOLS = ROOT / 'decompiler-project/tools/binutils'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def assemble(src, directory, name, address):
    obj, binary = directory / (name + '.o'), directory / (name + '.bin')
    subprocess.run([str(TOOLS / 'arc-elf32-as'), '-mcpu=arc700', '-I', str(directory), str(src), '-o', str(obj)], check=True)
    subprocess.run([str(TOOLS / 'arc-elf32-objcopy'), '-O', 'binary', str(obj), str(binary)], check=True)
    text = subprocess.check_output([str(TOOLS / 'arc-elf32-objdump'), '-d', '-M', 'cpu=arc700',
                                   f'--adjust-vma={address:#x}', str(obj)], text=True)
    (directory / (name + '.asm')).write_text(text)
    assert 'R_ARC_' not in subprocess.check_output([str(TOOLS / 'arc-elf32-objdump'), '-r', str(obj)], text=True)
    return binary.read_bytes()


def build(base, out):
    original = base.read_bytes()
    if sha(original) != BASE_SHA or kodakfw.check(original):
        raise ValueError('base must be the camera-confirmed, checksum-valid 8dce21de firmware')
    out.mkdir(parents=True, exist_ok=True)
    target = out / 'KC713.FW'
    if target.exists():
        raise FileExistsError('use a fresh output firmware directory')
    header, layout = make_metadata_header()
    (out / 'header.bin').write_bytes(header)
    (out / 'header-layout.json').write_text(json.dumps(layout, indent=2) + '\n')
    (out / 'metadata_offsets.inc').write_text(''.join(f'.equ H_{k}, {v}\n' for k, v in layout.items()))
    source = Path(__file__).with_name('metadata.s')
    code = assemble(source, out, 'metadata', META)
    (out / 'callsite.s').write_text(f'.text\n.global start\nstart:\n bl start + ({META:#x} - {SITE:#x})\n')
    call = assemble(out / 'callsite.s', out, 'callsite', SITE)
    assert len(call) == 4 and META + len(code) <= 0x130000 and len(header) == 1536
    image = bytearray(original)
    patches = []

    def put(at, expected, value, why):
        assert len(expected) == len(value)
        off = kodakfw.ram_to_file(image, at)
        if image[off:off + len(value)] != expected:
            raise ValueError(f'{at:#x}: expected bytes differ')
        image[off:off + len(value)] = value
        patches.append({'address': hex(at), 'file_offset': off, 'length': len(value), 'reason': why,
                        'old_sha256': sha(expected), 'new_sha256': sha(value)})

    assert original[kodakfw.ram_to_file(original, META):0x100200] == bytes(0x130000 - META)
    put(HEADER, make_header(), header, 'Same-size DNG header with DateTime and an EXIF sub-IFD')
    put(META, bytes(len(code)), code, 'Wrap stock capture EXIF builder; copy per-shot values')
    put(SITE, bytes.fromhex('c971ddfd'), call, 'Replace mov r1,r14 + short call with wrapper call')
    kodakfw.fix(image)
    assert not kodakfw.check(image) and len(image) == len(original)
    allowed = set(range(0x1F4, 0x1FC))
    for patch in patches:
        allowed.update(range(patch['file_offset'], patch['file_offset'] + patch['length']))
    for rec in kodakfw.records(original):
        if rec['dest'] == 0x30000:
            allowed.update(range(0x10 + rec['idx'] * 16 + 12, 0x10 + rec['idx'] * 16 + 16))
    changed = [i for i, (x, y) in enumerate(zip(original, image)) if x != y]
    assert all(i in allowed for i in changed)
    for at, size in [(0x67898, 6), (0x125a00, 544), (0x12ff00, 0x34)]:
        off = kodakfw.ram_to_file(image, at)
        assert image[off:off + size] == original[off:off + size], 'existing hook changed'
    with target.open('xb') as f:
        f.write(image)
    (out / 'code.bin').write_bytes(image[0x200:0x100200])
    # The unchanged v1 writer is retained for the existing 18-case regression script.
    off = kodakfw.ram_to_file(image, 0x125a00)
    (out / 'hook.bin').write_bytes(image[off:off + 544])
    manifest = {'status': 'experimental metadata v2; not camera-tested', 'base': str(base.relative_to(ROOT)),
        'base_sha256': BASE_SHA, 'firmware_sha256': sha(image), 'firmware_bytes': len(image),
        'header_bytes': len(header), 'header_sha256': sha(header), 'metadata_hook_bytes': len(code),
        'metadata_hook_sha256': sha(code), 'metadata_source_sha256': sha(source.read_bytes()),
        'header_layout': layout, 'mutable_header_ranges': mutable_ranges(layout),
        'patches': patches, 'changed_bytes': len(changed), 'checksums': kodakfw.check(image),
        'source_fields': {'date_tm': 'JPEG EXIF input +0x0c', 'exposure_us': '+0x48 (after stock clamp)',
                          'fnumber_100': '+0x4c', 'iso': '+0x60'},
        'limitations': ['fixed daylight WB retained', 'no embedded preview',
                        'timestamp follows camera clock; no timezone inference']}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (out / 'SHA256SUMS').write_text(f'{sha(image)}  KC713.FW\n')
    print(f'{target}: {sha(image)}; {len(code)} metadata bytes; checksums OK')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base', type=Path, default=ROOT / 'mods/native_dng/test-v1/KC713.FW')
    ap.add_argument('--outdir', required=True, type=Path)
    a = ap.parse_args()
    build(a.base.resolve(), a.outdir.resolve())
