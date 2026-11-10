# Validation and evidence

## ModernShare 0.9

Release firmware SHA-256:
`4025f886abb312dac31c60d923f67118843601663579ca53a96ac47ea33f609f`.

The standalone source builder first reproduced the accepted development firmware
byte for byte (`fd753680c2b0c1714fbab329d884d9dc4aac48df8f9a299014fa068f011c9c42`).
The release changes only four footer version digits from 0.8 to 0.9 and container
checksums. [Version-only comparison](validation/0.9/version-only.json).
The final release hash has automated regression coverage; camera acceptance and
installed-firmware readback apply to the development hash.

The camera owner accepts Ember styling/icon clearance, LCD shortcut return,
stored-photo Review High power, the Film chooser and film styles. Both brightness
settings survive a reset by user report; reset method was unspecified. Eight
labeled Stock, Neopan, Velvia and Kodachrome cases pass JPEG-only/JPEG+DNG and
paired-metadata checks. Neopan JPEGs are monochrome while RAW retains colour.
DNG CPU renders match independent linear references. Varying framing/exposure
prevents controlled colourimetric claims. Private sensor captures/dumps are not
published. [Scoped camera evidence](validation/0.9/camera-evidence.json).

## Automated coverage of the release

| Suite | Scenarios | Coverage |
|---|---:|---|
| Film chooser, brightness and preferences | 272 | All 98 choose/cancel pairs; native navigation/OK/return; stored-photo Review/Favorites; native brightness choices; SD load/save/error/retry; capture gate; 1,092 individual matrix getter checks |
| Ember row hook | 20 | Separate names/values, alignment, selected colours, ABI and stack preservation |
| Date | 15 | Supported dates, fallback, retained RTC and reset paths |
| DNG writer | 50 | Full writer, short writes/errors, fallback and same-shot metadata |
| Native paint replay | 70 | 49 chooser focus/applied combinations and 21 inherited menu/brightness paints |

All **427 scenarios** pass against the release firmware. The first four suites
are reproducible through `scripts/run_emulation.py` using a local stock Ghidra
project and synthetic DNG input: no camera dump or historical firmware is needed.
Their hash-bound reports are in [validation/0.9](validation/0.9/).
The paint replay uses a private captured-state fixture; its public
[summary](validation/0.9/paint-summary.json) records that boundary.

Tests execute actual ARC instructions while modeling file/UI/RTC/SDK/photo,
rendering and hardware boundaries. Known compiler restore aliases and the stock
multiply helper are modeled explicitly. Passing tests do not establish physical
output timing or interrupted-power FAT/SD durability. Historical UI7/UI8 negative
controls reproduced earlier defects before the final getter/brightness fixes;
they are separate development evidence, not additional release scenarios.

The standalone build regenerates every custom hook, DNG header, theme, icons,
Latin glyphs and boot tiles. Font inputs are pinned with licences. Source and
standard-library patcher outputs match exactly. Vendor English text and preserved
graphics are rebuilt from the local stock input. Output/container hashes and
boot tile roundtrips are checked before a firmware file is written.

**25 host tests** pass with local stock/updater input, plus **four GUI-flow cases**:
missing fields, invalid input, original updater to exact firmware, and refusal
to replace an existing output. Integration tests are skipped when proprietary
inputs are absent. The small app requires no assembler, Pillow or NumPy.

## Release applications

The [v0.9.0 release](https://github.com/Nacholmo/ModernShare/releases/tag/v0.9.0)
provides native Windows x86-64 and Linux x86-64 AppImage applications, corresponding
source, licences, checksums and `verification.json`. Native packaging runs through
[GitHub Actions](https://github.com/Nacholmo/ModernShare/actions/workflows/build-apps.yml).
The workflow runs host and GUI checks, then tests each actual packaged app for
startup, Tk initialization, exact firmware output, existing-output protection and
invalid-input rejection. AppImage CI uses extract-and-run mode where FUSE is
unavailable. Source archives and downloaded asset hashes are verified before
publication. The release verification record identifies the exact source commit,
workflow and executable hashes.

The previous [0.8 release](https://github.com/Nacholmo/ModernShare/releases/tag/v0.8.0)
remains available. Historical reports under `validation/0.8/` and the older
`validation/*.json` describe that release and earlier development, not 0.9.
Before downgrading, set Review brightness to Normal for the older CFG validator.

## Re-run

```sh
python3 -m unittest discover -s tests -v
```

For instruction suites, build the release and create a local stock project as
explained in [DEVELOPMENT.md](DEVELOPMENT.md), then:

```sh
bash -c 'source decompiler-project/scripts/environment.sh; \
  python3 scripts/run_emulation.py --build build/modernshare-0.9'
```

The project is opened read-only and firmware is overlaid only in the emulator.
Results are written into a fresh build directory. Test/build commands do not
flash the camera.
