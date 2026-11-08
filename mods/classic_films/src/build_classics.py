#!/usr/bin/env python3
"""Add Velvia 100 / Kodachrome 64, retaining the Film-first menu and preview path."""
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
BASE_SHA='73801de48242acecfccd31d917c73a025f83d27ff16d97a755b782969a28fecd'
NEW_FILMS=0xebc90
TRANSFORMS=0xebe10
POINTERS=0xebe6c
LABEL_TABLE=0x168324
STRINGS=0x168340

def build(base,fitdir,out):
    original=base.read_bytes()
    if sha(original)!=BASE_SHA or kodakfw.check(original):raise ValueError('base must be pinned Film-first 0.6')
    audit=json.loads((ROOT/'mods/classic_films/research/space-audit.json').read_text());assert audit['passed']
    fitting=json.loads((fitdir/'fit.json').read_text());new=(fitdir/'new-films.bin').read_bytes()
    assert fitting['base_sha256']==BASE_SHA and sha(new)==fitting['sha256'] and len(new)==384
    out.mkdir(parents=True,exist_ok=True);target=out/'KC713.FW'
    if target.exists():raise FileExistsError('use fresh firmware output directory')
    off=lambda a:kodakfw.ram_to_file(original,a)
    read=lambda a,n:original[off(a):off(a)+n]
    image=bytearray(original);patches=[]
    def put(a,expected,value,reason):
        assert len(expected)==len(value) and read(a,len(value))==expected,hex(a)
        image[off(a):off(a)+len(value)]=value
        patches.append({'address':hex(a),'file_offset':off(a),'length':len(value),'reason':reason,'old_sha256':sha(expected),'new_sha256':sha(value)})
    def snippet(name,source,address):
        path=out/(name+'.s');path.write_text('.text\n.global start\nstart:\n'+source+'\n');return assemble(path,out,name,address)
    # Only two data pointers target the reclaimed create/init code in this exact base.
    refs=[]
    for i in range(0x200,0x144c00-3,2):
        p=struct.unpack_from('<I',original,i)[0]
        if NEW_FILMS<=p<0xebecc and p%2==0:refs.append((i+0x2fe00,p))
    assert refs==[(0x1683a0,0xebc90),(0x1683a8,0xebd5c)]
    for a,target_address in refs:put(a,struct.pack('<I',target_address),struct.pack('<I',0xb953c),'Disconnect legacy Share create/init callbacks')
    for a,expected in [(0xebed0,'f9ff'),(0xebefc,'eeff'),(0xebf00,'8fff')]:
        put(a,bytes.fromhex(expected),bytes.fromhex('e078'),'Disconnect legacy Share helper call into reclaimed data')
    film_bases=[0x1257a0,0x125860,0x125920,NEW_FILMS,NEW_FILMS+192]
    old_manifest=json.loads((ROOT/'mods/mod_settings/test-v0.6/manifest.json').read_text())
    qblocks=bytearray(read(0x168324,54));relative=list(old_manifest['preview_transforms'])
    stock=np.array(struct.unpack('<12i',read(0x16cac8,48)),dtype=float).reshape(3,4)[:,:3]/65536
    for i in range(2):
        ccm=np.array(struct.unpack_from('<12i',new,i*192),dtype=float).reshape(3,4)[:,:3]/65536
        r=ccm@np.linalg.inv(stock);q=np.rint(r*4096).astype(np.int64);assert abs(q).max()<32768
        qblocks.extend(struct.pack('<9h',*q.reshape(-1)));relative.append({'film_id':i+4,'relative_rgb':r.tolist(),'q12':q.tolist(),'max_quantization_error':float(np.max(np.abs(q/4096-r)))})
    assert len(qblocks)==90
    block=bytearray(0xebecc-NEW_FILMS)
    def data(a,b):assert NEW_FILMS<=a and a+len(b)<=0xebecc;block[a-NEW_FILMS:a-NEW_FILMS+len(b)]=b
    data(NEW_FILMS,new);data(TRANSFORMS,qblocks)
    data(POINTERS,struct.pack('<20I',*[a+j*48 for a in film_bases for j in range(4)]))
    put(NEW_FILMS,read(NEW_FILMS,len(block)),block,'Reclaim disconnected Share create/init code for two films, five preview transforms and matrix pointers')
    # Keep the three proven records in place; common getter now indexes 20 pointers.
    lookup=snippet('matrix-lookup',f' mov r2,{POINTERS:#x}\n ld.as r0,[r2,r1]\n pop_s r2\n j_s [blink]',0x1256a8)
    assert len(lookup)==16
    put(0x1256a8,read(0x1256a8,24),lookup+bytes.fromhex('e078')*4,'Matrix pointer table supports five noncontiguous film records')
    for a in [0x1247b0,0x12573e]:put(a,bytes.fromhex('85e1'),snippet('limit-'+hex(a),' cmp_s r1,7',a),'Seven choices: By mode, Stock and five film looks')
    labels=dict(old_manifest['labels']);strings=bytearray()
    for i,name in [(5,'Film: Velvia 100'),(6,'Film: Kodachrome 64')]:labels['FILM_'+str(i)]=STRINGS+len(strings);strings.extend(name.encode()+b'\0')
    assert STRINGS+len(strings)<=0x168370
    private=bytearray(0x168370-LABEL_TABLE);struct.pack_into('<7I',private,0,*[int(labels['FILM_'+str(i)],16) if isinstance(labels['FILM_'+str(i)],str) else labels['FILM_'+str(i)] for i in range(7)])
    private[STRINGS-LABEL_TABLE:STRINGS-LABEL_TABLE+len(strings)]=strings
    put(LABEL_TABLE,read(LABEL_TABLE,len(private)),private,'Expanded seven-label menu table and new film names, replacing relocated preview transforms')
    put(0x125744,read(0x125744,8),snippet('label-pointer',f' mov r2,{LABEL_TABLE:#x}',0x125744),'Use relocated seven-choice label table')
    # Assemble from the confirmed preview source; only the film limit and R base change.
    source=(ROOT/'mods/film_preview/src/preview.s').read_text().replace('0x168324',hex(TRANSFORMS)).replace('cmp_s r2,4','cmp_s r2,6')
    path=out/'preview-expanded.s';path.write_text(source);blob=assemble(path,out,'preview-expanded',0xebc50)
    assert blob[:60]==read(0xebc50,60) and blob[0x12fe98-0xebc50:0x12fef0-0xebc50]==read(0x12fe98,88)
    put(0x125c24,read(0x125c24,142),blob[0x125c24-0xebc50:0x125cb2-0xebc50],'Preview supports film IDs 1..5 using relocated relative transforms')
    put(0x168250,b'FW: CD703 mod 0.6\0',b'FW: CD703 mod 0.7\0','Version label')
    kodakfw.fix(image);assert not kodakfw.check(image)
    allowed=set(range(0x1f4,0x1fc))
    for p in patches:allowed.update(range(p['file_offset'],p['file_offset']+p['length']))
    for r in kodakfw.records(original):
        if r['type']==1:allowed.update(range(0x10+16*r['idx']+12,0x10+16*r['idx']+16))
    changes=[i for i,(a,b) in enumerate(zip(original,image)) if a!=b]
    assert len(image)==len(original) and all(i in allowed for i in changes)
    for a,n in [(0x1257a0,576),(0x125780,24),(0x67898,6),(0x125a00,548),(0x1241a0,1536),(0x12ff40,180),
                (0x12ff00,0x34),(0xcbd00,6),(0x13358c,1),(0x16a708,36),(0x1284ac,36),(0x128540,36),(0xdc45a,18),(0xeae58,36)]:
        assert image[off(a):off(a)+n]==read(a,n),hex(a)
    with target.open('xb') as f:f.write(image)
    (out/'code.bin').write_bytes(image[0x200:0x100200])
    previous=ROOT/'mods/mod_settings/test-v0.6'
    for name in ['header.bin','header-layout.json','hook.bin','capture-fixtures.json']:(out/name).write_bytes((previous/name).read_bytes())
    (out/'fit.json').write_text(json.dumps(fitting,indent=2)+'\n')
    old_manifest.update({'status':'five-film candidate; not camera-tested','version':'CD703 mod 0.7','base':str(base.relative_to(ROOT)),'base_sha256':BASE_SHA,'firmware_sha256':sha(image),'builder_sha256':sha(Path(__file__).read_bytes()),'patches':patches,'changed_bytes':len(changes),'checksums':kodakfw.check(image),'film_choices':['By mode','Stock','Agfa Vista 200','Kodak E100VS','Fuji Neopan 1600','Velvia 100','Kodachrome 64'],'labels':{k:hex(v) if isinstance(v,int) else v for k,v in labels.items()},'film_label_table':hex(LABEL_TABLE),'film_record_bases':[hex(a) for a in film_bases],'matrix_pointer_table':hex(POINTERS),'preview_transforms':relative,'preview_transforms_address':hex(TRANSFORMS),'new_film_fits':fitting['records'],'reclaimed_callbacks_pointer_sites':[[hex(a),hex(b)] for a,b in refs],'space_audit':'mods/classic_films/research/space-audit.json'})
    old_manifest['source_sha256']=sha(path.read_bytes())
    old_manifest['menu_rows']=['Film','DNG saving','Hidden menu','FW: CD703 mod 0.7']
    (out/'manifest.json').write_text(json.dumps(old_manifest,indent=2)+'\n');(out/'SHA256SUMS').write_text(f'{sha(image)}  KC713.FW\n');print(f'{target}: {sha(image)}; five film looks; {len(changes)} changed bytes')
    return old_manifest
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,default=ROOT/'mods/mod_settings/test-v0.6/KC713.FW');p.add_argument('--fitdir',type=Path,default=ROOT/'mods/classic_films/fits-v1');p.add_argument('--outdir',type=Path,required=True);a=p.parse_args();build(a.base.resolve(),a.fitdir.resolve(),a.outdir.resolve())
