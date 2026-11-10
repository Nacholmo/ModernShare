#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build ModernShare from a local stock image and the editable repository sources."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys

import numpy as np
from PIL import Image, ImageFilter

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'mods/native_dng/src'),str(ROOT/'mods/fullscreen/src'),str(ROOT/'mods/ui/src')]
import kodakfw
import build_fullscreen as boot
from metadata_header import make_metadata_header
import skin
import english

def sha(data):return hashlib.sha256(data).hexdigest()

def tool(prefix,name):
    value=prefix+name
    found=shutil.which(value)
    if found:return found
    p=Path(value)
    if p.is_file() and os.access(p,os.X_OK):return str(p.resolve())
    raise ValueError(f'Cannot find {value}; pass --arc-prefix /path/to/arc-elf32-')

def assemble(source,out,name,origin,prefix):
    obj=out/(name+'.o');binary=out/(name+'.bin')
    subprocess.run([tool(prefix,'as'),'-mcpu=arc700','-I',str(out),'-I',str(ROOT/'src/firmware'),str(source),'-o',str(obj)],check=True)
    reloc=subprocess.check_output([tool(prefix,'objdump'),'-r',str(obj)],text=True)
    if 'R_ARC_' in reloc:raise ValueError(f'unresolved relocation in {name}')
    subprocess.run([tool(prefix,'objcopy'),'-O','binary',str(obj),str(binary)],check=True)
    listing=subprocess.check_output([tool(prefix,'objdump'),'-d','-M','cpu=arc700',f'--adjust-vma={origin:#x}',str(obj)],text=True)
    (out/(name+'.asm')).write_text(listing)
    return binary.read_bytes()

def build(stock,out,prefix,artwork,modified=False):
    original=stock.read_bytes()
    recipe=json.loads((ROOT/'src/release/recipe-0.9.json').read_text())
    if sha(original)!=recipe['stock_sha256'] or kodakfw.check(original):
        raise ValueError('Unsupported stock image; requires exact C713 firmware 1.30 SHA-256 in README')
    if out.exists():raise FileExistsError('Use a fresh output directory')
    # Check prerequisites before creating any output.
    for name in ['as','objcopy','objdump']:tool(prefix,name)
    out.mkdir(parents=True)
    fw=bytearray(original)
    def off(a):return kodakfw.ram_to_file(fw,a)
    def put(a,b):
        o=off(a)
        if o+len(b)>len(fw):raise ValueError('patch outside image')
        fw[o:o+len(b)]=b
    # Compute the theme from source; two palette copies and matching UI words.
    spec=importlib.util.spec_from_file_location('modernshare_theme',ROOT/'mods/theme/src/make_theme.py')
    theme=importlib.util.module_from_spec(spec);spec.loader.exec_module(theme)
    themefile=out/'theme-intermediate.fw';argv=sys.argv
    try:
        sys.argv=[str(ROOT/'mods/theme/src/make_theme.py'),str(stock),str(themefile)]
        theme.main()
    finally:sys.argv=argv
    fw=bytearray(themefile.read_bytes())
    # Repack original local graphics with authored Ember icons and pinned fonts.
    # The legacy banner participates in this repack; it is not written afterwards.
    legacy=Image.open(ROOT/'assets/legacy-banner-indexed.png')
    if legacy.mode!='P' or legacy.size!=(430,60):raise ValueError('legacy banner must retain palette indices')
    put(0x1d8127,boot.m.encode(legacy.tobytes()))
    fw=skin.apply(bytes(fw))
    # Small reverse-engineered instruction/default edits, new menu/film data and pointers.
    # No original firmware payloads or language text are stored in the recipe.
    for patch in recipe['edits']:
        at=patch['file_offset'];value=bytes.fromhex(patch['value'])
        if sha(original[at:at+len(value)])!=patch['stock_sha256']:
            raise ValueError(f'Unexpected input at {at:#x}')
        fw[at:at+len(value)]=value
    for copy in recipe['stock_copies']:
        a,b,n=copy['source_offset'],copy['destination_offset'],copy['length']
        fw[b:b+n]=original[a:a+n]
    header,layout=make_metadata_header()
    put(0x1241a0,header)
    (out/'header.bin').write_bytes(header)
    (out/'header-layout.json').write_text(json.dumps(layout,indent=2)+'\n')
    (out/'metadata_offsets.inc').write_text(''.join(f'.equ H_{k}, {v}\n' for k,v in layout.items()))
    for unit in recipe['assembly']:
        blob=assemble(ROOT/unit['source'],out,unit['name'],unit['origin'],prefix)
        maximum=max(s['offset']+s['length'] for s in unit['segments'])
        if len(blob)>maximum:raise ValueError(f'{unit["name"]}: assembly exceeds its allocated segments')
        covered=bytearray(len(blob))
        if unit['name']=='date-boot':covered[:2]=b'\1\1' # alignment-only nop, not installed
        for s in unit['segments']:covered[s['offset']:s['offset']+s['length']]=b'\1'*s['length']
        if any(b and not covered[i] for i,b in enumerate(blob)):
            raise ValueError(f'{unit["name"]}: instructions outside declared segments; update/audit the allocation map')
        for segment in unit['segments']:
            start,n=segment['offset'],segment['length'];code=blob[start:start+n]
            if len(code)!=n:raise ValueError(f'Assembly segment too short: {unit["name"]}')
            if not modified and sha(code)!=segment['sha256']:
                raise ValueError(f'{unit["name"]}: source differs from confirmed release; use --allow-modified for intentional edits')
            put(unit['origin']+start,code)
    # Exact same five-tile encoding as the camera-confirmed development build.
    im=Image.open(artwork).convert('RGB').resize((480,240),Image.Resampling.LANCZOS)
    prepared=im.filter(ImageFilter.MedianFilter(3))
    for box in [(0,0,180,52),(0,85,251,145),(0,203,480,240)]:prepared.paste(im.crop(box),box)
    prepared.save(out/'boot-prepared.png')
    # Boot artwork was accepted with the original ModernShare quantizer palette.
    # Ember's five formerly unused slots must not change its colour selection.
    quantizer=bytearray(fw)
    for table in theme.TABLES:
        for index in theme.EMBER:
            at=table+4*index
            quantizer[at:at+3]=bytes(theme.remap(*original[at:at+3]))
    palette_input=out/'palette-input.fw';palette_input.write_bytes(quantizer)
    boot.FLATTEN,boot.FLATTEN_N=16,1
    idx,palette=boot.quantize(out/'boot-prepared.png',boot.FW(palette_input))
    if idx.min()==0 or idx.max()>=252:raise ValueError('invalid boot palette index')
    english_source=boot.REC3_FILE
    # Reuse English from the user's image after the SEPIA->VIVID text edits.
    combo=english.apply(fw[english_source:english_source+0x5c00])+boot.MAGIC
    for i,y in enumerate(range(0,240,48)):
        pointer=boot.LANG_BUF+len(combo)
        put(0x1254b0+20*i,struct.pack('<I',pointer))
        pixels=idx[y:y+48].tobytes();stream=boot.m.encode(pixels)+b'\0'
        decoded,used=boot.decode_at(lambda a,n:stream[a:a+n],0,480*48)
        if decoded!=pixels or used!=len(stream)-1:raise ValueError('boot tile roundtrip failed')
        combo.extend(stream)
    used=len(combo)
    if used>boot.LANG_MAX:raise ValueError(f'Boot image is {used-boot.LANG_MAX} bytes too large')
    combo.extend(bytes(boot.LANG_MAX-used))
    destination=boot.REC3_FILE+0x6ba00
    fw[destination:destination+boot.LANG_MAX]=combo
    Image.fromarray(palette[idx]).resize((640,480),Image.Resampling.NEAREST).save(out/'boot-preview.png')
    kodakfw.fix(fw)
    problems=kodakfw.check(fw)
    if problems:raise ValueError(problems)
    digest=sha(fw);exact=digest==recipe['firmware_sha256']
    if not exact and not modified:raise ValueError(f'Release mismatch: {digest}; no flashable output written')
    with (out/'KC713.FW').open('xb') as f:f.write(fw)
    (out/'code.bin').write_bytes(fw[0x200:0x100200])
    (out/'hook.bin').write_bytes(fw[off(0x125a00):off(0x125a00)+548])
    # Ghidra test fixtures contain synthetic payloads and measured metadata only.
    shutil.copyfile(ROOT/'tests/capture-fixtures.json',out/'capture-fixtures.json')
    manifest=json.loads((ROOT/'src/release/runtime-layout.json').read_text())
    manifest.update(firmware_sha256=digest,firmware_bytes=len(fw),version='ModernShare 0.9',
                    status='Reproduced pinned release; behavior accepted on camera-tested base' if exact else 'Modified build; not camera-confirmed',
                    release_exact=exact,stock_sha256=sha(original),artwork_sha256=sha(artwork.read_bytes()),
                    boot_payload_bytes=used,checksums=problems)
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (out/'SHA256SUMS').write_text(f'{digest}  KC713.FW\n')
    for path in [themefile,palette_input]:path.unlink()
    print(f'{out/"KC713.FW"}\nSHA-256: {digest}\nExact pinned release: {exact}')
    return digest

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stock',type=Path,required=True);p.add_argument('--outdir',type=Path,required=True)
    p.add_argument('--arc-prefix',default=os.environ.get('ARC_PREFIX','arc-elf32-'))
    p.add_argument('--artwork',type=Path,default=ROOT/'boot_image.png')
    p.add_argument('--allow-modified',action='store_true',help='permit intentional source/art changes; output loses camera-confirmed status')
    a=p.parse_args()
    try:build(a.stock.resolve(),a.outdir.resolve(),a.arc_prefix,a.artwork.resolve(),a.allow_modified)
    except (ValueError,FileExistsError) as e:p.exit(1,f'{e}\n')
