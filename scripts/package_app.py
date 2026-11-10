#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Package the small Tk app on the current Windows/Linux host; never bundle firmware."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import urllib.request
import zipfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from audit_repo import audit

def download(item,destination):
    with urllib.request.urlopen(item['url'],timeout=120) as response:
        data=response.read()
    if hashlib.sha256(data).hexdigest()!=item['sha256']:
        raise ValueError('AppImage tool download hash mismatch: '+item['url'])
    destination.write_bytes(data);destination.chmod(0o755)

def appimage(executable,out):
    appdir=out/'ModernShare.AppDir'
    shutil.copytree(executable.parent,appdir/'usr/lib/modernshare')
    for name in ['AppRun','modernshare.desktop','modernshare.svg']:
        shutil.copyfile(ROOT/'packaging/appimage'/name,appdir/name)
    (appdir/'AppRun').chmod(0o755)
    # Include notices and source-download information in the mounted app.
    shutil.copytree(ROOT/'LICENSES',appdir/'usr/share/licenses/modernshare')
    shutil.copyfile(ROOT/'LICENSE',appdir/'usr/share/licenses/modernshare/LICENSE')
    tools=out/'appimage-tools';tools.mkdir()
    lock=json.loads((ROOT/'packaging/appimage/toolchain.json').read_text())
    download(lock['appimagetool'],tools/'appimagetool.AppImage')
    download(lock['runtime'],tools/'runtime-x86_64')
    destination=out/'release/ModernShare-0.9-Linux-x86_64.AppImage'
    env=os.environ.copy();env.update(ARCH='x86_64',APPIMAGE_EXTRACT_AND_RUN='1',VERSION='0.9')
    subprocess.run([str(tools/'appimagetool.AppImage'),'--no-appstream','--runtime-file',str(tools/'runtime-x86_64'),
                    str(appdir),str(destination)],env=env,check=True)
    destination.chmod(0o755)
    if destination.read_bytes()[8:11]!=b'AI\x02':raise ValueError('Output is not a type-2 AppImage')
    return destination

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--outdir',type=Path,required=True);a=p.parse_args()
    out=a.outdir.resolve()
    if out.exists():p.error('Use a fresh output directory')
    system=platform.system()
    if system not in ('Windows','Linux'):p.error('Package on Windows or Linux for the matching target')
    sources=audit();out.mkdir(parents=True)
    command=[sys.executable,'-m','PyInstaller','--onefile' if system=='Windows' else '--onedir','--windowed','--noupx','--name','ModernShare',
             '--distpath',str(out/'app'),'--workpath',str(out/'work'),'--specpath',str(out/'spec'),
             '--paths',str(ROOT),'--hidden-import','tools.kodakfw','--exclude-module','numpy','--exclude-module','PIL']
    for source,destination in [('src/release/bundle-0.9.json','src/release'),('LICENSE','.'),('NOTICE','.'),('THIRD_PARTY_NOTICES.md','.'),('LICENSES','LICENSES')]:
        command.extend(['--add-data',str(ROOT/source)+':'+destination])
    command.append(str(ROOT/'modernshare_gui.py'))
    subprocess.run(command,cwd=ROOT,check=True)
    (out/'release').mkdir()
    if system=='Windows':
        executable=out/'release/ModernShare-0.9-Windows-x86_64.exe'
        shutil.copyfile(out/'app/ModernShare.exe',executable)
    else:
        executable=appimage(out/'app/ModernShare/ModernShare',out)
    source_zip=out/'release/ModernShare-0.9-source.zip'
    with zipfile.ZipFile(source_zip,'x',compression=zipfile.ZIP_DEFLATED) as archive:
        for rel in sources:archive.write(ROOT/rel,'ModernShare-0.9/'+rel)
    for name in ['LICENSE','NOTICE','THIRD_PARTY_NOTICES.md']:shutil.copyfile(ROOT/name,out/name)
    shutil.copytree(ROOT/'LICENSES',out/'LICENSES')
    with zipfile.ZipFile(out/'release/ModernShare-0.9-licenses.zip','x',compression=zipfile.ZIP_DEFLATED) as archive:
        for name in ['LICENSE','NOTICE','THIRD_PARTY_NOTICES.md']:archive.write(ROOT/name,name)
        for path in sorted((ROOT/'LICENSES').glob('*')):archive.write(path,'LICENSES/'+path.name)
    (out/'release/SHA256SUMS').write_text(''.join(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n'
                                                for path in sorted((out/'release').iterdir()) if path.is_file()))
    print(f'App: {executable}\nCorresponding source: {source_zip}')
