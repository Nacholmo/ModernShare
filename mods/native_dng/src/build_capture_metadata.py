#!/usr/bin/env python3
"""Fix metadata timing using the active capture record before the DNG header write."""
import argparse
import json
from pathlib import Path
import re

from build_metadata_dng import BASE_SHA, HEADER, META, assemble, sha, kodakfw, ROOT
from metadata_header import make_metadata_header, mutable_ranges

HOOK, LOG = 0x125A00, 0x125CC0


def build(base, out):
    original = base.read_bytes()
    if sha(original) != BASE_SHA or kodakfw.check(original):
        raise ValueError('base must be the pinned camera-confirmed 8dce21de v1')
    out.mkdir(parents=True, exist_ok=True)
    target = out / 'KC713.FW'
    if target.exists():
        raise FileExistsError('use a fresh output firmware directory')
    header, layout = make_metadata_header()
    (out / 'header.bin').write_bytes(header)
    (out / 'header-layout.json').write_text(json.dumps(layout, indent=2) + '\n')
    (out / 'metadata_offsets.inc').write_text(''.join(f'.equ H_{k}, {v}\n' for k, v in layout.items()))
    source = Path(__file__).with_name('capture_metadata.s')
    writer_source = Path(__file__).with_name('hook_capture_metadata.s')
    code = assemble(source, out, 'metadata', META)
    writer = assemble(writer_source, out, 'hook', HOOK)
    assert len(header) == 1536 and META + len(code) <= 0x130000
    assert HOOK + len(writer) <= LOG and len(writer) == 548
    site_match = re.search(r'^\s*([0-9a-f]+):.*\bbl\b[^\n]*;12ff40\b', (out / 'hook.asm').read_text(), re.M)
    assert site_match, 'cannot identify metadata call site'
    site = int(site_match[1], 16)
    image = bytearray(original)
    patches = []

    def put(at, expected, value, reason):
        assert len(expected) == len(value)
        offset = kodakfw.ram_to_file(image, at)
        assert image[offset:offset + len(value)] == expected, hex(at)
        image[offset:offset + len(value)] = value
        patches.append({'address': hex(at), 'file_offset': offset, 'length': len(value),
                        'reason': reason, 'old_sha256': sha(expected), 'new_sha256': sha(value)})

    old_header = (ROOT / 'mods/native_dng/test-v1/header.bin').read_bytes()
    old_writer = (ROOT / 'mods/native_dng/test-v1/hook.bin').read_bytes()
    put(HEADER, old_header, header, 'Same metadata header/layout as v2')
    put(HOOK, old_writer + bytes(len(writer) - len(old_writer)), writer,
        'Insert metadata call before any header write; existing writer and fallback logic retained')
    put(META, bytes(len(code)), code, 'Read current capture record before saving its DNG')
    kodakfw.fix(image)
    allowed = set(range(0x1F4, 0x1FC))
    for p in patches:
        allowed.update(range(p['file_offset'], p['file_offset'] + p['length']))
    for r in kodakfw.records(original):
        if r['dest'] == 0x30000:
            allowed.update(range(0x10 + r['idx'] * 16 + 12, 0x10 + r['idx'] * 16 + 16))
    changed = [i for i, (x, y) in enumerate(zip(original, image)) if x != y]
    assert all(i in allowed for i in changed) and not kodakfw.check(image)
    for at, size in [(0x67898, 6), (0xa4290, 4), (0x12ff00, 0x34)]:
        off = kodakfw.ram_to_file(image, at)
        assert image[off:off + size] == original[off:off + size]
    with target.open('xb') as f:
        f.write(image)
    (out / 'code.bin').write_bytes(image[0x200:0x100200])
    manifest = {'status': 'experimental capture metadata v3; not camera-tested', 'base': str(base.relative_to(ROOT)),
        'base_sha256': BASE_SHA, 'firmware_sha256': sha(image), 'firmware_bytes': len(image),
        'metadata_timing': 'before_raw_write', 'metadata_hook_bytes': len(code),
        'metadata_hook_sha256': sha(code), 'metadata_source_sha256': sha(source.read_bytes()),
        'metadata_callsite_address': hex(site), 'capture_record_pointer': '0x1324fc',
        'writer_source_sha256': sha(writer_source.read_bytes()), 'hook_bytes': len(writer),
        'hook_sha256': sha(writer), 'header_bytes': len(header), 'header_sha256': sha(header),
        'header_layout': layout, 'mutable_header_ranges': mutable_ranges(layout),
        'patches': patches, 'changed_bytes': len(changed), 'checksums': kodakfw.check(image),
        'source_fields': {'date_tm': 'capture +0x64', 'exposure_us': '+0xb0 (minimum 714 us)',
                          'iso': '+0xb4 ushort', 'fnumber': 'stock mapping of +0xf2 byte and +0xf4 ushort'},
        'limitations': ['fixed daylight WB', 'no embedded preview', 'camera clock required',
                        'capture record pointer assumes the two verified stock RAW call sites']}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (out / 'SHA256SUMS').write_text(f'{sha(image)}  KC713.FW\n')
    print(f'{target}: {sha(image)}; helper {len(code)} bytes; writer {len(writer)} bytes; checksums OK')
    return manifest


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base', type=Path, default=ROOT / 'mods/native_dng/test-v1/KC713.FW')
    ap.add_argument('--outdir', type=Path, required=True)
    a = ap.parse_args()
    build(a.base.resolve(), a.outdir.resolve())
