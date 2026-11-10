#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Package authored patches from a verified source build for the small stdlib GUI."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import sys
import zlib
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modernshare_patcher import STOCK_SHA256,RELEASE_SHA256,PATCH_LIMIT,patch

def sha(b):return hashlib.sha256(b).hexdigest()

def package(stock,target,output):
    original=stock.read_bytes();final=target.read_bytes()
    if sha(original)!=STOCK_SHA256 or sha(final)!=RELEASE_SHA256:raise ValueError('Only the verified source-built 0.9 release can be packaged')
    if output.exists():raise FileExistsError(output)
    excluded=set(range(0x1f4,0x1fc))
    for index in range(4):excluded.update(range(0x10+index*16+12,0x10+index*16+16))
    copies=[dict(input='patched',source=0x194800,destination=0x200200,length=0x5c00,transform='sentence-case')]
    for c in copies:excluded.update(range(c['destination'],c['destination']+c['length']))
    sys.path.insert(0,str(ROOT/'mods/ui/src'))
    from gfx import Gfx
    from local_graphics import repack
    before,after=Gfx(original),Gfx(final);graphics=[]
    for i,address in enumerate(before.ids(246)):
        if not address or i==1:continue
        src=before.rec(address);dst=after.rec(after.ids(246)[i])
        if before.pixels(src)[0]!=after.pixels(dst)[0]:continue
        source=before.file_off(src['data']);at=after.file_off(dst['data'])
        value=repack(original,source,src['w']*src['h'])+b'\0'
        if value!=final[at:at+len(value)]:raise ValueError('Local graphics rebuild mismatch')
        graphics.append(dict(source=source,destination=at,pixels=src['w']*src['h'],sha256=sha(value)))
        excluded.update(range(at,at+len(value)))
    groups=[]
    for at,(a,b) in enumerate(zip(original,final)):
        if a==b or at in excluded:continue
        if groups and at==groups[-1][-1]+1:groups[-1].append(at)
        else:groups.append([at])
    edits=[dict(offset=g[0],value=final[g[0]:g[-1]+1].hex()) for g in groups]
    packed=json.dumps(edits,separators=(',',':')).encode()
    if len(packed)>PATCH_LIMIT:raise ValueError('Patch bundle exceeds the runtime bound')
    bundle=dict(format=1,version='ModernShare 0.9',stock_sha256=STOCK_SHA256,firmware_sha256=RELEASE_SHA256,
                copies=copies,local_graphics=graphics,patch_data_sha256=sha(packed),patch_data_zlib_base64=base64.b64encode(zlib.compress(packed,9)).decode(),
                source_build='scripts/build.py; final ARC assembly and editable assets are included in this repository')
    if patch(original,bundle)!=final:raise ValueError('Packaged patch did not reproduce source build')
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as f:f.write(json.dumps(bundle,indent=2)+'\n')
    print(f'{output}: {len(edits)} edits; {output.stat().st_size} bytes; exact firmware verified')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--stock',type=Path,required=True);p.add_argument('--firmware',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();package(a.stock,a.firmware,a.out)
