#!/usr/bin/env python3
"""Bind build, instruction-emulation reports and a fresh rebuild before staging."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools'))
import kodakfw
from settings_record import encode,decode,choose

def sha(b):return hashlib.sha256(b).hexdigest()

def verify(build,rebuild):
    firmware=(build/'KC713.FW').read_bytes();h=sha(firmware)
    m=json.loads((build/'manifest.json').read_text())
    assert h==m['firmware_sha256'] and not kodakfw.check(firmware)
    assert firmware==(rebuild/'KC713.FW').read_bytes()
    rebuilt=json.loads((rebuild/'manifest.json').read_text())
    builder=sha(Path(__file__).with_name('build_modernshare.py').read_bytes())
    assert rebuilt['builder_sha256']==builder
    assert m['settings_source_sha256']==sha(Path(__file__).with_name('settings.s').read_bytes())
    assert m['artwork']['sha256']==sha((ROOT/m['artwork']['source']).read_bytes())
    reports={}
    for name,count in [('settings-emulation.json',54),('menu-emulation.json',129),('date-emulation.json',15),('emulation.json',50)]:
        r=json.loads((build/name).read_text())
        assert r['passed'] and r['firmware_sha256']==h and len(r['scenarios'])==count
        assert all(case['passed'] for case in r['scenarios'])
        reports[name]=dict(scenarios=count,sha256=sha((build/name).read_bytes()))
    assert 'ERROR' not in (build/'ghidra-console.log').read_text()
    base=(ROOT/m['base']).read_bytes()
    assert sha(base)==m['base_sha256']
    allowed=set(range(0x1f4,0x1fc))
    for patch in m['patches']:
        offset,length=patch['file_offset'],patch['length']
        assert sha(base[offset:offset+length])==patch['old_sha256']
        assert sha(firmware[offset:offset+length])==patch['new_sha256']
        allowed.update(range(offset,offset+length))
    for record in kodakfw.records(base):
        if record['type'] in (0,1):allowed.update(range(0x10+record['idx']*16+12,0x10+record['idx']*16+16))
    assert len(base)==len(firmware)
    changed=[i for i,(a,b) in enumerate(zip(base,firmware)) if a!=b]
    assert len(changed)==m['changed_bytes'] and all(i in allowed for i in changed)
    # Independent host codec covers every supported combination and wrap selection.
    for film in range(7):
        for dng in range(2):
            for generation in [0,1,0xffffffff]:
                r=decode(encode(film,dng,generation))
                assert (r['film_index'],r['dng'],r['generation'])==(film,bool(dng),generation)
    assert choose(encode(1,0,0xffffffff),encode(6,1,0))[0]==1
    assert choose(b'broken',encode(2,1,7))[0]==1
    assert choose(b'',b'') is None
    # A metadata-only builder cleanup happened after candidate generation.
    # The final builder's fresh rebuild is byte-identical to the tested candidate.
    m['builder_sha256']=builder
    (build/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    result=dict(passed=True,firmware_sha256=h,rebuild=str(rebuild.relative_to(ROOT)),byte_identical_rebuild=True,
                checksums=kodakfw.check(firmware),changed_bytes=len(changed),reports=reports,
                host_record_roundtrips=42,boot_roundtrip=m['artwork']['roundtrip_exact'],
                boot_image_sha256=m['artwork']['sha256'],boot_bytes=m['artwork']['used'],
                preserved=['all graphics/palettes/stock images','English text prefix','shared Share helper and literal pool',
                           'all film matrices and preview code','DNG writer/header/metadata','date/clock code'],
                limits='File/UI/RTC boundaries mocked; physical camera persistence, SD write durability and boot display await trial')
    (build/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('build',type=Path);p.add_argument('rebuild',type=Path)
    a=p.parse_args();verify(a.build.resolve(),a.rebuild.resolve())
