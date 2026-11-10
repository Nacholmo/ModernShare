#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Audit the public Git file set; reject private inputs and generated binaries."""
from pathlib import Path
import hashlib
import re
import subprocess
ROOT=Path(__file__).resolve().parents[1]

# Explicitly authorized demonstration photos; never allow arbitrary captures.
PUBLIC_CAMERA_PHOTOS={
    'photos/modernshare.jpg': '9aa62de6ddfcf7fc36c216a566af2459eac1d5eee6a8ca6a2b56c1c7af177faf',
    'photos/film_selector.jpg': '90063244e800255fd99254b25ff69f70c8af58d9a53aa21907277ca51066bdf6',
    'photos/menus.jpg': '4b640f8ae74ad8949c85f5059b871cb9be7c850903ee694db30c8b8b465cca33',
}

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
        approved_photo=rel in PUBLIC_CAMERA_PHOTOS
        if (p.suffix.lower() in forbidden and not approved_photo) or any(part.startswith('cd703_card_') for part in p.parts):errors.append(f'private/generated file: {rel}')
        data=p.read_bytes()
        if approved_photo and hashlib.sha256(data).hexdigest()!=PUBLIC_CAMERA_PHOTOS[rel]:errors.append(f'unreviewed photo content: {rel}')
        if data[:4] in (b'RHIR',b'\x7fELF') or data[:2]==b'MZ':errors.append(f'firmware/executable payload: {rel}')
        if re.search(rb'-{5}BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-{5}',data):errors.append(f'private key: {rel}')
        if p.suffix in {'.py','.json','.md','.java','.sh'} and re.search(rb'/(?:home|run/media)/[A-Za-z0-9_.-]+/',data):errors.append(f'personal absolute path: {rel}')
    for required in ['LICENSE','NOTICE','THIRD_PARTY_NOTICES.md','LICENSES/MIT-Film-Luts.txt','LICENSES/Apache-2.0.txt','boot_image.png','src/release/bundle-0.9.json']:
        if required not in paths:errors.append(f'missing: {required}')
    if errors:raise ValueError('\n'.join(errors))
    return paths

if __name__=='__main__':
    try:print(f'Public-file audit passed: {len(audit())} files; no firmware, private captures, tool binaries or personal paths.')
    except ValueError as e:raise SystemExit(str(e))
