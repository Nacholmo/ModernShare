#!/usr/bin/env python3
"""Install or verify the pinned, project-local Linux x86-64 analysis toolchain."""
import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent

def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def check(path,digest):
    if not path.is_file() or sha(path)!=digest:raise RuntimeError(f'Missing or mismatched pinned file: {path.relative_to(ROOT)}')

def obtain(item,check_only):
    path=ROOT/item['archive'] if 'archive' in item else ROOT/item['path']
    if path.is_file():
        check(path,item['sha256']);return path
    if check_only:raise RuntimeError(f'Missing {path.relative_to(ROOT)}; run bootstrap.py without --check')
    path.parent.mkdir(parents=True,exist_ok=True);part=path.with_name(path.name+'.part')
    subprocess.run(['curl','--fail','--location','--retry','3',item['url'],'--output',str(part)],check=True)
    check(part,item['sha256']);part.replace(path);return path

def safe_zip_extract(archive):
    with zipfile.ZipFile(archive) as zipped:
        for entry in zipped.infolist():
            target=(ROOT/'tools'/entry.filename).resolve()
            if not target.is_relative_to((ROOT/'tools').resolve()):raise RuntimeError('Archive path escaped tool directory')
        zipped.extractall(ROOT/'tools')
        for entry in zipped.infolist():
            mode=entry.external_attr>>16
            if mode&0o111:(ROOT/'tools'/entry.filename).chmod(mode&0o777)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true',help='Verify existing downloads, pinned processor sources, and generated model')
    args=parser.parse_args();lock=json.loads((ROOT/'toolchain.lock.json').read_text())
    if platform.system()!='Linux' or platform.machine() not in ('x86_64','AMD64'):parser.error('The pinned binary toolchain supports Linux x86-64.')
    for name in ['downloads','tools','logs','runtime/tmp']: (ROOT/name).mkdir(parents=True,exist_ok=True)
    for name in ['ghidra','jdk']:
        item=lock[name];archive=obtain(item,args.check);target=ROOT/item['directory']
        if not target.is_dir():
            if args.check:raise RuntimeError(f'{name} is not extracted')
            if name=='ghidra':safe_zip_extract(archive)
            else:
                with tarfile.open(archive) as tar:tar.extractall(ROOT/'tools',filter='data')
        executable=target/('support/analyzeHeadless' if name=='ghidra' else 'bin/java')
        if not executable.is_file() or not os.access(executable,os.X_OK):raise RuntimeError(f'Not executable: {executable}')
    for item in lock['processor']['files']:obtain(item,args.check)
    if args.check:
        model=json.loads((ROOT/'patches/processor_model.json').read_text())
        lang=ROOT/'tools/ghidra_12.2_PUBLIC/Ghidra/Processors/ARC/data/languages'
        for name,digest in model['generated_files_sha256'].items():check(lang/name,digest)
        if 'compiled_sla_sha256' not in model:raise RuntimeError('Model build receipt is missing; run bootstrap.py without --check')
        check(lang/'KodakARCompact.sla',model['compiled_sla_sha256'])
    else:
        subprocess.run([sys.executable,str(ROOT/'scripts/build_processor_model.py')],cwd=ROOT,check=True)
        subprocess.run(['bash','-c','source "$1"; "$GHIDRA_ROOT/support/sleigh" "$GHIDRA_ROOT/Ghidra/Processors/ARC/data/languages/KodakARCompact.slaspec"','_',str(ROOT/'scripts/environment.sh')],cwd=ROOT,check=True)
    if not args.check:
        model_path=ROOT/'patches/processor_model.json';model=json.loads(model_path.read_text())
        model['compiled_sla_sha256']=sha(ROOT/'tools/ghidra_12.2_PUBLIC/Ghidra/Processors/ARC/data/languages/KodakARCompact.sla')
        model_path.write_text(json.dumps(model,indent=2)+'\n')
    print('Toolchain verified: Ghidra 12.2, JDK 25.0.5+8, pinned upstream sources, Kodak processor model.')

if __name__=='__main__':
    try:main()
    except (RuntimeError,OSError,subprocess.CalledProcessError) as error:raise SystemExit(f'Toolchain setup failed: {error}')
