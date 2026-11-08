#!/usr/bin/env python3
"""DNG v2 header: same sensor layout and WB, with a proper EXIF sub-IFD."""
from datetime import datetime
import struct

from make_dng import camera_tags, PIXEL_BYTES

HEADER_BYTES = 1536
UNKNOWN_DATE = '    :  :     :  :  '


def make_metadata_header():
    root = camera_tags()
    root.update({273: (4, [HEADER_BYTES]), 279: (4, [PIXEL_BYTES]),
                 305: (2, 'CD703 native DNG metadata v2'),
                 306: (2, UNKNOWN_DATE), 34665: (4, [0])})
    exif = {33434: (5, [(0, 1000000)]), 33437: (5, [(0, 100)]),
            34855: (3, [0]), 36864: (7, b'0221'),
            36867: (2, UNKNOWN_DATE), 36868: (2, UNKNOWN_DATE)}
    data = bytearray(b'II*\0' + struct.pack('<I', 8))
    data.extend(bytes(2 + len(root) * 12 + 4))
    while len(data) % 4:
        data.append(0)
    exif_offset = len(data)
    data.extend(bytes(2 + len(exif) * 12 + 4))
    root[34665] = (4, [exif_offset])
    layout = {'HEADER_BYTES': HEADER_BYTES, 'EXIF_IFD': exif_offset}
    date_offset = None

    def packed(typ, values):
        if typ == 2:
            b = values.encode('ascii') + b'\0'
            return len(b), b
        if typ in (1, 7):
            return len(values), bytes(values)
        if typ in (3, 4):
            return len(values), struct.pack('<' + ('H' if typ == 3 else 'I') * len(values), *values)
        if typ in (5, 10):
            return len(values), b''.join(struct.pack('<II' if typ == 5 else '<ii', *v) for v in values)
        raise ValueError(typ)

    for ifd, tags in [(8, root), (exif_offset, exif)]:
        struct.pack_into('<H', data, ifd, len(tags))
        for i, (tag, (typ, values)) in enumerate(sorted(tags.items())):
            entry = ifd + 2 + 12 * i
            count, blob = packed(typ, values)
            struct.pack_into('<HHI', data, entry, tag, typ, count)
            if len(blob) > 4:
                if tag in (306, 36867, 36868) and date_offset is not None:
                    offset = date_offset
                else:
                    while len(data) % 4:
                        data.append(0)
                    offset = len(data)
                    data.extend(blob)
                struct.pack_into('<I', data, entry + 8, offset)
                if tag in (306, 36867, 36868):
                    date_offset = offset
                    layout['DATE'] = offset
                elif tag == 33434:
                    layout['EXPOSURE'] = offset
                elif tag == 33437:
                    layout['FNUMBER'] = offset
            else:
                data[entry + 8:entry + 12] = blob.ljust(4, b'\0')
                if tag == 34855:
                    layout['ISO'] = entry + 8
    layout['USED_BYTES'] = len(data)
    if len(data) > HEADER_BYTES:
        raise ValueError('metadata header exceeds the proven 1536-byte allocation')
    for field in ('DATE', 'EXPOSURE', 'FNUMBER'):
        assert layout[field] % 4 == 0
    assert layout['ISO'] % 2 == 0
    return bytes(data).ljust(HEADER_BYTES, b'\0'), layout


def mutable_ranges(layout):
    return [(layout['DATE'], 20), (layout['EXPOSURE'], 4),
            (layout['FNUMBER'], 4), (layout['ISO'], 2)]


def read_metadata(header):
    template, layout = make_metadata_header()
    if len(header) != len(template):
        raise ValueError('wrong header size')
    cleaned = bytearray(header)
    for offset, size in mutable_ranges(layout):
        cleaned[offset:offset + size] = template[offset:offset + size]
    if cleaned != template:
        raise ValueError('unexpected changes outside EXIF value fields')
    date = header[layout['DATE']:layout['DATE'] + 20].split(b'\0')[0].decode('ascii')
    if date.strip(' :'):
        datetime.strptime(date, '%Y:%m:%d %H:%M:%S')
    else:
        date = None
    return {'date': date, 'exposure_us': struct.unpack_from('<I', header, layout['EXPOSURE'])[0],
            'fnumber_100': struct.unpack_from('<I', header, layout['FNUMBER'])[0],
            'iso': struct.unpack_from('<H', header, layout['ISO'])[0]}


def fill_metadata(date, exposure_us, fnumber_100, iso):
    header, layout = make_metadata_header()
    datetime.strptime(date, '%Y:%m:%d %H:%M:%S')
    encoded = date.encode('ascii') + b'\0'
    assert len(encoded) == 20 and 0 <= iso <= 65535
    out = bytearray(header)
    out[layout['DATE']:layout['DATE'] + 20] = encoded
    struct.pack_into('<I', out, layout['EXPOSURE'], exposure_us)
    struct.pack_into('<I', out, layout['FNUMBER'], fnumber_100)
    struct.pack_into('<H', out, layout['ISO'], iso)
    return bytes(out)
