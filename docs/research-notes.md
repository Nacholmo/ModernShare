> Archived development notes. Paths to historical firmware builds, card backups and generated exports describe the private research workspace; those artifacts are not distributed here. Use the root README for the supported public build.

# Kodak CD703 / C713 custom firmware — notes

Started 2026-11-07. The CD703's own firmware is "lost media". This camera runs
the **C713 build, version 1.30**: the hidden menu reports MCU 66, MAIN 1.3000 and
CamOS 2.2501, and a RAM dump of the camera's code section is byte-identical to
`kc713.fw`.

## ModernShare 0.8 — supplied artwork and SD preferences (2026-11-08)

The user renamed the mod **ModernShare**, supplied `boot_image.png`, requested
DNG OFF by default and persistence on SD. Camera-confirmed build
`mods/sd_settings/test-v0.8/KC713.FW`, SHA-256
`091663ac848b6ee07c2a9252b9a9662e8cc7c463275e2dde62edb10d8e0f6003`.
Pinned base is five-film 0.7 (`57a25b3f…`), independently read back from the card's
KC713.OLD. All previous firmware outputs remain unchanged. The user subsequently
reported **“works as intended”** for 0.8; it is now the current user-confirmed
baseline. This is user acceptance, without a subsequent independent CFG/capture/OLD
readback or separately reported test steps. Evidence: `test-v0.8/camera-confirmation.json`.
Full implementation/test procedure:
`mods/sd_settings/README.md`; current state is in `HANDOFF.md`.

- New-card defaults: Film By mode, **DNG OFF** (`0x13358c=0`), JPEG ON unchanged.
  Film / DNG OK actions automatically save both choices to SD-root `KMOD0.CFG`
  and `KMOD1.CFG` (`B:\` is SD). Capture init loads once after original `0xcabfc`
  succeeds; Review-first menu init also loads. Restored film replays map fill and
  preview refresh without advancing. A saved DNG ON choice restores ON. No save
  on opening/refreshing the menu or starting the camera. Hidden/debug toggle does
  not auto-save; native clock/settings are outside this record.
- Record: four LE u32 words, magic KMOD `0x444f4d4b`, config
  `0x10000 | film<<8 | dng`, uint32 generation, `~(magic ^ config ^ generation)`.
  Validate checksum, schema/reserved bits, film 0–6 and DNG 0/1. Compare generations
  with signed wrapping difference, A wins ties. Write/truncate inactive slot;
  require status 0, 16 bytes and successful close before advancing in-RAM sequence
  and slot. Keep runtime choices and previous active file on failure; show SD
  error. Inactive-slot retry is independent of generation parity. This handles
  incomplete records, not guaranteed SD/FAT survival during power interruption.
- Actual OS ABI: open `0x73224(path,create,access,&handle)` with 0/0 read, 1/1
  create/truncate; read `0x73234(handle,buf,16,1,&count)`; write
  `0x73240(handle,buf,16,0,&count)`; close `0x7324c(&handle)` flushes and zeros it.
  Confirmed against stock updater/SD paths and DNG writer. Never writes A:.
- SD hooks reclaim `0xebecc–0xec00f` (324 bytes) and `0xec088–0xec207` (384).
  The only raw code pointers were in the retired Share table, now reused as
  176-byte state/paths/status space `0x16839c–0x16844b`. Its sole pointer
  `0xec050` is cleared. Keep shared literal `0xec05c`, the rest of that literal
  gap, shared helpers `0xec208/0xec394`, and widget data `0xec540` unchanged.
  Ghidra static audit and raw pointer scan pass. Old 0.7 NOPs at
  `0xebed0/0xebefc/0xebf00` are now SD instructions; do not assert NOPs there.
  Capture callback pointer `0x1508bc`, menu init `0x1682d8`, Film `0x1682e8` and
  DNG `0x1682f0` target new wrappers; all old actions still execute.
- Menu title/version now ModernShare; fourth row shows v0.8 and defaults / SD
  loaded / SD saved / SD error. Five film records, Q12 transforms, getters, preview
  guards, original DNG writer/header/metadata and all date/clock hooks are unchanged.
- User artwork SHA-256 `da2630f58fe6046c9d5fab8e2e42a9d1f24c8ee82d1b25bd3f4d2b4672ee8ce9`.
  Original 1448×1086 PNG is preserved. Existing five 480×48 tiles/renderer/guard
  retained. Technical resize, 3×3 median texture reduction with protected text
  rectangles, Lab flatten16 and fixed stock/theme palette mapping fit the limit.
  Converted preview was visually inspected: main branding/text remains readable;
  colours/gradients simplify. Static artwork includes its own progress bar.
  Tile payload 24,052 bytes; combined English+magic+streams 47,608/47,616, eight
  bytes spare. Five records' stream pointers change; English prefix, language
  tables, palettes, graphics and old boot hook remain unchanged. Other languages
  retain the previous guarded plain-screen fallback; no additional language lost.
- **248 instruction-emulation scenarios pass**, all bound to exact firmware hash:
  54 SD/startup/failure cases; 129 menu/preview/capture cases (1,092 getter cases);
  15 date cases; 50 full DNG writer cases. SD cases cover all 14 film/DNG choices,
  newest slot/ties/wrap, invalid/short records, missing card/files, read/write/open/
  close failures, interrupted-slot fallback, retry, actual menu autosave, loading
  before capture, Review-first init, stock-init failure and register/stack/handle
  preservation. APIs deliberately destroy caller-saved registers. Known SLEIGH
  restore alias and stock multiply boundaries modeled as in prior tests.
- Container checksums, strict change allowlist, preserved regions, exact tile
  decode roundtrip, 42 host codec roundtrips and fresh final-builder byte-identical
  rebuild pass. 24,311 bytes differ from 0.7, mostly new boot payload. Source,
  manifest, preview and reports are in `mods/sd_settings/`. Rebuild with
  `src/build_modernshare.py --outdir FRESH`; `src/verify_modernshare.py BUILD REBUILD`
  verifies the bound reports and final rebuild before staging.
- Before staging: **182 new/changed card files** copied/hash-verified to
  `cd703_card_modernshare_20261108T212825Z/`: 90 JPEGs, 91 DNGs (0333–0423), and
  KC713.OLD matching 0.7. JPEG 0347 absent, cause not inferred. Full inventory 204
  files. No deletion since previous inventory; older unchanged files stay in the
  backup chain. MEMDUMP/root firmware unchanged. Card has no preference files yet,
  enabling the first-boot OFF test. New firmware written exclusively to
  `SYSTEM/KC713.FW`, flushed and byte-readback verified; all 204 preexisting files
  rehashed unchanged. SD safely unmounted; see `test-v0.8/card-staging.json`.

## Files

| Path | What |
|---|---|
| `KC713130.exe`, `KC813130.exe` | Original Kodak updaters (WinZip self-extractors) |
| `firmware/stock/kc713.fw` | Extracted stock image (sha256 `06133ed6…`) |
| `tools/kodakfw.py` | `info` / `patch` / `replace` / `fix`: verifies and rewrites all checksums |
| `mods/*/KC713.FW` | Every build we made (see the mod table below) |
| `mods/vivid_tone/src/`, `mods/vivid_contrast/src/` | Assembly hooks (`hook.s`) and curve generators |
| `cd703_card_*` | Backups of everything the camera wrote (RAM dumps, test photos), with SHA256SUMS |

## Firmware format (`kc713.fw`, 2,172,416 bytes)

- `0x000` "RHIR". Byte 6 = number of section records. `(u32@8 & 0xFFFF00)` must be `0x034200` (C713; C813 = `0x034300`).
- `0x010` records, 16 bytes each: `u32 type, u16 start sector, u16 sector count, u32 RAM address, u32 sum32`.
  - rec0, type 1: code, file `0x200`, RAM `0x30000`, 1 MB
  - rec1, type 1: data, file `0x100200`, RAM `0x130000`
  - rec2, type 0: graphics, RAM `0x1a0000`
  - rec3, type 0: language text, RAM `0x1f0000`
  - rec4, type 2: special, sum 0. **Never "fix" its checksum.**
- `0x1F0` "KHIR", then `sum32(header[0:0x1F0])` and its bitwise NOT.
- sum32 = sum of little-endian 32-bit words. The updater checks only the type-1 sums.
- RAM to file offset: code `addr - 0x30000 + 0x200`, data `addr - 0x130000 + 0x100200`.

## Flashing

- Copy to `SD:\SYSTEM\KC713.FW`. Then hidden menu → **UPDATE FIRMWARE**. After a successful update the camera renames the file to `KC713.OLD`.
- The updater (validator at `0xFE304`) checks the magic, model word, size and type-1 sums. It writes NAND partition 6 and reads it back to verify, with 3 tries.
- The bootloader is **not** part of the update, which is why a bad image has so far always been recoverable.

## Hardware and code facts

- ARCompact CPU (ARC600-like: XMAC, DCCM; no cache-flush code found). MetaWare compiler, MQX RTOS, Altek ODM.
- The image runs from SDRAM: sp = `0x19f5e8`, gp = `0x172ef4`.
- Disassembly: binutils 2.43 built for `arc-elf32`. Wrap the code in an ELF with objcopy, then `objdump -d -M cpu=arc700 --adjust-vma=0x30000`. Literal pools are pc-relative, and long immediates are stored middle-endian.
- Our own code is assembled with `gas -mcpu=arc700`. Branches to fixed addresses are written as `b start + (TARGET - BASE)`.
- Original free-space candidates are now partly allocated; use the pinned builders and current `HANDOFF.md` before adding code. Fullscreen uses `0x125420–0x1255ff` plus hook `0x12ff00`; non-diagnostic scene code ends at `0x1256c0`, tables start `0x125780`; DNG writer starts `0x125a00`, diagnostics `0x125cc0`; DNG header `0x1241a0`, metadata helper `0x12ff40`. The pending Share menu uses `0x1256c0–0x125769`. Earlier zero-tail/whole-zero-run notes are historical and do not describe current free capacity.
- Key events: `(id << 7) | (0 press / 1 release)`. Key ids: UP 7, DOWN 8, LEFT 9, RIGHT 10, OK 11, zoom-out (W) 5. **The script engine's name table is misaligned; don't trust its key names.**

### MEMDUMP (built-in RAM dump to SD)

Hold **zoom-out (W)** and release **UP** (routine `0x40ee4`, enabled by flag `0x132b5a`). It writes `MEMDUMP.BIN`: 256 bytes, then RAM `0x100–0x1efbd6`, so file offset = RAM address. Each dump takes about 4 minutes and new dumps are appended to the file.

**Best technique so far:** take dumps at different settings, diff them to find the variable, then trace who writes it.

## Mods

| Mod | sha256 | Status |
|---|---|---|
| `hello_world` | `9ad0751e` | ✅ "CAMERA SOUNDS" → "HELLO WORLD" (3 strings) |
| `flash_off` | `ca9f237b` | ✅ Flash defaults to Off: `0x3bd92` `mov_s r0,4→1`, `0x132928` `4→1` |
| `vivid` (v4) | `3f330b8a` | ✅ **Recommended.** flash_off + Sepia replaced by VIVID (saturation ×1.5) |
| `vivid_tone` | `d26cd45d` | ⚠ v4 + tone-LUT swap hook. Works, but the contrast has no effect |
| `bootlogo` | `d6cbc2e7` | ✅ v4 + "Claude OS" startup banner (confirmed on camera). v1 (`871b67b7`, kept as `KC713_v1_fd.FW`) booted, but the text was hollow: it used reserved palette index 253 |
| `drawprobe` | `7e9918f9` | 🔬 Diagnostic build: bootlogo + logs every image draw (caller, args) to `0x125420` for MEMDUMP. Finds the boot-screen code |
| `fullscreen` | `29909410` | ✅ bootlogo + full-screen 480×240 boot image (claude_os.png) in 5 tiles (confirmed on camera). Sacrifices language 17 (non-Latin, 47 KB) |
| `theme` | `ff69e8b1` | ✅ boot image claude_os_v2_4_3.png (FLATTEN_N=5 FLATTEN=12: snaps to the 5 dominant colours; wide claude_os_v2 build kept as KC713_v2wide.FW; v3 with claude_os.png `c41291db` ✅ kept as KC713_v3_claude_os.FW) — fullscreen + "Claude dark" palette theme (v1 `97a1f923` patched only the image palette → boot image vanished, menus unchanged; v2 `73a2a212` patched both tables → see-through menus; v3 also rewrites the UI colour words) (navy→charcoal, red/yellow→coral accent). Build chain: `make_theme.py` → banner → `build_fullscreen.py` (FLATTEN=8) |
| `lut` | `fdb4784a` | ❌ warm_film test, made with the old (wrong) model: it edited the preview CCMs |
| `lut/vista_e100vs` | `68e8d302` | ❌ Old model. Tested (0235–0237): whites came out magenta because only its curves took effect |
| `lut/neopan1600` | `bee646da` | ❌ Old model (preview CCMs); never flashed |
| `lut/mtest` | `7574c244` | ❌ Result (photos 0241–0246, `cd703_card_mtest/`): NO effect on saved photos, so these level CCMs are not the capture matrices (probably the live preview). Was: stock curves. Level 0 = R↔B rows swapped, level 1 = G↔B swapped, level 2 = stock with green row ×0.8. Shows which level COLOR uses and the matrix/curve order (white G/R ≈ 0.90 = matrix before curves, 0.80 = after, 1.0 = AWB cancels) |
| `lut/mtest2` | `9cabad2e` | ✅ Confirmed (0247–0255, `cd703_card_mtest2/`): red flowers turned blue, and the paper moved by Cr +27 / Cb −9 (predicted +28 / −7). Changes were:
| `lut/vista200_neopan` | `53d34434` | ❌ Tested (0256–0261, `cd703_card_vista/`): white paper came out lavender (G −40 vs. a stock shot). Only builds that rewrote the tone curves did this; no curve-assignment hypothesis explains it, so `--matrix-only` builds leave the curves stock. The model also predicted slightly pink highlights (fit traded grey neutrality for colour) |
| `curve_inverse/vista_lavender_fix` | `739d7ab9` | ✅ Tested (0291 COLOR, 0292 B&W; `cd703_card_curveinv/`): **lavender gone** — paper G−(R+B)/2 = −2 (lavender build 0259: −42); the remaining blue (B−R +30) is outdoor shade light, smaller than the neutral matrix-only shot 0264 (+61). B&W paper 230/230/230. = lavender build `53d34434` + flash Off + both companion tables (`0x16bec8`, `0x16c4c8`) rewritten as the midpoint inverse of its curve B (`mods/curve_inverse/src/build_curve_inverse.py`). **Rule: whenever curve B changes, rewrite both companions = inverse(curve B).** |
| `film_color/vista200_neopan` | `8b28b6b6` | ✅ Tested (0294 COLOR, 0295 B&W, 0296 VIVID; `cd703_card_raw/`): no lavender (COLOR paper G−(R+B)/2 −8, B−R +38 = shade light, as in 0291/0264; B&W paper 248/248/248). Theme + **full fit with film curves**: COLOR/VIVID = Vista 200 (ΔE 2.6, vs 6.2 matrix-only), B&W = Neopan 1600 (6.2); companions = inverse of the new curve B; SCN presets refitted through the new curves (Sunset 5.6, Children 4.8, Museum 5.2); flash Off. Predicted greys within 2–7 levels (`mods/film_color/src/build_film_color.py`) |
| `raw_plus_jpeg/test_both` | `033e3531` | ✅ Works (0293–0296, `cd703_card_raw/`): every shot saved `100_nnnn.JPG` + `CCDInnnn.RAW` (7,096,320 B) + `YRGBnnnn.RAW` (10,506,528 B), ~6–12 s per shot. = `film_color` + hidden save flags on at boot: SaveCFAonTake `0x13358c` (true sensor RAW, writer `0x67898`) and SaveFullYRGB `0x133184` (processed YCbCr 4:2:0 `YRGBnnnn.RAW`); JPEG `0x133185` stays on. Only the hidden-menu toggles change these bytes, and the save code tests each flag on its own (`0x47c14`, `0x4a98c`, `0x33c2c`) |
| `raw_plus_jpeg/cfa` | `d1db5168` | ✅ Flashed; RAWs converted with `tools/ccdi2dng.py` open in Lightcraft (user: "way better for editing than the jpg"). = `film_color` + SaveCFAonTake only: JPG + sensor RAW. **CCDI RAW format:** headerless 3072×2310, 8 bit/pixel, Bayer **RGGB** ((0,0)=R, (1,1)=B), black ≈ 14; values look already gamma-encoded (an untested guess). Taken before any colour processing (the B&W shot's RAW is in colour, no date stamp) |
| `film_color/stock_color_neopan` | `655cbb39` | Flashed (KC713.OLD = 655cbb39); SCN with the non-diag hook not yet confirmed. User asked for no filter in normal COLOR: COLOR/VIVID = **stock** (curves, CCMs, normal Ymat, companions all byte-identical to stock; they share these, so VIVID is stock too). B&W = Neopan 1600 via the B&W Ymat only (luma weights 0.271/0.567/0.353, ΔE 6.9). SCN presets (Sunset/Children/Museum, non-diag hook), flash Off, sensor RAW on. `build_film_color.py --color none --raw` |
| `date_fix/stock_color_neopan` | `4765fbbb` | ✅ Works (user): year past 2025 settable, no stamp after restart, and photo metadata now has the correct date. = `655cbb39` + year limit 2025 → **2037** (date screens `0xdc604`/`0xeb020`: `cmp r1,2025` and wrap value 125; validator `0x7166c`) + **date stamp Off at every power-on** (`0x3e7dc` `ldb r0,[r13,0x39]` → `mov r0,0`; stamp byte `0x135235`, 0 = Off, saved at +0x39 of the settings record and restored by `0x3e7a8`). `mods/date_fix/src/build_date_fix.py` |
| `native_dng/test-v1` | `8dce21de` | ✅ **Camera-confirmed (0303–0306)**; user reports no errors/problems. Flashed hash verified. Four correct-size DNGs render pixel-identically to linear references in LightCraft; 0304/0305 B&W JPEGs have colour DNGs. Latest dump: phase 5, error 0, header 1536 + payload 7096320 written, code/header intact. = `4765fbbb` + direct DNG; fixed daylight WB, other kinds/sizes retain stock RAW path. Older confirmed DNG fallback; keep the pre-DNG baseline too. |
| `native_dng/metadata-v2` | `3f4df4fb` | ⚠️ **Flashed; metadata timing failed** on 0307–0312. Valid DNGs, first metadata blank and subsequent values one shot late. JPEG EXIF hook runs after RAW save. Preserve for diagnosis; use v1 as confirmed fallback. |
| `native_dng/metadata-v3` | `9760823a` | ✅ **Camera-confirmed (0313–0317); confirmed pre-menu fallback.** Five valid DNGs render identically to linear references; four retained JPEG pairs match same-shot date/time, exposure, aperture and ISO. First DNG populated; user deleted its JPEG due to old clock date. Fixed WB unchanged. 50 emulator cases and identical rebuild also pass. |
| `share_menu/test-v1` | `f992a106` | ✅ **Current firmware; basic menu and ON/OFF saving camera-confirmed.** UI works as intended (user); flashed hash verified. Shot 0318 JPEG+DNG, second shot 0319 JPEG only with no DNG/RAW. Enabled-shot metadata and editor render pass. Session toggle, boot default ON; 19 menu + 50 DNG emulator cases pass. |
| `lut/e100vs_neopan` | `280742bc` | ❌ Superseded by `_m` (never flashed). COLOR/VIVID = Ektachrome E100VS (3.9), B&W mode = Neopan 1600 (5.9) |
| `lut/vista200_neopan_m` | `884b7de8` | ✅ Tested (0264–0266 paper, 0273–0275 geranium; `cd703_card_vista_m/`, labelled shots): whites neutral (garden label 239/244/247), no pink, all modes save. **Matrices only** (`--matrix-only`): stock tone curves, greys forced neutral, luma weights and Y offset ≥ 0. COLOR/VIVID = Vista 200 (ΔE 6.2), B&W = Neopan 1600 (6.6) |
| `lut/e100vs_neopan_m` | `191ef3af` | 🧪 Matrices only. COLOR/VIVID = E100VS (4.6), B&W = Neopan 1600 (7.4) |
| `flash_all_off` | | Patch script (no build of its own): flash defaults to Off in EVERY capture mode. All 11 per-mode flash slots (`0x132928–0x132932`) start at 1, every slot reset (`0x3bd84…0x3be5c`, `0x3cad0`) stores 1, and the two no-slot modes that forced a value (Landscape 4, Candle Light 8; `0x3c6a6`, `0x3c6c8`) store 1 |
| `scene_films` v1 | `327ac134` | ❌ Tested (0276–0281, `cd703_card_scenefilms/`; papers 0279 Sunset, 0280 Children, 0281 Museum): Museum (Neopan) stayed in **colour**. It also hooked GetYmat `0xaf514`, but in colour mode the photo conversion `0x9fec0` (and siblings `0xa00e4…`) calls GetYmat only for B&W/sepia (then chroma = the Ymat's constant Cb/Cr offsets); normal chroma comes from tables `0x196b78`/`0x197078` built at start-up |
| `scene_films` v2 | `92c8477d` | ❌ Tested (0282–0284, `cd703_card_scenefilms2/`): Museum still in colour, so the per-scene CCM doesn't reach saved photos either. Flash Off by default confirmed by the user |
| `scene_films/diag` | `c44493c0` | 🔬 Result (`cd703_card_diag/`: dump 0 after a Museum shot, dump 1 after an Auto B&W shot): both getters ARE called once per photo (11 calls: 9× CCM from `0x98990`, CCM from `0x11e134`, Ymat from `0x11e142` with the colour mode, 3 in B&W). But Museum's mode was **17**, not 12: the scene table was off by one (the menu starts at "High ISO"), so v1/v2 never applied a film |
| `scene_films` v3 | `dbad1d67` | ✅ **Works** (0287 Auto, 0288 Sunset, 0289 Children, 0290 Museum = B&W; `cd703_card_scenefilms3/`, log confirms modes 0/22/9/17). Colours agree with the model's prediction from the Auto shot (e.g. Vista roofs pred 89/50/43 vs 85/48/40). Scenes keep their own exposure: Sunset 1/8 s ISO 80, Children ISO 400, Museum ISO 800. Correct modes: Sunset 22 = Vista (CCM + Ymat, ΔE 5.6), Children 9 = E100VS (CCM + Ymat, 5.1), Museum 17 = Neopan (CCM only, 3 equal rows, 5.7). Call log kept on |
    - Capture CCMs `0x16cac8/0x16caf8/0x16cb28`: R↔B rows swapped.
    - Normal YCbCr `0x16cb58`: Cr offset +20.
    - B&W YCbCr `0x16cb88`: luma = green only. |
| `vivid_contrast`, `vivid_v5`, `curvetest*` | | ❌ Experiments (see below) |

### How VIVID (v4) works

- **Colour menu:** a 5-way switch at `0x445c8`.
  - Its jump table at `0x445de` is `[9,13,3,17,19]`.
  - Indices 0/1/2 = Color with *colour level* 0/1/2 (`0x1334de`), 3 = B&W, 4 = Sepia.
  - The level picks the colour-correction matrix (CCM) `0x17d0c4[8+level]`. All three are identical in stock.
- **The patch:**
  - Jump-table byte `0x445e2` `19→3`: Sepia/VIVID now runs "Color + level 2".
  - Level-2 CCM at `0x16b7f8` = saturation 1.5 × stock CCM, in int32 Q16, rows sum to 1.0.
  - Menu highlight `0xcedee` and status icon `0xcdc5c`: `cmp_s r0,4 → 2`.
  - All 16 "SEPIA" strings → "VIVID".

## Graphics (rec2, RAM `0x1a0000`)

- **Image record (20 bytes):** `u16 w, u16 h, u16 stride, u16 bpp, u32 flags, u32 palette, u32 data`.
  - 1-bpp records (flags `0x80`) are mostly font glyphs; the font pointer table is at gfx+`0x90`.
  - **Never use palette indices 252–255.** No stock image does, and on the LCD they don't show their table colour (index 253 "dark brown" showed as near-background).
  - 245 records are 8-bit with flags 1 (RLE). They all use the RGBA palette at `0x1cb83c`: index 0 = transparent, 2 = white, and it includes Kodak red and yellow.
- **Image ID table:** `0x1ccf50`, 246 entries, entry 0 is null. It is registered at boot by `0x9038c` → `0xf1120`.
- **RLE format:** read count byte `c` and let `L = c >> 1`.
  - Odd `c`: `L` literal bytes follow.
  - Even `c`: one byte follows, repeated `L` times.
  - Runs cross row boundaries, and decoding stops at `w*h` pixels. Stock streams are followed by one pad byte.
  - (My earlier "2w × h/2 layout" theory was wrong; it came from decoding with the wrong length rule.)
- **Startup logo:** image ID 93, record `0x1cc35c`, 430×60.
  - It is drawn centred at the top of a white screen (about x 25, y 15 on the 480-wide OSD), with the 140×90 Share button (ID 92) in the middle.
  - Its data is at `0x1d8127`, 6554 bytes, on a white background.
  - The screen/OSD is 480 wide (`0x1e0` appears everywhere in the code).
  - `mods/bootlogo/src/make_logo.py` re-encodes any 430×60 image into the same slot, so the size and position are unchanged and no code is patched.
  - The new data must be ≤ 6554 bytes. Photo-like art at 430×60 compresses to about 10 KB and doesn't fit; flat graphics do.
  - `compose_claude.py` builds the "Claude OS" banner and limits the wordmark to 4 colours so it fits (5735 bytes).
- **Draw path:** `0x789f8` UI DrawImage(x, y, id) → coordinate scaling → `0x67e04` (getter `0x67dec`, decompress into the buffer at [`0x1335a4`], blit by bpp: 8-bit = `0x43ad4`). `0x36c30` draws by dialog-icon index. Width/height helpers: `0x78ad8` / `0x78b14`.
- **There is no spare space** in rec2 or rec3: zero tails are only 46 and 56 bytes.
  - A bigger image would need a repack of the 8-bit data area (`0x1cd328–0x1e8c8e`). That would recover about 1.8 KB through dedup and better encoding, and could spill into the code zero run.
  - Several blocks overlap their neighbour by 2 bytes, so a repack has to be done carefully.

## Full-screen boot image (`mods/fullscreen`)

- **The drawprobe log** (`cd703_card_drawprobe/`) showed that every widget draw comes from `0xc98b2`. The boot screen draws logo ID 93 at (20, 10) and Share ID 92 at (170, 90).
- **Screens are static structs** in the data section: `u32 0x402, u16 id, u16 count, ptr widget list, ptr handler`. There are 144 of them, and the boot screen is `0x15eedc` (id `0x73`).
- **Image widget** (type 7, 0x1c bytes): `+0 type`, `+4 widget id`, `+8 parent` (filled in at runtime), `+c x`, `+e y`, `+10 w`, `+12 h`, `+14 align`, `+18 image ID`, `+1a alternate ID`. The renderer is `0xc97ec`.
- **The OSD is 480×240** on a 4:3 panel, so a 4:3 picture is resized straight to 480×240.
- **Decode buffer:** images decode whole into `0x18fad8`, just below the main stack (top `0x19f5e8`). Keep each image ≤ 25,800 px, the stock logo's size; that's why the image is split into 480×48 tiles.
- **The language section is NOT in RAM.** `0x8a2f8` copies the selected language block from flash (rec3 file offset + table `0x14fca4`: 19 offsets and 19 sizes) into a `0xba00`-byte buffer at `0x183330`.
  - The graphics section is loaded the same way by `c8a3c(0x144c00, 0x4fc00, 0x1a0000)`.
  - Languages: 0 EN, 1 FR, 2 DE, 3 ES, 4 IT, 5 PT, 6–9 CJK, 10 SV, 11 DA, 12 FI, 13 PL, 14 TR, 15 (Russian?), 16 CS, 17 (non-Latin, 47 KB), 18 NL.
- **The trick:** the English block (23.5 KB) is followed by `CLOS` and the tile streams, all inside language 17's flash space. English and 17 both point there. The tiles appear in RAM at `0x188f34+` whenever English is loaded.
- **Guard hook** at `0x789f8`: tile IDs 246–250 draw nothing unless the magic is present. With another language selected, the boot screen is just blank.
- **New image IDs:** the ID table was extended to 251 entries by moving the first data block (225 bytes) to the code zero run. The count is set by `mov_s r1,0xf6` at `0x90390`/`0x90398`.
- **RLE count byte 0** is legal (zero-length run); one stock image uses it.

## UI theme (palette)

- **Two palette tables:** the hardware OSD palette (`0x175420`) is loaded at boot (`0x3b5dc`) from a *data-section copy* at `0x141c00`, NOT from the graphics palette `0x1cb83c`. They are identical for 0–251; 252–255 in the data copy are system colours (magenta, green, purple, cyan). A theme must change both.
- **How 8-bit art is drawn:** the blitter (`0x43960`) maps each image palette entry to an OSD index by *exact match* via `0x42040`; no match → 0 = transparent.
- **Consequence:** editing the graphics palette recolours the whole UI consistently (`mods/theme/src/make_theme.py`).
- **Boot image:** the full-screen image must be rebuilt after any palette change.
- **Colour lookup `0x42040`:** input `R<<24|G<<16|B<<8|A` (A 0 = opaque, 0xff = transparent). It converts to the hardware form `q(R) | G<<8 | q(B)<<16 | alpha4<<24` with `q(x) = (x+1 if x<=0x53, x-1 if x>=0xac, else x) >> 2` and `alpha4 = (30*(255-A)+255)//510`, then takes the first exact match in `0x175420`. The palette loader `0x43730` uses the same conversion. Checked 256/256 against a RAM dump.
- **UI colours (menu fills, text):** 32-bit `0xAABBGGRR` words (UI fill wrapper near `0x788a8`, `0xffffffff` = none, `0xfffefefe` = clear). They live in a colour table at data `0x14d310–0x14d3a0` and in code literal pools (`0x6f9e4 0x73ccc 0x73cd8 0xc9ac0 0xd0c74 0xd15c8 0xdd2b8 0xe0d64 0xe6f00 0xe6f04 0xea5c4–0xea5d4`). Menu background = navy `3d4875` (palette 18). Theme v2 left them stock: no match → transparent → live view showed through the menus. Theme v3 rewrites each to its entry's new colour. Palette 167 is kept stock because it is also passed as immediate components (`0x8771c`).
- Text colours are read at runtime from struct `0x1335a4` (+4 fg, +8 shadow, +c outline, low byte 0xff = off; text draw `0x67fc0`).

## 3D LUT → camera (`mods/lut/src/fit_lut.py`)

- `fit_lut.py BASE_FW COLOR.cube OUT_FW [--bw BW.cube] [--photo IN.JPG PREVIEW.png]`
- **Capture pipeline of saved photos (confirmed by `mtest2`):** camera RGB → CCM_illum → tone curves → YCbCr matrix + offsets → JPEG.
  - **CCM_illum:** `0x16cac8 / 0x16caf8 / 0x16cb28`, 3×4 int32 Q16, one per illuminant. The fit multiplies all three by the same R, so the look is the same whichever is active. Stock values are multiples of 64.
  - **Curves:** A `0x16bac8` (green) and B `0x16c0c8` (red + blue), for every mode. `0x16bec8` and `0x16c4c8` (512 B each) are passed by the same init `0xf26f8`. The decompiler workspace (`decompiler-project/`) shows they are 256 × u16 tables, identical, and an **inverse of stock curve B** (8-bit → 10-bit, mean error 1.5). A third curve C `0x16c6c8` (struct +0x10) is used by the software photo converters. Loader `0x11de40` uploads companion A + curve B + curve C. Our curve rewrites left these inverse tables stale, which caused the lavender whites (confirmed by `curve_inverse`, photo 0291). Matrix packing `0x11e0b8` keeps 12 magnitude bits of Q16>>6, so |coef| < 4.0.
  - **YCbCr matrices:**
    - `0x16cb58`: normal, used by COLOR *and* VIVID. VIVID adds its own saturation somewhere else.
    - `0x16cb88`: B&W.
    - `0x16cbb8`: sepia.
    - Offsets are in ¼ units. Stock is Y 2 and Cb/Cr 514; negative Y offsets are avoided (signedness unknown).
  - The level CCMs `0x16b798…` do *not* affect saved photos (`mtest`): probably the live preview. VIVID v4's 0x16b7f8 edit therefore only changed the preview.
- **Model fitted:**
  - `v = curves_stock⁻¹(stock photo)`.
  - Colour: `out = P · curves(R · v) + o`, written as `Ymat = Ystd · P`.
  - B&W: `grey(w · curves(R · v) + oy)` in the B&W matrix, sharing R and the curves.
  - The fit takes the best of three starts: identity; least squares; colour alone, then B&W added.
- **Limits:** one colour film and one B&W film per firmware. VIVID = the colour film plus the camera's own extra saturation.
- **Old model** (CCM-only, level CCMs, before 2026-11-07): wrong, see `lut`, `vista_e100vs` and `neopan1600`. The `batch_films.py` ranking was made with it and should be rerun.

### Scene modes (SCN)

- **Capture mode** byte `0x1328ff` (settings struct `0x1328fc` + 3, getter `0x3bd7c`, 0..23). Auto = 0. `+5` (`0x132901`) = last SCN menu position.
- **SetScene** `0x3c5ec(menu index)`: stores +5, then jump table `0x3c604` → mode, applied by `0x3c128`. Menu index → mode (help-string order **starting at "High ISO"**): High ISO 21, Portrait 5, Sport 4, Landscape 3, Night Portrait 6, Night Landscape 15, Snow 10, Beach 11, Text 13, Fireworks 16, Flower 12, Museum 17, Self Portrait 7, Children 9, Backlight 14, last item (user calls it Sunset) 22. Museum = 17 measured by the diag call log; flash defaults agree (Backlight 14 = forced fill; Night Portrait 6 / Self Portrait 7 = red-eye). Earlier dumps: `cd703_card_scn/`, dumps 17–24.
- **Flash per mode:** on a mode switch `0x3c66a` jumps through `0x3c682` (indexed by mode) to that mode's slot reset; modes without a slot force a value. One slot per group of modes, 11 in total.
- **Colour matrices:** the 0x401 message (task start-up, `0x4a514` → `0x48d68`) loads them via `0x1206f4` → `0x11e3a0` → `0x11e124`, and the photo conversion `0x9fec0` fetches the CCM again per photo, through `0xaf508 GetCCM(illuminant 0..2)` (= `[0x197868 + 4n]`) and `0xaf514 GetYmat(colour mode)` (3 → B&W `+0x3c`, 4 → sepia `+0x40`, else `+0x38` of struct `0x197844`). So per-mode looks only need these two getters hooked.
- Pipeline struct `0x197844` (0x48 B): +0 curve A, +4 X table, +8 curve B, +0xc X table, +0x10 curve C, +0x24/+0x28/+0x2c CCMs, +0x38/+0x3c/+0x40 Ymats.

## What we learned the hard way

1. **Sepia and B&W are hardware effects.** SetColorMode `0x629f4` writes `(effect << 2)` to ISP register `0xff10118` (effect 0 = normal, 1 = B&W, 2 = sepia). Editing the "Sepia" colour matrices changed nothing (v1).
2. **There is a second sepia source.** Even with the hardware effect off and every sepia matrix neutralised, photos come out sepia (exactly Cb −16, Cr +20) whenever the colour value seen by the capture code is **4**. VIVID must therefore not report 4 internally (v3, v5).
3. **The colour mode resets to Color at every power-on.** This is stock behaviour, not a bug of ours.
4. **The live preview and saved photos use different paths.** The preview can look right while the saved JPEG doesn't. Always check the files.
5. **Tone curves for saved photos:**
   - Curve **A** `0x16bac8` = green, curve **B** `0x16c0c8` = red + blue (1024 bytes each, 10-bit → 8-bit).
   - Proven by distorting them (tests 1 and 2).
   - They are loaded once at boot, so swapping them at runtime does nothing (`vivid_contrast`).
6. **A per-shot tone LUT (`0x14a26c`, a straight line)** is loaded into `0xff11000+` before every capture by `0x63070(0)` → `0xa56f4`. Swapping it at runtime had **no visible effect**; the stage is probably bypassed.
7. **Measure with identical framing.** Our quantile comparisons only work when nothing in the frame moves; different framing gave misleading numbers once.

## Ideas not yet done

- Contrast for all modes: apply an S-curve to curves A/B. This is guaranteed to work.
- VIVID-only black-point lift through the level-2 CCM offsets. Converter `0x627ac` uses sign-magnitude Q8 with sign bit `0x400`; the offset units are unknown.
- A RAW (YRGB `.RAW`, 3056×2292×1.5 bytes) converter for the PC.
- A larger or taller boot image: needs the draw position for ID 93, found in the code, before changing w/h.

## Sensor RAW (CCDI) and the DNG converter

- **Enable:** `mods/raw_plus_jpeg` sets the hidden save flag SaveCFAonTake (`0x13358c`) at boot. Each shot then also writes `CCDInnnn.RAW`, plus a `BLACnnnn.RAW` black frame when the camera takes one. JPEG is unaffected.
- **Format (photos 0293–0296):**
  - Headerless, 3072 × 2310, 8 bit/pixel, Bayer RGGB.
  - Black already removed (min 0); taken before any colour processing.
  - The JPG is the RAW cropped at x 8, y 10 to 3056 × 2292.
- **Not linear:** decode with the **stock** companion table `0x16bec8` (8 → 10 bit).
  - Evidence: it fits the JPG-inverted values best (dog shot: gain 0.996, offset 0.006), ahead of linear, gamma 2.2 and gamma 1.5.
  - The build's companion is ruled out: the film curve B never outputs code 1, but the RAW histogram is smooth and has many 1s.
  - So the RAW encoding is fixed in hardware and does not depend on the installed firmware's curves.
- **White balance:** each JPG's own WB, fitted by inverting the firmware pipeline (`ccdi2dng.py --fw`).
  - Fitted neutrals (R, B) relative to G = 1: 0293 0.48/0.64, 0294 0.38/0.78, 0296 0.40/0.77.
  - Daylight shots fit the stock CCM `0x16cb28` best.
  - The maker note (12.7 KB) holds AE statistics; no WB gains were found in it.
- **`tools/ccdi2dng.py FILE_OR_FOLDER [-o DIR] [--wb R,G,B|grey] [--fw FW]`:**
  - Writes `100_nnnn.DNG` (DNG 1.4): uncompressed 16-bit CFA, values 0..1023, BlackLevel 0, WhiteLevel 1023, crop to the JPG frame.
  - Colour: ForwardMatrix1 = sRGB→XYZ(D50) · stock CCM; ColorMatrix1 for D65; AsShotNeutral = the camera's WB.
  - Copies exposure, ISO and date from the JPG, and subtracts the black frame when present.
  - Verified with LibRaw (`dcraw_emu`): renders match the JPGs' white balance. B&W-mode shots get the typical daylight WB.
  - Target editor: Lightcraft (reads Bayer DNG with its own decoder).

### Velvia 100 + Kodachrome 64 candidate 0.7 ready (2026-11-08)

- User asks for classic Velvia/Chrome, clarifies **Kodachrome 64 + Velvia 100**. Film-first selector now has seven choices: By mode, Stock, Vista 200, E100VS, Neopan 1600, Velvia 100, Kodachrome 64. Version **CD703 mod 0.7**. Current card OLD independently verifies installed 0.6 `73801de4…`; no new captures or separately reported 0.6 UI trial. Backup `cd703_card_film_first_test_20261108T034353Z/`: one changed OLD, hash-verified; prior captures remain in the backup chain.
- New candidate **`mods/classic_films/test-v0.7/KC713.FW`**, SHA **`57a25b3f46bff1b6bf19f23853034abe665909f379831501dff13b48ff572c4e`**. Uses `colorslide/fuji_velvia_100_generic.cube` and `colorslide/kodak_kodachrome_64.cube` from the existing Film-Luts collection. `fit_classics.py` fits CCM-only with stock curves and normal YCbCr, preserving gray neutrality. Mean sample ΔE versus those LUTs improves 11.56→6.63 (Velvia), 21.90→9.07 (Kodachrome). This is a matrix approximation, not full LUT or physical-film accuracy; no tone-curve changes. Original three film records remain byte-identical.
- Space solution: reclaim original Share create/init callbacks `0xebc90–0xebecb` (572 bytes). Static audit initially found legacy helper calls; explicitly disconnect old event pointers `0x1683a0/0x1683a8` (to stock default callback) and calls `0xebed0/0xebefc/0xebf00` (NOP). No other external references or remaining base pointers into the range. The active Share root already points to the mod menu; original callbacks must never be restored with this allocation.
- Allocation: Velvia record192 at `0xebc90`, Kodachrome192 at `0xebd50`, all five Q12 preview transforms90 at `0xebe10`, 20 matrix pointers80 at `0xebe6c`. Existing records stay at `0x1257a0/0x125860/0x125920`; common getter address resolver `0x1256a8` now loads matrix pointers, retaining the original ABI. Old private coefficient area becomes seven-label pointer table at `0x168324`, new names at `0x168340`. Menu limits 7; preview supports film IDs1–5 and reads relocated R data. Existing Review/no-double-transform guards unchanged.
- **129 menu/preview/capture scenarios pass**, including 84 preview cases and **1,092 getter cases**, plus **15 date +50 full DNG regressions**. All seven choices/labels/wrap, row mapping, old/new getter pointers, preview upload args/guards, disconnections, stack/registers and DNG gating checked. UI/ISP/file/RTC mocked; stock multiply and known SLEIGH restore issue modeled. Floating-point comparison covers all five films×three levels within one Q8 unit; magnitudes <4. Checksums and strict change allowlist pass (688 changed bytes). Independent fresh fit and final rebuild are byte-identical. Reports `mods/classic_films/test-v0.7/verification.json` and related JSON; source and audit under `mods/classic_films/`.
- Candidate staged at SD SYSTEM/KC713.FW, read-back SHA verified; all 23 existing files unchanged; safely unmounted. **Not flashed or camera-tested yet.** Test ordinary COLOR with steady scene/light: Stock, Velvia, Kodachrome, Neopan; check live/new-shot immediate/later Review, RAW color/metadata, wrap, DNG OFF. Procedure `mods/classic_films/README.md`. Recover with installed 0.6, or user-confirmed preview0.5. No new dump.

### Preview confirmed; Film-first menu 0.6 ready (2026-11-08)

- User reports 0.5 “works” and requests Film as the first menu option. Card KC713.OLD independently matches **`9e1e406461966d3beab7fd3c2381bf2310bc8cfeb8849756f175696afe1ff5d0`**. Preview trial is confirmed by user report; individual steps were not separately reported. Seven new/changed files (0330–0332 JPEG/DNG pairs and OLD) backed up/hash-verified to **`cd703_card_film_preview_test_20261108T032816Z/`**. No removed files or new dump; these new captures were not independently rendered/analyzed during this menu-only change. Report `mods/film_preview/test-v0.5/camera-user-report.json`.
- New menu order: **Film / DNG saving / Hidden menu / FW: CD703 mod 0.6**. Opening selects Film. Swap the first two text pointers, event handlers (Film=0x5000, DNG=0x5001), and refresh store offsets (Film +4, DNG +28). Hidden/version events remain unchanged. This is a reorder of existing behavior; session defaults/preview/DNG/date paths are byte-identical.
- Builder `mods/mod_settings/src/build_film_first.py` pins confirmed 0.5, checks original bytes, refuses existing outputs, verifies exact change allowlist and container checksums. Candidate **`mods/mod_settings/test-v0.6/KC713.FW`**, **`73801de48242acecfccd31d917c73a025f83d27ff16d97a755b782969a28fecd`**. Only **16 bytes** differ, including version and checksums. Separate rebuild byte-identical.
- Reused instruction suite, adapted to reordered labels/actions (`TestFilmFirst.java`): **93 menu/preview/capture scenarios including 780 matrix-getter cases pass**. UI/ISP mocked; stock multiply and known SLEIGH restore issue modeled as previously. Date/full DNG suites were not rerun because all other bytes are unchanged. Evidence and quick procedure under `mods/mod_settings/test-v0.6/`.
- New 0.6 staged at SD SYSTEM/KC713.FW, read-back SHA verified; all 23 pre-existing files unchanged; safely unmounted. **Reordered menu camera check pending.** Current confirmed recovery is preview 0.5. No new code allocation.

### Film selector works in files; preview-path candidate 0.5 (2026-11-08)

- User confirms 0.4 menu/film behavior, but effects are missing from viewfinder, immediate after-shot preview and later Review. Independently verified 0.4 hash `9e780daf…` from KC713.OLD. New backup `cd703_card_mod_settings_test_20261108T031018Z/`: ten new/changed files, five JPEGs 0325–0329, four DNGs 0326–0329 and OLD; all copied and hash-verified. Older captures were already absent before this turn and remain in earlier backups. No new memory dump.
- **0329 proves the embedded-preview mismatch:** full 3056×2292 JPEG has mean RGB channel spread 0, while its 160×120 and 640×480 embedded JPEGs have spread 22.44/22.65. Embedded JPEG offsets 13860/17477. Four actual DNGs render identically to linear references and match JPEG date/exposure/f-number/ISO. Color-film identities for other shot numbers were not separately supplied. Evidence `mods/mod_settings/test-v0.4/camera-verification.json`, `camera-render-verification.json`, `mods/film_preview/research/embedded-preview-analysis.json`.
- Preview path: `InitializeCaptureTables` initializes independent preview CCM pointers at `0x17d0e4`; preview setter `0x62a9c`, live setup `0x62afc`, and scaled/WB paths `0x62d54`/`0x62ea8`/`0x63004` all pack through `0x62a28`. Converter `0x627ac` packs signed-magnitude Q8, sign bit 0x400. The call in `0x62fc0` already uses the capture getter and returns to **0x62ff8**, so it must bypass any additional film transform.
- New **0.5 candidate** `mods/film_preview/test-v0.5/KC713.FW`, **`9e1e406461966d3beab7fd3c2381bf2310bc8cfeb8849756f175696afe1ff5d0`**, based on pinned 0.4. Wraps `0x62a28` and composes the film's relative RGB transform with the incoming preview CCM on a 48-byte stack buffer. Three signed-Q12 transforms (54 bytes) at unused Share-private `0x168324`, derived as film CCM × inverse(stock capture CCM), preserving independent preview calibration. Uses stock multiply helper 0x11b114 and original coefficient packing. Existing capture film records/getters, DNG writer/header/metadata and date fixes unchanged.
- Guard transforms **only camera state 1**, bypasses Review/other states and the already-filmed `0x62fc0` call. Menu film change now refreshes the current preview color level through stock `0x62a9c` before repaint; native BW/sepia levels skip this immediate upload. Intended to fix live view and newly generated embedded previews. Old file previews are not rewritten; physical timing and thumbnail path coverage await camera trial. Preview is a CCM approximation, not an exact JPEG simulation.
- Code allocations: 142 bytes at `0x125c24` after the DNG writer, 88 bytes at `0x12fe98` before boot hook. Both ranges are zero in pinned base and all 29 historical unique frames; no stock references. Refresh/trampoline uses 60 bytes of the old Share root handler's 64-byte body `0xebc50–0xebc8f`; the only stock external reference was the now-replaced root handler pointer, and current pinned image has no remaining data pointers into any halfword of this range. Original Share handler must not be restored alongside this build. Static/pointer audits pass.
- **93 menu/preview/capture scenarios pass**, including 56 preview cases and 780 grouped getter cases, plus **15 date and 50 DNG regressions**. Actual preview composition/stock coefficient packing executed; integer multiply modeled, ISP/UI/file/RTC services mocked; stock restore boundary modeled for known SLEIGH alias. Tests cover source/destination guards, saved registers/stack, live upload arguments, no double application and Review bypass. Floating-point reference error stays below one Q8 coefficient unit; Neopan rows are identical. Checksums/change allowlist (348 bytes) and byte-identical rebuild pass.
- Candidate staged at SD `SYSTEM/KC713.FW`, SHA read-back verified and all 17 existing files unchanged, then safely unmounted. **Not flashed or camera-tested yet.** Trial: ordinary COLOR → Neopan → live view → new shot → immediate and later Review → Stock/color shot → compare playback of both. See `mods/film_preview/README.md`. If it fails, a fresh Neopan-selected dump can help. 0.4 remains confirmed saved-file recovery. Preserve draft artifacts but use only `test-v0.5` / `rebuild-v0.5-final`; their earlier development counterparts lack the final guards.

### Mod Settings 0.4: firmware label and film selector ready (2026-11-08)

- User requests a firmware label and film selector, confirms existing looks and session-only scope. New native rows: DNG saving, Film, Hidden menu, **FW: CD703 mod 0.4**. OK cycles By mode → Stock → Agfa Vista 200 → Kodak E100VS → Fuji Neopan 1600 → By mode. Version row is inert; existing close/navigation/hidden-menu behavior preserved. Boot defaults: By mode and DNG ON. The fixed date fallback remains 2026-11-07 noon as requested originally.
- Candidate `mods/mod_settings/test-v0.4/KC713.FW`, **`9e780daf4f0597788f802088ccaf5734554c2b0b8f65bf61de668b979b6d0f72`**, pinned to confirmed date build `b37ad3c6…`. Reuses existing film matrices by updating the 24-byte map at `0x125780` in RAM. Stock clears overrides; named looks fill film IDs 1/2/3; By mode restores entries 9=2, 17=3, 22=1. Existing CCM/Ymat getters and film records are unchanged. Native exposure/color modes still apply; first physical comparison should use ordinary COLOR. DNG data is unaffected. This is the existing matrix approximation, not a new full 3D LUT pipeline.
- Main callback 184 bytes at `0x1256c0`; film action 88 bytes at `0x1247a0` (outside the 1536-byte DNG header); hidden-menu/no-op 16 bytes at `0x1259e0` after all film records. Both extensions are in audited zero allocations, have no stock static references, and are zero across all 29 unique historical frames checked. Four-row data uses Share-private `0x168190–0x16836f`, ownership checked against all registered roots. Session film byte `0x1682d0`. Sparse assembler object is patched only in the three explicit ranges, preserving intervening code/data.
- **37 menu/capture scenarios pass, including 780 actual CCM/Ymat getter cases**, plus **15 date scenarios and 50 full DNG writer regressions**. UI/file/RTC services mocked; stock restore boundary modeled for the known SLEIGH alias issue. Separate rebuild is byte-identical; checksums/change allowlist pass (513 changed bytes). Reports under `mods/mod_settings/test-v0.4/`; sources under `mods/mod_settings/src/`. Physical menu layout and JPEG rendering await camera trial; procedure `mods/mod_settings/README.md`.
- Card staging: backed up three new/changed files to **`cd703_card_date_default_test_20261108T030015Z/`**, all SHA-256 verified. Date firmware OLD hash now independently confirms `b37ad3c6…`; new shot 0320 JPEG/DNG agree on 2026-11-07 12:00:20, 72127 μs, f/4.3, ISO160, with pixel-identical LightCraft/linear-reference renders. No new dump. Date evidence `mods/date_default/test-20261107/camera-verification.json`.
- New 0.4 image staged at SD `SYSTEM/KC713.FW`, SHA read-back verified; all 88 pre-existing card files unchanged. First final inventory recheck was interrupted by an early unmount; remounted and repeated the complete firmware/inventory check successfully, then safely unmounted. Receipt `mods/mod_settings/test-v0.4/card-staging.json`. New firmware has **not** been flashed or camera-confirmed yet; keep date `b37ad3c6…` as recovery.

### Fixed fallback date: user confirms camera behavior

- User replied “works” to the date-default flash/reset trial. Current user-confirmed build is `mods/date_default/test-20261107/KC713.FW` (`b37ad3c6…`). Record `camera-user-report.json` distinguishes this report from independent firmware/capture readback, which has not been performed for this build. Detailed individual test steps were not separately reported.
- Keep the pinned builder manifest and earlier staging/verification records as historical build evidence. The implementation-stage pending status below is superseded by this user report. Preserve Share-menu `f992a106…` as the latest independently read-back fallback.

### Fixed fallback date candidate (2026-11-07)

- User reports opening the battery flap to remove the SD card loses the clock. Requested today's default: **2026-11-07**, Argentina local date; keep noon. This is a fixed fallback, not RTC persistence or automatic host-date synchronization.
- New builder `mods/date_default/src/build_date_default.py` starts from confirmed Share-menu `f992a106…`. Candidate `mods/date_default/test-20261107/KC713.FW`: **`b37ad3c6a0d86ce8c1e8a9b34a38f93236f82bab2477b6252b824098ce294c34`**. Exactly 81 bytes differ, confined to five patch ranges and container checksums; independent rebuild is byte-identical.
- Default `struct tm` templates: lost-RTC `0x16a708`, startup reset `0x1284ac`, setup reset `0x128540`; complete fields `[0,0,12,7,10,126,6,310,0]`. Startup initializer `0xdc45a` now copies six fields, replacing its hardcoded January 2007. Normal setup initializer `0xeae58` also uses the fallback for invalid years and fixes its previously missed 2025 upper cap to 2037. Valid retained dates survive normal setup.
- RTC epoch at `0x408a8`, 2006 invalid-clock sentinels, hardware clock functions and all previous Share/DNG/film code remain byte-identical. Both replacement code blocks fit in-place, no cave. ARC `BL` assembly preserves the startup snippet's 2-mod-4 origin using a two-byte object prefix, excluded from the patch; disassembly confirms both calls target `0x54010`.
- **15 instruction scenarios pass**, using actual patched screen and stock recovery/reset code; memcpy, RTC hardware and widget-property services mocked. Tests include valid 2007/2025/2026/2037, invalid 1900/2006/2038, RTC read failure, adjacent globals, stack and saved registers. Reset actions stop at RTC setter; rendering/hardware are not emulated. Reports `mods/date_default/test-20261107/{verification,date-emulation,manifest}.json`.
- Camera validation pending. Staging/unmount receipt: `mods/date_default/test-20261107/card-staging.json`; trial procedure `mods/date_default/README.md`. Preserve confirmed Share-menu `f992a106…` as fallback and do not mark this candidate camera-confirmed until SD firmware readback and reset-date trial.

### Share menu and DNG-off capture confirmed (2026-11-07)

- Actual flashed `SYSTEM/KC713.OLD` SHA-256 = **`f992a106e1f6a96807e528658a7909f4ecb9cf451df1d8ec3a2e6f3fda9edba5`**. User reports the menu works as intended, then specifically requests an independent check of the second shot with RAW disabled. **Check passes.** Use `mods/share_menu/test-v1/KC713.FW` as the current confirmed firmware, retaining pre-menu metadata v3 `9760823a…` as fallback.
- New backup **`cd703_card_share_menu_test_20261108T023024Z/`**: four new/changed files — `100_0318.JPG`, `100_0319.JPG`, `CCDI0318.DNG`, `SYSTEM/KC713.OLD` — all copied and SHA-256 verified. Full card inventory checked; no previous files disappeared. Pending SYSTEM firmware consumed by updater. SD safely unmounted after verification; no new firmware staged. No new MEMDUMP; old card dump remains from v1.
- **First shot 0318 has JPEG + DNG. Second shot 0319 has JPEG only**, with no same-number sensor DNG, CFA RAW or processed RAW file in the full card inventory. Both JPEGs decode. Thus the DNG OFF option correctly gates off RAW saving while retaining JPEG capture.
- Enabled DNG 0318 is exactly 7,097,856 bytes, valid/populated header; date 2026-11-07 12:01:24, exposure 38713 μs, f/2.7, ISO 400 match its JPEG exactly. Pillow parses independent TIFF/EXIF; LightCraft recognizes 3056×2292 RAW and renders identically to an independent linear reference at 1536 pixels. Source backup unchanged.
- Evidence `mods/share_menu/test-v1/camera-verification.json`, `capture-toggle-verification.json`, `camera-readback.json`, `camera-render-verification.json`, `camera-backup.json`, `camera-comparison.jpg`. The two-shot sample does not independently exercise another enabled capture after OFF→ON or a restart; those remain additional file-based checks. Existing code/emulator checks establish the intended default/session behavior. No new hardware behavior beyond this evidence is claimed. This result supersedes the pending reports below.

### Share menu user report; DNG-off shot check pending (2026-11-07)

- User reports **“works as intended”** for the Share mod menu (`f992a106…`). They then ask to verify the **second test shot** has RAW/DNG disabled, explaining they did not inspect that file behavior. Accept the menu UI report; **do not infer verified JPEG-only capture behavior from it**.
- `mods/share_menu/test-v1/camera-verification.json` records this partial confirmation. No new card backup, post-flash KC713.OLD hash or memory dump has been read yet; card is currently disconnected. Next: back up new files, verify flashed hash, compare the new shot sequence, and require a JPEG with no same-number DNG/RAW for the second shot. Preserve the confirmed `9760823a…` fallback.

### Share button mod-menu prototype (2026-11-07)

- User requested repurposing Share for mod settings and a hidden-menu shortcut; chose **DNG saving ON/OFF + hidden menu** as the first scope. Film selection is not included. Prototype **`mods/share_menu/test-v1/KC713.FW`**, SHA-256 **`f992a106e1f6a96807e528658a7909f4ecb9cf451df1d8ec3a2e6f3fda9edba5`**, starts from pinned confirmed DNG metadata v3 `9760823a…`. **Staged for test, not yet flashed or camera-tested.** Confirmed binary/backups preserved.
- Actual physical Share press **`0x680`**, release `0x681` (key ID 13); this is proven by capture binding `0x1508f0` → `0xcbc74` → UI open `0x7c260(0xa8,0)`. The script engine's key names remain misaligned; `0x880` handlers are information-overlay changes. Common Share handler `0xb9760` also opens screen `0xa8`.
- Root Share descriptor `0x168370` is replaced by a 2-widget native title/list cloned from hidden debug page styles. Title **MOD SETTINGS**; rows **DNG saving: ON/OFF** and **Hidden menu**. Menu events use stock `0x416f4` dispatch, normal UP/DOWN/OK focus/navigation. The old Print/Email/Favorite tagging screen is replaced. DNG toggle flips the existing `0x13358c` CFA-save flag: OFF gates out the raw writer and leaves JPEG saving enabled. It is session-only; boot default remains ON.
- Native callbacks: **170 bytes at `0x1256c0–0x125769`**, after scene hook return `0x1256be`, before film table `0x125780`. Zero in pinned current firmware and latest confirmed dump, no exported static references. 26/29 unique historical frames are zero; nonzero frames contain the old diagnostic scene-hook overlay, absent from current non-diagnostic base. Do not combine that older DIAG overlay with this allocation. `test-v1/placement-audit.json` records sources.
- Menu title/list/items/strings/table reuse Share-only widgets `0x168190–0x16827f`; list widget `0x168154` becomes a 2-row hidden-menu style list. Ownership scanned across the registered screen table: no other root owns reused widgets. The existing screen table entry/ID `0xa8`, language section and graphics stay intact.
- Hidden shortcut opens **original root `0x3b`** through `0x7c260(0x3b,0)`. Its updater and original access routes are unchanged. Share/Menu/Delete on the mod screen call stock close handler `0xb97c4`. Six bytes at `0xcbd00` skip the capture Share path's old `state=2` switch, retaining capture state 1; review remains state 2. Existing capture busy checks/preparation are untouched.
- **19 menu/capture instruction scenarios pass**: initial labels/selection, toggle and reopen behavior, refresh, missing-list refresh, hidden target, capture/review close paths, release/default delegation, actual stock CFA capture gate ON/OFF and patched capture entry state. Stock event dispatch/close/capture-gate instructions run; UI services and mode-dial query mocked. The known SLEIGH shared-restore alias issue is modeled at that compiler-helper boundary only. No actual LCD drawing/focus or real transition is claimed.
- **50 DNG writer/metadata regressions pass**, firmware checksums valid and second build byte-identical. Confirmed DNG code/header/metadata helper, scene code/tables, boot hook and initial CFA byte remain byte-identical. Sources `mods/share_menu/src/`; implementation `mods/share_menu/README.md`; candidate reports under `test-v1/`. Transient UI callback decompilations in `research/callbacks/` were made from the stock Ghidra project read-only, with changes discarded.
- SD files re-hashed against verified `cd703_card_dng_metadata_v3_test_20261108T020104Z/card-inventory.json` before staging; confirmed KC713.OLD preserved. New SYSTEM/KC713.FW flushed, read-back verified and SD safely unmounted. Camera test: Share screen, ON photo → OFF photo → ON photo, hidden menu, capture/review exit, restart default ON. Retain test JPEGs/DNGs. Optional dump reader `src/inspect_share_menu.py` checks code patches, live flags and current screen ID. Existing old dump correctly fails the new patch checks. **Native menu hardware behavior still needs validation.**

### DNG metadata v3 camera-confirmed (2026-11-07)

- User completed the trial and reports no saving error. SD `SYSTEM/KC713.OLD` matches **`9760823a368db1c6012337dda892470c0612fe31e64e2cc59e94d00eef00e297`**; the pending SYSTEM firmware file is absent. Use **`mods/native_dng/metadata-v3/KC713.FW` as the current confirmed firmware**. Preserve older confirmed v1 `8dce21de…` and pre-DNG `4765fbbb…` fallback images.
- Backup **`cd703_card_dng_metadata_v3_test_20261108T020104Z/`**: 10 new/changed files, four JPEGs 0314–0317, five DNGs 0313–0317 and updated KC713.OLD. Copied and SHA-256 verified; old backups and card files preserved. MEMDUMP unchanged from v1, so no v3 dump evidence is claimed.
- **All five actual DNGs pass** header/layout/7,097,856-byte size and have populated date/exposure/f-number/ISO. LightCraft CLI 0.19.0 recognizes 3056×2292 RAW; 1536-pixel CPU exports match independent 16-bit linear-reference DNGs exactly (maximum channel error 0). The contact sheet was visually inspected. Fixed daylight WB is retained.
- **All four retained JPEG/DNG pairs match exactly**, independently parsed with Pillow: 0314 (2026-11-07 12:00:13, 85215 μs, f/2.7, ISO 160); 0315 (12:00:29, 125000 μs, f/4.3, ISO 200); 0316 (12:00:36, 60990 μs, f/4.3, ISO 400); 0317 (12:00:49, 41734 μs, f/2.7, ISO 400). Editor date/ISO/aperture also agree. The one-shot delay is resolved in these real captures.
- **0313 is intentionally unpaired:** user corrected their initial reply and confirmed deleting its JPEG because the clock was still at 2007. DNG metadata is populated (2007-01-01 12:00:24, 125000 μs, f/2.7, ISO 200), and it decodes correctly. No same-shot JPEG comparison is claimed for that file. Verifier `--allow-unpaired` explicitly records this limit; default still requires matching JPEGs.
- Evidence under `mods/native_dng/metadata-v3/`: `camera-verification.json`, `camera-readback.json`, `camera-render-verification.json`, `camera-backup.json`, `camera-comparison.jpg`. Reproduce editor check with `python3 mods/native_dng/src/verify_camera.py cd703_card_dng_metadata_v3_test_20261108T020104Z --build mods/native_dng/metadata-v3 --allow-unpaired`. Camera test supersedes the staged/awaiting status in the implementation history below.
- Requested DNG metadata work is complete. SD card safely unmounted after readback; no further firmware staged. Remaining optional coverage: long-exposure black frames, card-full/interrupted writes, more modes and native GUI/GPU/other editors.

### DNG metadata camera trial and timing fix (2026-11-07)

- V2 `3f4df4fb…` was actually flashed (SD `SYSTEM/KC713.OLD` matches). New backup **`cd703_card_dng_metadata_test_20261108T014417Z/`** has 18 new/changed files: 0307–0312 JPEG/DNG pairs, five SLI files and updated firmware OLD. All copied and hash-verified; old backups/card captures preserved. MEMDUMP unchanged from v1, so no v2 dump result is claimed.
- All six DNGs have correct layout/size and decode as 3056×2292 RAW. LightCraft 1536-pixel exports equal independent linear-reference renders. **Metadata timing fails:** 0307 blank; 0308–0312 exactly match the preceding JPEG's date, exposure, aperture and ISO. JPEGs still show 2007-01-01. `metadata-v2/camera-verification.json` and `camera-render-verification.json` record failure; do not treat v2 as a working metadata build.
- Root cause: stock RAW save precedes JPEG EXIF serialization. V2's mocked callback tests missed capture ordering. The verifier now records all paired-file mismatches while retaining image/render results, exits nonzero on metadata failure, and independently parses TIFF/EXIF with Pillow. Emulated outputs are explicitly labeled with `--evidence-kind emulated`.
- **V3 `9760823a368db1c6012337dda892470c0612fe31e64e2cc59e94d00eef00e297`** starts from confirmed v1. A call at `0x125a34` in the writer populates the header before any file operation. Helper `0x12ff40`, 180 bytes; writer 548 bytes. Stock JPEG callback `0xa4290` restored by using v1 as base. Same header layout, fixed WB, payload, crop and output size.
- Source record is `[0x1324fc]`, explicitly set by `0x34430` and consumed by its synchronous state-6 capture worker `0x33c2c`, which calls the RAW writer with that record's ID/buffer. Fields: tm `+0x64`, exposure us `+0xb0` clamped to 714 minimum, ISO u16 `+0xb4`, aperture flag/index `+0xf2/+0xf4`. Stock `0x54528` supplies the same JPEG fields. Table ×100: zero flag `[270,300,340,380,430,480]`, nonzero `[480,540,600,670,760,850]`, out-of-range 480. Preserve capture record, photo ID, stack/callee-saved registers. The known double-size/black-frame paths still fall back to stock before the helper.
- **50 full-writer scenarios pass:** 18 prior writer/error/fallback cases, six current JPEG fixtures, 24 aperture combinations, leap-day/minimum exposure and 2037. Each starts with deliberately stale values and must populate current metadata before path/open/write; fallback never calls the helper. Actual stock aperture switch instructions are independently executed. This caught a draft transcription of 5.4 as 5.5; corrected before staging, draft archived under `validation/metadata-v3-aperture-draft`.
- Six emulator-written DNGs equal independent same-shot headers + unchanged actual sensor payloads. Pillow and LightCraft verify metadata against JPEGs; all editor renders match linear references exactly. **These are emulated proofs, not v3 hardware results.** Checksums, source hashes, placement margins and deterministic rebuild pass. Reports under `mods/native_dng/metadata-v3/`; sources `src/capture_metadata.s`, `hook_capture_metadata.s`, `build_capture_metadata.py`.
- V3 copied to SD `SYSTEM/KC713.FW`, flushed/read-back verified and safely unmounted. Existing card inventory/OLD unchanged. **Awaiting camera test:** first shot immediately after boot, zoom/ISO changes, restart and first shot again. Set the real clock; dump optional. Keep confirmed v1 `8dce21de…` fallback and pre-DNG `4765fbbb…`. [Procedure](mods/native_dng/metadata-v3/TEST.md).

### Direct DNG metadata v2 ready (before camera trial, 2026-11-07)

- User requested next step 2: add date/time, ISO, shutter speed and aperture now. Fixed daylight WB remains accepted; no per-shot WB work added.
- **`mods/native_dng/metadata-v2/KC713.FW`**, SHA-256 **`3f4df4fb9f9421fd12279bc13b817bfc91b503a1b3e2ee4bf8edde34b64f9e98`**. Built only from the pinned camera-confirmed `8dce21de…` image; stock, pre-DNG and v1 firmware files preserved. New builder `src/build_metadata_dng.py`; second build byte-identical. **Staged on SD `SYSTEM/KC713.FW`, flushed/read-back verified and safely unmounted; no camera trial yet.**
- Traced the real capture JPEG path: `0x33360` → `0x54800` → metadata preparation `0x54528` → header builder `0xa41c8` → capture EXIF serializer `0xa3a04`. The temporary EXIF input has capture `struct tm` at `+0x0c`, exposure microseconds `+0x48`, f-number×100 `+0x4c`, ISO `+0x60`. These are the same source fields written to JPEG tags 0x9003, 0x829a, 0x829d and 0x8827. Copy after the stock routine so its exposure minimum clamp (714 μs) is preserved.
- Four bytes at **`0xa4290`** (`mov_s r1,r14; bl_s 0xa3a04`) become a 32-bit call to the **156-byte** wrapper at **`0x12ff40`**. It forwards the original arguments, runs the stock serializer, copies exposure/aperture/ISO, and formats capture time with the stock `strftime` at `0x116be4`, format `0x127a08`. Stack/callee-saved registers and original serializer result are preserved. Clear prior values before each call so failure cannot reuse a previous shot's EXIF.
- Header remains **1536 bytes** at `0x1241a0`, now with TIFF DateTime and a proper EXIF sub-IFD (date original/digitized share the same string). Exposure denominator = 1,000,000; aperture = 100; ISO SHORT. Four mutable value ranges occupy 30 bytes; used header length 1364. All WB/calibration/CFA values and file size remain unchanged. Existing v1 writer/entry and fullscreen hook are byte-identical.
- Tail placement: current base and latest confirmed camera dump are zero in `0x12ff40–0x12ffff`; no exported static references enter. Among 109 historical frames, 106 are zero; three contain the same older drawprobe overlay, absent from current firmware. Recorded in `metadata-v2/placement-audit.json`.
- Verification: Pillow independently follows the EXIF sub-IFD and checks all requested tags against four JPEG fixtures. LightCraft displays their capture times, ISO, aperture and shutter; the rendered pixels equal v1. **18 original writer scenarios + 8 consecutive metadata scenarios** pass in the instruction emulator, external stock EXIF builder/strftime mocked. Includes actual JPEG fixtures, ISO/aperture changes, leap day, 2037, clamp and failure clearing. Emulated DNGs equal the host/editor-tested proof files byte-for-byte. Initial unflashed draft caught a clobbered incoming r0 during clearing; fixed before staging and archived under validation.
- `inspect_capture.py --build mods/native_dng/metadata-v2` now masks only the dynamic metadata values while checking the header, reports populated fields, and checks helper/callsite bytes in dumps. `verify_camera.py BACKUP_DIR --build mods/native_dng/metadata-v2` additionally compares actual DNG metadata with paired JPEGs. v1 reader behaviour retained.
- Before staging, all existing SD files were re-hashed and matched the verified `cd703_card_native_dng_test_20261108T003143Z/card-inventory.json`; no new capture needed another copy. Existing `SYSTEM/KC713.OLD` matches v1 fallback. Procedure: flash, set the real clock, take normal/zoomed/SCN Children shots, restart and take another shot; then compare JPEG/DNG metadata. Optional dump. **No v2 hardware results claimed.**

### Direct DNG camera confirmation (2026-11-07)

- User: **“seems fine, no errors or problems”**; supplied a memory dump as well. Camera card `SYSTEM/KC713.OLD` SHA-256 = **`8dce21de78bf28f2a3c8a029f40dd8ae84a5ee0c517c28080d1a67148199fd5e`**. There is no pending `SYSTEM/KC713.FW` after the successful update.
- New/changed files backed up, without editing the card or old backups, to **`cd703_card_native_dng_test_20261108T003143Z/`**: 0303–0306 JPEG+DNG pairs, updated MEMDUMP and KC713.OLD (10 files), all SHA-256 verified. Earlier unchanged files remain in the pre-test backup; complete card inventory is recorded alongside the new files.
- **All four real camera DNGs pass**: 7,097,856 bytes, exact static header; LightCraft CLI 0.19.0 recognizes full 3056×2292 RAW. At 1536-pixel sRGB export, each matches an independently expanded 16-bit linear reference **pixel-for-pixel** (maximum channel difference 0). JPEGs 0304/0305 are monochrome, while both DNGs retain colour. Visual contact sheet inspected: `mods/native_dng/test-v1/camera-comparison.jpg`. Report `camera-render-verification.json`; reproduce with `src/verify_camera.py BACKUP_DIR`.
- MEMDUMP contains two complete frames, no partial tail. Latest entry/header/hook bytes match this firmware. `DNG1` log: attempts 1 since boot, phase **5 (closed successfully)**, first error 0, input 7096320, header written 1536, payload written 7096320, close error 0, buffer `0x2e6800`. Runtime flags: CFA=1, JPEG=1, YRGB=0, date stamp=0, capture mode=0. This confirms actual sequential header/payload writes and intact padding allocation during this trial.
- **Use `8dce21de…` as the current working firmware**, preserving pre-DNG `4765fbbb…` as recovery baseline. No further image staged during readback. Remaining coverage: black-frame/long-exposure, card-full/interrupted writes, broader mode/regression checks and native GUI/GPU/other editors. Current test JPEGs show 2007-01-01 (camera clock needs setting); DNG dynamic EXIF/preview remains deliberately absent.
- Structured summary: `mods/native_dng/test-v1/camera-verification.json`. The implementation/build/staging history below records the earlier pending-test state, now superseded by this confirmation.

### Direct DNG firmware experiment ready (2026-11-07, before camera trial)

- User explicitly requested implementation and copying the test firmware to the inserted SD when ready, including memory-dump support as useful.
- **`mods/native_dng/test-v1/KC713.FW`**, full SHA-256 **`8dce21de78bf28f2a3c8a029f40dd8ae84a5ee0c517c28080d1a67148199fd5e`**. Base pinned to confirmed `4765fbbb…`. Code-only changes: six-byte entry patch at `0x67898`, 1536-byte header at `0x1241a0`, 544-byte hook at `0x125a00`, plus checksums. Stock/confirmed binaries untouched. A second build is byte-identical.
- Header allocation `0x1241a0–0x12479f` sits inside zero padding `0x1241a0–0x1247ff`, after a return at `0x12419c` and before a function at `0x124800`. No exported static data references enter it. All **107 validated memory-dump frames** keep the full padding zero (`placement-audit.json`). This is strong placement evidence; hardware test still pending.
- File API assembly: open `0x73224(path,1,1,&handle)`; write `0x73240(handle,buffer,bytes,0,&written)`; close `0x7324c(&handle)`. Hook handles only main (`kind == 0`) 7,096,320-byte frames, changes the basename to `CCDInnnn.DNG`, writes fixed header then untouched sensor bytes. Checks both return codes and byte counts, closes every opened file, retains first error. Other kinds/sizes replay the stock prologue then continue at `0x6789e`; black-frame saving remains RAW.
- **18 p-code emulator scenarios pass** (`test-v1/emulation.json`): actual patched instructions plus real save helper; path/strlen/file APIs mocked and caller-saved registers clobbered. Success, filename boundaries, path/open/header/payload/close failures, short writes, error precedence, register/stack preservation and stock fallback covered. Successful emulated write equals the desktop proof byte-for-byte. Explicit restore instructions avoid the analysis processor's `ld.ab r13,[sp,r13]` alias issue in the stock shared epilogue; the stock project/processor were not changed. Preliminary `build-v1` is superseded by `test-v1`.
- Diagnostics at `0x125cc0`, ten u32: magic `DNG1`, attempts, phase, first error, input bytes, header written, payload written, close error, buffer pointer, reserved. Phase 5 + error 0 + counts 1536/7096320 means complete. `inspect_capture.py` checks actual DNG layout and the latest complete MEMDUMP frame against the test code/header.
- SD before staging: 49 source files copied to **`cd703_card_native_dng_before_20261108T002215Z/`**, each SHA-256 verified. Includes current photos/RAWs, `SYSTEM/KC713.OLD`, root firmware and MEMDUMP; see `mods/native_dng/card-backup.json`. Card `SYSTEM/KC713.OLD` matches confirmed `4765fbbb…`.
- Test image copied to **`SD:/SYSTEM/KC713.FW`**, flushed and read-back SHA-256 verified, then safely unmounted (`test-v1/card-staging.json`). Root-level old firmware was left untouched. **No new firmware flashed or camera results claimed.** First test: COLOR, B&W, restart/COLOR; expect JPEG + 7,097,856-byte DNG. If needed, hold W and press/release UP for a memory dump (~4 minutes). Full procedure `test-v1/TEST.md`.

### Direct DNG format proof, fixed WB accepted (2026-11-07)

- User scope decision: a sane fixed default WB is enough; the editor can adjust it. Per-shot WB discovery is not required for the first direct-DNG implementation.
- `mods/native_dng/src/make_dng.py` produces a **1536-byte static DNG header + the original 7,096,320 sensor bytes**, total **7,097,856 bytes**. Stored bits/sample = 8, `LinearizationTable` = the stock inverse at `0x16bec8`, linear white = 1023, black = 0, RGGB and the existing crop/colour matrices. Fixed `AsShotNeutral [0.42, 1, 0.73]`. No on-camera pixel expansion, demosaicing or WB fitting is needed for this layout.
- **20 checks pass** (`mods/native_dng/VERIFICATION.json`): source payload exact; direct table matches stock; 0293–0296 import as full RAW in installed LightCraft CLI 0.19.0; all four renders are pixel-identical to the established 16-bit converter with the same explicit daylight WB. Editing to 7000 K also gives an identical render between representations and preserves raw data. Wrong-sized input/existing outputs refused; source RAW and firmware hashes unchanged.
- `mods/native_dng/proof-v1/` contains the header, four openable DNGs and a manifest. The proof omits dynamic exposure/date/ISO, embedded previews and black-frame subtraction. No other editor/native GPU path tested yet.
- At this **format-proof stage**, no firmware hook had been implemented or flashed. The subsequent `native_dng/test-v1` work above implements that hook; camera testing remains pending. Detail: `mods/native_dng/README.md`.
- Recovered the still-present binutils 2.43 `gas/as-new` from the old scratch build into `decompiler-project/tools/binutils/arc-elf32-as`; recorded its source and SHA-256 in `provenance.json`. New hooks no longer depend on the temporary assembler surviving a reboot.

### LightCraft film workflow verified (2026-11-07)

- Continued from `HANDOFF.md`: keep the fully camera-confirmed `date_fix/stock_color_neopan` firmware (`4765fbbb…`); film work currently happens in the editor. No new firmware built or flashed here.
- Installed AppImage's actual CLI reports **0.19.0** (desktop launcher metadata still says 0.18.0). Extracted locally under `workflow/lightcraft/runtime/`; all tests use separate configuration and fresh libraries.
- **Native 3D `.cube` support works:** imported all 63 existing Film-Luts, a 3-profile starter ZIP and an identity control (67 total, zero failures), then reopened the library and checked persistence. Upstream source confirms the LUT operates on output-encoded colour after adjustments; export sRGB for these sRGB LUTs.
- `workflow/lightcraft/packs/CD703-Starter.zip`: **Amber 200** (Vista 200 source), **Chrome 100** (E100VS source), **Silver 1600** (Neopan 1600 source). Our names replace only the Cube `TITLE`; table values remain intact. `CD703-All-Films.zip` preserves all 63 source LUTs unchanged. Both include the MIT license and attribution; `packs/manifest.json` records hashes.
- **22 integration checks pass** (`workflow/lightcraft/VERIFICATION.json`): convert 0293–0296 using their actual `raw_plus_jpeg/test_both` firmware, verify decoded CFA bytes and crop, import as full 3056×2292 RAW, render base + three films, verify Amount 0 equals identity, and compare film renders on a synthetic RGB chart against the fitter's independent trilinear implementation. Mean error ≈0.33 and maximum <1 in 8-bit channel units. The B&W-mode shot's DNG still renders in colour. All source backup files, stock firmware and confirmed firmware remain byte-identical.
- `workflow/lightcraft/comparison.jpg` was visually inspected. These older samples retain their original 2007 metadata dates; B&W-mode RAW uses typical daylight WB. Native GUI clicks, GPU preview and new lighting/black-frame samples remain untested.
- Everyday instructions: `workflow/lightcraft/README.md`. Reproduce with `python3 workflow/lightcraft/verify.py`; regenerate packs with `python3 workflow/lightcraft/prepare.py`. These commands write editor artifacts under `workflow/lightcraft/` and do not modify old card backups or the everyday editor library.
