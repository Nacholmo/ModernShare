# Validation and evidence

## Confirmed release

ModernShare 0.8 firmware SHA-256:
`091663ac848b6ee07c2a9252b9a9662e8cc7c463275e2dde62edb10d8e0f6003`.

The camera owner reports **“works as intended”** following the artwork, branding,
DNG default-OFF and SD-persistence trial. This is overall user acceptance; the
individual trial steps were not reported separately, and there is no independent
post-0.8 CFG/capture/KC713.OLD readback in this repository.

Historical results from the development workspace are preserved in
`docs/validation/0.8/`. They refer to the original workspace's paths; those paths
are provenance, not bundled photos, firmware or tools. The original manifest
identifies source/build hashes before repository packaging changes.

## Automated coverage

| Suite | Scenarios | Coverage |
|---|---:|---|
| Preferences | 54 | Every film/DNG combination; missing/invalid/short records; A/B newest/ties/wrap; read/write/open/close errors; retry; previous-slot recovery; Review-first and failed stock init |
| Menu/preview/capture | 129 | Seven choices, wrap, native callbacks, DNG gate, preview guards, 1,092 matrix getter cases |
| Date | 15 | Supported dates, fallback, retained RTC and reset paths |
| DNG writer | 50 | Full writer, error/short-write handling, black/unknown/size fallback and capture metadata |

Suites execute actual ARC instructions. Stock UI, RTC, file APIs and selected
hardware boundaries are modeled. Caller-saved registers are deliberately
destroyed by mocked services. The known SLEIGH compiler-restore alias and stock
multiply helper are modeled explicitly. Ghidra process exit status alone is not
accepted: the runner checks logs plus every hash-bound JSON result.

The public DNG suite uses deterministic synthetic sensor bytes and measured
metadata values. It requires no personal photo, RAW, DNG or memory-dump fixture.
Historical development tests also used real camera payloads; that is separate
evidence, not a claim that those images are included here.

The standalone repository build reassembles every custom hook, generates header,
theme and artwork, verifies the exact final release hash and checks tile decoder
roundtrips. Package verification records are in `docs/validation/repository.json`.

## Public repository and GUI checks

The standalone source build and the standard-library GUI patch bundle both
reproduce the exact confirmed release. An isolated source archive was extracted
into a clean path containing spaces, with PYTHONPATH cleared; both build paths
passed without using the original workspace's sources. See
`validation/isolated-export.json` and `validation/repository.json`.

Nineteen host tests pass when supplied the local stock/updater. Four GUI cases
pass on Linux using a virtual display. A packaged Linux executable starts the GUI
and generates the exact firmware from the original updater. Windows packaging is
prepared in GitHub Actions but no Windows runtime result is claimed. Reports:
`validation/gui.json`, `validation/linux-app.json`, and `validation/public-emulation.json`.

The mirror download was independently fetched and hash-checked; see
`validation/download-source.json`. No downloaded firmware is included.

## Re-run

```sh
python3 -m unittest discover -s tests -v
```

For firmware suites, first build the release and create a local stock Ghidra
project using [DEVELOPMENT.md](DEVELOPMENT.md). Then:

```sh
bash -c 'source decompiler-project/scripts/environment.sh; \
  python3 scripts/run_emulation.py --build build/modernshare-0.8'
```

The project is opened read-only and firmware bytes are overlaid only in the
emulator. The runner writes results into the chosen build directory. Use a fresh
build for a repeated run. Firmware is not flashed by any test/build command.

## Camera regression checklist

Check boot/title; with no valid CFG files, take a JPEG-only shot. Change Film,
restart through a battery-flap reset and verify Film restores. Enable DNG,
restart and capture a JPEG+DNG pair; disable, restart and capture JPEG only.
Confirm SD saved/loaded feedback and film in live view/immediate/later Review.
Interrupted-power FAT/SD durability is not established by the virtual file tests.
