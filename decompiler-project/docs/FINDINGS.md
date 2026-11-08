# Findings and evidence

This document separates facts inherited from camera experiments from findings made during this workspace's static analysis. The firmware remains byte-identical to stock. No new camera tests were performed here.

## Corrections to the first import

| Initial annotation | Reviewed interpretation | Evidence |
|---|---|---|
| `0x9038c` as a function entry | Internal registration call; function starts at `0x90384` | Push/save prologue and call sequence in `diagnostics/boundaries.binutils.asm` |
| `0xf26f8` as the capture-table initializer entry | Internal block; initializer starts at `0xf2664` and reserves 204 stack bytes | Independent GNU disassembly, followed by Ghidra body-owner audit |
| `0x1206f4` as handler entry | Internal message comparison; handler starts at `0x1206d0` | Independent prologue/control-flow review |
| `0x67fc0` as a separate `DrawText` | Shadow/outline block in the glyph renderer at `0x67f10` | Control-flow review; the preceding decoder at `0x67e04` is a separate function |
| Children mode 7, Museum mode 12 | Children 9, Museum 17; final SCN item 22 | Updated notes snapshot, camera diagnostic logs described there, and `SetScene` switch |

Function names in this workspace are descriptive annotations. A matching Ghidra entry alone does not establish a boundary. `annotations/boundary_corrections.json` records the reviewed repairs, and `diagnostics/project_audit.json` checks their actual ownership in the saved program.

## Processor model repairs

The upstream ARCompact implementation is an unmerged Ghidra contribution. The derived `ARCompact:LE:32:kodak` language retains its pinned sources and changes only local analysis tooling:

1. **Auxiliary addressing.** The upstream space and LR/SR expressions truncate addresses to 16 bits. Stock capture setup writes auxiliary register index `0x10f20`, whose byte address in Ghidra's auxiliary space is `0x43c80`. The derived model uses 32-bit addressing. The project audit evaluates the instruction p-code and verifies this address. These auxiliary-space addresses are distinct from ordinary RAM/MMIO addresses.
2. **Shared compiler helpers.** The firmware shares register-save suffixes at `0x11adb8–0x11adf0` and restore suffixes through `0x11ae9a`. Ordinary function modeling split these sequences and caused callers to acquire fictitious return values and lose arguments. Twenty-eight call-fixups model the complete save/restore effects. Helper entry functions deliberately own only their initial instruction because suffix ownership overlaps. Their standalone decompilations are incomplete; use the full GNU disassembly and the call-fixup descriptions.
3. **Saved register r24.** The default upstream compiler specification omitted r24 from its preserved registers. The camera's save/restore sequences preserve it, so the derived ABI includes it.
4. **Predication in delay slots.** Six stock functions originally failed with a bad relative p-code branch. Their tail-branch delay slots conditionally clear a register. Equivalent branchless semantics for `sub_s.ne` and non-flag-setting conditional `sub` remove the intra-instruction branch while preserving predication and flags. `VerifyDelaySlots.java` reruns all six regressions against the actual saved program.

Generated language sources and their hashes are described in `patches/processor_model.json`. `scripts/build_processor_model.py` regenerates them from the pinned upstream files without changing those originals. This is a targeted static-analysis model, not full CPU or MetaWare runtime emulation.

## Capture setup becomes readable

With the helper model and reviewed types, `ConfigureCapturePipeline` at `0x11e124` takes a request pointer rather than the fictitious return of a register-save helper:

- Request byte `+0x14` selects the illuminant CCM.
- Request byte `+0x13` selects the normal/B&W/sepia YCbCr matrix.
- `GetCaptureCcm` indexes the three pointer slots in `capture_pipeline`.
- `GetCaptureYmat` selects B&W for 3, sepia for 4, and normal otherwise.
- `PackCaptureMatrixRegisters` packs each three-coefficient row plus offset into two 32-bit words.
- Six CCM words are written to auxiliary indices `0x10f20–0x10f25`; six YCbCr words follow at `0x10f26–0x10f2b`.

Packing takes the absolute coefficient, shifts it right by six, and uses bit 12 for its sign. The fourth row element is placed in the high half of the second packed word without that coefficient shift. Offset units are stage-specific; do not assume the fourth element has the same scaling as the first three.

The request type is explicitly a **prefix**, not a claim to know the complete capture request layout. Invocation timing comes from camera experiments and task dispatch, not from the existence of a static call edge alone.

## Better discovery, with limits

The initial import found roughly 3,500 functions. A conservative second pass searches 16-bit-aligned `push_s blink` followed immediately by a direct call to a reviewed save helper. It adds functions only outside an existing function and outside defined data. Follow-on Ghidra analysis discovers further callers/callees.

`diagnostics/function_discovery.json` records every matched candidate and whether it was created, already known, inside another function, or preserved as data. Interior candidates are not split automatically. Leaf routines and other prologue styles can still be missed.

Coverage counts instructions, defined data, and unclassified bytes in the mixed 1 MiB code section. Unclassified bytes include possible code, literal pools, tables, and padding. Neither a high classification count nor successful decompilation proves semantic completeness.

## Remaining research areas

These are limitations for future firmware research, rather than missing setup work:

- Opaque ARC extension/DSP instructions are retained as named user operations. Their precise effects need instruction documentation or experiments.
- Hardware loops and indirect dispatch can produce imperfect control flow. The offline browser exposes warnings, computed flows, and opaque operations for each function.
- Runtime pointers remain unknown unless initialized by the firmware. No RAM dump was overlaid onto the stock program, so the project does not silently mix static image bytes with a particular camera state.
- Labels, inferred structure fields, pixel formats of software converter variants, and most ABIs still require review before patching. Sensor CCDI format is now established by the newer camera experiments described below.
- The selected-language flash resource is not resident at its nominal section address. Language strings are not exhaustively decoded by the Ghidra string list.

Start deeper work with the capture getters, the two software photo converter variants, the typed initialization routine, or the corrected glyph-rendering function. Keep experimental firmware builds separate from this stock analysis database.

## Common-info record builder

The function at `0x98734` constructs a record containing the text `KodakCommonInfo`. It fetches nine CCM coefficients through `GetCaptureCcm`, selecting positions 0/1/2, 4/5/6 and 8/9/10 from the 3×4 matrix. This explains the nine getter calls described in the camera diagnostic notes; those calls are not nine independent scene changes. The descriptive name `BuildKodakCommonInfo` reflects the written record. Its precise role in the complete record layout still needs tracing; the newer CCDI sensor format and DNG conversion are already established independently by camera experiments.

## New camera findings: curves, RAW and dates

The updated source snapshot reports that rewriting both companion tables as inverse(curve B) removed lavender whites. This workspace independently confirmed that the two stock 256×uint16 tables are identical and match the midpoint inverse with mean absolute error 0.203125 (see `diagnostics/curve_inverse_verification.json`). Curve C at `0x16c6c8` and uploader `0x11de40` are now annotated.

The parent project also reports working JPEG plus sensor RAW, an existing LibRaw-checked DNG converter, and fixed date/year behaviour. CCDI is 3072×2310 8-bit RGGB; decode it with the stock inverse table regardless of installed film curves, then crop x=8/y=10 to 3056×2292. The latest RAW section supersedes the earlier tentative black≈14/gamma guesses: it reports black already removed and a fixed nonlinear sensor encoding.

The user's preferred normal COLOR/VIVID pipeline is stock. The combined build adds Neopan B&W, SCN presets, sensor RAW, flash Off and the date fix. The remaining camera check explicitly noted is SCN operation with the non-diagnostic hook in that combined build. See `NEXT_STEPS.md` for the revised priorities.
