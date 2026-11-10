# Pinned Ember font inputs

Noto Sans Condensed Bold and SemiBold are unmodified fonts, copyright 2022 The Noto
Project Authors (https://github.com/notofonts/latin-greek-cyrillic), under SIL OFL 1.1.
The exact original bytes and SHA-256 values are in `manifest.json`.
Licence: `LICENSES/OFL-Noto.txt`. The embedded font metadata specifies OFL.

`ModernShareMaterialIcons.ttf` is a renamed subset containing only the 43 Material
Design glyphs used by `mods/ui/src/design.py`, extracted from Symbols Nerd Font.
Material Design Icons: copyright Austin Andrews and contributors,
https://github.com/Templarian/MaterialDesign, Apache-2.0.
Nerd Fonts: copyright Ryan L McIntyre, https://github.com/ryanoasis/nerd-fonts.
See `LICENSES/Apache-MaterialDesign.txt`, `LICENSES/Apache-2.0.txt` and
`LICENSES/Nerd-Fonts.txt`. Other Symbols glyph collections are not included.
These font files and glyphs retain their original applicable licences.

`material-subset.json` pins the original font digest, glyph names and FontTools
version. To reproduce the renamed subset from that original, locally supplied
font, write to a fresh path:

```sh
python3 scripts/subset_icons.py /path/to/SymbolsNerdFont-Regular.ttf \
  --output /tmp/ModernShareMaterialIcons.ttf
```

The source builder verifies all three bundled font hashes before rasterizing.
The bitmap results reproduce the accepted camera build exactly. To change a font,
update its manifest deliberately and validate a separate `--allow-modified` build.
