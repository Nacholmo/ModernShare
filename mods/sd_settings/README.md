> Public export: use the root README and `scripts/build.py` for the standalone build. References below to historical `test-v0.8/` files describe development provenance; reports are exported under `docs/validation/0.8/`. Firmware images are not distributed.

# ModernShare 0.8

Camera-confirmed build: `test-v0.8/KC713.FW` (SHA-256
`091663ac848b6ee07c2a9252b9a9662e8cc7c463275e2dde62edb10d8e0f6003`).
Built from pinned five-film 0.7 (`57a25b3f…`). The user reports **“works as intended”**
after the camera trial. This is the current confirmed baseline; see
`test-v0.8/camera-confirmation.json`. Independent post-flash card readback and
interrupted-power durability testing have not been performed.

The Share button now opens **ModernShare**. Film stays first; the seven choices,
preview handling, JPEG looks, hidden-menu shortcut and original sensor DNG data
are retained. The supplied project-root `boot_image.png` replaces the old boot
artwork. The version/status row shows v0.8 and SD settings feedback.

On a card without valid preferences, **DNG saving defaults OFF**, Film **By mode**.
Changing either choice with OK automatically saves both to the SD card. Startup
restores them before the first capture. An enabled DNG preference therefore stays
enabled after restarting or opening the battery flap. Settings belong to the card;
formatting it or removing both preference files restores the defaults.

## Preferences

The root files `KMOD0.CFG` and `KMOD1.CFG` are alternating 16-byte records. On the
camera the paths are `B:\KMOD0.CFG` / `B:\KMOD1.CFG` (B: is SD). No settings file
is written to internal storage. Opening/refreshing the menu or starting the camera
does not write a file. Only changing Film or DNG writes preferences.

Four little-endian u32 words:

| Word | Value |
|---|---|
| Magic | `0x444f4d4b` (`KMOD`) |
| Configuration | `0x10000 \| film_index << 8 \| dng_on` |
| Generation | Increasing uint32, wrapping at `0xffffffff` |
| Checksum | `~(magic ^ configuration ^ generation)` |

Film index is 0–6; DNG is 0/1. Invalid magic, schema/reserved bits, film index,
checksum or short reads are rejected. Choose the newer valid generation using a
signed wraparound difference; A wins ties. The next save truncates/writes the
inactive slot and closes it before committing generation/slot in RAM. A partial
record leaves the previous valid slot available. This does not guarantee FAT or
SD hardware integrity during power loss; physical interruption testing is pending.

The row displays `v0.8: defaults`, `v0.8: SD loaded`, `v0.8: SD saved`, or
`v0.8: SD error`. On failure the selected setting remains active for the current
session. A later successful change retries the same inactive slot. The original
debug/hidden-menu DNG toggle bypasses this save callback; use ModernShare's row
for persistent choices. Clock and native camera settings are outside this record.

Inspect files without changing them:

```sh
python3 mods/sd_settings/src/settings_record.py /path/to/card/KMOD*.CFG
```

## Boot artwork

The existing 480×240 five-tile boot renderer and palette are unchanged. The
English text plus image must fit a 47,616-byte language buffer: 24,060 bytes are
available for tile streams. The source is resized, lightly median-filtered to
remove subpixel texture (text areas retain original antialiasing), then mapped
to the existing palette with background flattening. Colours and gradients are
simplified by this palette/budget. `test-v0.8/boot-preview.png` shows the converted
art at the screen's visible aspect ratio. The source PNG is unchanged. Its progress
bar is part of the static artwork.

Tile streams occupy 24,052 bytes, leaving eight bytes. English text is unchanged;
the existing guard still suppresses tiles when their English language payload
isn't loaded. Other languages retain the previous plain-screen fallback. No new
language is sacrificed, and all stock graphics/menu colours are byte-identical.

## Implementation and validation

`src/settings.s` occupies two reclaimed legacy Share code spans:
`0xebecc–0xec00f` (324 bytes) and `0xec088–0xec207` (384 bytes).
The old event table `0x16839c–0x16844b` becomes state/paths/status labels. Its sole
remaining pointer at `0xec050` is cleared. The literal gap, especially shared
`0xec05c`, and helpers at `0xec208` onward remain unchanged. Static references and
raw pointers are audited; the earlier 0.7 film allocation remains intact.

Capture root 1's 0x4405 callback at `0x1508bc` wraps the original `0xcabfc` init:
load only after it succeeds, preserving its result and arguments. Menu init also
loads once, covering Review-first startup. Restored film uses the existing table
fill/preview refresh at `0x1247b8` without incrementing it. Film/DNG callbacks wrap
the original actions, save, then repaint status. JPEG/DNG capture hooks are unchanged.

**248 instruction-emulation scenarios pass:** 54 preferences/startup/error cases,
129 menu/preview/capture cases (including 1,092 getter cases), 15 date cases and
50 complete DNG-writer cases. Coverage includes every film/DNG combination, A/B
selection, invalid records, wraparound, read/write/open/close failures, short writes,
retry, previous-slot recovery, Review-first init and failed stock init. File/UI/RTC
services are modeled with caller-saved registers destroyed. The known SLEIGH
compiler-restore alias and stock multiply boundaries are modeled as before.
The user accepted the camera build; physical interrupted-power SD durability remains untested.

Container checksums, strict patch allowlist, exact five-tile reconstruction,
42 host record roundtrips and a byte-identical fresh rebuild pass. Reports are
`test-v0.8/{verification,settings-emulation,menu-emulation,date-emulation,emulation}.json`.

```sh
python3 mods/sd_settings/src/build_modernshare.py --outdir mods/sd_settings/my-build
```

The builder refuses existing firmware outputs. Run Ghidra read-only as documented
in the handoff, then `src/verify_modernshare.py BUILD FRESH_REBUILD` before staging.

## Camera trial procedure (user accepted build)

Flash `SYSTEM/KC713.FW` through Share → Hidden menu → UPDATE FIRMWARE.

1. Check the ModernShare boot image/title and `v0.8: defaults`. With no CFG files,
   the first shot should save JPEG only.
2. Select a film such as Velvia. Expect `SD saved`. Restart (battery-flap reset is
   useful); verify the film restores, `SD loaded` appears, and DNG stays OFF.
3. Enable DNG, restart, take a shot; expect JPEG + DNG. Disable DNG, restart and
   take another; expect JPEG only. Check live view and later Review as usual.

Then reconnect the card for CFG, capture and installed-firmware readback. A memory
dump is optional if there is a startup, save, display or persistence problem.
