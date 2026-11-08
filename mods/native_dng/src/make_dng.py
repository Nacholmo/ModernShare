#!/usr/bin/env python3
"""Prototype the camera-friendly DNG layout: fixed header + unchanged CCDI buffer.

Host-side format proof, not a firmware patch. No JPEG processing, pixel expansion,
compression, auto white balance or black-frame subtraction is performed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
import ccdi2dng as dng

PIXEL_BYTES = dng.W * dng.H
ALIGNMENT = 512


def camera_tags():
    fm = dng.SRGB_XYZ_D50 @ dng.CCM
    cm = np.linalg.inv(dng.SRGB_XYZ_D65 @ dng.CCM @ np.diag(1 / dng.DAYLIGHT_NEUTRAL))
    cm /= (cm @ dng.SRGB_XYZ_D65 @ np.ones(3)).max()
    return {
        254: (4, [0]), 256: (4, [dng.W]), 257: (4, [dng.H]),
        258: (3, [8]), 259: (3, [1]), 262: (3, [32803]),
        271: (2, 'EASTMAN KODAK COMPANY'),
        272: (2, 'KODAK EASYSHARE C713 ZOOM DIGITAL CAMERA'),
        274: (3, [1]), 277: (3, [1]), 278: (4, [dng.H]), 284: (3, [1]),
        305: (2, 'CD703 native DNG format prototype'),
        33421: (3, [2, 2]), 33422: (1, [0, 1, 1, 2]),
        50706: (1, [1, 4, 0, 0]), 50707: (1, [1, 4, 0, 0]),
        50708: (2, 'Kodak EasyShare C713 (CCDI)'),
        50710: (1, [0, 1, 2]), 50711: (3, [1]),
        50712: (3, dng.DECODE.tolist()),
        50713: (3, [1, 1]), 50714: (4, [0]), 50717: (4, [dng.WHITE]),
        50719: (4, [dng.CROP_X, dng.CROP_Y]),
        50720: (4, [dng.CROP_W, dng.CROP_H]),
        50721: (10, [dng.rat(v) for v in cm.flat]),
        50728: (5, [dng.rat(v) for v in dng.DAYLIGHT_NEUTRAL]),
        50778: (3, [21]),
        50964: (10, [dng.rat(v) for v in fm.flat]),
    }


def make_header():
    tags = camera_tags()
    tags[273] = (4, [0])
    tags[279] = (4, [PIXEL_BYTES])

    def pack(typ, values):
        if typ == 2:
            data = values.encode('ascii') + b'\0'
            return len(data), data
        if typ == 1:
            return len(values), bytes(values)
        if typ in (3, 4):
            return len(values), struct.pack('<' + ('H' if typ == 3 else 'I') * len(values), *values)
        if typ in (5, 10):
            return len(values), b''.join(struct.pack('<II' if typ == 5 else '<ii', *v) for v in values)
        raise ValueError(typ)

    base = 8 + 2 + 12 * len(tags) + 4
    extra = bytearray()
    entries = []
    for tag, (typ, values) in sorted(tags.items()):
        count, data = pack(typ, values)
        if len(data) > 4:
            field = struct.pack('<I', base + len(extra))
            extra.extend(data)
            if len(extra) % 2:
                extra.append(0)
        else:
            field = data.ljust(4, b'\0')
        entries.append((tag, struct.pack('<HHI', tag, typ, count) + field))
    size = ((base + len(extra) + ALIGNMENT - 1) // ALIGNMENT) * ALIGNMENT
    ifd = b''.join(struct.pack('<HHII', 273, 4, 1, size) if tag == 273 else data for tag, data in entries)
    header = b'II*\0' + struct.pack('<I', 8) + struct.pack('<H', len(tags)) + ifd + b'\0' * 4 + extra
    return header.ljust(size, b'\0')


def wrap(raw_path, output, header=None):
    raw_path, output = Path(raw_path), Path(output)
    data = raw_path.read_bytes()
    if len(data) != PIXEL_BYTES:
        raise ValueError(f'{raw_path}: expected {PIXEL_BYTES} bytes, got {len(data)}')
    # Exclusive creation protects existing photos and prototypes from accidental replacement.
    with output.open('xb') as f:
        f.write(make_header() if header is None else header)
        f.write(data)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('raw', type=Path, nargs='*')
    ap.add_argument('-o', '--outdir', required=True, type=Path,
                    help='new output directory; existing directories are refused')
    a = ap.parse_args()
    a.outdir.mkdir(parents=True, exist_ok=False)
    header = make_header()
    (a.outdir / 'header.bin').write_bytes(header)
    manifest = {'header_bytes': len(header), 'pixel_bytes': PIXEL_BYTES,
                'file_bytes': len(header) + PIXEL_BYTES, 'bits_stored': 8,
                'linear_white': dng.WHITE, 'linearization_entries': len(dng.DECODE),
                'as_shot_neutral': dng.DAYLIGHT_NEUTRAL.tolist(),
                'header_sha256': hashlib.sha256(header).hexdigest(),
                'status': 'host format proof; not camera-tested firmware', 'files': []}
    for raw in a.raw:
        output = a.outdir / (raw.stem + '.DNG')
        wrap(raw, output, header)
        manifest['files'].append({'source': str(raw), 'output': output.name,
                                 'source_sha256': hashlib.sha256(raw.read_bytes()).hexdigest()})
        print(f'{raw} -> {output}')
    (a.outdir / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Fixed header: {len(header)} bytes; unchanged sensor payload: {PIXEL_BYTES} bytes')


if __name__ == '__main__':
    main()
