#!/usr/bin/env python3
"""Move Film to the first menu row on the confirmed 0.5 preview firmware."""
import argparse
import json
from pathlib import Path
import struct
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'mods/native_dng/src')]
import kodakfw
from build_metadata_dng import sha
BASE_SHA='9e1e406461966d3beab7fd3c2381bf2310bc8cfeb8849756f175696afe1ff5d0'

def build(base,out):
    original=base.read_bytes()
    if sha(original)!=BASE_SHA or kodakfw.check(original):raise ValueError('base must be pinned confirmed preview 0.5')
    out.mkdir(parents=True,exist_ok=True);target=out/'KC713.FW'
    if target.exists():raise FileExistsError('use a fresh firmware output directory')
    off=lambda a:kodakfw.ram_to_file(original,a)
    read=lambda a,n:original[off(a):off(a)+n]
    image=bytearray(original);patches=[]
    def put(at,expected,value,reason):
        assert len(expected)==len(value) and read(at,len(value))==expected,hex(at)
        image[off(at):off(at)+len(value)]=value
        patches.append({'address':hex(at),'file_offset':off(at),'length':len(value),'reason':reason,'old_sha256':sha(expected),'new_sha256':sha(value)})
    row=lambda text:struct.pack('<6I',0,text,0,0,0,0)
    put(0x1681b8,row(0x168225)+row(0x168262),row(0x168262)+row(0x168225),'Film row first, DNG row second')
    put(0x1682e4,struct.pack('<4I',0x5000,0x125758,0x5001,0x1247a0),
        struct.pack('<4I',0x5000,0x1247a0,0x5001,0x125758),'Match OK actions to the reordered rows')
    put(0x125732,bytes.fromhex('41a0'),bytes.fromhex('47a0'),'Refresh DNG label in second row')
    put(0x125750,bytes.fromhex('27a0'),bytes.fromhex('21a0'),'Refresh film label in first row')
    put(0x168250,b'FW: CD703 mod 0.5\0',b'FW: CD703 mod 0.6\0','Firmware version label')
    kodakfw.fix(image);assert not kodakfw.check(image)
    allowed=set(range(0x1f4,0x1fc))
    for p in patches:allowed.update(range(p['file_offset'],p['file_offset']+p['length']))
    for r in kodakfw.records(original):
        if r['type']==1:allowed.update(range(0x10+16*r['idx']+12,0x10+16*r['idx']+16))
    changed=[i for i,(a,b) in enumerate(zip(original,image)) if a!=b]
    assert len(original)==len(image) and all(i in allowed for i in changed)
    with target.open('xb') as f:f.write(image)
    (out/'code.bin').write_bytes(image[0x200:0x100200])
    previous=ROOT/'mods/film_preview/test-v0.5'
    for name in ['header.bin','header-layout.json','hook.bin','capture-fixtures.json']:(out/name).write_bytes((previous/name).read_bytes())
    m=json.loads((previous/'manifest.json').read_text())
    m.update({'status':'Film-first menu; awaiting camera trial','version':'CD703 mod 0.6','base':str(base.relative_to(ROOT)),'base_sha256':BASE_SHA,'firmware_sha256':sha(image),'builder_sha256':sha(Path(__file__).read_bytes()),'patches':patches,'changed_bytes':len(changed),'checksums':kodakfw.check(image),'menu_rows':['Film','DNG saving','Hidden menu','FW: CD703 mod 0.6'],'row_events':{'film':'0x5000','dng':'0x5001','hidden':'0x5002','version':'0x5003'},'initial_selection':'Film','inherited_camera_confirmation':'mods/film_preview/test-v0.5/camera-user-report.json'})
    (out/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');(out/'SHA256SUMS').write_text(f'{sha(image)}  KC713.FW\n');print(f'{target}: {sha(image)}; {len(changed)} changed bytes')
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,default=ROOT/'mods/film_preview/test-v0.5/KC713.FW');p.add_argument('--outdir',type=Path,required=True);a=p.parse_args();build(a.base.resolve(),a.outdir.resolve())
