#!/usr/bin/env python3
"""Inspect ModernShare's 16-byte SD preference records (standard library only)."""
import argparse
import json
from pathlib import Path
import struct

MAGIC = 0x444f4d4b
FILMS = ['By mode', 'Stock', 'Agfa Vista 200', 'Kodak E100VS', 'Fuji Neopan 1600', 'Velvia 100', 'Kodachrome 64']


def encode(film, dng, generation):
    if not 0 <= film < len(FILMS) or dng not in (False, True, 0, 1):
        raise ValueError('invalid preferences')
    config = 0x10000 | (film << 8) | int(dng)
    generation &= 0xffffffff
    return struct.pack('<4I', MAGIC, config, generation, ~(MAGIC ^ config ^ generation) & 0xffffffff)


def decode(data):
    if len(data) != 16:
        raise ValueError('record must be exactly 16 bytes')
    magic, config, generation, checksum = struct.unpack('<4I', data)
    film = (config >> 8) & 255
    if magic != MAGIC or magic ^ config ^ generation ^ checksum != 0xffffffff:
        raise ValueError('bad magic/checksum')
    if config & 0xfffff8fe != 0x10000 or film >= len(FILMS):
        raise ValueError('unsupported schema or invalid preferences')
    return dict(film_index=film, film=FILMS[film], dng=bool(config & 1), generation=generation)


def choose(a, b):
    """Newest valid slot; signed wraparound comparison; A wins ties."""
    valid = []
    for slot, data in enumerate((a, b)):
        try:
            valid.append((slot, decode(data)))
        except ValueError:
            pass
    if len(valid) < 2:
        return valid[0] if valid else None
    delta = (valid[1][1]['generation'] - valid[0][1]['generation']) & 0xffffffff
    return valid[1] if 0 < delta < 0x80000000 else valid[0]


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('records', type=Path, nargs='+')
    a = p.parse_args()
    for path in a.records:
        try:
            print(json.dumps(dict(path=str(path), **decode(path.read_bytes()))))
        except (OSError, ValueError) as error:
            print(json.dumps(dict(path=str(path), error=str(error))))
