# SPDX-License-Identifier: AGPL-3.0-or-later
"""Sentence-case English copied from the user-supplied firmware image."""
import re
import struct

KEEP_WORDS = {"AF", "AE", "ISO", "LCD", "MP", "DMY", "MDY", "YMD", "DD", "MM", "YYYY", "HH", "H", "M",
              "DDMMYYYY", "MMDDYYYY", "YYYYMMDD", "TV", "USB", "OK", "PC", "SD", "NTSC", "PAL", "DNG"}
NAMES = {"KODAK": "Kodak", "EASYSHARE": "EasyShare", "PICTBRIDGE": "PictBridge"}
# Setting names shortened so "name ... value" always fits the row (id: stock text, new text).
RENAMES = {0xDC: ("EXPOSURE METERING", "Metering"), 0xB6: ("IMAGE STORAGE", "Storage"),
           0xAE: ("SET ALBUM (STILL)", "Album")}

RENAMES[0x5F] = ("EXPOSURE COMPENSATION", "Exposure")

def sentence(s):
    """ALL-CAPITALS -> Sentence case; acronyms and names kept. Same length."""
    if any(c.islower() for c in s) or sum(c.isalpha() for c in s) < 2:
        return s

    def word(m):
        w = m.group(0)
        firstword = m.start() == 0               # "10 SECONDS" -> "10 seconds"
        if w in KEEP_WORDS:
            return w
        if w in NAMES:
            return NAMES[w]
        return (w[0] if firstword else w[0].lower()) + w[1:].lower()
    return re.sub(r"[A-ZÀ-ÖØ-Þ]+", word, s)


def apply(data):
    out=bytearray(data)
    count=0x345
    if len(data)!=0x5c00:raise ValueError('Unexpected English allocation')
    for sid in range(1,count):
        at=4+count*4+struct.unpack_from('<I',data,4+4*sid)[0]
        raw=data[at:data.index(0,at)]
        if not raw or any(0x80<=c<0xa0 for c in raw):continue
        if sid in RENAMES:
            if raw.decode('latin-1')!=RENAMES[sid][0]:raise ValueError('Unexpected original English string')
            new=RENAMES[sid][1].encode('latin-1').ljust(len(raw),b'\0')
        else:new=sentence(raw.decode('latin-1')).encode('latin-1')
        if len(raw)!=len(new):raise ValueError('English string exceeds its allocation')
        out[at:at+len(new)]=new
    return out
