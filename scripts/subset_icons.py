#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Recreate the pinned Material Design subset from the original Symbols font."""
import argparse
import hashlib
import json
from pathlib import Path
from fontTools import subset
from fontTools.ttLib import TTFont

ROOT=Path(__file__).resolve().parents[1]

def build(source, output):
    spec=json.loads((ROOT/'assets/fonts/material-subset.json').read_text())
    if hashlib.sha256(source.read_bytes()).hexdigest()!=spec['source_sha256']:
        raise ValueError('Unexpected original Symbols font')
    if output.exists():raise FileExistsError(output)
    font=TTFont(source,recalcTimestamp=False)
    options=subset.Options()
    options.glyph_names=True
    options.name_IDs=['*']
    options.name_legacy=True
    options.name_languages=['*']
    selection=subset.Subsetter(options=options)
    selection.populate(glyphs=spec['glyph_names'])
    selection.subset(font)
    for record in font['name'].names:
        if record.nameID in (1,3,4,6):
            record.string='ModernShareMaterialIcons'.encode(record.getEncoding())
    font.save(output)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source',type=Path)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();build(a.source,a.output)
