#!/usr/bin/env python3
"""Validate and extract the isolated, byte-exact C713 1.30 stock snapshot."""
import hashlib
import json
import struct
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
STOCK_SHA256='06133ed6bc6272f6b1ab9c784723d9259c71cb4ef88b3defb6ed36f4a4e66c9b'

class FirmwareError(ValueError):
    """The input is not a valid instance of this project's stock firmware."""

def require(condition,message):
    if not condition:raise FirmwareError(message)

def sum32(blob):
    require(len(blob)%4==0,'sum32 input is not word-aligned')
    return sum(struct.unpack('<%dI'%(len(blob)//4),blob))&0xffffffff

def validate_firmware(raw):
    require(len(raw)==2172416,f'Unexpected firmware size: {len(raw)}')
    require(raw[:4]==b'RHIR','Missing RHIR magic')
    require(raw[0x1f0:0x1f4]==b'KHIR','Missing KHIR magic')
    require(struct.unpack_from('<I',raw,8)[0]&0xffff00==0x034200,'Wrong camera model')
    require(raw[6]==5,'Expected five stock section records')
    header_sum,header_not=struct.unpack_from('<II',raw,0x1f4)
    require(sum32(raw[:0x1f0])==header_sum,'Header checksum mismatch')
    require(header_sum^header_not==0xffffffff,'Header complement mismatch')
    sections=[]
    for i in range(raw[6]):
        kind,sector,count,address,checksum=struct.unpack_from('<IHHII',raw,0x10+16*i)
        offset,size=sector*512,count*512
        require(size>0 and offset+size<=len(raw),f'Section {i} outside file or empty')
        blob=raw[offset:offset+size];actual=sum32(blob)
        if kind==1:require(actual==checksum,f'Section {i} checksum mismatch')
        name=['code','data','graphics','language','special'][i]
        sections.append(dict(index=i,name=name,type=kind,file_offset=offset,size=size,
            ram_address=address,checksum=checksum,calculated_sum32=actual,checksum_verified=kind==1,
            mapped=i in (0,1,2),path=f'input/{name}.bin',sha256=hashlib.sha256(blob).hexdigest()))
    require([s['type'] for s in sections]==[1,1,0,0,2],'Unexpected section types')
    digest=hashlib.sha256(raw).hexdigest()
    require(digest==STOCK_SHA256,'Input differs from pinned stock SHA256; this workspace analyzes stock firmware only')
    return dict(source='input/kc713.fw',size=len(raw),sha256=digest,header_checksum_verified=True,
        sections=sections,language_mapping='Flash-backed; not mapped at nominal RAM address.',
        provenance='User-authorized read-only copy of ../firmware/stock/kc713.fw. Parent project files are never modified.')

def prepare(root=ROOT):
    raw=(root/'input/kc713.fw').read_bytes();manifest=validate_firmware(raw)
    # No output is written until every validation has passed.
    for section in manifest['sections']:
        start=section['file_offset'];(root/section['path']).write_bytes(raw[start:start+section['size']])
    (root/'input/manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest

def main():
    try:manifest=prepare()
    except (FirmwareError,OSError) as error:raise SystemExit(f'Firmware validation failed: {error}')
    for section in manifest['sections']:
        print(f"{section['name']:10s} RAM=0x{section['ram_address']:08x} size=0x{section['size']:x} mapped={section['mapped']}")
    print('Stock SHA256:',manifest['sha256'])

if __name__=='__main__':main()
