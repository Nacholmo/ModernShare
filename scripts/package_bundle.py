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
from modernshare_patcher import STOCK_SHA256,RELEASE_SHA256,patch

def sha(b):return hashlib.sha256(b).hexdigest()

def package(stock,target,output):
    original=stock.read_bytes();final=target.read_bytes()
    if sha(original)!=STOCK_SHA256 or sha(final)!=RELEASE_SHA256:raise ValueError('Only the verified source-built 0.8 release can be packaged')
    if output.exists():raise FileExistsError(output)
    excluded=set(range(0x1f4,0x1fc))
    for index in range(4):excluded.update(range(0x10+index*16+12,0x10+index*16+16))
    copies=[dict(input='stock',source=0x171f28,destination=0xf5720,length=224),
            dict(input='patched',source=0x194800,destination=0x200200,length=0x5c00)]
    for c in copies:excluded.update(range(c['destination'],c['destination']+c['length']))
    groups=[]
    for at,(a,b) in enumerate(zip(original,final)):
        if a==b or at in excluded:continue
        if groups and at==groups[-1][-1]+1:groups[-1].append(at)
        else:groups.append([at])
    edits=[dict(offset=g[0],value=final[g[0]:g[-1]+1].hex()) for g in groups]
    packed=json.dumps(edits,separators=(',',':')).encode()
    if len(packed)>128*1024:raise ValueError('Patch bundle exceeds the runtime bound')
    bundle=dict(format=1,version='ModernShare 0.8',stock_sha256=STOCK_SHA256,firmware_sha256=RELEASE_SHA256,
                copies=copies,patch_data_sha256=sha(packed),patch_data_zlib_base64=base64.b64encode(zlib.compress(packed,9)).decode(),
                source_build='scripts/build.py; final ARC assembly and editable assets are included in this repository')
    if patch(original,bundle)!=final:raise ValueError('Packaged patch did not reproduce source build')
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as f:f.write(json.dumps(bundle,indent=2)+'\n')
    print(f'{output}: {len(edits)} edits; {output.stat().st_size} bytes; exact firmware verified')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--stock',type=Path,required=True);p.add_argument('--firmware',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();package(a.stock,a.firmware,a.out)
