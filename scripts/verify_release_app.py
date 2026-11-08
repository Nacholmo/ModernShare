#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Test the actual release executable, including Tk startup and exact firmware output."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modernshare_patcher import RELEASE_SHA256,read_stock

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--app',type=Path,required=True);p.add_argument('--updater',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    app=a.app.resolve();updater=a.updater.resolve();read_stock(updater)
    env=os.environ.copy()
    if platform.system()=='Linux':
        app.chmod(app.stat().st_mode|0o111)
        if app.read_bytes()[8:11]!=b'AI\x02':raise ValueError('Expected a real type-2 AppImage')
        env['APPIMAGE_EXTRACT_AND_RUN']='1' # CI hosts may not allow FUSE mounts.
    def run(args,success=True):
        r=subprocess.run([str(app),*args],env=env,capture_output=True,text=True,timeout=120)
        if (r.returncode==0)!=success:raise RuntimeError(f'Executable check failed: {args[0]}\n{r.stdout}\n{r.stderr}')
    run(['--version']);run(['--smoke-test'])
    with tempfile.TemporaryDirectory(prefix='ModernShare-release-') as temporary:
        directory=Path(temporary);output=directory/'KC713.FW'
        run(['--headless','--input',str(updater),'--output',str(output)])
        digest=hashlib.sha256(output.read_bytes()).hexdigest()
        if digest!=RELEASE_SHA256:raise ValueError('Release executable generated the wrong firmware')
        run(['--headless','--input',str(updater),'--output',str(output)],success=False)
        if hashlib.sha256(output.read_bytes()).hexdigest()!=digest:raise ValueError('Existing output was overwritten')
        invalid=directory/'invalid.exe';invalid.write_bytes(b'unsupported');missing=directory/'must-not-exist.fw'
        run(['--headless','--input',str(invalid),'--output',str(missing)],success=False)
        if missing.exists():raise ValueError('Invalid input produced an output file')
    report=dict(passed=True,platform=platform.system(),architecture=platform.machine(),asset=app.name,
                executable_sha256=hashlib.sha256(app.read_bytes()).hexdigest(),firmware_sha256=digest,
                checks=['executable startup','packaged Tk GUI startup','original updater to exact confirmed firmware','existing output preserved','invalid input rejected'],
                appimage_extraction_mode=platform.system()=='Linux')
    a.report.write_text(json.dumps(report,indent=2)+'\n')
    release=a.report.parent
    (release/'SHA256SUMS').write_text(''.join(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n'
                                            for path in sorted(release.iterdir()) if path.is_file() and path.name!='SHA256SUMS'))
    print(json.dumps(report,indent=2))
