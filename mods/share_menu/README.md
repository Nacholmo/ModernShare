# Share-button mod settings

The next menu candidate adds a firmware label and film selection: see
[`mods/mod_settings/README.md`](../mod_settings/README.md). It is based on the
confirmed date-default firmware; the two-row version below is historical.

Requested controls: **DNG saving ON/OFF** and a shortcut to the original **hidden menu**. Film selection is outside this first prototype.

Current confirmed **`test-v1/KC713.FW`**, SHA-256 **`f992a106e1f6a96807e528658a7909f4ecb9cf451df1d8ec3a2e6f3fda9edba5`**, starts from camera-confirmed DNG metadata v3 `9760823a…`. **Basic camera test passed.** User reports the mod menu works as intended. Independent card readback confirms first shot **0318 JPEG + DNG**, second shot **0319 JPEG only** with no same-number DNG/RAW. Flashed hash matches; enabled-shot metadata and LightCraft render checks pass. [Camera evidence](test-v1/camera-verification.json) · [capture-toggle evidence](test-v1/capture-toggle-verification.json) · [procedure/results](test-v1/TEST.md).

Press Share in capture/review to open a native list headed **MOD SETTINGS**. UP/DOWN choose a row; OK toggles DNG saving or opens the original hidden menu. Share, Menu or Delete close the mod screen through the stock capture/review return handler. DNG OFF means ordinary JPEG-only captures. DNG ON retains the existing same-shot metadata and fixed daylight WB. The toggle is for the current session; every power-on still defaults to DNG ON. No SD preference file or settings-record write is introduced.

## Implementation and evidence

- **Actual Share press is `0x680` (key ID 13)**, release `0x681`. The script engine's key-name table is misaligned: `0x880` is handled by capture/review information-overlay code. Evidence: the `0x680` binding at `0x1508f0` reaches `0xcbc74`, which opens Share screen **`0xa8`** through `0x7c260`; common handler `0xb9760` also opens it. Existing key routing and busy guards remain in place.
- Replaces only the original Share root `0x168370`, its private list widget `0x168154`, and Share-owned widget storage `0x168190–0x16827f`. A 2-row native list/title is cloned from the stock hidden debug page, retaining the existing font/style/navigation. Widget ownership is checked across the registered screen table; no other root owns reused widgets. The old Print/Email/Favorite interface is replaced.
- A **170-byte** callback block occupies **`0x1256c0–0x125769`**, after the non-diagnostic scene hook's return at `0x1256be` and before its table at `0x125780`. It is zero in the pinned base and latest confirmed dump, with no exported static data references. 26 of 29 unique historical dump frames are zero there; the exceptions contain the older diagnostic scene-hook overlay. That older diagnostic build is not the current base. [Placement audit](test-v1/placement-audit.json).
- `0x416f4` performs native event-table dispatch. Init `0x4405` resets selection and fills the DNG label; refresh `0x4409` reads flag `0x13358c`. Selection events `0x5000/0x5001` toggle that existing CFA save flag or open hidden-menu screen **`0x3b`** via `0x7c260`. The hidden menu, updater and factory shortcuts are unchanged.
- Six bytes at **`0xcbd00`** skip the capture Share path's old switch to review state. Capture remains state 1; review remains state 2. All existing entry guards/preparation stay intact. Close buttons use stock `0xb97c4`, which returns to capture/review according to the current state.
- Confirmed DNG writer, header, metadata helper, scene code/tables, boot hook and boot-default CFA byte remain byte-identical. Only the code/data sections and their checksums change. Builder pins the exact base, checks expected bytes, refuses existing firmware output and verifies a change allowlist.

## Verification

**19 menu/capture instruction scenarios pass:** open ON/OFF, toggling, reopening with the preference retained, dynamic labels, refresh with a missing list, hidden-menu target, capture/review close controls, release/unknown-event delegation, actual stock CFA capture gate ON/OFF, and capture entry without switching state. Tests execute the custom callbacks, stock table dispatcher, stock close handler and stock capture-gate instructions. UI lookup/drawing/selection/screen-opening services and the mode-dial query are mocked. The known SLEIGH shared-restore alias issue is modeled at that compiler-helper boundary; production code uses normal stock helpers. The user reports native menu behavior works as intended; the independent card checks below establish ON/OFF file behavior.

**Camera evidence:** actual `KC713.OLD` matches the build; 0318 has valid JPEG/DNG and exact same-shot metadata, while 0319 has only its JPEG. All new files were backed up and hash-verified to `cd703_card_share_menu_test_20261108T023024Z/`. The enabled DNG renders pixel-identically to a linear reference in LightCraft. No new dump was supplied. This two-shot sample does not independently test an ON-after-OFF capture or a post-restart capture; those remain useful additional file checks.

All **50 DNG writer/metadata regression scenarios** also pass, bound to this firmware hash. Checksums pass and a separate rebuild is byte-identical. Reports: [menu-emulation.json](test-v1/menu-emulation.json), [emulation.json](test-v1/emulation.json), [verification.json](test-v1/verification.json).

```sh
python3 mods/share_menu/src/build_share_menu.py --outdir mods/share_menu/my-rebuild
bash -c 'source decompiler-project/scripts/environment.sh; "$GHIDRA_ROOT/support/analyzeHeadless" "$PROJECT_ROOT/projects" KodakC713 -process code.bin -noanalysis -readOnly -scriptPath "$PWD/mods/share_menu/src;$PWD/mods/native_dng/src" -postScript TestShareMenu.java "$PWD/mods/share_menu/test-v1" -postScript TestNativeDng.java "$PWD" "$PWD/mods/share_menu/test-v1"'
```

The stock Ghidra project is opened read-only and not saved. `research/callbacks/` records transient decompilations of UI callbacks missing from the main export; `src/ResearchShareMenu.java` reproduces them. Preserve **`mods/native_dng/metadata-v3/KC713.FW`** as the camera-confirmed pre-menu fallback.
