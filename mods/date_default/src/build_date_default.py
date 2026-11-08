#!/usr/bin/env python3
"""Set a fixed fallback date after RTC power loss, preserving a valid retained clock."""
import argparse
from datetime import date
import json
from pathlib import Path
import struct
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools'))
sys.path.insert(0,str(ROOT/'mods/native_dng/src'))
import kodakfw
from build_metadata_dng import assemble,sha

BASE_SHA='f992a106e1f6a96807e528658a7909f4ecb9cf451df1d8ec3a2e6f3fda9edba5'
TEMPLATE=0x1284ac


def build(base,out,day):
    if not 2007<=day.year<=2037:raise ValueError('date must be within the supported 2007..2037 range')
    original=base.read_bytes()
    if sha(original)!=BASE_SHA or kodakfw.check(original):raise ValueError('base must be pinned confirmed Share menu f992a106')
    out.mkdir(parents=True,exist_ok=True);target=out/'KC713.FW'
    if target.exists():raise FileExistsError('use a fresh firmware output directory')
    off=lambda a:kodakfw.ram_to_file(original,a)
    read=lambda a,n:original[off(a):off(a)+n]
    old_tm=struct.pack('<9i',0,0,12,1,0,107,0,0,0)
    fields=[0,0,12,day.day,day.month-1,day.year-1900,(day.weekday()+1)%7,day.timetuple().tm_yday-1,0]
    template=struct.pack('<9i',*fields)
    source=out/'boot-default.s'
    source.write_text(f'''.text
.global start
 nop_s
start:
 mov_s r0,r1
 mov r1,{TEMPLATE:#x}
 mov_s r2,24
 bl start + (0x54010 - 0xdc45a)
 nop_s
''')
    # The real snippet starts at 2 mod 4. Keep that alignment in the object so
    # ARC's PC-relative BL is encoded against the correct aligned PC base.
    boot=assemble(source,out,'boot-default',0xdc458)[2:];assert len(boot)==18
    source=out/'setup-fallback.s'
    source.write_text(f'''.text
.global start
start:
 ld_s r0,[r13,0x14]
 cmp_s r0,107
 blt_s fallback
 cmp r0,137
 ble_s done
fallback:
 mov_s r0,r13
 mov r1,{TEMPLATE:#x}
 mov_s r2,24
 bl start + (0x54010 - 0xeae58)
done:
 .fill (36-(.-start))/2,2,0x78e0
''')
    setup=assemble(source,out,'setup-fallback',0xeae58);assert len(setup)==36
    image=bytearray(original);patches=[]
    def put(at,expected,value,reason):
        assert len(expected)==len(value) and read(at,len(value))==expected,hex(at)
        image[off(at):off(at)+len(value)]=value
        patches.append({'address':hex(at),'file_offset':off(at),'length':len(value),'reason':reason,'old_sha256':sha(expected),'new_sha256':sha(value)})
    for at,reason in [(0x16a708,'Lost-RTC recovery in 0xf054c'),(TEMPLATE,'Boot date reset action and shared screen default'),(0x128540,'Setup date reset action 0xeb220')]:
        put(at,old_tm,template,reason)
    put(0xdc45a,bytes.fromhex('0cd802a101d803a16bd8c0a1c1a1c4a105a1'),boot,
        'Boot date screen copies six default date/time fields instead of hard-coded January 2007')
    put(0xeae58,bytes.fromhex('0585ebe083f6fde0cef6c0a5fde0c1a5c3f6c2a503f00cd802a501d803a5c4a56bd805a5'),setup,
        'Setup screen preserves supported retained dates through 2037; invalid dates use the new default')
    kodakfw.fix(image)
    allowed=set(range(0x1f4,0x1fc))
    for p in patches:allowed.update(range(p['file_offset'],p['file_offset']+p['length']))
    for r in kodakfw.records(original):
        if r['type']==1:allowed.update(range(0x10+r['idx']*16+12,0x10+r['idx']*16+16))
    changed=[i for i,(a,b) in enumerate(zip(original,image)) if a!=b]
    assert len(image)==len(original) and not kodakfw.check(image) and all(i in allowed for i in changed)
    # Preserve RTC origin/reset-invalid markers and every confirmed injected feature.
    for at,n in [(0x408a8,0x100),(0x124944,36),(0x128488,36),(0x6921c,0x340),
                 (0x1256c0,170),(0x168154,60),(0x168190,240),(0x168370,16),
                 (0xcbd00,6),(0x67898,6),(0x125a00,548),(0x1241a0,1536),
                 (0x12ff40,180),(0x125600,192),(0x125780,0x260),(0x12ff00,0x34)]:
        assert image[off(at):off(at)+n]==read(at,n),f'confirmed feature changed at {at:#x}'
    with target.open('xb') as f:f.write(image)
    (out/'code.bin').write_bytes(image[0x200:0x100200])
    for name in ['header.bin','header-layout.json','hook.bin','menu.bin']:
        (out/name).write_bytes((ROOT/'mods/share_menu/test-v1'/name).read_bytes())
    inherited=json.loads((ROOT/'mods/share_menu/test-v1/manifest.json').read_text())
    manifest={k:inherited[k] for k in ['metadata_timing','metadata_hook_bytes','metadata_callsite_address',
        'menu_hook_address','menu_hook_bytes','symbols','labels']}
    manifest.update({'status':'fixed default date; not camera-tested','base':str(base.relative_to(ROOT)),
        'base_sha256':BASE_SHA,'firmware_sha256':sha(image),'firmware_bytes':len(image),
        'default_date':day.isoformat(),'default_time':'12:00:00','struct_tm':fields,
        'source_sha256':sha(Path(__file__).read_bytes()),'patches':patches,'changed_bytes':len(changed),
        'checksums':kodakfw.check(image),'valid_clock_preserved':True,
        'inherited_verification':'mods/share_menu/test-v1/camera-verification.json',
        'limits':['fixed build date, not automatic current-date detection','RTC still loses power when battery flap opens']})
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (out/'SHA256SUMS').write_text(f'{sha(image)}  KC713.FW\n')
    print(f'{target}: {sha(image)}; fallback {day.isoformat()} 12:00:00; checksums OK')
    return manifest


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base',type=Path,default=ROOT/'mods/share_menu/test-v1/KC713.FW')
    ap.add_argument('--outdir',type=Path,required=True)
    ap.add_argument('--date',type=date.fromisoformat,required=True)
    a=ap.parse_args();build(a.base.resolve(),a.outdir.resolve(),a.date)
