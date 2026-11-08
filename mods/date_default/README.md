# Fixed fallback date

Camera-confirmed firmware: `test-20261107/KC713.FW`, SHA-256
`b37ad3c6a0d86ce8c1e8a9b34a38f93236f82bab2477b6252b824098ce294c34`.
Based on camera-confirmed Share-menu firmware `f992a106…`.

After the battery flap interrupts the clock, the default is **November 7, 2026,
12:00:00**, replacing January 1, 2007. This is the date requested in the user's
Argentina timezone, fixed in this build. It does not advance with the computer's
date or preserve the RTC through power loss. Normal clock adjustment still works.

The lost-RTC template at `0x16a708` and reset-action templates at `0x1284ac` and
`0x128540` now hold the complete nine-field `struct tm`, including Saturday and
zero-based day-of-year 310. Boot screen initialization at `0xdc45a` copies the
first six fields (24 bytes), preserving the adjacent globals. Setup screen code
at `0xeae58` accepts retained years 2007–2037 and uses the same fallback for invalid
years. This also fixes its previously missed 2025 upper limit.

Only those five ranges and container checksums differ: 81 bytes total. The RTC
epoch, invalid-clock sentinels, low-level RTC routines, Share menu, DNG writer,
metadata helper, sensor defaults and film hooks remain byte-identical to the base.
No new code cave is used.

## Validation

- Container checksums pass; a separate rebuild is byte-identical.
- Fifteen Ghidra instruction scenarios pass: startup screen, setup date
  preservation for 2007/2025/2026/2037, fallback for 2006/1900/2038, RTC read
  failure, old/retained RTC dates, and both reset actions through the RTC setter.
- Screen tests check stack, saved registers and canaries beyond the 24-byte copy.
- RTC hardware, memcpy and the setup widget property service are mocked; tests
  stop before rendering or actual RTC writes. The user reports “works” after the
  camera trial instructions. Subsequent KC713.OLD readback matches this build; shot
  0320 JPEG/DNG agree on 2026-11-07 12:00:20 and exposure/aperture/ISO, with an
  identical LightCraft/linear-reference render (`test-20261107/camera-verification.json`).
  Existing Share/DNG behavior is inherited
  from the confirmed base; its
  code is unchanged, so its earlier 69 instruction tests were not repeated here.

Reports: `test-20261107/verification.json`, `date-emulation.json`, `manifest.json`
and generated `.asm` disassembly. `card-staging.json` records SD staging/unmount.

The next menu candidate adds film selection and a version label: see
[`../mod_settings/README.md`](../mod_settings/README.md). This date build remains
the current confirmed recovery image.

## Reproduce

Use a fresh output directory:

```sh
python3 mods/date_default/src/build_date_default.py --date 2026-11-07 --outdir mods/date_default/my-rebuild
source decompiler-project/scripts/environment.sh
"$GHIDRA_ROOT/support/analyzeHeadless" "$PROJECT_ROOT/projects" KodakC713 \
  -process code.bin -noanalysis -readOnly \
  -scriptPath "$PWD/mods/date_default/src;$PWD/mods/share_menu/src;$PWD/mods/native_dng/src" \
  -postScript TestDateDefault.java "$PWD/mods/date_default/my-rebuild"
```

The builder requires the pinned confirmed Share-menu base, asserts original bytes,
refuses an existing output firmware, and accepts dates only in 2007–2037.

## Camera trial

1. Install the staged image through Share → Hidden menu → UPDATE FIRMWARE.
2. Open and close the battery flap to lose RTC power, then turn the camera on.
   The date prompt should start at **2026-11-07 12:00**, not 2007.
3. Accept it, open normal date/time setup, and check that 2026 remains selected.
   Set a different supported date/time, power-cycle without opening the flap,
   and check that it remains intact.
4. Take a shot with DNG enabled. A JPEG/DNG pair should have the chosen clock
   value; reconnect the card for independent firmware and metadata readback.

No memory dump is required unless something behaves unexpectedly. The confirmed
fallback remains `mods/share_menu/test-v1/KC713.FW` (`f992a106…`).
