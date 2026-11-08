#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Run all four firmware suites against a local stock Ghidra project, read-only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build',type=Path,required=True)
    p.add_argument('--ghidra-home',type=Path,default=Path(os.environ.get('GHIDRA_ROOT',ROOT/'decompiler-project/tools/ghidra_12.2_PUBLIC')))
    p.add_argument('--project-dir',type=Path,default=ROOT/'decompiler-project/projects')
    p.add_argument('--project-name',default='KodakC713');a=p.parse_args()
    build=a.build.resolve();digest=hashlib.sha256((build/'KC713.FW').read_bytes()).hexdigest()
    log=build/'emulation-console.log'
    if log.exists():p.error('Emulation log already exists; use a fresh build directory')
    paths=';'.join(str(ROOT/'mods'/name/'src') for name in ['sd_settings','date_default','native_dng'])
    command=[str(a.ghidra_home/'support/analyzeHeadless'),str(a.project_dir.resolve()),a.project_name,
             '-process','code.bin','-noanalysis','-readOnly','-scriptPath',paths,
             '-postScript','TestSettings.java',str(build),'-postScript','TestModernShare.java',str(build),
             '-postScript','TestDateDefault.java',str(build),'-postScript','TestNativeDng.java',str(ROOT),str(build)]
    with log.open('x') as f:
        result=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT)
    reports={}
    if result.returncode or 'ERROR' in log.read_text():raise SystemExit(f'Emulation failed; inspect {log}')
    for filename,count in [('settings-emulation.json',54),('menu-emulation.json',129),('date-emulation.json',15),('emulation.json',50)]:
        path=build/filename;r=json.loads(path.read_text())
        if not (r['passed'] and r['firmware_sha256']==digest and len(r['scenarios'])==count and all(c['passed'] for c in r['scenarios'])):
            raise SystemExit(f'Invalid or failed report: {path}')
        reports[filename]={'scenarios':count,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    summary={'passed':True,'firmware_sha256':digest,'scenarios':248,'sensor_fixture':'synthetic deterministic bytes; no personal photos','reports':reports}
    (build/'public-emulation-verification.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
