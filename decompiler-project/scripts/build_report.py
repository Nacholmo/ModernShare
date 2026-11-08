#!/usr/bin/env python3
"""Build an entirely offline browser and readable indices from current exports."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent

def read(path):return json.loads((ROOT/path).read_text())
def js(value):return json.dumps(value,ensure_ascii=True,separators=(',',':'))

def main():
    summary=read('exports/workspace_complete.json')
    functions=read('exports/function_index.json');calls=read('exports/call_graph.json')
    annotations=read('exports/annotations.json');strings=read('exports/strings.json')
    topics=[
        dict(title='Capture & colour',description='Saved photographs and live preview have different paths. Follow the capture getters, register packing, and software photo converters.',functions=[
            dict(address='0x0011e124',role='Configure capture matrices from request'),
            dict(address='0x000af508',role='Select illuminant CCM'),dict(address='0x000af514',role='Select normal / B&W / sepia matrix'),
            dict(address='0x0011e0b8',role='Pack Q16 matrix for auxiliary registers'),dict(address='0x0009fec0',role='Software photo conversion variant'),dict(address='0x00098734',role='Build KodakCommonInfo metadata with CCM values')],
            note='Tone curves are loaded at boot. Both inverse companions must be regenerated when curve B changes; this fixed the lavender cast in camera tests. The first-pass init label at 0xf26f8 is an internal code location; the reviewed function entry is 0xf2664.'),
        dict(title='Scene films & settings',description='The corrected SCN ordering begins at High ISO. Camera logs identify Children as mode 9, Museum as 17, and the final scene as 22 (called Sunset by the user).',functions=[
            dict(address='0x0003c5ec',role='SCN menu index → capture mode'),dict(address='0x0003c128',role='Apply capture mode'),dict(address='0x0003bd7c',role='Read capture mode')],
            note='The copied notes record scene_films v3 as working. Scene-specific exposure remains active. Earlier names assigned to modes 7/12 were wrong.'),
        dict(title='Graphics & interface',description='The OSD is 480 × 240. Image records, palettes, image IDs, and screen/widget layouts are typed in the saved database.',functions=[
            dict(address='0x000789f8',role='UI image draw entry'),dict(address='0x00067e04',role='Decode and blit image records'),dict(address='0x00067f10',role='Glyph shadow and outline rendering'),
            dict(address='0x00067dec',role='Look up image record by ID'),dict(address='0x00042040',role='Exact-match OSD palette lookup'),
            dict(address='0x00090384',role='Register firmware image tables')],
            note='Patch both palette copies for a theme. Image palette indices 252–255 are reserved. The language flash section is deliberately not mapped as resident RAM.'),
        dict(title='Firmware & diagnostics',description='The stock snapshot is immutable. The workspace validates checksums, preserves unknown runtime values, and keeps all application state inside its own directory.',functions=[
            dict(address='0x000fe304',role='Firmware update validator'),dict(address='0x00040ee4',role='Built-in MEMDUMP shortcut'),
            dict(address='0x0008a2f8',role='Load selected language from flash'),dict(address='0x000f2664',role='Initialize ISP and capture tables'),dict(address='0x0011de40',role='Upload inverse/forward capture curves')],
            note='The decompiler is a static analysis tool. Hardware-loop recovery, opaque extension instructions, indirect dispatch, and inferred ABIs remain review areas. No firmware was flashed.'),
        dict(title='Sensor RAW & DNG',description='Camera tests now confirm JPEG plus sensor RAW. CCDI is headerless 3072 × 2310, 8-bit RGGB. The parent project already provides a tested DNG converter.',functions=[dict(address='0x00067898',role='Write sensor CFA RAW')],note='Decode CCDI using the STOCK inverse curve-B table, independent of installed film curves. Crop x=8, y=10 to 3056 × 2292. Latest notes report black already removed. White balance and DNG rendering were checked with LibRaw; target editor is Lightcraft.'),
        dict(title='Current build & date fixes',description='Normal COLOR/VIVID are stock by user preference. B&W is Neopan; SCN films and sensor RAW remain enabled. The latest build also fixes year selection and the default date stamp.',functions=[dict(address='0x0007166c',role='Validate camera date')],note='date_fix/stock_color_neopan (4765fbbb) is camera-confirmed for years through 2037, stamp Off after restart, and correct metadata dates. Non-diagnostic SCN behaviour in this final combined build remains to be confirmed.'),
    ]
    data=dict(summary=summary,functions=functions,calls=calls,annotations=annotations,strings=strings,
              manifest=read('input/manifest.json'),reviewCount=sum(f['needs_review'] for f in functions),topics=topics)
    report=ROOT/'report';(report/'functions').mkdir(parents=True,exist_ok=True)
    # Public source export ships only the authored atlas shell, not vendor data.
    import shutil
    shutil.copyfile(ROOT/'web/index.html',report/'index.html')
    shutil.copytree(ROOT/'web/assets',report/'assets',dirs_exist_ok=True)
    (report/'data.js').write_text('window.KODAK_ATLAS='+js(data)+';\n')
    allowed=set()
    for function in functions:
        address=function['address'];stem=function['export_stem'];folder=ROOT/'exports/functions'
        cfile=folder/(stem+'.c');asmfile=folder/(stem+'.asm')
        detail=dict(address=address,c=cfile.read_text() if cfile.exists() else None,assembly=asmfile.read_text())
        name=address[2:]+'.js';allowed.add(name)
        (report/'functions'/name).write_text('window.KodakAtlas.register('+js(detail)+');\n')
    for path in (report/'functions').glob('*.js'):
        if path.name not in allowed:path.unlink()
    # These generated directories are exclusively managed by this exporter.
    stems={f['export_stem'] for f in functions}
    for path in (ROOT/'exports/functions').iterdir():
        if path.suffix in ('.asm','.c') and path.stem not in stems:path.unlink()
    seeded=[f for f in functions if f['seeded']]
    intro=(f'# Firmware analysis exports\n\nStock C713 1.30, `{data["manifest"]["sha256"]}`. '
           f'The saved Ghidra database contains **{summary["function_count"]:,} functions**; '
           f'**{summary["decompiled"]:,} decompiled**, **{summary["failed"]:,} failed**. '
           f'{data["reviewCount"]:,} functions have review flags. A generated C file is not proof of semantic correctness.\n\n'
           '[Open the offline firmware atlas](../report/index.html) · [All functions](ALL_FUNCTIONS.md) · '
           '[Coverage](coverage.json) · [Project audit](../diagnostics/project_audit.json)\n\n'
           '## Annotated functions\n\n| Function | Address | Exports | Review flags |\n|---|---|---|---|\n')
    def row(f):
        links=f'[assembly](functions/{f["export_stem"]}.asm)'
        if f['status']=='decompiled':links=f'[pseudocode](functions/{f["export_stem"]}.c), '+links
        flags=[]
        if f['warnings']:flags.append(f'{len(f["warnings"])} warnings')
        if f['opaque_operations']:flags.append(f'{len(f["opaque_operations"])} opaque operations')
        if f.get('call_fixup'):flags.append('shared helper')
        if f['status']!='decompiled':flags.append('failed')
        return f'| {f["name"]} | `{f["address"]}` | {links} | {", ".join(flags) or "—"} |\n'
    (ROOT/'exports/INDEX.md').write_text(intro+''.join(row(f) for f in seeded))
    (ROOT/'exports/ALL_FUNCTIONS.md').write_text('# All discovered functions\n\n[Offline browser](../report/index.html) · [Annotated index](INDEX.md)\n\n| Function | Address | Exports | Review flags |\n|---|---|---|---|\n'+''.join(row(f) for f in functions))
    print(f'Built offline atlas: {len(functions):,} functions, {len(annotations)} annotations, {len(strings):,} defined strings.')

if __name__=='__main__':main()
