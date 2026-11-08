#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Fetch the original updater into ignored CI storage for integration checks only."""
import argparse
import hashlib
from pathlib import Path
import sys
import time
import urllib.request
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modernshare_patcher import read_stock
URL='https://fichiers.touslesdrivers.com/19867/KC713130.exe'
UPDATER_SHA256='0228ebb1bd13fea29942c9f67d572773b829b133bef53d4841cd43f5bd17f712'

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--outdir',type=Path,required=True);a=p.parse_args()
    if a.outdir.exists():p.error('Use a fresh input directory')
    for attempt in range(3):
        try:
            with urllib.request.urlopen(URL,timeout=60) as response:data=response.read(2*1024*1024)
            break
        except OSError:
            if attempt==2:raise
            time.sleep(3)
    if hashlib.sha256(data).hexdigest()!=UPDATER_SHA256:raise ValueError('Original updater download hash mismatch')
    a.outdir.mkdir(parents=True)
    updater=a.outdir/'KC713130.exe';updater.write_bytes(data)
    (a.outdir/'kc713.fw').write_bytes(read_stock(updater))
    print('Original updater and embedded stock hashes verified. These CI inputs are not release assets.')
