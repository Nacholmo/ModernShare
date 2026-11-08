#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Prepare ignored, local Ghidra inputs from an explicitly supplied stock image."""
import argparse
import importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--stock',type=Path,required=True);a=p.parse_args()
    spec=importlib.util.spec_from_file_location('prepare',ROOT/'decompiler-project/scripts/prepare_firmware.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    data=a.stock.read_bytes();module.validate_firmware(data)
    base=ROOT/'decompiler-project'
    for name in ['input','projects','logs','exports','report','diagnostics','runtime/tmp']:(base/name).mkdir(parents=True,exist_ok=True)
    target=base/'input/kc713.fw'
    if target.exists():raise FileExistsError('Analysis input exists; it was not overwritten')
    with target.open('xb') as f:f.write(data)
    module.prepare(base)
    print('Local analysis inputs prepared; see docs/DEVELOPMENT.md for tool setup and analysis.')
