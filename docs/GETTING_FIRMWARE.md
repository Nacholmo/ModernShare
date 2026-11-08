# Getting the original Kodak updater

Use the verified TousLesDrivers archive listing:

**[Kodak EasyShare C713 Zoom 1.30 — KC713130.exe](https://www.touslesdrivers.com/index.php?v_page=23&v_code=19867&v_langue=en)**

Its direct mirror is
[KC713130.exe](https://fichiers.touslesdrivers.com/19867/KC713130.exe).
On 2026-11-08 this returned HTTP 200 and contained the exact supported firmware.
The check is recorded in `validation/download-source.json`. This is a verified
source, not a claim that no other working archive exists. Other sites reported
by the camera owner either linked to a 404 (UserDrivers) or redirected to a
driver-download utility (DeviceDriverFinder); those are not recommended here.

| File | Size | SHA-256 |
|---|---:|---|
| `KC713130.exe` | 1,110,016 | `0228ebb1bd13fea29942c9f67d572773b829b133bef53d4841cd43f5bd17f712` |
| Contained `kc713.fw` | 2,172,416 | `06133ed6bc6272f6b1ab9c784723d9259c71cb4ef88b3defb6ed36f4a4e66c9b` |

The updater is a self-extracting ZIP. ModernShare reads the archive in memory;
it does not execute the Windows program, unpack arbitrary paths or install
Kodak software. It verifies the contained firmware's size and SHA-256 before
patching. A different wrapper is acceptable only if its contained firmware still
matches exactly. The original updater and firmware are not redistributed here.
