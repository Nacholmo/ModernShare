#!/usr/bin/env python3
"""Preview-matrix candidate on top of camera-tested Mod Settings 0.4."""
import argparse
import json
from pathlib import Path
import struct
import subprocess
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'mods/native_dng/src')]
import kodakfw
from build_metadata_dng import assemble,sha
from build_native_dng import branch
BASE_SHA='9e780daf4f0597788f802088ccaf5734554c2b0b8f65bf61de668b979b6d0f72'
ORIGIN=0xebc50

def build(base,out):
    original=base.read_bytes()
    if sha(original)!=BASE_SHA or kodakfw.check(original):raise ValueError('base must be pinned Mod Settings 0.4')
    out.mkdir(parents=True,exist_ok=True);target=out/'KC713.FW'
    if target.exists():raise FileExistsError('use fresh output directory')
    off=lambda a:kodakfw.ram_to_file(original,a)
    read=lambda a,n:original[off(a):off(a)+n]
    src=Path(__file__).with_name('preview.s');blob=assemble(src,out,'preview',ORIGIN)
    syms={};objdump=ROOT/'decompiler-project/tools/binutils/arc-elf32-objdump'
    for line in subprocess.check_output([str(objdump),'-t',str(out/'preview.o')],text=True).splitlines():
        f=line.split()
        if len(f)>=5 and f[1]=='g' and '.text' in f:syms[f[-1]]=ORIGIN+int(f[0],16)
    ranges=[(ORIGIN,syms['refresh_end'],64),(syms['start'],syms['body_end'],156),(syms['guard'],syms['tail_end'],104)]
    assert syms['start']==0x125c24 and syms['guard']==0x12fe98
    for a,b,c in ranges:assert 0<b-a<=c
    # Recover the same relative film RGB transform from the saved capture matrices.
    # Existing preview matrices use their own calibration, so do not substitute a
    # capture CCM directly. Store R as signed Q12 and compose it at the packer.
    matrix=lambda a:np.array(struct.unpack('<12i',read(a,48)),dtype=float).reshape(3,4)/65536
    stock=matrix(0x16cac8)[:,:3];packed=bytearray();transforms=[]
    for k in range(3):
        r=matrix(0x1257a0+192*k)[:,:3]@np.linalg.inv(stock)
        q=np.rint(r*4096).astype(np.int64)
        assert np.max(np.abs(q))<32768
        packed.extend(struct.pack('<9h',*q.reshape(-1)))
        transforms.append({'film_id':k+1,'relative_rgb':r.tolist(),'q12':q.tolist(),'max_quantization_error':float(np.max(np.abs(q/4096-r)))})
    # The old Share root entry has no remaining pointer in the current image.
    # Ghidra also audits all direct references into its full reclaimed 64 bytes.
    pointer=struct.pack('<I',ORIGIN)
    pointer_sites=[i+0x2fe00 for i in range(0x200,0x144c00-3,2) if original[i:i+4]==pointer]
    assert not pointer_sites and read(0x16837c,4)==struct.pack('<I',0x1256c0)
    site=out/'refresh-call.s';site.write_text(f'.text\n nop_s\n.global start\nstart:\n bl start + ({ORIGIN:#x} - 0x1247ee)\n')
    call=assemble(site,out,'refresh-call',0x1247ec)[2:];assert len(call)==4
    image=bytearray(original);patches=[]
    def put(a,expected,value,reason):
        assert len(expected)==len(value) and read(a,len(value))==expected,hex(a)
        image[off(a):off(a)+len(value)]=value
        patches.append({'address':hex(a),'file_offset':off(a),'length':len(value),'reason':reason,'old_sha256':sha(expected),'new_sha256':sha(value)})
    for a,b,c in ranges:
        expected=read(a,c)
        if a!=ORIGIN:assert expected==bytes(c)
        code=blob[a-ORIGIN:b-ORIGIN]+bytes(c-(b-a))
        put(a,expected,code,'Preview matrix composition / stock trampoline / live-view refresh')
    put(0x168324,bytes(54),packed,'Three relative RGB transforms in unused Share-private storage')
    put(0x62a28,bytes.fromhex('f1c0c20b205c0872'),branch(0x62a28,syms['guard'])+bytes.fromhex('e078')*2,'Wrap capture-mode preview CCM packing; review/capture-CCM calls retain stock packing')
    put(0x1247ee,read(0x1247ee,4),call,'Film selection refreshes current live-view color matrix before menu repaint')
    put(0x168250,b'FW: CD703 mod 0.4\0',b'FW: CD703 mod 0.5\0','Version label')
    kodakfw.fix(image);assert not kodakfw.check(image)
    allowed=set(range(0x1f4,0x1fc))
    for p in patches:allowed.update(range(p['file_offset'],p['file_offset']+p['length']))
    for rec in kodakfw.records(original):
        if rec['type']==1:allowed.update(range(0x10+16*rec['idx']+12,0x10+16*rec['idx']+16))
    changed=[i for i,(a,b) in enumerate(zip(original,image)) if a!=b]
    assert len(image)==len(original) and all(i in allowed for i in changed)
    for a,n in [(0x67898,6),(0x125a00,548),(0x1241a0,1536),(0x12ff40,180),(0x125600,192),
                (0x125780,0x260),(0x12ff00,0x34),(0xcbd00,6),(0x13358c,1),
                (0x16a708,36),(0x1284ac,36),(0x128540,36),(0xdc45a,18),(0xeae58,36)]:
        assert image[off(a):off(a)+n]==read(a,n),hex(a)
    with target.open('xb') as f:f.write(image)
    (out/'code.bin').write_bytes(image[0x200:0x100200])
    previous=ROOT/'mods/mod_settings/test-v0.4'
    for name in ['header.bin','header-layout.json','hook.bin','capture-fixtures.json']:(out/name).write_bytes((previous/name).read_bytes())
    m=json.loads((previous/'manifest.json').read_text());m.update({'status':'preview-path candidate; not camera-tested','version':'CD703 mod 0.5','base':str(base.relative_to(ROOT)),'base_sha256':BASE_SHA,'firmware_sha256':sha(image),'source_sha256':sha(src.read_bytes()),'builder_sha256':sha(Path(__file__).read_bytes()),'patches':patches,'changed_bytes':len(changed),'checksums':kodakfw.check(image),'preview_symbols':{k:hex(v) for k,v in syms.items()},'preview_code_ranges':[{'start':hex(a),'end_exclusive':hex(b),'capacity':c} for a,b,c in ranges],'preview_transforms':transforms,'preview_transforms_address':'0x168324','reclaimed_share_entry_pointer_sites':pointer_sites,'preview_limits':['New captures only: existing color thumbnails are not rewritten','Preview uses the film CCM transform; curve/Ymat differences can prevent exact JPEG matching','Hardware preview timing/thumbnail generation requires camera trial']})
    (out/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');(out/'SHA256SUMS').write_text(f'{sha(image)}  KC713.FW\n');print(f'{target}: {sha(image)}; preview bytes {[b-a for a,b,c in ranges]}')
    return m
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,default=ROOT/'mods/mod_settings/test-v0.4/KC713.FW');p.add_argument('--outdir',type=Path,required=True);a=p.parse_args();build(a.base.resolve(),a.outdir.resolve())
