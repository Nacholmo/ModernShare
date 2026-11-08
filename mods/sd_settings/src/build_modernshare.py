#!/usr/bin/env python3
"""Build ModernShare 0.8: SD preferences, default DNG off, supplied boot artwork."""
import argparse
import json
from pathlib import Path
import struct
import subprocess
import sys

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'tools'), str(ROOT/'mods/native_dng/src'), str(ROOT/'mods/fullscreen/src')]
import kodakfw
from build_metadata_dng import assemble, sha, TOOLS
import build_fullscreen as boot

BASE_SHA = '57a25b3f46bff1b6bf19f23853034abe665909f379831501dff13b48ff572c4e'
BASE, DATA, DATA_END = 0xebecc, 0x16839c, 0x16844c


def build(base, artwork, out):
    original = base.read_bytes()
    assert sha(original) == BASE_SHA and not kodakfw.check(original), 'requires pinned 0.7'
    out.mkdir(parents=True, exist_ok=True)
    target = out/'KC713.FW'
    if target.exists():
        raise FileExistsError('use a fresh firmware output directory')
    audit = json.loads((Path(__file__).resolve().parents[1]/'research/space-audit.json').read_text())
    assert audit['passed']
    fw = boot.FW(base)
    patches = []
    def put_file(offset, value, why, address=None):
        previous = bytes(fw.d[offset:offset+len(value)])
        assert len(previous) == len(value)
        fw.d[offset:offset+len(value)] = value
        patches.append(dict(address=hex(address) if address is not None else None, file_offset=offset,
                            length=len(value), reason=why, old_sha256=sha(previous), new_sha256=sha(value)))
    def put(address, value, why):
        put_file(fw.off(address), value, why, address)
    # Audit raw pointers independently of Ghidra's inferred references.
    refs = []
    for i in range(0x200, 0x144c00-3, 2):
        pointer = struct.unpack_from('<I', original, i)[0]
        if BASE <= pointer < 0xec04c or 0xec088 <= pointer < 0xec208:
            refs.append((i+0x2fe00, pointer))
    assert len(refs) == 13 and all(DATA <= a < DATA_END for a, _ in refs), refs
    data_refs = [i+0x2fe00 for i in range(0x200, 0x144c00-3, 2)
                 if DATA <= struct.unpack_from('<I', original, i)[0] < DATA_END]
    assert data_refs == [0xec050]
    assert fw.u32(0xec050) == DATA
    put(0xec050, bytes(4), 'Disconnect obsolete Share event table before reclaiming it')
    private = bytearray(struct.pack('<4I', 0, 0, 1, 0))
    layout = {'STATE': DATA}
    values = dict(PATH0='B:\\KMOD0.CFG', PATH1='B:\\KMOD1.CFG',
                  LABEL_DEFAULT='v0.8: defaults', LABEL_LOADED='v0.8: SD loaded',
                  LABEL_SAVED='v0.8: SD saved', LABEL_ERROR='v0.8: SD error')
    for key, value in values.items():
        layout[key] = DATA+len(private)
        private.extend(value.encode('ascii')+b'\0')
    assert len(private) <= DATA_END-DATA
    private.extend(bytes(DATA_END-DATA-len(private)))
    (out/'settings_layout.inc').write_text(''.join(f'.equ {k}, {v:#x}\n' for k,v in layout.items()))
    source = Path(__file__).with_name('settings.s')
    blob = assemble(source, out, 'settings', BASE)
    table = subprocess.check_output([str(TOOLS/'arc-elf32-objdump'), '-t', str(out/'settings.o')], text=True)
    names = ['capture_init','menu_init','changed','load_once','apply','status','first_end','read_slot','validate','save','code_end']
    symbols = {name:BASE+int(next(line.split()[0] for line in table.splitlines() if line.split()[-1:]==[name]),16) for name in names}
    assert symbols['first_end'] <= 0xec04c and symbols['read_slot'] == 0xec088 and symbols['code_end'] <= 0xec208
    put(BASE, blob[:symbols['first_end']-BASE], 'SD preferences: startup, menu actions and status')
    put(0xec088, blob[0xec088-BASE:], 'SD preferences: validated read and alternating-slot write')
    put(DATA, private, 'SD state, absolute card paths and status strings')
    for address, expected, name in [(0x1508bc,0xcabfc,'capture_init'),(0x1682d8,0x1256da,'menu_init'),
                                     (0x1682e8,0x1247a0,'changed'),(0x1682f0,0x125758,'changed')]:
        assert fw.u32(address) == expected
        put(address, struct.pack('<I', symbols[name]), f'Install {name} callback')
    assert fw.get(0x13358c,1) == b'\1'
    put(0x13358c,b'\0','DNG off on cards with no valid saved preference')
    put(0x1681d4,struct.pack('<I',0x168234),'Initial DNG label OFF')
    put(0x168204,struct.pack('<I',layout['LABEL_DEFAULT']),'Firmware version and SD status row')
    assert fw.get(0x168218,13) == b'MOD SETTINGS\0'
    put(0x168218,b'ModernShare\0\0','ModernShare menu title')
    assert fw.get(0x168250,18) == b'FW: CD703 mod 0.7\0'
    put(0x168250,b'ModernShare 0.8\0'.ljust(18,b'\0'),'ModernShare version label')
    # Prepare the supplied bitmap for the existing palette and 24,060-byte budget.
    # A 3x3 median removes subpixel texture; retain original antialiasing in text areas.
    im = Image.open(artwork).convert('RGB').resize((480,240),Image.Resampling.LANCZOS)
    prepared = im.filter(ImageFilter.MedianFilter(3))
    text_boxes = [(0,0,180,52),(0,85,251,145),(0,203,480,240)]
    for box in text_boxes:
        prepared.paste(im.crop(box),box)
    prepared.save(out/'boot-prepared.png')
    boot.FLATTEN, boot.FLATTEN_N = 16, 1
    idx, palette = boot.quantize(out/'boot-prepared.png',fw)
    assert idx.min() > 0 and idx.max() < 252
    english_offset = fw.u32(boot.LANG_TAB)
    assert english_offset == 0x6ba00 and fw.u32(boot.LANG_TAB+76) == 0xba00
    at = boot.REC3_FILE+english_offset
    english = bytes(fw.d[at:at+0x5c00])
    assert bytes(fw.d[at+0x5c00:at+0x5c04]) == boot.MAGIC
    combo = bytearray(english)+boot.MAGIC
    streams, pointers = [], []
    for y in range(0,240,48):
        stream = boot.m.encode(idx[y:y+48].tobytes())+b'\0'
        pointers.append(boot.LANG_BUF+len(combo));streams.append(stream);combo.extend(stream)
    used = len(combo)
    assert used <= boot.LANG_MAX, (used,boot.LANG_MAX)
    combo.extend(bytes(boot.LANG_MAX-len(combo)))
    put_file(at,combo,'ModernShare boot streams; preserve English text prefix')
    for i,pointer in enumerate(pointers):
        assert fw.u32(boot.TABLE+4*(246+i)) == 0x1254a0+20*i
        assert fw.get(0x1254a0+20*i,16) == struct.pack('<HHHHII',480,48,480,8,1,boot.PAL)
        put(0x1254b0+20*i,struct.pack('<I',pointer),'Updated boot tile data pointer')
    # Decode each stream through the firmware records and reconstruct the screen.
    def ram(a,n):
        if boot.LANG_BUF <= a < boot.LANG_BUF+boot.LANG_MAX:
            return combo[a-boot.LANG_BUF:a-boot.LANG_BUF+n]
        return fw.get(a,n)
    rebuilt = np.empty((240,480),np.uint8)
    for i in range(5):
        pointer = fw.u32(0x1254b0+20*i)
        px,consumed = boot.decode_at(ram,pointer,480*48)
        assert consumed == len(streams[i])-1
        rebuilt[i*48:(i+1)*48] = np.frombuffer(px,np.uint8).reshape(48,480)
    assert np.array_equal(idx,rebuilt)
    Image.fromarray(palette[rebuilt]).resize((640,480),Image.Resampling.NEAREST).save(out/'boot-preview.png')
    (out/'boot-indices.bin').write_bytes(idx.tobytes())
    kodakfw.fix(fw.d)
    assert not kodakfw.check(fw.d)
    allowed = set(range(0x1f4,0x1fc))
    for p in patches:
        allowed.update(range(p['file_offset'],p['file_offset']+p['length']))
    for r in kodakfw.records(original):
        if r['type'] in (0, 1):
            allowed.update(range(0x10+16*r['idx']+12,0x10+16*r['idx']+16))
    changed = [i for i,(a,b) in enumerate(zip(original,fw.d)) if a!=b]
    assert len(fw.d)==len(original) and all(i in allowed for i in changed)
    for a,n in [(0xec04c,4),(0xec054,52),(0xec208,0x800),(0x1257a0,576),(0xebc90,572),
                (0x67898,6),(0x125a00,548),(0x1241a0,1536),(0x12ff40,180),(0x12ff00,0x34),
                (0xcbd00,6),(0x16a708,36),(0x1284ac,36),(0x128540,36),(0xdc45a,18),(0xeae58,36),
                (0x1a0000,0x4fc00),(0x125c24,142),(0x12fe98,88),(0xebc50,60)]:
        off = fw.off(a)
        assert fw.get(a,n) == original[off:off+n], hex(a)
    with target.open('xb') as f:
        f.write(fw.d)
    (out/'code.bin').write_bytes(fw.d[0x200:0x100200])
    for name in ['header.bin','header-layout.json','hook.bin','capture-fixtures.json']:
        (out/name).write_bytes((base.parent/name).read_bytes())
    manifest = json.loads((base.parent/'manifest.json').read_text())
    manifest.update(status='ModernShare 0.8; awaiting camera trial',version='ModernShare 0.8',
        base=str(base.relative_to(ROOT)),base_sha256=BASE_SHA,firmware_sha256=sha(fw.d),
        builder_sha256=sha(Path(__file__).read_bytes()),settings_source_sha256=sha(source.read_bytes()),
        settings_symbols={k:hex(v) for k,v in symbols.items()},settings_layout={k:hex(v) for k,v in layout.items()},
        settings_strings=values,default_dng=False,default_film='By mode',
        settings_format={'bytes':16,'magic':'KMOD','schema':1,'words':['magic','0x10000 | film<<8 | dng','generation','~(magic ^ config ^ generation)'],
                         'files':['KMOD0.CFG','KMOD1.CFG'],'write_policy':'alternate inactive slot; commit sequence after close succeeds'},
        artwork={'source':str(artwork.relative_to(ROOT)),'sha256':sha(artwork.read_bytes()),'dimensions':list(Image.open(artwork).size),
                 'palette':'existing unchanged palette, indices 1..251','flatten_lab':16,'median_size':3,'protected_text_boxes':text_boxes,
                 'tile_bytes':[len(s)-1 for s in streams],'used':used,'capacity':boot.LANG_MAX,'free':boot.LANG_MAX-used,'roundtrip_exact':True},
        patches=patches,changed_bytes=len(changed),checksums=kodakfw.check(fw.d),
        reclaimed_raw_references=[[hex(a),hex(p)] for a,p in refs],menu_rows=['Film','DNG saving','Hidden menu','Version / SD status'])
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (out/'SHA256SUMS').write_text(f'{sha(fw.d)}  KC713.FW\n')
    print(f'{target}: {sha(fw.d)}; boot {used}/{boot.LANG_MAX}; settings {symbols["code_end"]-BASE} span bytes')


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base',type=Path,default=ROOT/'mods/classic_films/test-v0.7/KC713.FW')
    p.add_argument('--artwork',type=Path,default=ROOT/'boot_image.png')
    p.add_argument('--outdir',type=Path,required=True)
    a=p.parse_args();build(a.base.resolve(),a.artwork.resolve(),a.outdir.resolve())
