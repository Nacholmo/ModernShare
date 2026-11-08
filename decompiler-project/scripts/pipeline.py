#!/usr/bin/env python3
"""Create, refresh, or export the isolated analysis workspace."""
import argparse
import subprocess
import sys
from pathlib import Path
from prepare_firmware import prepare
from run_headless import run

ROOT=Path(__file__).resolve().parent.parent

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['create','refresh','export'])
    args=parser.parse_args()
    project=ROOT/'projects/KodakC713.gpr'
    if args.action=='create' and project.exists():parser.error('Project exists; use refresh.sh or reexport.sh. Nothing was overwritten.')
    if args.action!='create' and not project.exists():parser.error('Project is missing; run analyze.sh first.')
    if (ROOT/'projects/KodakC713.lock').exists():parser.error('Ghidra project is locked. Close the GUI or running headless job first; lock files are never deleted automatically.')
    subprocess.run([sys.executable,str(ROOT/"scripts/bootstrap.py"),"--check"],cwd=ROOT,check=True)
    prepare()
    command=[ROOT/'projects','KodakC713','-scriptPath',ROOT/'scripts',
             '-max-cpu','4','-log',ROOT/f'logs/{args.action}.log',
             '-scriptlog',ROOT/f'logs/{args.action}-scripts.log']
    if args.action=='create':
        command+=['-import',ROOT/'input/code.bin','-loader','BinaryLoader','-loader-baseAddr','0x30000',
                  '-processor','ARCompact:LE:32:kodak','-cspec','default','-analysisTimeoutPerFile','600',
                  '-preScript','SeedKodak.java',ROOT,'-preScript','ApplyCompilerModel.java',ROOT]
    else:command+=['-process','code.bin','-noanalysis']
    if args.action=='refresh':command+=['-postScript','CorrectBoundaries.java',ROOT,'-postScript','ApplyAnnotations.java',ROOT,'-postScript','ApplyCompilerModel.java',ROOT]
    if args.action!='export':
        command+=['-postScript','DiscoverFunctions.java',ROOT,'-postScript','RefineCaptureTypes.java',
                  '-postScript','EnrichKodak.java',ROOT]
    command+=['-postScript','ExportKodak.java',ROOT,'-postScript','VerifyKodak.java',ROOT,
              '-postScript','VerifyDelaySlots.java',ROOT,'-postScript','ExportWorkspace.java',ROOT]
    # Remove the previous completion marker before beginning; failures never leave it looking fresh.
    (ROOT/'exports/workspace_complete.json').unlink(missing_ok=True)
    run(command,args.action)
    for script in ['build_report.py','verify_workspace.py']:
        subprocess.run([sys.executable,str(ROOT/'scripts'/script)],cwd=ROOT,check=True)
    print(f'Workspace {args.action} finished. Open report/index.html or projects/KodakC713.gpr.')

if __name__=='__main__':
    try:main()
    except (RuntimeError,OSError,subprocess.CalledProcessError) as error:raise SystemExit(str(error))
