#!/usr/bin/env python3
"""Read-only menu patch/flag inspection of the last complete camera memory dump."""
import argparse
import json
from pathlib import Path
import struct
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'mods/native_dng/src'))
from inspect_capture import inspect_dump,DUMP_BYTES


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('dump',type=Path)
    ap.add_argument('--build',type=Path,default=ROOT/'mods/share_menu/test-v1')
    a=ap.parse_args();data=a.dump.read_bytes();frames,tail=divmod(len(data),DUMP_BYTES)
    if not frames:ap.error('no complete memory-dump frame')
    frame=data[(frames-1)*DUMP_BYTES:frames*DUMP_BYTES]
    manifest=json.loads((a.build/'manifest.json').read_text());fw=(a.build/'KC713.FW').read_bytes()
    def matches(at,n):return frame[at:at+n]==fw[at-0x2fe00:at-0x2fe00+n]
    u32=lambda at:struct.unpack_from('<I',frame,at)[0]
    screen=u32(0x134db8)
    report={'dump':str(a.dump),'complete_frames':frames,'trailing_incomplete_bytes':tail,
        'menu_code_matches':matches(int(manifest['menu_hook_address'],16),manifest['menu_hook_bytes']),
        'capture_state_patch_matches':matches(0xcbd00,6),
        'share_screen_handler_matches':u32(0x16837c)==int(manifest['symbols']['start'],16),
        'dng_saving_enabled':bool(frame[0x13358c]),'jpeg_saving_enabled':bool(frame[0x133185]),
        'camera_state':frame[0x132904],'current_screen_pointer':hex(screen),
        'current_screen_id':hex(struct.unpack_from('<H',frame,screen+4)[0]) if 0x100<=screen<len(frame)-6 else None,
        'dng_writer':inspect_dump(a.dump,a.build)}
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
