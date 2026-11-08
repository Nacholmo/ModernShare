# Next steps after the confirmed firmware baseline

Updated 2026-11-07 from the root `HANDOFF.md` and the LightCraft integration checks.
The user authorizes work throughout the project. Preserve stock firmware, confirmed binaries and old card backups; put experiments in new output directories.

## Immediate trial: Velvia/Kodachrome, version 0.7

User selected Velvia 100 and Kodachrome 64. Candidate
`mods/classic_films/test-v0.7/KC713.FW` (`57a25b3f…`) is staged, verified and
safely unmounted. Film remains first; seven choices include the original three
looks plus the two new CCM approximations, Stock and By mode. 129 menu/preview/
capture cases (1,092 getter cases), 15 date, 50 DNG, float/reference proofs, audits
and independent fresh-fit rebuild pass. New look hardware trial is pending:
ordinary COLOR, steady scene/light, Stock → Velvia → Kodachrome → Neopan, checking
live view, immediate/later Review, RAW color/metadata and wrap. Details
`mods/classic_films/README.md`.

Installed/recovery 0.6 (`73801de4…`) now independently matches KC713.OLD. Latest
backup `cd703_card_film_first_test_20261108T034353Z/` has one changed OLD; no new
captures/dump or removed files. All 23 card files preserved while staging 0.7.
0.5 remains the additional user-confirmed preview recovery.

New allocations: old Share create/init bodies `0xebc90–0xebecb` contain new film
records, five preview transforms and 20 matrix pointers. Original event pointers
`0x1683a0/0x1683a8` are redirected, legacy calls `0xebed0/0xebefc/0xebf00` NOPed;
never restore them. Main getter resolver `0x1256a8` now indexes pointers. Seven
menu labels at `0x168324`, names `0x168340`, R data `0xebe10`. Preserve existing
preview wrapper `0x125c24/0x12fe98`, refresh/trampoline `0xebc50`, DNG/boot regions.
Stock Ghidra project remains read-only.

## Confirmed baseline

- Keep `mods/date_fix/stock_color_neopan/KC713.FW`, SHA-256 `4765fbbbc64c4fb3db63c3ee4c5227ebe023a3678f9c9c81ea009642ce3a2630`.
- Confirmed DNG fallback is `mods/native_dng/test-v1/KC713.FW`, SHA-256 `8dce21de78bf28f2a3c8a029f40dd8ae84a5ee0c517c28080d1a67148199fd5e`: direct DNG saving is confirmed on four camera shots. The older image above is the pre-DNG recovery baseline.
- The handoff confirms **every feature on camera**, including the final non-diagnostic SCN presets. The earlier request to validate those again is superseded.
- Rebuilding this firmware has already been verified byte-identical. Do not overwrite the confirmed image for another rebuild check.
- RAW encoding, the lavender cause, inverse companions and the date patch are resolved. Reuse `tools/ccdi2dng.py`.

## Current direction: films in the editor

The workflow is documented in [workflow/lightcraft/README.md](../../workflow/lightcraft/README.md).
LightCraft CLI 0.19.0 successfully imported all 63 original 3D `.cube` LUTs and three renamed starter profiles. Profiles survive reopening. Four sample RAWs convert and render correctly; synthetic-chart LUT results match an independent calculation within one 8-bit channel value. Source samples and firmware were hashed before and after and remain intact.

Ready artifacts (paths from the project root):

- `workflow/lightcraft/packs/CD703-Starter.zip`: Amber 200, Chrome 100 and Silver 1600.
- `workflow/lightcraft/packs/CD703-All-Films.zip`: all 63 original LUTs.
- `workflow/lightcraft/comparison.jpg`: camera JPEG, DNG base and starter looks for shots 0293–0296.
- `workflow/lightcraft/VERIFICATION.json`: 22 passing integration checks and provenance.

Next: try daylight, indoor and high-contrast shots; adjust exposure/WB and choose preferred profile amounts. Use sRGB export. The native desktop import clicks and GPU preview path remain untested; the CLI exercised actual decoding, library persistence and rendering. B&W-mode RAW uses the converter's daylight WB fallback. New black-frame samples would extend coverage.

Native `.cube` support works, so embedding films into DNG LookTables is unnecessary for this editor workflow.

## Direct DNG: implemented and camera-confirmed

The user accepts fixed daylight white balance and editor adjustments. The host format proof passes 20 checks, the instructions pass 18 mocked-API emulator scenarios, and **the actual camera trial now passes too**. Flashed hash verified from KC713.OLD; four DNGs 0303–0306 have the expected header/size and render pixel-identically to linear reference DNGs in LightCraft. The two B&W JPEGs retain colour DNGs. Latest dump shows matching entry/header/hook, phase 5 and zero errors, with all header/payload bytes written. Evidence: `mods/native_dng/test-v1/camera-verification.json` and `camera-comparison.jpg`.

Keep this working firmware. New photos can be imported directly as DNG; the converter is only needed for older RAW captures. Further coverage can include long-exposure black frames, card-full/interrupted writes, broader mode checks and other editors. Diagnostics: `0x125cc0`, header `0x1241a0`, hook `0x125a00`. `inspect_capture.py` reads DNGs/dumps; `verify_camera.py BACKUP_DIR` reproduces the real-file editor checks. Camera trial backup: `cd703_card_native_dng_test_20261108T003143Z/` (10 new/changed files, hash verified). The assembler is preserved as `tools/binutils/arc-elf32-as` (binutils 2.43), with provenance.

## Share mod menu: basic camera confirmation complete

Current firmware is **`mods/share_menu/test-v1/KC713.FW` (`f992a106…`)**, based on metadata v3. The user reports the menu works as intended. Actual KC713.OLD hash matches; first capture 0318 is JPEG+DNG, second capture 0319 is JPEG-only with no same-number RAW/DNG in the full card inventory. The enabled DNG's metadata matches its JPEG and LightCraft render matches the linear reference. Backup `cd703_card_share_menu_test_20261108T023024Z/`, four files hash-verified; no new dump. Evidence `mods/share_menu/test-v1/camera-verification.json`. The session toggle defaults ON at power-on by design; an additional capture after OFF→ON and after restart would extend the two-shot file evidence. Nineteen menu/capture plus 50 DNG regressions and identical rebuild pass. Preserve metadata v3 `9760823a…` as pre-menu fallback. Native Share event is `0x680`, screen `0xa8`; hidden shortcut opens `0x3b`. Allocation `0x1256c0–0x125769` must not overlap an older diagnostic scene hook. Implementation/research under `mods/share_menu/`; stock Ghidra project remains read-only.

## Other firmware ideas for later

**Current firmware and completed work:** metadata **v3** `mods/native_dng/metadata-v3/KC713.FW` (`9760823a…`) is flashed and camera-confirmed. Five DNGs 0313–0317 decode and render identically to independent linear references. Four retained JPEG pairs match same-shot date/time, exposure, aperture and ISO. JPEG 0313 was intentionally deleted due to its wrong clock date; its DNG is populated and valid, with no pair comparison claimed. This resolves v2's one-shot delay. The helper reads `[0x1324fc]` before DNG writing; 50 emulator cases and deterministic rebuild also pass. Latest backup `cd703_card_dng_metadata_v3_test_20261108T020104Z/`, 10 files hash-verified; no new dump. Evidence `mods/native_dng/metadata-v3/camera-verification.json`. Requested metadata scope is complete; optional further coverage is listed above. Preserve v1 `8dce21de…` and pre-DNG fallback.

An independent film selector could separate looks from SCN exposure policies. Per-scene tone curves are also plausible: loader `0x11de40` runs per photo, and getters `0xaf4e0`, `0xaf4e8`, `0xaf500` are hook candidates. The green curve A loader still needs tracing.

The ARC assembler, objdump and objcopy are retained in this workspace. Change curve B together with **both** inverse companions (`0x16bec8`, `0x16c4c8`). Keep reviewed CCM coefficient magnitudes below 4.0. Use our own names in camera UI and give each build a short hardware test procedure and checksum manifest.

The Ghidra project remains the stock firmware analysis. The user flashed the new DNG build; the firmware hash, actual files and memory dump now provide separate hardware evidence alongside the editor and emulator checks.
