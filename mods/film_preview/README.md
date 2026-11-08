# Film preview candidate: Mod Settings 0.5

Candidate `test-v0.5/KC713.FW`, SHA-256
`9e1e406461966d3beab7fd3c2381bf2310bc8cfeb8849756f175696afe1ff5d0`.
Base is camera-tested Mod Settings 0.4 (`9e780daf…`). **User confirms 0.5 preview behavior works; installed hash independently matches
KC713.OLD.** Individual screen steps were not separately reported; new 0330–0332
pairs are backed up but not independently rendered in the subsequent menu-reorder
turn. See `test-v0.5/camera-user-report.json`.

The next build moves Film to the first menu row: [Mod Settings 0.6](../mod_settings/test-v0.6/README.md).
0.5 remains the confirmed recovery image.

## Observed issue

User reports film effects work in the computer's JPEGs, but neither live view,
immediate review nor later Review shows them. Card KC713.OLD matches 0.4. Backup
`cd703_card_mod_settings_test_20261108T031018Z/` has ten new/changed files: five
JPEGs 0325–0329, four DNGs 0326–0329 and KC713.OLD. Older captures were already
absent on connection; they remain in the earlier backup chain. No card deletion
was performed here. No new memory dump was supplied.

Shot **0329 is exactly monochrome in its full 3056×2292 JPEG**, but both embedded
JPEG previews are colored: 160×120 at byte 13860 and 640×480 at byte 17477.
Mean max-minus-min RGB channel spreads are 22.44 and 22.65, versus zero in the
main image. This is consistent with the camera displaying an independently
generated preview. Analysis: `research/embedded-preview-analysis.json`; extracted
preview files are beside it. Color-film identities for individual other shots
were not separately supplied. All four DNGs have matching JPEG metadata and
pixel-identical LightCraft/linear-reference renders; see the 0.4 camera reports.

## Candidate behavior

The viewfinder matrix path uses its own calibration, so it should not be replaced
directly with a capture CCM. Instead this candidate composes the selected film's
relative RGB transform with the matrix being packed for the preview hardware.
It reads the existing runtime film map, retaining By mode and Stock behavior.
After a film selection in capture mode, it calls the stock preview matrix setter
with the current color level, then refreshes the menu. Native B&W/sepia levels
keep their existing hardware effect; the normal preview path still uses the wrapper.

**Only capture state 1 is transformed.** Review and other states pass through the
stock packer, so playback does not add the currently selected film to an already
processed photo. The caller in `0x62fc0` already fetches the capture film CCM;
its call returning to `0x62ff8` also bypasses the transform to avoid applying it
twice. Existing JPEG capture getters, matrices, DNG writer/data and date default
stay byte-identical to 0.4.

The intended result is a film preview in live view, and correct embedded previews
in **newly captured** files. Whether the camera's thumbnail generation uses the
newly refreshed/packed preview exactly as expected remains a hardware question.
Old files' colored embedded previews are not rewritten. The preview is a CCM
approximation; it does not promise pixel-identical saved-JPEG tone/YCbCr processing.

## Implementation and validation

- Entry `0x62a28` branches to a guard at `0x12fe98`. The stock prologue is replayed
  in a trampoline before resuming the original packer at `0x62a30`.
- Main transform code: **142 bytes at `0x125c24`**, directly after the DNG writer
  and before its diagnostics at `0x125cc0`. Guard/loop tail: **88 bytes at
  `0x12fe98`**, before boot code at `0x12ff00`. Both allocations are zero in the
  pinned base and all 29 unique historical dump frames checked; no stock static
  references point inside them.
- Refresh/trampoline: **60 bytes at `0xebc50`**, reclaiming the original Share
  root handler's 64-byte body. Its only stock external reference is the old root
  handler pointer; the current root points to `0x1256c0`. The pinned base has no
  remaining data pointers into any halfword in the reclaimed range. Ghidra finds
  no unexpected external references. The original Share handler must never be
  restored or called alongside this candidate.
- Relative film transforms: 54 bytes of signed Q12 coefficients at `0x168324`,
  unused Share-private storage immediately after the event table. They are derived
  from film CCM × inverse(stock capture CCM), retaining preview calibration.
  Each 3×4 input is composed on a 48-byte stack buffer; source data is untouched.
  Multiplication uses the stock integer helper `0x11b114`; original register
  packing and coefficient conversion remain in use. Saved registers/stack are
  restored through stock compiler helpers.
- **93 menu/preview/capture scenarios pass**, consisting of 56 preview-specific
  cases and the previous 37 menu/capture cases (including 780 getter cases).
  Preview tests cover all films, all three preview levels, custom scaled matrices,
  bypassing already-filmed capture CCMs, Review bypass, hardware-upload arguments,
  refresh roots, source/destination guards, stack and saved registers. Stock
  multiplication is modeled in the emulator; ISP/UI/file/RTC services are mocked.
  The known SLEIGH shared-restore alias issue is modeled at that compiler boundary.
- **15 date scenarios and 50 DNG regressions pass.** Independent floating-point
  composition agrees within one Q8 coefficient unit, coefficient magnitudes stay
  below 4, and Neopan output rows are identical. Rebuild is byte-identical;
  checksums and change allowlist pass (348 changed bytes from 0.4).

Reports under `test-v0.5/`: `verification.json`, `menu-emulation.json`,
`date-emulation.json`, `emulation.json`, allocation audits, `manifest.json`, generated
assembly and `card-staging.json`. The stock Ghidra project is read-only.

## Reproduce

```sh
python3 mods/film_preview/src/build_film_preview.py --outdir mods/film_preview/my-rebuild
source decompiler-project/scripts/environment.sh
"$GHIDRA_ROOT/support/analyzeHeadless" "$PROJECT_ROOT/projects" KodakC713 \
  -process code.bin -noanalysis -readOnly \
  -scriptPath "$PWD/mods/film_preview/src;$PWD/mods/date_default/src;$PWD/mods/native_dng/src" \
  -postScript TestFilmPreview.java "$PWD/mods/film_preview/my-rebuild" \
  -postScript TestDateDefault.java "$PWD/mods/film_preview/my-rebuild" \
  -postScript TestNativeDng.java "$PWD" "$PWD/mods/film_preview/my-rebuild"
```

Use a fresh output directory. Preserved `draft-v0.5` and `rebuild-v0.5` are
superseded development artifacts; only `test-v0.5` / `rebuild-v0.5-final` contain
the current guarded candidate.

## Camera trial

1. Install staged `SYSTEM/KC713.FW` through Share → Hidden menu → UPDATE FIRMWARE.
   Check the version row reads **CD703 mod 0.5**.
2. In ordinary COLOR mode, point at something colorful. Select Neopan; close the
   menu. Check whether live view becomes monochrome immediately.
3. Take a **new** picture. Check immediate preview, then reopen it later in Review.
   Both should be monochrome if the preview-generation path is covered.
4. Switch to Stock. Live view should regain color. Photograph again; Review should
   show the new color shot and retain the previous monochrome shot's appearance,
   regardless of the currently selected film. Try Vista/E100VS and restart defaults.
5. Reconnect the card with all JPEG/DNG pairs retained. We can independently check
   main JPEGs and both embedded previews, plus DNG color and metadata. If a display
   path still fails, a fresh memory dump with Neopan selected can help trace it.

Recovery: confirmed **Mod Settings 0.4** `mods/mod_settings/test-v0.4/KC713.FW`
(`9e780daf…`), whose saved JPEGs/DNGs work despite the preview limitation.
