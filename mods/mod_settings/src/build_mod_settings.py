#!/usr/bin/env python3
"""Extend the confirmed date/Share firmware with JPEG film choice and a build label."""
import argparse
import json
from pathlib import Path
import struct
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'mods/native_dng/src')]
import kodakfw
from build_metadata_dng import assemble,sha

BASE_SHA='b37ad3c6a0d86ce8c1e8a9b34a38f93236f82bab2477b6252b824098ce294c34'
VERSION='CD703 mod 0.4'
BASE=0x1247a0
TITLE,LIST,ITEMS,STRINGS,END=0x168190,0x1681b0,0x1681b8,0x168218,0x168370
WIDGET,SCREEN,FILMTAB=0x168154,0x168370,0x125780
FILMS=['By mode','Stock','Agfa Vista 200','Kodak E100VS','Fuji Neopan 1600']

def build(base,out):
    original=base.read_bytes()
    if sha(original)!=BASE_SHA or kodakfw.check(original):raise ValueError('base must be pinned user-confirmed date-default b37ad3c6')
    out.mkdir(parents=True,exist_ok=True);target=out/'KC713.FW'
    if target.exists():raise FileExistsError('use a fresh firmware output directory')
    off=lambda a:kodakfw.ram_to_file(original,a)
    read=lambda a,n:original[off(a):off(a)+n]
    old_menu=json.loads((ROOT/'mods/share_menu/test-v1/manifest.json').read_text())
    # Audit the expanded Share-private storage against the original screen registry.
    registry=(ROOT/'mods/native_dng/metadata-v3/KC713.FW').read_bytes()
    rr=lambda a,n:registry[off(a):off(a)+n]
    owners=[]
    for i in range(0xb6):
        root=struct.unpack('<I',rr(0x14ce50+4*i,4))[0]
        if not 0x130000<=root<0x172e00:continue
        flags,ids,lis,handler=struct.unpack('<4I',rr(root,16))
        if ids>>16>100 or not 0x130000<=lis<0x172e00:continue
        for j in range(ids>>16):
            child=struct.unpack('<I',rr(lis+4*j,4))[0]
            if TITLE<=child<END:owners.append({'screen':hex(i),'child':hex(child)})
    assert len(owners)==14 and all(x['screen']=='0xa8' for x in owners)
    assert read(FILMTAB,24)==bytes([0]*9+[2]+[0]*7+[3]+[0]*4+[1,0])
    labels={};strings=bytearray()
    texts=[('TITLE','MOD SETTINGS'),('DNG_ON','DNG saving: ON'),('DNG_OFF','DNG saving: OFF'),
           ('HIDDEN','Hidden menu'),('VERSION','FW: '+VERSION)]
    texts += [('FILM_'+str(i),'Film: '+v) for i,v in enumerate(FILMS)]
    for name,text in texts:
        labels[name]=STRINGS+len(strings);strings.extend(text.encode('ascii')+b'\0')
    label_table=(STRINGS+len(strings)+3)&~3
    state=label_table+20;events=state+4
    assert events+80<=END
    constants=dict(labels,FILM_STATE=state,FILM_LABELS=label_table,EVENTS=events)
    (out/'menu_layout.inc').write_text(''.join(f'.equ {k}, {v:#x}\n' for k,v in constants.items()))
    src=Path(__file__).with_name('menu.s');blob=assemble(src,out,'menu',BASE)
    syms={}
    objdump=ROOT/'decompiler-project/tools/binutils/arc-elf32-objdump'
    for line in subprocess.check_output([str(objdump),'-t',str(out/'menu.o')],text=True).splitlines():
        fields=line.split()
        if len(fields)>=5 and fields[1]=='g' and '.text' in fields:syms[fields[-1]]=BASE+int(fields[0],16)
    ranges=[(BASE,syms['film_end'],96),(syms['start'],syms['menu_end'],192),(syms['hidden_menu'],syms['tail_end'],32)]
    for start,end,cap in ranges:assert 0<end-start<=cap
    assert syms['start']==0x1256c0 and syms['hidden_menu']==0x1259e0
    block=bytearray(END-TITLE)
    def data(at,b):
        assert TITLE<=at and at+len(b)<=END
        block[at-TITLE:at-TITLE+len(b)]=b
    title=bytearray(read(TITLE,32));struct.pack_into('<I',title,28,labels['TITLE']);data(TITLE,title)
    data(LIST,struct.pack('<2I',TITLE,WIDGET))
    for i,key in enumerate(['DNG_ON','FILM_0','HIDDEN','VERSION']):data(ITEMS+24*i,struct.pack('<6I',0,labels[key],0,0,0,0))
    data(STRINGS,strings);data(label_table,struct.pack('<5I',*[labels['FILM_'+str(i)] for i in range(5)]))
    table=[(0x4405,syms['init']),(0x4409,syms['refresh']),(0x5000,syms['toggle_dng']),
           (0x5001,syms['film_next']),(0x5002,syms['hidden_menu']),(0x5003,syms['version']),
           (0x680,0xb97c4),(0x780,0xb97c4),(0x700,0xb97c4),(0,0xb953c)]
    data(events,b''.join(struct.pack('<2I',*row) for row in table))
    widget=bytearray(read(WIDGET,60));widget[0x1c]=4
    image=bytearray(original);patches=[]
    def put(at,expected,value,reason):
        assert len(expected)==len(value) and read(at,len(value))==expected,hex(at)
        image[off(at):off(at)+len(value)]=value
        patches.append({'address':hex(at),'file_offset':off(at),'length':len(value),'reason':reason,'old_sha256':sha(expected),'new_sha256':sha(value)})
    for start,end,cap in ranges:
        expected=read(start,cap)
        if start!=syms['start']:assert expected==bytes(cap)
        else:assert expected[:170]==(ROOT/'mods/share_menu/test-v1/menu.bin').read_bytes() and expected[170:]==bytes(22)
        code=blob[start-BASE:end-BASE]+bytes(cap-(end-start))
        put(start,expected,code,'Extended mod-menu callback allocation')
    put(TITLE,read(TITLE,len(block)),block,'Four-row list, version/film strings and session film state in Share-private storage')
    put(WIDGET,read(WIDGET,60),widget,'Increase native list from two to four rows')
    kodakfw.fix(image)
    allowed=set(range(0x1f4,0x1fc))
    for p in patches:allowed.update(range(p['file_offset'],p['file_offset']+p['length']))
    for r in kodakfw.records(original):
        if r['type']==1:allowed.update(range(0x10+r['idx']*16+12,0x10+r['idx']*16+16))
    changes=[i for i,(a,b) in enumerate(zip(original,image)) if a!=b]
    assert len(image)==len(original) and not kodakfw.check(image) and all(i in allowed for i in changes)
    # Preserve every capture/default-date feature. The film map changes only at runtime.
    for at,n in [(0x67898,6),(0x125a00,548),(0x1241a0,1536),(0x12ff40,180),(0x125600,192),
                 (FILMTAB,0x260),(0x12ff00,0x34),(0xcbd00,6),(0x13358c,1),
                 (0x16a708,36),(0x1284ac,36),(0x128540,36),(0xdc45a,18),(0xeae58,36)]:
        assert image[off(at):off(at)+n]==read(at,n),f'inherited feature changed at {at:#x}'
    with target.open('xb') as f:f.write(image)
    (out/'code.bin').write_bytes(image[0x200:0x100200])
    for name in ['header.bin','header-layout.json','hook.bin','capture-fixtures.json']:
        (out/name).write_bytes((ROOT/'mods/native_dng/metadata-v3'/name).read_bytes())
    inherited=json.loads((ROOT/'mods/date_default/test-20261107/manifest.json').read_text())
    manifest={k:inherited[k] for k in ['metadata_timing','metadata_hook_bytes','metadata_callsite_address','default_date','default_time','struct_tm']}
    manifest.update({'status':'version and film selector candidate; not camera-tested','version':VERSION,
        'base':str(base.relative_to(ROOT)),'base_sha256':BASE_SHA,'firmware_sha256':sha(image),'firmware_bytes':len(image),
        'builder_sha256':sha(Path(__file__).read_bytes()),'source_sha256':sha(src.read_bytes()),
        'symbols':{k:hex(v) for k,v in syms.items()},'labels':{k:hex(v) for k,v in labels.items()},
        'menu_hook_address':hex(syms['start']),'menu_hook_bytes':syms['menu_end']-syms['start'],
        'code_ranges':[{'start':hex(a),'end_exclusive':hex(b),'capacity':c} for a,b,c in ranges],
        'widget_address':hex(WIDGET),'items_address':hex(ITEMS),'events_address':hex(events),
        'film_state_address':hex(state),'film_label_table':hex(label_table),'film_table_address':hex(FILMTAB),
        'film_choices':FILMS,'film_default':'By mode','film_persistence':'current session',
        'dng_default_on_at_boot':True,'toggle_persistence':'current session','widget_owners':owners,
        'patches':patches,'changed_bytes':len(changes),'checksums':kodakfw.check(image),
        'limitations':['camera test required','JPEG matrix approximations, not full 3D LUTs','DNG sensor data unaffected','native exposure/color-mode behavior remains active','film and DNG selections reset at power-on']})
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (out/'SHA256SUMS').write_text(f'{sha(image)}  KC713.FW\n')
    print(f'{target}: {sha(image)}; version {VERSION}; film/main/tail bytes '+str([b-a for a,b,c in ranges]))
    return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,default=ROOT/'mods/date_default/test-20261107/KC713.FW');p.add_argument('--outdir',type=Path,required=True)
    a=p.parse_args();build(a.base.resolve(),a.outdir.resolve())
