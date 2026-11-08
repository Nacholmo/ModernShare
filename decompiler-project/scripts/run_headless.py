#!/usr/bin/env python3
"""Run Ghidra and fail on script errors even when its process returns zero."""
import os
import re
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent

def run(arguments,label):
    log=ROOT/'logs'/f'{label}-console.log'
    command=[str(ROOT/'tools/ghidra_12.2_PUBLIC/support/analyzeHeadless'),*map(str,arguments)]
    errors=[]
    with log.open('w') as output:
        process=subprocess.Popen(command,cwd=ROOT,env=os.environ.copy(),stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,text=True,bufsize=1)
        for line in process.stdout:
            output.write(line);output.flush()
            if re.search(r'\bERROR\b',line):errors.append(line.rstrip())
            if any(token in line for token in ['ERROR','PROGRESS','COMPLETE','DISCOVERY:','Applied ','Save succeeded','Import succeeded']):
                print(line.rstrip(),flush=True)
        code=process.wait()
    if code or errors:
        raise RuntimeError(f'Ghidra failed (exit {code}, {len(errors)} error messages). Inspect {log.relative_to(ROOT)}')
    return log
