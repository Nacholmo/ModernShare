# Development

Use the standalone builder and final assembly described in [BUILDING.md](BUILDING.md).
The `mods/` staged builders preserve implementation history and feature-specific
reasoning; they are not a substitute for the standalone build interface.

## ModernShare 0.9 UI

The Ember interface, icon clearance, native LCD brightness shortcut, Review-only
High power option and Film chooser are accepted on camera. The user confirms both
brightness settings survive a reset; the reset method was unspecified. Installed
firmware readback independently matches the accepted development build. Labeled
Stock, Neopan, Velvia and Kodachrome captures pass JPEG-only/JPEG+DNG checks,
metadata comparison and CPU RAW-render checks. Sensor captures and memory dumps
remain private; authorized interface photos appear in the README.

The public builder and portable apps produce 0.9, a version-label-only derivative
of that accepted build. Preferred sources include `mods/ui/src/` for rasterization,
`assets/fonts/` for pinned licensed font inputs and `src/firmware/` for final hooks.
The relocated film getters are separately allocated from brightness code. The
standalone instruction runner requires only local stock firmware and analysis
tools, with synthetic DNG input; it needs no historical firmware or camera dump.
See [validation](VALIDATION.md) for the evidence and modeled boundaries.

## Annotated decompiler project

Only our annotations, layouts, scripts, model patches and pinned download metadata
are shipped. Vendor decompilation exports, Ghidra databases, binaries and dumps
are generated locally. The optional tool bootstrap supports Linux x86-64 and
downloads the pinned Ghidra/JDK/ARCompact sources under ignored directories.

```sh
python3 scripts/setup_analysis.py --stock /path/to/kc713.fw
python3 decompiler-project/scripts/bootstrap.py
bash decompiler-project/scripts/analyze.sh
```

This creates `decompiler-project/projects/KodakC713.gpr`, local exports and an
offline atlas. The first analysis can take several minutes. The setup and model
scripts are retained from the verified development environment; tool versions,
URLs and hashes are in `decompiler-project/toolchain.lock.json`. The custom
ARCompact model expands auxiliary-register addresses and corrects the reviewed
MetaWare helper/delay-slot issues. It does not make decompiler output equivalent
to original source or prove all inferred types/functions correct.

Open the generated project with:

```sh
bash decompiler-project/scripts/open-project.sh
```

Findings and implementation history are in [research-notes.md](research-notes.md).
Its old build/card-backup paths identify the private development workspace; those
artifacts are deliberately not part of this source export.

## Tests and review

Run the host tests, source build and all four read-only emulator suites. Verify
the final firmware hash; review source placement, entry pointers, stack/callee-
saved registers, write errors and generated boot preview. Preserve the previous
camera-confirmed image locally. Treat changed builds as unconfirmed until tested.

The repo audit rejects firmware, private sensor captures, credentials, tool
binaries and generated databases from the public file set. The three newly
authorized interface JPEGs use exact path/hash exceptions; their public copies
omit location metadata and preserve the original image pixels:

```sh
python3 scripts/audit_repo.py
```

Original authored code/documentation uses AGPL-3.0-or-later. Keep upstream notices
when updating LUTs or processor snippets. Do not add firmware images or vendor
decompilation exports to pull requests.
