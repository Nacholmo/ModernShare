#!/usr/bin/env python3
"""Fit Velvia 100 and Kodachrome 64 to the existing stock-curve CCM pipeline."""
import argparse
import json
from pathlib import Path
import struct
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'mods/lut/src'),str(ROOT/'mods/native_dng/src')]
import fit_lut as F
from build_metadata_dng import sha
LOOKS=[('Velvia 100','colorslide/fuji_velvia_100_generic'),('Kodachrome 64','colorslide/kodak_kodachrome_64')]

def fit(out):
    out.mkdir(parents=True,exist_ok=True)
    base=(ROOT/'mods/mod_settings/test-v0.6/KC713.FW').read_bytes()
    stock=(ROOT/'firmware/stock/kc713.fw').read_bytes();cam=F.load_camera(stock)
    for a,n in [(F.CURVE_A,1024),(F.CURVE_B,1024),(F.YMAT,48),*[ (a,48) for a in F.CCM_ILLUM]]:
        assert base[F.DATA(a):F.DATA(a)+n]==stock[F.DATA(a):F.DATA(a)+n]
    records=[];blob=bytearray()
    for name,key in LOOKS:
        path=ROOT/'mods/lut/looks/filmluts'/f'{key}.cube';cube=F.read_cube(str(path));result=F.fit_ccm(cam,cube)
        d=bytearray(stock);F.patch(d,cam,result)
        matrices=b''.join(d[F.DATA(a):F.DATA(a)+48] for a in [*F.CCM_ILLUM,F.YMAT])
        values=np.array(struct.unpack('<48i',matrices));assert np.max(np.abs(values.reshape(4,3,4)[:,:,:3]))<4*65536
        blob.extend(matrices);records.append({'name':name,'lut':str(path.relative_to(ROOT)),'lut_sha256':sha(path.read_bytes()),'method':'CCM-only, stock curves/Ymat; grayscale neutrality preserved','R':result['R'].tolist(),'stock_deltaE':list(map(float,result['colour']['stock'])),'fit_deltaE':list(map(float,result['colour']['fit'])),'matrices_sha256':sha(matrices)})
        print(name,'mean deltaE:',float(result['colour']['stock'][0]),'->',float(result['colour']['fit'][0]),flush=True)
    (out/'new-films.bin').write_bytes(blob);(out/'fit.json').write_text(json.dumps({'source_sha256':sha(Path(__file__).read_bytes()),'base_sha256':sha(base),'records':records,'bytes':len(blob),'sha256':sha(blob)},indent=2)+'\n')
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--outdir',type=Path,required=True);a=p.parse_args();fit(a.outdir.resolve())
