# Third-party notices

## Film-Luts — MIT

The LUTs in `mods/lut/looks/filmluts/` come from
https://github.com/YahiaAngelo/Film-Luts, copyright (c) 2024 Yahia. Their original
MIT licence and source note are preserved in that directory; a second copy is
in `LICENSES/MIT-Film-Luts.txt`. They are not relicensed as exclusively AGPL.
The firmware fits selected LUTs to small matrices; it does not run full 3D LUTs.

## Ghidra and the ARCompact processor model — Apache-2.0

Analysis setup scripts fetch Ghidra and ARCompact processor sources separately.
URLs, commit IDs and SHA-256 values are pinned in
`decompiler-project/toolchain.lock.json`. The upstream processor work is
`niooss-ledger/ghidra` commit `d3fbf109ada6d051750e973779170c1758622530`,
associated with https://github.com/NationalSecurityAgency/ghidra/pull/3006.
Ghidra is developed by the United States National Security Agency and its
contributors. The model-generation script contains upstream instruction snippets
and applies local corrections; upstream portions retain Apache-2.0 terms.
The licence is preserved in `LICENSES/Apache-2.0.txt`. No Ghidra/JDK executables
or complete upstream source distribution is bundled here.

## Kodak firmware — external input

No stock or modified firmware image, original updater, decompiled vendor source,
RAM dump or private sensor capture is included. User-authorized photos of the
camera interface are provided as project demonstrations under `photos/`. Build
scripts require a user-supplied stock image. Original English strings and the relocated graphic block are copied from
that local image during a build. The project licence does not relicense Kodak's
firmware or imply permission to redistribute it.

## Artwork and names

`boot_image.png` is the artwork supplied for ModernShare. Original project
contributions are covered by the project licence; third-party logos, characters
and trademarks remain subject to their owners' rights. `assets/legacy-banner-indexed.png`
is the editable indexed source for an older banner retained in an unused graphic
slot solely to reproduce the confirmed firmware byte-for-byte. The same rights
reservation applies to it. No independent third-party artwork licence is asserted.

Kodak, EasyShare and film/product names identify hardware and simulated looks.
No affiliation, endorsement or trademark licence is implied.

## External build/runtime dependencies

GNU binutils, Python, NumPy, Pillow, Ghidra and the JDK retain their own licences.
They are installed separately. Their binaries are not part of this repository.
Packaged GUI applications bundle Python, Tcl/Tk and the PyInstaller bootloader;
their notices are in `LICENSES/Python.txt`, `LICENSES/Tcl.txt`, `LICENSES/Tk.txt`
and `LICENSES/PyInstaller.txt`. The PyInstaller bootloader exception permits
bundling applications under their chosen licence. Other system libraries retain
their existing terms. The corresponding ModernShare source archive is generated
alongside each packaged application.

The Linux AppImage contains the AppImage type-2 runtime and its statically linked
dependencies. Their original terms are preserved in `LICENSES/AppImage-runtime.txt`.
Its source commit and binary digest are pinned in `packaging/appimage/toolchain.json`.
`appimagetool` is a separately downloaded, hash-verified build tool and is not
included in the runtime payload.
