#!/usr/bin/env python3
"""Verify backed-up camera DNGs in LightCraft against independent linear references."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from io import BytesIO
import os
from pathlib import Path
import subprocess

import numpy as np
from PIL import Image, ImageDraw, TiffImagePlugin

from make_dng import ROOT, make_header, dng
from metadata_header import read_metadata


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('backup', type=Path)
    ap.add_argument('--build', type=Path, default=ROOT / 'mods/native_dng/test-v1')
    ap.add_argument('--evidence-kind', choices=['camera', 'emulated'], default='camera')
    ap.add_argument('--allow-unpaired', action='store_true', help='verify DNGs with missing JPEGs, reporting unverified pairs explicitly')
    ap.add_argument('--cli', type=Path, default=ROOT / 'workflow/lightcraft/runtime/squashfs-root/usr/bin/lightcraft-cli')
    a = ap.parse_args()
    backup, cli = a.backup.resolve(), a.cli.resolve()
    files = sorted((backup / 'DCIM/100KC713').glob('*.DNG'))
    if not files:
        ap.error('no camera DNGs in backup/DCIM/100KC713')
    unpaired = [f.stem[-4:] for f in files if not f.with_name(f'100_{f.stem[-4:]}.JPG').is_file()]
    if unpaired and not a.allow_unpaired:
        ap.error(f'missing JPEGs for {unpaired}; use --allow-unpaired to verify their DNGs separately')
    run = ROOT / 'mods/native_dng/validation' / datetime.now(timezone.utc).strftime('camera-%Y%m%dT%H%M%S%fZ')
    run.mkdir(parents=True)
    env = dict(os.environ, LIGHTCRAFT_CONFIG_DIR=str(run / 'config'))
    before = {str(p): sha(p) for p in backup.rglob('*') if p.is_file()}
    results = []

    def execute(requests):
        p = subprocess.run([str(cli), 'run', '--library', str(run / 'library'), '--script', '-'],
                input=''.join(json.dumps({'command': c, 'params': params}) + '\n' for c, params in requests),
                text=True, capture_output=True, env=env, timeout=180)
        with (run / 'commands.jsonl').open('a') as f:
            f.write(p.stdout)
        with (run / 'stderr.log').open('a') as f:
            f.write(p.stderr)
        lines = [json.loads(l) for l in p.stdout.splitlines() if l.strip()]
        if p.returncode or len(lines) != len(requests) or any(not x['ok'] for x in lines):
            raise RuntimeError(f'LightCraft failure; see {run}')
        return [x['result'] for x in lines]

    def render(photo, output):
        execute([('library.select', {'ids': [photo], 'active': photo}),
            ('app.export', {'path': str(output), 'longEdge': 1536, 'colorSpace': 'srgb',
                            'bitDepth': 8, 'metadata': 'none', 'sharpen': 'none'})])
        return np.asarray(Image.open(output).convert('RGB'), dtype=np.int16)

    manifest = json.loads((a.build / 'manifest.json').read_text())
    metadata_build = 'metadata_hook_bytes' in manifest
    header = (a.build / 'header.bin').read_bytes()
    for f in files:
        num = f.stem[-4:]
        source = f.read_bytes()
        fields = read_metadata(source[:len(header)]) if metadata_build else None
        assert (fields is not None or source[:len(header)] == header) and len(source) == 7097856, f
        refdir = run / f'reference-{num}'
        refdir.mkdir()
        raw = refdir / f'CCDI{num}.RAW'
        raw.write_bytes(source[len(header):])
        reference = Path(dng.convert(str(raw), str(refdir), tuple(1 / dng.DAYLIGHT_NEUTRAL), False, None))
        imported = execute([('library.import', {'paths': [str(f), str(reference)]})])[0]
        assert len(imported['imported']) == 2 and not imported['failed'], imported
        native_id, ref_id = imported['imported']
        info = execute([('photo.inspect', {'id': native_id})])[0]
        assert info['kind'] == 'raw' and (info['width'], info['height']) == (3056, 2292)
        native = render(native_id, run / f'{num}-native.png')
        linear = render(ref_id, run / f'{num}-linear.png')
        delta = np.abs(native - linear)
        assert delta.max() == 0, f'{num}: render differs'
        jpg = f.with_name(f'100_{num}.JPG')
        exif = {}
        jpg_mono = None
        if jpg.is_file():
            with Image.open(jpg) as im:
                j = np.asarray(im.convert('RGB'), np.int16)
                exif = im.getexif().get_ifd(0x8769)
            jpg_mono = bool(np.mean(np.ptp(j, axis=2) > 3) < 0.01)
        metadata_match = None
        editor_match = None
        expected = None
        if metadata_build:
            editor_match = bool(fields['date'] and fields['iso'] and fields['exposure_us'] and fields['fnumber_100']
                and info['captured'] == fields['date'].replace(':', '-', 2).replace(' ', 'T')
                and info['meta']['iso'] == fields['iso']
                and abs(info['meta']['aperture'] - fields['fnumber_100'] / 100) < 1e-5)
            stream = BytesIO(source[:len(header)])
            stream.seek(8); root_ifd = TiffImagePlugin.ImageFileDirectory_v2(); root_ifd.load(stream)
            stream.seek(root_ifd[34665]); exif_ifd = TiffImagePlugin.ImageFileDirectory_v2(); exif_ifd.load(stream)
            independent_match = (root_ifd[306] == exif_ifd[36867] == exif_ifd[36868] == fields['date']
                and abs(float(exif_ifd[33434]) - fields['exposure_us'] / 1000000) < 1e-12
                and abs(float(exif_ifd[33437]) - fields['fnumber_100'] / 100) < 1e-12
                and exif_ifd[34855] == fields['iso'])
            editor_match = editor_match and independent_match
            if jpg.is_file():
                expected = {'date': str(exif[36867]), 'exposure_us': round(float(exif[33434]) * 1000000),
                            'fnumber_100': round(float(exif[33437]) * 100), 'iso': int(exif[34855])}
                metadata_match = fields == expected and editor_match
        colour = float(np.mean(np.ptp(native, axis=2) > 20))
        if jpg_mono:
            assert colour > 0.05, 'B&W shot did not yield colour RAW'
        results.append({'shot': num, 'dng': str(f.relative_to(ROOT)), 'bytes': len(source),
            'sha256': sha(f), 'editor_kind': info['kind'], 'editor_dimensions': [info['width'], info['height']],
            'max_channel_error_against_linear_reference': int(delta.max()),
            'jpeg_monochrome': jpg_mono, 'raw_colour_pixel_fraction': colour,
            'metadata_matches_jpeg': metadata_match, 'dng_metadata': fields,
            'paired_jpeg_present': jpg.is_file(), 'editor_metadata_matches_dng': editor_match,
            'jpeg_metadata': expected, 'editor_captured': info.get('captured'), 'editor_metadata': info.get('meta'),
            'jpeg_date': str(exif.get(36867)), 'passed': metadata_match is not False and editor_match is not False})
        print(f'{"FAIL metadata" if not results[-1]["passed"] else "PASS"} {num}: {a.evidence_kind} DNG renders identically to linear reference; JPEG present={jpg.is_file()}', flush=True)

    sheet = Image.new('RGB', (960, 274 * len(files)), '#202126')
    draw = ImageDraw.Draw(sheet)
    for row, f in enumerate(files):
        num = f.stem[-4:]
        for col, (label, p) in enumerate([('Camera JPG', f.with_name(f'100_{num}.JPG')),
                    ('Camera DNG', run / f'{num}-native.png'), ('Linear reference', run / f'{num}-linear.png')]):
            if not p.is_file():
                draw.text((col * 320 + 8, row * 274 + 110), f'{num} - no matching JPEG', fill='white')
                continue
            with Image.open(p) as im:
                thumb = im.convert('RGB');thumb.thumbnail((320, 240))
                sheet.paste(thumb, (col * 320 + (320 - thumb.width) // 2, row * 274 + 34))
            draw.text((col * 320 + 8, row * 274 + 10), f'{num} - {label}', fill='white')
    sheet.save(run / 'comparison.jpg', quality=94)
    unchanged = all(sha(Path(p)) == digest for p, digest in before.items())
    assert unchanged, 'source backup changed'
    report = {'passed': all(r['passed'] for r in results), 'backup': str(backup.relative_to(ROOT)), 'run': str(run.relative_to(ROOT)),
        'evidence_kind': a.evidence_kind,
        'unpaired_shots': unpaired, 'metadata_pair_verification_complete': not unpaired,
        'cli_version': subprocess.check_output([str(cli), '--version'], text=True, env=env).strip(),
        'cli_sha256': sha(cli), 'shots': results, 'backup_unchanged': unchanged,
        'comparison': str((run / 'comparison.jpg').relative_to(ROOT)),
        'limits': '1536-pixel CPU exports; native GUI/GPU and card-full/black-frame behaviour not exercised'}
    (run / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    (a.build / f'{a.evidence_kind}-render-verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'{a.evidence_kind} verification {"passed" if report["passed"] else "FAILED"}: {run / "comparison.jpg"}')
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
