# Kodak C713 / CD703 analysis sources

This directory contains the original annotation, compiler-model, layout and
analysis scripts. Generated vendor decompilation, assembly, Ghidra databases,
firmware inputs and tool binaries are deliberately excluded.

Follow [setup and development](../docs/DEVELOPMENT.md) to supply your own stock
image, download the pinned toolchain and generate the local Ghidra project and
offline firmware atlas. [Reviewed findings](docs/FINDINGS.md),
[research snapshot](annotations/NOTES.snapshot.md) and
[host layouts](types/kodak_layouts.h) are included.

Generated outputs stay under ignored input, tools, projects, report, exports,
diagnostics and runtime directories. The public audit does not redistribute
historical vendor-disassembly evidence. Current function discovery, annotated
memory, coverage and delay-slot checks are regenerated from local input.
