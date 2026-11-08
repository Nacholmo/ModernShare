# Firmware architecture

Target: CD703 using the C713 1.30 image, ARCompact CPU, MetaWare compiler and
MQX/Altek firmware. Runtime addresses below are RAM addresses. The update is
2,172,416 bytes; code/data RAM offsets map to file address minus `0x2fe00`.

| Section | File offset | Runtime base | Size |
|---|---:|---:|---:|
| Code | `0x200` | `0x30000` | `0x100000` |
| Data | `0x100200` | `0x130000` | `0x44a00` |
| Graphics | `0x144c00` | `0x1a0000` | `0x4fc00` |
| Language flash | `0x194800` | flash-backed, selected block loaded separately | `0x7dc00` |

See `tools/kodakfw.py` for the record parser. The updater validates model, size,
type-1 sums and the RHIR/KHIR headers. The builder also checks type-0 sums.

## Capture and films

The 24-byte map at `0x125780` selects a film per capture mode. By mode uses
Children=E100VS, Museum=Neopan and Sunset=Vista; other modes use stock. An explicit
film fills the map for all modes; Stock clears it. Matrix getters `0xaf508` and
`0xaf514` branch to `0x125600`, indexing five 192-byte records through the pointer
table at `0xebe6c`. The three older records live at `0x1257a0/0x125860/0x125920`,
Velvia at `0xebc90`, Kodachrome at `0xebd50`.

Preview code composes the selected film's relative Q12 RGB transform with the
current calibrated preview matrix. Review and already-transformed capture paths
bypass the extra transform. The 90-byte Q12 table is at `0xebe10`.

## Direct DNG

The native RAW entry `0x67898` reaches a 548-byte writer at `0x125a00`. Main
3072×2310 frames contain 7,096,320 companded sensor bytes. A 1,536-byte DNG header
stores their inverse linearization table, CFA, crop, matrices and fixed daylight
white balance. Total DNG size is 7,097,856 bytes; the original sensor bytes remain
unchanged. Non-main or incompatible-size frames fall back to stock handling.

Before writing, `0x12ff40` reads the active capture record `[0x1324fc]`: date/time
at +0x64, exposure +0xb0, ISO +0xb4, aperture flag/index +0xf2/+0xf4. This avoids
the earlier one-shot delay from waiting for JPEG EXIF serialization. Diagnostics
at `0x125cc0` contain attempt, phase, counts and first error. Phase 5 is closed.

## Share menu and SD preferences

The Share root at `0x168370` dispatches through `0x1256c0` and event table
`0x1682d4`. Menu data begins `0x168154`, items at `0x1681b8`, film index
`0x1682d0`. Event 0x5000 changes Film; 0x5001 toggles DNG; 0x5002 opens hidden
screen 0x3b; 0x5003 is the inert version/status row. DNG boot flag `0x13358c=0`.

Preferences code reclaims `0xebecc–0xec00f` and `0xec088–0xec207` from retired
Share code. The old table `0x16839c–0x16844b` becomes state, paths and status text;
its old pointer at `0xec050` is zeroed. **Preserve shared literal `0xec05c`,
helpers `0xec208/0xec394`, and widget data `0xec540`.**

Capture-init callback `0x1508bc` wraps original init `0xcabfc`, loading only after
success. Review-first menu init loads the same state once. Opening/refreshing the
menu writes nothing. Changing Film/DNG writes the inactive SD slot, validates the
write count and close, then commits generation/slot in RAM.

`B:\KMOD0.CFG` and `B:\KMOD1.CFG` hold four little-endian u32 words: magic KMOD,
`0x10000 | film<<8 | dng`, generation, and the inverted XOR of the first three.
Validate magic/schema/reserved bits, film 0–6, DNG 0/1 and checksum; choose the
newer valid generation with signed wraparound comparison. A wins ties. Invalid
or missing files retain By mode / DNG OFF. Save failures retain session choices
and show SD error. This protects against partial records; physical FAT/SD
power-interruption durability has not been established.

## Boot and clock

Five 480×48 RLE tiles stay below the shared decoder's 25,800-pixel capacity. Their
records are at `0x1254a0`; English text + CLOS marker + streams occupy
47,608/47,616 bytes in the already-sacrificed language-17 flash block. English
text is copied from local stock during the build. The guard at `0x12ff00` suppresses
tiles if another language is loaded. Palettes at `0x141c00` and `0x1cb83c` must
match: the blitter maps by exact hardware colour, with 0 transparent and 252–255
reserved. The artwork's progress bar is static.

Date fallback is 2026-11-07 noon, not an automatically current date. Battery-flap
opening still removes RTC power. The six-field date-screen copies, fallback
templates and year checks support normal setup through 2037; native retained
dates are preserved. The mod preferences record does not contain the clock.
