#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Small, standard-library patch engine for the GUI and frozen release apps."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import sys
import zipfile
import zlib

ROOT=Path(__file__).resolve().parent
STOCK_SHA256='06133ed6bc6272f6b1ab9c784723d9259c71cb4ef88b3defb6ed36f4a4e66c9b'
RELEASE_SHA256='091663ac848b6ee07c2a9252b9a9662e8cc7c463275e2dde62edb10d8e0f6003'
STOCK_BYTES=2172416
DOWNLOAD_PAGE='https://www.touslesdrivers.com/index.php?v_page=23&v_code=19867&v_langue=en'

def sha(data):return hashlib.sha256(data).hexdigest()

def read_stock(path):
    """Read a local .fw or ZIP/SFX updater without executing or extracting paths."""
    path=Path(path)
    size=path.stat().st_size
    if size>32*1024*1024:raise ValueError('Selected file is too large to be the Kodak updater.')
    with path.open('rb') as f:magic=f.read(4)
    if magic==b'RHIR':
        if size!=STOCK_BYTES:raise ValueError('Stock firmware has the wrong size.')
        data=path.read_bytes()
    else:
        try:
            with zipfile.ZipFile(path) as archive:
                members=[i for i in archive.infolist() if i.filename.replace('\\','/').rsplit('/',1)[-1].lower()=='kc713.fw' and not i.is_dir()]
                if len(members)!=1:raise ValueError('Updater must contain exactly one kc713.fw file.')
                member=members[0]
                if member.file_size!=STOCK_BYTES or member.flag_bits&1:
                    raise ValueError('Updater contains unsupported or encrypted firmware.')
                with archive.open(member) as f:data=f.read(STOCK_BYTES+1)
        except (zipfile.BadZipFile,NotImplementedError,RuntimeError) as e:
            raise ValueError('Select the original KC713130.exe updater or a stock kc713.fw file.') from e
    if len(data)!=STOCK_BYTES or sha(data)!=STOCK_SHA256:
        raise ValueError('This is not the supported C713 firmware 1.30. The input SHA-256 does not match.')
    return data

def patch(stock,bundle=None):
    if len(stock)!=STOCK_BYTES or sha(stock)!=STOCK_SHA256:raise ValueError('Unsupported stock firmware.')
    if bundle is None:bundle=json.loads((ROOT/'src/release/bundle-0.8.json').read_text())
    if bundle['stock_sha256']!=STOCK_SHA256 or bundle['firmware_sha256']!=RELEASE_SHA256:
        raise ValueError('Unsupported modification bundle.')
    result=bytearray(stock)
    # Bound decoding even if a local bundle is accidentally damaged/replaced.
    decoder=zlib.decompressobj()
    packed=decoder.decompress(base64.b64decode(bundle['patch_data_zlib_base64'],validate=True),128*1024+1)
    if len(packed)>128*1024 or not decoder.eof or decoder.unused_data:raise ValueError('Invalid modification data.')
    if sha(packed)!=bundle['patch_data_sha256']:raise ValueError('Modification data checksum mismatch.')
    edits=json.loads(packed)
    for edit in edits:
        at=edit['offset'];value=bytes.fromhex(edit['value'])
        if at<0 or at+len(value)>len(result):raise ValueError('Modification lies outside firmware.')
        result[at:at+len(value)]=value
    for copy in bundle['copies']:
        a,b,n=copy['source'],copy['destination'],copy['length']
        if min(a,b,n)<0 or max(a+n,b+n)>len(result):raise ValueError('Invalid local firmware copy.')
        source=stock if copy['input']=='stock' else result
        result[b:b+n]=source[a:a+n]
    from tools import kodakfw
    kodakfw.fix(result)
    if kodakfw.check(result) or sha(result)!=RELEASE_SHA256:
        raise ValueError('Generated firmware failed verification. No output was written.')
    return bytes(result)

def generate(source,output,progress=None):
    output=Path(output)
    if output.exists():raise FileExistsError('KC713.FW already exists here. Choose another output folder.')
    progress=progress or (lambda value,message:None)
    progress(10,'Reading Kodak updater…');stock=read_stock(source)
    progress(40,'Generating ModernShare firmware…');firmware=patch(stock)
    progress(85,'Verifying and saving…')
    # Exclusive creation never overwrites a user's firmware, input or photo.
    created=False
    try:
        with output.open('xb') as f:
            created=True;f.write(firmware);f.flush()
            import os
            os.fsync(f.fileno())
        if output.read_bytes()!=firmware:raise OSError('Firmware read-back verification failed.')
    except Exception:
        if created:output.unlink(missing_ok=True)
        raise
    progress(100,'Firmware ready.')
    return dict(path=str(output),sha256=RELEASE_SHA256,bytes=len(firmware))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('updater',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    try:print(json.dumps(generate(a.updater,a.output),indent=2))
    except (OSError,ValueError) as e:p.exit(1,f'{e}\n')
