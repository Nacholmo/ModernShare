# Mod Settings 0.4: film choice and firmware label

Latest candidate: [Velvia 100 / Kodachrome 64, version 0.7](../classic_films/README.md),
retaining the Film-first menu from 0.6 and working preview path from 0.5.
The 0.4 implementation below is historical.

Camera-tested `test-v0.4/KC713.FW`, SHA-256
`9e780daf4f0597788f802088ccaf5734554c2b0b8f65bf61de668b979b6d0f72`.
**Known limitation:** saved JPEG effects work, but viewfinder and both review
paths do not show them. The 0329 JPEG is monochrome while both embedded previews
remain colored. A separate preview-path candidate is documented in
[`../film_preview/README.md`](../film_preview/README.md); 0.4 remains the confirmed
saved-file recovery. Evidence: `test-v0.4/camera-verification.json`.

Base: user-confirmed date-default `b37ad3c6…`, subsequently independently verified
from card `SYSTEM/KC713.OLD`. Date fallback stays November 7, 2026 at noon.

Press **Share** to open **MOD SETTINGS**. UP/DOWN select a row; OK activates it:

| Row | Action |
|---|---|
| DNG saving | Toggle ON/OFF |
| Film | Cycle By mode → Stock → Agfa Vista 200 → Kodak E100VS → Fuji Neopan 1600 → By mode |
| Hidden menu | Open the original hidden menu, including the firmware updater |
| FW: CD703 mod 0.4 | Display this firmware's version; OK has no effect |

Share, Menu or Delete close the menu. Film changes last for the current session;
power-on returns to **By mode**, retaining the previous per-scene behavior:
Sunset/Vista, Children/E100VS and Museum/Neopan. DNG defaults ON at power-on.
Stock clears the scene film overrides. The named films use the exact existing
camera matrix approximations, applied independently of the selected exposure scene.
Normal camera color-mode/exposure processing still applies. Start the trial in
ordinary COLOR to compare the looks consistently; other color modes, video and
live preview require additional physical coverage. DNG sensor data and its fixed
editable daylight WB are unchanged; the selector affects the processed look.

## Validation

**37 menu/capture scenarios pass**, including all five film transitions, wraparound,
label refresh/reopening, an inert version row, DNG toggle, hidden-menu access,
capture/review closing, missing-list behavior and stock capture gating. Within
five grouped scenarios, **780 actual CCM/Ymat getter cases** cover all modes
0–23 plus invalid modes 24/255, three illuminants and normal/B&W/sepia arguments.
The selected pointers match the original film records; stack, saved registers,
DNG header/flags and film-map guard bytes are checked.

**15 date-path and 50 full DNG-writer regression scenarios also pass** against this
firmware hash. External UI/file/RTC services are mocked. The stock compiler restore
boundary is modeled for its documented SLEIGH alias issue. Physical screen layout,
JPEG film effects are now user-confirmed and 0329 monochrome output independently
verified, with the preview limitation above. A separate rebuild
is byte-identical and container checksums pass.

Reports: `test-v0.4/verification.json`, `menu-emulation.json`, `date-emulation.json`,
`emulation.json`, `manifest.json`. SD copy/readback and unmount status are recorded
in `card-staging.json`; all existing card files are preserved.

## Implementation

No new film matrices or capture hooks are introduced. Film selection updates the
existing 24-byte map at `0x125780` in RAM: By mode restores the three original
entries, Stock writes zero, and the named looks fill it with film IDs 1/2/3.
The existing capture-time getters read this map. Firmware and fresh-boot map remain
byte-identical to the base. No flash/settings-file writes or persistence are added.

The previous Share callback allocation at `0x1256c0–0x12577f` now holds 184 bytes.
The 88-byte film action occupies `0x1247a0–0x1247f7`, immediately after the fixed
1536-byte DNG header and outside every header write. The hidden-menu/no-op code
uses 16 bytes at `0x1259e0`, after all three 192-byte film records. Both extensions
are inside previously audited zero allocations, have no stock static references,
and were zero in all 29 unique historical dump frames examined. Eight bytes of
header padding and 16 bytes of film padding remain unused. These allocations must
not be overwritten by future larger headers/film records or old diagnostic hooks.

The four-row list and strings use `0x168190–0x16836f`, previously owned only by
the original Share page; ownership is checked against all registered stock roots.
Session film byte: `0x1682d0`; label pointer table: `0x1682bc`; event table:
`0x1682d4`. Selected rows dispatch events `0x5000` (DNG), `0x5001` (film), `0x5002`
(hidden menu), `0x5003` (version). Root/Share ID and existing capture entry patch
stay unchanged. Only callback allocations, private widget storage, row count and
container checksums differ: 513 bytes total.

The code object is sparse: its binary includes gaps between the three allocations.
The builder patches only the three audited ranges, never the intervening bytes.
The DNG writer/header/metadata, film getter hooks and records, date fixes, boot art,
theme, flash defaults and other capture code stay byte-identical to the base.

## Reproduce

```sh
python3 mods/mod_settings/src/build_mod_settings.py --outdir mods/mod_settings/my-rebuild
source decompiler-project/scripts/environment.sh
"$GHIDRA_ROOT/support/analyzeHeadless" "$PROJECT_ROOT/projects" KodakC713 \
  -process code.bin -noanalysis -readOnly \
  -scriptPath "$PWD/mods/mod_settings/src;$PWD/mods/date_default/src;$PWD/mods/native_dng/src" \
  -postScript TestModSettings.java "$PWD/mods/mod_settings/my-rebuild" \
  -postScript TestDateDefault.java "$PWD/mods/mod_settings/my-rebuild" \
  -postScript TestNativeDng.java "$PWD" "$PWD/mods/mod_settings/my-rebuild"
```

Use a fresh output directory. The builder pins the exact base and original bytes,
checks code capacity and widget ownership, and verifies a change allowlist.

## Camera trial

1. Install staged `SYSTEM/KC713.FW` through Share → Hidden menu → UPDATE FIRMWARE.
2. Open Share; check that the firmware row shows **CD703 mod 0.4**. Verify all five
   film labels cycle and wrap, and that the version row does nothing when selected.
3. In ordinary COLOR, photograph one colorful scene under steady lighting with
   Stock, Vista, E100VS, Neopan and By mode. Neopan JPEG should be monochrome;
   DNGs should retain color. Keep all files for readback comparison.
4. Check DNG OFF still saves JPEG only and Hidden menu still opens. Restart: film
   should return to By mode and DNG to ON. Existing date fallback stays unchanged.

Reconnect the card afterward for firmware hash, JPEG/DNG and metadata inspection.
Memory dump is optional if a failure needs diagnosis. Recovery image:
`mods/date_default/test-20261107/KC713.FW` (`b37ad3c6…`).
