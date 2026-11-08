# Kodak CD703 / C713 custom firmware — notes

Started 2026-11-07. The CD703's own firmware is "lost media". This camera runs
the **C713 build, version 1.30**: the hidden menu reports MCU 66, MAIN 1.3000 and
CamOS 2.2501, and a RAM dump of the camera's code section is byte-identical to
`kc713.fw`.

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
- Free space for code and data:
  - `0x12fed6–0x130000`: zero tail of the code section.
  - `0x125420–0x125cef`: unreferenced zero run (`0x125420–0x1255ff` used by `fullscreen`, `0x125600–0x125960` by `scene_films`).
  - Both stay zero in 20 RAM dumps.
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
