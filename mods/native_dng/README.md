# Direct DNG: camera-tested firmware

The user accepts a sensible fixed white balance and will adjust it in the editor. Accurate per-shot WB recovery is **outside the first implementation's scope**.

**Confirmed DNG metadata baseline: [metadata v3](metadata-v3/README.md), SHA-256 `9760823a…`, is flashed and camera-confirmed.** Five real DNGs 0313–0317 decode correctly and render identically to independent linear references. All four retained JPEG pairs match their own capture date/time, exposure, aperture and ISO. User intentionally deleted the first JPEG because its date setting was wrong; that DNG is valid and populated. Fixed daylight WB and original sensor samples are retained. [Camera report](metadata-v3/camera-verification.json) · [comparison](metadata-v3/camera-comparison.jpg).

**`test-v1/KC713.FW` (`8dce21de…`) remains the older confirmed DNG fallback**, with four successful shots 0303–0306, including colour RAW beside B&W JPEGs and a successful memory dump. [v1 results](test-v1/camera-verification.json).

Metadata v2 `3f4df4fb…` is superseded: its JPEG callback ran after RAW saving, leaving metadata one shot late. V3 reads the active capture before writing. It also passes 50 full-writer instruction cases, six emulator-output editor proofs and a byte-identical rebuild. [V2 failure evidence](metadata-v2/camera-verification.json).

Current camera firmware adds the [Share mod menu](../share_menu/README.md) on top of this baseline (`f992a106…`). DNG saving can be switched off for the session; actual ON/OFF captures are verified.

## Proven file layout

```text
1536-byte fixed DNG header
7096320-byte original CCDI sensor buffer, unchanged
```

Total: **7,097,856 bytes**. The camera writes the header and then its original sensor bytes, without expanding samples to 16 bits, demosaicing, estimating white balance or compressing pixels.

The header declares 3072 × 2310 8-bit RGGB storage, crop x=8/y=10 to 3056 × 2292, stock 256-entry decoding table in `LinearizationTable`, linear white level 1023, black level 0 and the same colour matrices as the established converter. `AsShotNeutral = [0.42, 1.0, 0.73]` provides the existing typical-daylight starting point. White balance stays editable; it is not multiplied into the sensor bytes.

See Adobe's [DNG specification](https://helpx.adobe.com/content/dam/help/en/camera-raw/digital-negative/jcr_content/root/content/flex/items/position/position-par/download_section_733958301/download-1/DNG_Spec_1_7_1_0.pdf), especially `LinearizationTable` and `AsShotNeutral`.

## Results

[VERIFICATION.json](VERIFICATION.json): **20 passing checks** on 2026-11-07 Argentina time.

- The decoding table matches the stock firmware bytes directly.
- Shots 0293–0296 retain their original sensor buffers byte-for-byte.
- LightCraft imports all four as full-size editable RAWs.
- All four default renders are **pixel-identical** to the existing converter's 16-bit DNG output at the same fixed WB.
- Changing both representations to 7000 K gives pixel-identical results, changes the appearance and leaves the sensor data untouched.
- Wrong-sized input and existing output files are refused. Source RAWs, stock firmware and confirmed firmware remain unchanged.

The reference uses the existing converter with explicit daylight gains; it does not estimate per-shot WB. Rendering checks use 1024-pixel sRGB exports through the actual installed CLI. Native desktop/GPU previews and other editors are not yet tested.

`proof-v1/header.bin` is the fixed header; `proof-v1/CCDI0293.DNG` through `CCDI0296.DNG` are files you can open directly. `proof-v1/manifest.json` records sizes, default WB and hashes. This initial fixed template omits dynamic exposure/date/ISO metadata and embedded previews. Black-frame subtraction is not performed.

## Reproduce

From the project root, choose a **new** output directory:

```sh
python3 mods/native_dng/src/make_dng.py cd703_card_raw/CCDI0293.RAW -o mods/native_dng/my-proof
python3 mods/native_dng/src/verify_format.py
```

The wrapper uses exclusive output creation. The verifier makes a fresh `validation/run-*` directory, separate LightCraft configuration/library, linear reference files, renders and command logs. NumPy and Pillow are required. Supply `--cli /path/to/lightcraft-cli` if the locally extracted CLI is absent.

## Firmware test v1

`src/build_native_dng.py` accepts only the pinned confirmed base, asserts stock entry bytes and empty allocations, assembles `src/hook.s`, fixes checksums and rejects changes outside the documented patches/checksum fields. Rebuild into a fresh directory:

```sh
python3 mods/native_dng/src/build_native_dng.py --outdir mods/native_dng/my-test-build
```

- Entry `0x67898` branches to a **544-byte** hook at `0x125a00`.
- Header at `0x1241a0` occupies a 1536-byte slice of a 1632-byte zero run. It is bounded by a return and the next function, has no recorded static data references, and remains zero in **107 validated memory-dump frames**. `placement-audit.json` records the evidence; camera testing is still required.
- Main frames (`kind == 0`) of exactly 7,096,320 bytes become `CCDInnnn.DNG`. Other kinds/sizes execute the original prologue and stock RAW path, including separate black frames.
- Open/write/close ABI was checked in assembly. Both header and payload writes check return values and reported byte counts. Every opened file is closed, including after failure; the first error is retained.
- Ten u32 diagnostics at `0x125cc0` record the most recent attempt. `src/inspect_capture.py` checks returned DNGs and decodes a memory dump without modifying it.
- `src/TestNativeDng.java` executes the patched machine instructions using Ghidra's ARCompact p-code emulator, mocking external path/strlen/file APIs and deliberately clobbering caller-saved registers. **18 scenarios pass**, including success, path limits, open/header/payload/close failures, short writes, error precedence, callee-saved registers/stack, and stock fallback. Its success write is byte-identical to the desktop DNG proof.

Reproduce the emulator run (reads the saved stock project with `-readOnly`, never saves it):

```sh
bash -c 'source decompiler-project/scripts/environment.sh; "$GHIDRA_ROOT/support/analyzeHeadless" "$PROJECT_ROOT/projects" KodakC713 -process code.bin -noanalysis -readOnly -scriptPath "$PWD/mods/native_dng/src" -postScript TestNativeDng.java "$PWD" "$PWD/mods/native_dng/test-v1"'
```

`test-v1/manifest.json`, `emulation.json` and `card-staging.json` record the build, tests and SD readback. The original SD contents (49 files, including JPEGs/RAWs, the memory dump and old firmware) were copied and hash-verified into a new backup directory recorded in `card-backup.json`. The old card firmware remains in `SYSTEM/KC713.OLD`.

**Camera evidence now collected:** actual flashed firmware hash matches; all four DNG headers and lengths are correct; all render as full-size RAW and are pixel-identical to independent 16-bit linear references at 1536-pixel export size. B&W JPEGs 0304/0305 have colour DNGs. The newest of two dump frames matches the live entry/header/hook and reports phase 5, no error, header written 1536 and payload written 7096320. Flags: CFA on, JPEG on, YRGB off, date stamp off. New/changed card files were copied and hashed into `cd703_card_native_dng_test_20261108T003143Z/`; sources remain unchanged. `src/verify_camera.py BACKUP_DIR` reproduces the editor check, with all generated files under `validation/`.

Further coverage remains useful for scene/flash/date regression checks, card-full behaviour and long-exposure black frames. Native desktop/GPU previews and other editors were not tested. DNGs omit per-shot EXIF and embedded previews; the current camera clock is 2007-01-01 in the JPEGs. Keep this working build while testing additional conditions.

Do not block the first hook on per-shot WB, compression, embedded JPEG previews or dynamic EXIF. Those can be separate improvements. Keep the confirmed `4765fbbb…` firmware intact.
