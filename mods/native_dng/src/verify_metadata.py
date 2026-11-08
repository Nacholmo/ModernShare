#!/usr/bin/env python3
"""Host proofs and LightCraft checks for the v2 EXIF layout (no camera claims)."""
import argparse
from datetime import datetime, timezone
from io import BytesIO
import json
import os
from pathlib import Path
import struct
import subprocess

import numpy as np
from PIL import Image, TiffImagePlugin

from make_dng import ROOT
from metadata_header import make_metadata_header, fill_metadata, read_metadata


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--build', type=Path, default=ROOT / 'mods/native_dng/metadata-v2')
    a = ap.parse_args()
    build = a.build.resolve()
    run = ROOT / 'mods/native_dng/validation' / datetime.now(timezone.utc).strftime('metadata-%Y%m%dT%H%M%S%fZ')
    run.mkdir(parents=True)
    cli = ROOT / 'workflow/lightcraft/runtime/squashfs-root/usr/bin/lightcraft-cli'
    env = dict(os.environ, LIGHTCRAFT_CONFIG_DIR=str(run / 'config'))
    backup = ROOT / 'cd703_card_native_dng_test_20261108T003143Z/DCIM/100KC713'
    rows, fixtures = [], []

    def execute(commands):
        p = subprocess.run([str(cli), 'run', '--library', str(run / 'library'), '--script', '-'],
            input=''.join(json.dumps({'command': c, 'params': args}) + '\n' for c, args in commands),
            text=True, capture_output=True, env=env, timeout=180)
        with (run / 'commands.jsonl').open('a') as f:
            f.write(p.stdout)
        with (run / 'stderr.log').open('a') as f:
            f.write(p.stderr)
        lines = [json.loads(l) for l in p.stdout.splitlines() if l.strip()]
        assert p.returncode == 0 and len(lines) == len(commands) and all(x['ok'] for x in lines), p.stdout + p.stderr
        return [x['result'] for x in lines]

    def render(photo, path):
        execute([('library.select', {'ids': [photo], 'active': photo}),
                 ('app.export', {'path': str(path), 'longEdge': 1536, 'colorSpace': 'srgb',
                                 'bitDepth': 8, 'metadata': 'none', 'sharpen': 'none'})])
        return np.asarray(Image.open(path).convert('RGB'), dtype=np.int16)

    for n in ('0303', '0304', '0305', '0306'):
        with Image.open(backup / f'100_{n}.JPG') as im:
            ex = im.getexif().get_ifd(0x8769)
        fixture = {'name': n, 'date': ex[36867], 'exposure_us': round(float(ex[33434]) * 1000000),
                   'fnumber_100': round(float(ex[33437]) * 100), 'iso': int(ex[34855]),
                   'payload_dng': str((backup / f'CCDI{n}.DNG').relative_to(ROOT)), 'stock_result': 1}
        fixtures.append(fixture)
        expected = {k: fixture[k] for k in ('date', 'exposure_us', 'fnumber_100', 'iso')}
        header = fill_metadata(**expected)
        assert read_metadata(header) == expected
        # Pillow's independent TIFF parser follows the real EXIF IFD pointer, not our layout map.
        f = BytesIO(header)
        f.seek(8);ifd = TiffImagePlugin.ImageFileDirectory_v2();ifd.load(f)
        f.seek(ifd[34665]);exif = TiffImagePlugin.ImageFileDirectory_v2();exif.load(f)
        assert ifd[306] == fixture['date'] == exif[36867] == exif[36868]
        assert abs(float(exif[33434]) - float(ex[33434])) < 1e-12
        assert abs(float(exif[33437]) - float(ex[33437])) < 1e-12 and exif[34855] == ex[34855]
        original = backup / f'CCDI{n}.DNG'
        payload = original.read_bytes()[1536:]
        proof = run / f'metadata-{n}.DNG';proof.write_bytes(header + payload)
        imported = execute([('library.import', {'paths': [str(proof), str(original)]})])[0]
        assert len(imported['imported']) == 2 and not imported['failed']
        new_id, old_id = imported['imported']
        info = execute([('photo.inspect', {'id': new_id})])[0]
        assert info['kind'] == 'raw' and (info['width'], info['height']) == (3056, 2292)
        assert info['captured'] == fixture['date'].replace(':', '-', 2).replace(' ', 'T')
        assert info['meta']['iso'] == fixture['iso'] and abs(info['meta']['aperture'] - fixture['fnumber_100'] / 100) < 1e-5
        new_render = render(new_id, run / f'metadata-{n}.png')
        old_render = render(old_id, run / f'v1-{n}.png')
        assert np.array_equal(new_render, old_render)
        rows.append({'shot': n, 'pillow_exif_matches_jpeg': True, 'lightcraft_metadata': {
            'captured': info['captured'], 'iso': info['meta']['iso'], 'aperture': info['meta']['aperture'],
            'shutter': info['meta']['shutter']}, 'render_matches_v1': True, 'expected': expected})
        print(f'PASS {n}: TIFF/EXIF fields and editor metadata; render unchanged', flush=True)
    # Distinct values exercise changing shots, source clamping and the accepted year range.
    fixtures.extend([
        {'name': 'leap-2028', 'date': '2028:02:29 23:59:58', 'exposure_us': 125000,
         'fnumber_100': 510, 'iso': 800, 'stock_result': 1},
        {'name': 'year-2037', 'date': '2037:12:31 01:02:03', 'exposure_us': 2000000,
         'fnumber_100': 960, 'iso': 80, 'stock_result': 1},
        {'name': 'clamp', 'date': '2026:11:07 21:00:01', 'exposure_us': 100,
         'fnumber_100': 270, 'iso': 160, 'stock_result': 1},
        {'name': 'failed-stock-build', 'date': '2037:01:01 00:00:00', 'exposure_us': 300000,
         'fnumber_100': 320, 'iso': 400, 'stock_result': 0},
    ])
    (build / 'metadata-fixtures.json').write_text(json.dumps(fixtures, indent=2) + '\n')
    # The default/unknown header must remain parseable as a DNG before any metadata callback.
    template, layout = make_metadata_header()
    assert read_metadata(template) == {'date': None, 'exposure_us': 0, 'fnumber_100': 0, 'iso': 0}
    report = {'passed': True, 'status': 'host format/editor verification; not camera-tested',
              'run': str(run.relative_to(ROOT)), 'header_bytes': len(template), 'used_bytes': layout['USED_BYTES'],
              'same_sensor_bytes_and_wb': True, 'rows': rows}
    (build / 'host-verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS: four host metadata proofs; camera firmware still requires hardware test')


if __name__ == '__main__':
    main()
