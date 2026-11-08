#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Audit the public Git file set; reject private inputs and generated binaries."""
from pathlib import Path
import re
import subprocess
ROOT=Path(__file__).resolve().parents[1]

def public_files():
    top=subprocess.run(['git','-C',str(ROOT),'rev-parse','--show-toplevel'],capture_output=True,text=True)
    if top.returncode==0 and Path(top.stdout.strip()).resolve()==ROOT:
        result=subprocess.run(['git','-C',str(ROOT),'ls-files','--cached','--others','--exclude-standard','-z'],capture_output=True,check=True)
        return sorted(set(p.decode() for p in result.stdout.split(b'\0') if p))
    excluded={'.git','__pycache__','.venv','build','dist','runtime','downloads','projects','exports','report','input','diagnostics'}
    return sorted(p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file() and not any(s in excluded for s in p.relative_to(ROOT).parts))

def audit():
    paths=public_files();errors=[]
    forbidden={'.fw','.old','.raw','.dng','.jpg','.jpeg','.exe','.appimage','.bin','.o','.class','.sla','.gpr','.so','.dll','.zip'}
    for rel in paths:
        p=ROOT/rel
        if p.is_symlink():errors.append(f'symlink: {rel}');continue
        if p.suffix.lower() in forbidden or any(part.startswith('cd703_card_') for part in p.parts):errors.append(f'private/generated file: {rel}')
        data=p.read_bytes()
        if data[:4] in (b'RHIR',b'\x7fELF') or data[:2]==b'MZ':errors.append(f'firmware/executable payload: {rel}')
        if re.search(rb'-{5}BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-{5}',data):errors.append(f'private key: {rel}')
        if p.suffix in {'.py','.json','.md','.java','.sh'} and re.search(rb'/(?:home|run/media)/[A-Za-z0-9_.-]+/',data):errors.append(f'personal absolute path: {rel}')
    for required in ['LICENSE','NOTICE','THIRD_PARTY_NOTICES.md','LICENSES/MIT-Film-Luts.txt','LICENSES/Apache-2.0.txt','boot_image.png','src/release/bundle-0.8.json']:
        if required not in paths:errors.append(f'missing: {required}')
    if errors:raise ValueError('\n'.join(errors))
    return paths

if __name__=='__main__':
    try:print(f'Public-file audit passed: {len(audit())} files; no firmware, captures, tool binaries or personal paths.')
    except ValueError as e:raise SystemExit(str(e))
