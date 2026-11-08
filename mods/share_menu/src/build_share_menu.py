#!/usr/bin/env python3
"""Replace the discontinued Share tagging screen with a two-row native mod menu."""
import argparse
import json
from pathlib import Path
import struct
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools'))
sys.path.insert(0,str(ROOT/'mods/native_dng/src'))
import kodakfw
from build_metadata_dng import assemble,sha

BASE_SHA='9760823a368db1c6012337dda892470c0612fe31e64e2cc59e94d00eef00e297'
HOOK=0x1256C0
SCREEN=0x168370
WIDGET=0x168154
TITLE=0x168190
LIST=0x1681B0
ITEMS=0x1681B8
STRINGS=0x1681E8
EVENTS=0x168240
END=0x168280


def build(base,out):
    original=base.read_bytes()
    if sha(original)!=BASE_SHA or kodakfw.check(original):
        raise ValueError('base must be the pinned camera-confirmed DNG metadata v3')
    out.mkdir(parents=True,exist_ok=True)
    target=out/'KC713.FW'
    if target.exists():raise FileExistsError('use a fresh firmware output directory')
    off=lambda a:kodakfw.ram_to_file(original,a)
    read=lambda a,n:original[off(a):off(a)+n]
    # Every widget whose storage is reused belongs only to the old Share root.
    owners=[]
    for i in range(0xb6):
        root=struct.unpack('<I',read(0x14ce50+4*i,4))[0]
        if not 0x130000<=root<0x172e00:continue
        flags,ids,lis,handler=struct.unpack('<4I',read(root,16))
        if ids>>16>100 or not 0x130000<=lis<0x172e00:continue
        for j in range(ids>>16):
            child=struct.unpack('<I',read(lis+4*j,4))[0]
            if TITLE<=child<END:owners.append({'screen':hex(i),'child':hex(child)})
    assert owners and all(x['screen']=='0xa8' for x in owners)
    labels={};strings=bytearray()
    for name,value in [('TITLE','MOD SETTINGS'),('DNG_ON','DNG saving: ON'),('DNG_OFF','DNG saving: OFF'),('HIDDEN','Hidden menu')]:
        labels[name]=STRINGS+len(strings);strings.extend(value.encode('ascii')+b'\0')
    assert STRINGS+len(strings)<=EVENTS
    constants=dict(labels,EVENTS=EVENTS)
    (out/'menu_layout.inc').write_text(''.join(f'.equ {k}, {v:#x}\n' for k,v in constants.items()))
    source=Path(__file__).with_name('menu.s')
    code=assemble(source,out,'menu',HOOK)
    assert len(code)<=0xc0, f'{len(code)} bytes do not fit the audited padding'
    objdump=ROOT/'decompiler-project/tools/binutils/arc-elf32-objdump'
    syms={}
    for line in subprocess.check_output([str(objdump),'-t',str(out/'menu.o')],text=True).splitlines():
        fields=line.split()
        if len(fields)>=5 and fields[1]=='g' and '.text' in fields:syms[fields[-1]]=int(fields[0],16)
    fn=lambda name:HOOK+syms[name]
    block=bytearray(END-TITLE)
    def data(at,b):block[at-TITLE:at-TITLE+len(b)]=b
    title=bytearray(read(0x159fa8,32));struct.pack_into('<I',title,28,labels['TITLE'])
    data(TITLE,title)
    data(LIST,struct.pack('<2I',TITLE,WIDGET))
    data(ITEMS,struct.pack('<12I',0,labels['DNG_ON'],0,0,0,0,0,labels['HIDDEN'],0,0,0,0))
    data(STRINGS,strings)
    events=[(0x4405,fn('init')),(0x4409,fn('refresh')),(0x5000,fn('toggle_dng')),
            (0x5001,fn('hidden_menu')),(0x680,0xb97c4),(0x780,0xb97c4),(0x700,0xb97c4),(0,0xb953c)]
    data(EVENTS,b''.join(struct.pack('<2I',*row) for row in events))
    widget=bytearray(read(0x15a118,60));widget[0x1c]=2
    struct.pack_into('<I',widget,0x38,ITEMS)
    screen=struct.pack('<IHHII',0x402,0xa8,2,LIST,fn('start'))
    image=bytearray(original);patches=[]
    def put(at,expected,value,reason):
        assert len(expected)==len(value) and read(at,len(value))==expected,hex(at)
        image[off(at):off(at)+len(value)]=value
        patches.append({'address':hex(at),'file_offset':off(at),'length':len(value),'reason':reason,'old_sha256':sha(expected),'new_sha256':sha(value)})
    assert read(HOOK,0xc0)==bytes(0xc0)
    put(HOOK,bytes(len(code)),code,'Native mod-menu event callbacks in unused scene-hook padding')
    put(WIDGET,read(WIDGET,60),widget,'Use the stock hidden-menu list style with two rows')
    put(TITLE,read(TITLE,len(block)),block,'Reuse Share-only widgets for title, list, text and dispatch table')
    put(SCREEN,bytes.fromhex('02040000a80011002c83160050bc0e00'),screen,'Replace Share root widget list/handler; keep screen ID 0xa8')
    put(0xcbd00,bytes.fromhex('e20f2fb802d8'),bytes.fromhex('e078')*3,
        'Keep capture state while opening mod menu; preserve existing busy checks and preparation')
    kodakfw.fix(image)
    allowed=set(range(0x1f4,0x1fc))
    for p in patches:allowed.update(range(p['file_offset'],p['file_offset']+p['length']))
    for r in kodakfw.records(original):
        if r['type']==1:allowed.update(range(0x10+r['idx']*16+12,0x10+r['idx']*16+16))
    changed=[i for i,(a,b) in enumerate(zip(original,image)) if a!=b]
    assert len(image)==len(original) and not kodakfw.check(image) and all(i in allowed for i in changed)
    for at,size in [(0x67898,6),(0x125a00,548),(0x1241a0,1536),(0x12ff40,180),(0x125780,0x280),(0x12ff00,0x34),(0x13358c,1)]:
        assert image[off(at):off(at)+size]==read(at,size),'confirmed feature changed'
    with target.open('xb') as f:f.write(image)
    (out/'code.bin').write_bytes(image[0x200:0x100200])
    # Retain proven DNG regression inputs for the full-writer tests.
    for name in ['header.bin','header-layout.json','hook.bin','capture-fixtures.json']:
        (out/name).write_bytes((ROOT/'mods/native_dng/metadata-v3'/name).read_bytes())
    manifest={'status':'experimental Share mod menu; not camera-tested','base':str(base.relative_to(ROOT)),
        'base_sha256':BASE_SHA,'firmware_sha256':sha(image),'firmware_bytes':len(image),
        'menu_hook_address':hex(HOOK),'menu_hook_bytes':len(code),'source_sha256':sha(source.read_bytes()),
        'symbols':{k:hex(HOOK+v) for k,v in syms.items()},'labels':{k:hex(v) for k,v in labels.items()},
        'screen_id':'0xa8','hidden_menu_screen_id':'0x3b','share_press_event':'0x680','widget_owners':owners,
        'patches':patches,'changed_bytes':len(changed),'checksums':kodakfw.check(image),
        'dng_default_on_at_boot':True,'toggle_persistence':'current session',
        'metadata_timing':'before_raw_write','metadata_hook_bytes':180,'metadata_callsite_address':'0x125a34',
        'limitations':['native UI/camera regression test required','DNG preference resets ON at boot','film selector outside this prototype']}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (out/'SHA256SUMS').write_text(f'{sha(image)}  KC713.FW\n')
    print(f'{target}: {sha(image)}; menu {len(code)} bytes; checksums OK')
    return manifest


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base',type=Path,default=ROOT/'mods/native_dng/metadata-v3/KC713.FW')
    ap.add_argument('--outdir',type=Path,required=True)
    a=ap.parse_args();build(a.base.resolve(),a.outdir.resolve())
