# Velvia 100 and Kodachrome 64 — Mod Settings 0.7

Candidate `test-v0.7/KC713.FW`, SHA-256
`57a25b3f46bff1b6bf19f23853034abe665909f379831501dff13b48ff572c4e`.
Base is Film-first 0.6 (`73801de4…`), independently verified from KC713.OLD.
**The new looks await camera testing.**

Film remains the first/highlighted Share → MOD SETTINGS row. OK cycles:

**By mode → Stock → Agfa Vista 200 → Kodak E100VS → Fuji Neopan 1600 →
Velvia 100 → Kodachrome 64 → By mode.**

The other rows remain DNG saving, Hidden menu and **FW: CD703 mod 0.7**.
Selections are session-only; boot defaults remain By mode and DNG ON. DNG sensor
data and its editable fixed daylight WB stay unchanged. The existing preview fix
is extended to both new films; the camera trial must check their actual previews.

## New film fits

The user selected **Kodachrome 64** for “Chrome,” alongside **Velvia 100**.
Sources are the existing Film-Luts files:

- `colorslide/fuji_velvia_100_generic.cube`
- `colorslide/kodak_kodachrome_64.cube`

Each is fitted to a relative RGB matrix through the existing stock tone curves and
normal YCbCr path, preserving gray neutrality. The same transform is applied to
all three illuminant CCMs. No new tone curves, inverse tables or per-shot processing
are introduced. Capture records hold three 3×4 Q16 CCMs and a normal YCbCr matrix;
preview uses the corresponding Q12 relative RGB transform with preview calibration.

These are **matrix approximations of the LUT looks**, not exact full 3D LUTs or
claims of reproducing physical film. Velvia mean sample ΔE improves from 11.56
to 6.63; Kodachrome from 21.90 to 9.07. Errors are measured against the local LUTs
using the existing fitter's samples/model, not real camera captures. Fit source,
LUT hashes, parameters, error distributions and binary hashes are in `fits-v1/fit.json`
and copied to `test-v0.7/fit.json`. The original three film records are byte-identical.

## Space and implementation

The original Share create/init code at **`0xebc90–0xebecb` (572 bytes)** is no
longer used by the replacement menu. Before reclaiming it, the builder checks its
only remaining data pointers (old event table entries at `0x1683a0` and `0x1683a8`)
and redirects them to the stock default callback. Three legacy calls into the
region at `0xebed0`, `0xebefc`, `0xebf00` become NOPs. The static audit permits
only these explicitly disconnected edges and internal references; no unexpected
outside references remain. These Share callbacks must not be restored in this build.

Allocation within that region:

| Address | Data |
|---|---|
| `0xebc90` | Velvia's 192-byte record |
| `0xebd50` | Kodachrome's 192-byte record |
| `0xebe10` | Five Q12 preview transforms, 90 bytes |
| `0xebe6c` | Twenty matrix pointers, 80 bytes |

Existing film records stay at `0x1257a0`, `0x125860`, `0x125920`. The shared matrix
address resolver at `0x1256a8` now indexes the pointer table, preserving existing
record addresses and getter ABI. No additional capture entry hook is added.

The original preview coefficient storage in Share-private RAM becomes a seven-label
pointer table at `0x168324`, followed by new labels at `0x168340`. Selector/refresh
limits increase from five to seven choices. Preview accepts film IDs 1–5 and reads
the relocated transforms; its Review and already-filmed-CCM guards remain unchanged.
The Film-first label/action mapping remains intact.

Only 688 bytes differ from 0.6. The original three film records, scene defaults,
DNG writer/header/metadata, boot code, date default and clock fixes are byte-identical.

## Validation

**129 menu/preview/capture scenarios pass**, including 84 preview cases and
**1,092 actual CCM/Ymat getter cases** covering all seven choices, all 24 capture
modes plus invalid modes, three illuminants and normal/B&W/sepia arguments.
Tests execute actual lookup/selector/preview code; check all seven labels, wrap,
row callbacks, stock defaults, preserved stack/registers, matrix source/destination
guards, preview hardware-upload arguments, Review bypass and no double transform.
Legacy pointers/calls are checked disconnected in the actual firmware.

**15 date and 50 full DNG writer regressions pass.** Preview fixed-point matrices
agree with independent floating-point composition within one Q8 coefficient unit
for all five films/three preview levels. All coefficient magnitudes stay below 4;
existing Neopan rows remain identical. Container checksums, change allowlist and a
separate rebuild from freshly regenerated fits pass byte-identically. UI/ISP/file/RTC services are mocked; stock multiply and the
known SLEIGH restore alias issue are modeled as in the confirmed preview tests.
Hardware color rendering, thumbnails and display remain the next trial.

Reports in `test-v0.7/`: `verification.json`, `menu-emulation.json`,
`date-emulation.json`, `emulation.json`, `matrix-reference-proof.json`, `manifest.json`.
Space audit: `research/space-audit.json`; card backup/staging receipts are beside
the firmware. The stock Ghidra project remains read-only.

## Reproduce

Use fresh output directories:

```sh
python3 mods/classic_films/src/fit_classics.py --outdir mods/classic_films/my-fits
python3 mods/classic_films/src/build_classics.py \
  --fitdir mods/classic_films/my-fits --outdir mods/classic_films/my-rebuild
source decompiler-project/scripts/environment.sh
"$GHIDRA_ROOT/support/analyzeHeadless" "$PROJECT_ROOT/projects" KodakC713 \
  -process code.bin -noanalysis -readOnly \
  -scriptPath "$PWD/mods/classic_films/src;$PWD/mods/date_default/src;$PWD/mods/native_dng/src" \
  -postScript TestClassics.java "$PWD/mods/classic_films/my-rebuild" \
  -postScript TestDateDefault.java "$PWD/mods/classic_films/my-rebuild" \
  -postScript TestNativeDng.java "$PWD" "$PWD/mods/classic_films/my-rebuild"
```

`AuditClassicSpace.java OUTPUT_JSON` reproduces the required stock reference audit.
The builder pins base/fit hashes, asserts original bytes, rejects an existing
firmware output and checks each allocation and preservation range.

## Camera trial

Install through Share → Hidden menu → UPDATE FIRMWARE. Check **CD703 mod 0.7**
and all seven Film choices. In ordinary COLOR with steady light/framing, capture
Stock, Velvia 100 and Kodachrome 64, then Neopan as an existing-look regression.
Check live view, immediate preview and later Review; keep all JPEG/DNG pairs.
The DNGs should retain unfiltered sensor color. Test returning to Stock and
wraparound to By mode, plus DNG OFF and Hidden menu access.

Reconnect the card for firmware, embedded-preview, JPEG/DNG and metadata readback.
Existing photos are not rewritten. Recovery: Film-first 0.6
`mods/mod_settings/test-v0.6/KC713.FW` (`73801de4…`), or user-confirmed preview 0.5
(`9e1e4064…`).
