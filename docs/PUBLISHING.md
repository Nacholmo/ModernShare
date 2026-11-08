# Publishing releases

The public repository is [Nacholmo/ModernShare](https://github.com/Nacholmo/ModernShare),
with ready-to-run applications on the [release page](https://github.com/Nacholmo/ModernShare/releases).

Before pushing source changes:

```sh
python3 scripts/audit_repo.py
python3 -m unittest discover -s tests -v
git add .
git commit -m "Describe the change"
git push
```

For a release, manually run **Build Windows and Linux apps** in GitHub Actions
against the exact source commit. Both native jobs must pass all host, GUI and
packaged-app checks. Download each platform artifact and combine the Windows
`.exe`, Linux `.AppImage`, corresponding source archive, licence archive and
verification reports. Recalculate an overall `SHA256SUMS`.

Create a draft release against the tested commit, upload these assets, verify
the draft and its hashes, then publish. The build workflow uploads artifacts;
it does not publish a release by itself. Include corresponding source and licence
notices alongside the applications. Keep README direct download links aligned
with the published tag and asset names.

Never publish `KC713130.exe`, stock or modified firmware, personal camera photos,
memory dumps or generated vendor decompilation exports. End users obtain the
original updater from the [verified archive](GETTING_FIRMWARE.md) and generate
firmware locally.
