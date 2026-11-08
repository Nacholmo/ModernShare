# Building and changing the release

The supported interface is `scripts/build.py`; start with the root README.
Python dependencies are pinned to the versions used for the 0.8 bitmap encoding
and header arithmetic. GNU ARC binutils 2.43 was used to validate assembly output.
No complete intermediate firmware images are needed from the original workspace.
End users can use the smaller [GUI/CLI patcher](GUI.md) without these source-build
dependencies; its compact release bundle is regenerated from this source build.

## Build steps

1. Validate the exact local stock image's SHA-256 and container checksums.
2. Compute the two matching palettes and UI colour-word edits from
   `mods/theme/src/make_theme.py`.
3. Apply 378 small fixed edits (1,707 changed bytes) from
   `src/release/recipe-0.8.json`. These encode the reverse-engineered default,
   entry-branch, widget, label, matrix and pointer edits. Only changed bytes are
   stored; original vendor text/code regions are not shipped as payloads.
4. Copy the relocated 224-byte stock graphic block from the local input. Generate
   the DNG header from `mods/native_dng/src/metadata_header.py` and `make_dng.py`.
5. Assemble every custom hook from the final sources in `src/firmware/`. The
   segment map and expected compiled hashes are in the release recipe. Reject
   unresolved relocations, oversized segments or code outside declared segments.
6. Encode the editable indexed legacy banner and the supplied ModernShare PNG.
   Reuse the original English text from the local image, with the existing VIVID
   label edit. Decode/reassemble the five boot tiles to verify their streams.
7. Recompute type-0/type-1 section checksums and the header complement pair.
   Type 2 is left untouched. Verify the final release SHA-256 before writing
   the flashable output.

The stock image and existing outputs are never overwritten. Temporary firmware,
object files and listings are local build products and are ignored by Git.

## Preferred editable sources

| Change | Source |
|---|---|
| SD load/save, defaults/status callbacks | `src/firmware/settings.s`, `settings_layout.inc` |
| Native Film/DNG menu actions | `src/firmware/menu.s`, `menu_layout.inc` |
| Film matrix lookup | `src/firmware/scene-getters.s` |
| Live preview transform and refresh | `src/firmware/preview.s` |
| Native DNG writing | `src/firmware/dng-writer.s` |
| Same-shot capture metadata | `src/firmware/capture-metadata.s` |
| DNG tags/linearization | `mods/native_dng/src/metadata_header.py`, `make_dng.py`, `tools/ccdi2dng.py` |
| Date fallback | `src/firmware/date-boot.s`, `date-setup.s` |
| Boot renderer guard | `src/firmware/boot-guard.s` |
| Visible boot artwork | `boot_image.png`; protected text/filter boxes in `scripts/build.py` |
| Fixed edits and generated film data | `src/release/recipe-0.8.json` |
| Theme algorithm | `mods/theme/src/make_theme.py` |
| Film fitting | `mods/lut/src/fit_lut.py`, `mods/classic_films/src/fit_classics.py` |

The original staged feature builders and older assembly are retained in `mods/`
as implementation history. Some expect old local build directories and source
fixtures; the final standalone builder does not run them. Edit the final
`src/firmware/` files for the supported build path, not an older copy in `mods/`.

## Intentional changes

Pass `--allow-modified` to assemble intentional edits or an alternative `--artwork`.
It permits differing segment/final hashes, while retaining stock validation,
segment boundaries, boot-buffer limits and container checks. Output is marked
unconfirmed. This flag does not make arbitrary changes safe to flash.

Layouts are fixed. If a feature grows, audit its allocation and update
`src/release/assembly.json`, the recipe segment map, labels/pointers and tests
together. The literal pool at `0xec05c`, shared helpers, boot decoder buffer,
DNG header and capture metadata allocations must remain protected.

To refresh a recipe after an independently reviewed rebuild, use a new filename:

```sh
python3 scripts/export_recipe.py --stock /path/to/kc713.fw \
  --target /path/to/reviewed/KC713.FW --out /path/to/new-recipe.json
```

This tool extracts fixed changed bytes and compiled segment hashes, and excludes
all source-generated regions and vendor copies. Review the resulting edits before
replacing a release recipe. Preserve the confirmed release and test new firmware
separately. `--allow-modified` builds must never inherit a camera-confirmed claim.
