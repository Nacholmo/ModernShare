#!/usr/bin/env python3
"""Read back test DNGs and the last complete camera MEMDUMP frame; never writes inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from make_dng import ROOT, PIXEL_BYTES
from metadata_header import read_metadata

DUMP_BYTES = 0x1EFBD6
LOG = 0x125CC0
FIELDS = ['magic', 'attempts', 'phase', 'first_error', 'input_bytes', 'header_written',
          'payload_written', 'close_error', 'buffer_pointer', 'reserved']


def inspect_dng(path, header, metadata=False):
    data = path.read_bytes()
    fields = None
    matches = data[:len(header)] == header
    if metadata:
        try:
            fields = read_metadata(data[:len(header)])
            matches = True
        except (ValueError, UnicodeError):
            matches = False
    good = len(data) == len(header) + PIXEL_BYTES and matches
    return {'path': str(path), 'valid_test_layout': good, 'bytes': len(data),
            'header_matches': matches, 'metadata': fields,
            'metadata_populated': bool(fields and fields['date'] and fields['exposure_us']
                                       and fields['fnumber_100'] and fields['iso']) if metadata else None,
            'payload_sha256': hashlib.sha256(data[len(header):]).hexdigest() if good else None}


def inspect_dump(path, build):
    data = path.read_bytes()
    frames, tail = divmod(len(data), DUMP_BYTES)
    if not frames:
        raise ValueError('No complete 0x1efbd6-byte MEMDUMP frame')
    frame = data[(frames - 1) * DUMP_BYTES:frames * DUMP_BYTES]
    fw = (build / 'KC713.FW').read_bytes()
    manifest = json.loads((build / 'manifest.json').read_text())
    metadata = 'metadata_hook_bytes' in manifest
    matches = {}
    for name, addr, n in [('entry', 0x67898, 6), ('header', 0x1241a0, 1536),
                          ('hook', 0x125a00, (build / 'hook.bin').stat().st_size)]:
        off = addr - 0x30000 + 0x200
        matches[name] = frame[addr:addr+n] == fw[off:off+n]
    dynamic_fields = None
    if metadata:
        try:
            dynamic_fields = read_metadata(frame[0x1241a0:0x1241a0+1536])
            matches['header'] = True
        except (ValueError, UnicodeError):
            matches['header'] = False
        site = int(manifest.get('metadata_callsite_address', '0xa4290'), 16)
        for name, addr, n in [('metadata_hook', 0x12ff40, manifest['metadata_hook_bytes']),
                              ('metadata_callsite', site, 4)]:
            off = addr - 0x30000 + 0x200
            matches[name] = frame[addr:addr+n] == fw[off:off+n]
    values = dict(zip(FIELDS, struct.unpack_from('<10I', frame, LOG)))
    values['magic_ascii'] = frame[LOG:LOG+4].decode('ascii', errors='replace')
    values['phase_name'] = {0: 'not entered', 1: 'constructing/opening path',
          2: 'open; writing header', 3: 'header complete; writing payload',
          4: 'payload complete; closing', 5: 'success; closed'}.get(values['phase'], 'unknown')
    success = (all(matches.values()) and values['magic_ascii'] == 'DNG1'
               and values['phase'] == 5 and values['first_error'] == 0
               and values['close_error'] == 0 and values['header_written'] == 1536
               and values['payload_written'] == PIXEL_BYTES)
    return {'path': str(path), 'complete_frames': frames, 'trailing_incomplete_bytes': tail,
            'test_firmware_memory_matches': matches, 'log': values, 'header_metadata': dynamic_fields,
            'metadata_populated': bool(dynamic_fields and dynamic_fields['date'] and dynamic_fields['exposure_us']
                                       and dynamic_fields['fnumber_100'] and dynamic_fields['iso']) if metadata else None,
            'last_save_success': success}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('inputs', nargs='*', type=Path, help='test DNG files or a folder containing CCDI*.DNG')
    ap.add_argument('--dump', type=Path)
    ap.add_argument('--build', type=Path, default=ROOT / 'mods/native_dng/test-v1')
    a = ap.parse_args()
    if not a.inputs and not a.dump:
        ap.error('supply DNGs/a folder and/or --dump MEMDUMP.BIN')
    files = []
    for p in a.inputs:
        files.extend(sorted(f for f in p.iterdir() if f.is_file() and f.name.upper().startswith('CCDI')
                            and f.suffix.upper() == '.DNG') if p.is_dir() else [p])
    manifest = json.loads((a.build / 'manifest.json').read_text())
    metadata = 'metadata_hook_bytes' in manifest
    header = (a.build / 'header.bin').read_bytes()
    report = {'dngs': [inspect_dng(f, header, metadata) for f in files]}
    if a.dump:
        report['dump'] = inspect_dump(a.dump, a.build)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
