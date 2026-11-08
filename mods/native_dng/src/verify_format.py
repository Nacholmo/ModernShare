#!/usr/bin/env python3
"""Compare original-byte DNGs against the existing converter in installed LightCraft."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess

import numpy as np
from PIL import Image

from make_dng import ROOT, PIXEL_BYTES, make_header, wrap, dng


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cli', type=Path, default=ROOT / 'workflow/lightcraft/runtime/squashfs-root/usr/bin/lightcraft-cli')
    a = ap.parse_args()
    cli = a.cli.resolve()
    if not cli.is_file():
        ap.error('LightCraft CLI not found; supply --cli /path/to/lightcraft-cli')
    run = ROOT / 'mods/native_dng/validation' / datetime.now(timezone.utc).strftime('run-%Y%m%dT%H%M%S%fZ')
    run.mkdir(parents=True)
    env = dict(os.environ, LIGHTCRAFT_CONFIG_DIR=str(run / 'config'))
    sources = sorted((ROOT / 'cd703_card_raw').glob('CCDI*.RAW'))
    sources += [ROOT / 'firmware/stock/kc713.fw', ROOT / 'mods/date_fix/stock_color_neopan/KC713.FW']
    before = {str(p.relative_to(ROOT)): sha(p) for p in sources}
    checks = []
    report = {'run': str(run.relative_to(ROOT)), 'checks': checks,
              'source_sha256': before, 'cli_sha256': sha(cli), 'passed': False}

    def check(name, ok, **details):
        checks.append({'check': name, 'passed': bool(ok), **details})
        if not ok:
            raise RuntimeError(f'{name}: {details}')

    def execute(commands):
        p = subprocess.run([str(cli), 'run', '--library', str(run / 'library'), '--script', '-'],
                input=''.join(json.dumps({'command': c, 'params': args}) + '\n' for c, args in commands),
                capture_output=True, text=True, env=env, timeout=120)
        with (run / 'commands.jsonl').open('a') as f:
            f.write(p.stdout)
        with (run / 'stderr.log').open('a') as f:
            f.write(p.stderr)
        results = [json.loads(l) for l in p.stdout.splitlines() if l.strip()]
        if p.returncode or len(results) != len(commands) or any(not d.get('ok') for d in results):
            raise RuntimeError(f'LightCraft command failed; see {run}')
        return [d['result'] for d in results]

    def render(photo, output, temp=None):
        commands = [('library.select', {'ids': [photo], 'active': photo})]
        if temp is not None:
            commands += [('develop.set', {'control': 'wb.temp', 'value': temp})]
        commands += [('app.export', {'path': str(output), 'longEdge': 1024, 'colorSpace': 'srgb',
                    'bitDepth': 8, 'metadata': 'none', 'sharpen': 'none'})]
        execute(commands)
        return np.asarray(Image.open(output).convert('RGB'), dtype=np.int16)

    try:
        report['cli_version'] = subprocess.check_output([str(cli), '--version'], text=True, env=env).strip()
        header = make_header()
        report['header_bytes'] = len(header)
        report['file_bytes'] = len(header) + PIXEL_BYTES
        report['header_sha256'] = hashlib.sha256(header).hexdigest()
        (run / 'header.bin').write_bytes(header)
        stock = (ROOT / 'firmware/stock/kc713.fw').read_bytes()
        offset = 0x16BEC8 - 0x130000 + 0x100200
        check('decode table matches stock firmware', stock[offset:offset + 512] == dng.DECODE.astype('<u2').tobytes())
        for raw in sources:
            if raw.suffix.upper() != '.RAW':
                continue
            num = raw.stem[-4:]
            wrapped = run / f'wrapped-{num}.DNG'
            wrap(raw, wrapped, header)
            blob = wrapped.read_bytes()
            check(f'{num}: original sensor bytes preserved', blob[len(header):] == raw.read_bytes()
                  and len(blob) == len(header) + PIXEL_BYTES)
            try:
                wrap(raw, wrapped, header)
            except FileExistsError:
                pass
            else:
                raise RuntimeError('existing-file protection failed')

            # Use the established converter, with explicit gains so both files have identical
            # daylight WB. JPEG exposure/date metadata on the reference is not baked into pixels.
            refdir = run / f'reference-{num}'
            refdir.mkdir()
            reference = Path(dng.convert(str(raw), str(refdir),
                             tuple(1 / dng.DAYLIGHT_NEUTRAL), False, None))
            imported = execute([('library.import', {'paths': [str(wrapped), str(reference)]})])[0]
            check(f'{num}: both DNG encodings import', len(imported['imported']) == 2 and not imported['failed'])
            native_id, ref_id = imported['imported']
            info = execute([('photo.inspect', {'id': native_id})])[0]
            check(f'{num}: full-size editable RAW', info['kind'] == 'raw'
                  and (info['width'], info['height']) == (3056, 2292)
                  and info['develop']['wb']['scale'] == 'kelvin')
            native = render(native_id, run / f'wrapped-{num}.png')
            converted = render(ref_id, run / f'reference-{num}.png')
            error = np.abs(native - converted)
            check(f'{num}: same render as linear 16-bit DNG', error.max() == 0,
                  max_channel_error=int(error.max()), mean_channel_error=float(error.mean()))
            if num == '0293':
                edited_native = render(native_id, run / 'edited-wb-wrapped.png', temp=7000)
                edited_ref = render(ref_id, run / 'edited-wb-reference.png', temp=7000)
                delta = np.abs(edited_native - edited_ref)
                change = np.abs(edited_native - native)
                check('WB remains editable without changing sensor data', delta.max() == 0
                      and change.mean() > 1 and wrapped.read_bytes() == blob,
                      max_reference_error=int(delta.max()), mean_change=float(change.mean()))
            print(f'PASS {num}: original-byte and expanded DNG renders match exactly', flush=True)

        bad = run / 'wrong-size.RAW'
        bad.write_bytes(b'bad raw')
        try:
            wrap(bad, run / 'invalid.DNG')
        except ValueError:
            pass
        else:
            raise RuntimeError('wrong-sized RAW was accepted')
        check('malformed input refused before output', not (run / 'invalid.DNG').exists())
        report['passed'] = True
    finally:
        same = all(sha(ROOT / p) == value for p, value in before.items())
        checks.append({'check': 'source RAW and firmware unchanged', 'passed': same})
        report['passed'] = report['passed'] and same and all(c['passed'] for c in checks)
        (run / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        (ROOT / 'mods/native_dng/VERIFICATION.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'{len(checks)} checks; passed={report["passed"]}; {run}', flush=True)
    if not report['passed']:
        raise RuntimeError('verification failed')


if __name__ == '__main__':
    main()
