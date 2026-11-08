#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Manual/virtual-display GUI integration test; requires a local original updater."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch
import tkinter as tk
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from modernshare_gui import App
from modernshare_patcher import RELEASE_SHA256

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--updater',type=Path,required=True);p.add_argument('--report',type=Path);p.add_argument('--screenshot',type=Path);a=p.parse_args()
    root=tk.Tk();app=App(root);root.geometry('740x540+0+0');root.update()
    if a.screenshot:
        from PIL import ImageGrab
        ImageGrab.grab(bbox=(0,0,740,540)).save(a.screenshot)
    app.start()
    if 'first' not in app.status.get():raise RuntimeError('Missing fields were not rejected')
    infos=[];errors=[]
    def drain():
        end=time.time()+15
        while app.busy and time.time()<end:root.update();time.sleep(.02)
        if app.busy:raise RuntimeError('GUI worker did not finish')
    try:
        with tempfile.TemporaryDirectory(prefix='ModernShare-ui-') as folder,patch('modernshare_gui.messagebox.showinfo',side_effect=lambda *a,**k:infos.append(a)),patch('modernshare_gui.messagebox.showerror',side_effect=lambda *a,**k:errors.append(a)):
            bad=Path(folder)/'bad.exe';bad.write_bytes(b'bad');app.folder.set(folder);app.source.set(str(bad));app.start();drain()
            if len(errors)!=1:raise RuntimeError('Invalid updater was not rejected')
            app.source.set(str(a.updater.resolve()));app.start();drain()
            output=Path(folder)/'KC713.FW'
            if len(infos)!=1 or hashlib.sha256(output.read_bytes()).hexdigest()!=RELEASE_SHA256:raise RuntimeError('GUI output mismatch')
            app.start();drain()
            if len(errors)!=2 or hashlib.sha256(output.read_bytes()).hexdigest()!=RELEASE_SHA256:raise RuntimeError('Existing output not preserved')
        report=dict(passed=True,cases=['missing fields','invalid updater','original updater to exact firmware','existing output preserved'],firmware_sha256=RELEASE_SHA256)
        if a.report:a.report.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
    finally:root.destroy()
