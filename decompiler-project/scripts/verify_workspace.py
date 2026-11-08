#!/usr/bin/env python3
"""Audit the export, saved-project checks, input identity, and offline report."""
import hashlib
import json
import re
from pathlib import Path
from prepare_firmware import validate_firmware

ROOT=Path(__file__).resolve().parent.parent

def require(value,message):
    if not value:raise RuntimeError(message)
def read(path):return json.loads((ROOT/path).read_text())

def main():
    manifest=validate_firmware((ROOT/'input/kc713.fw').read_bytes())
    saved=read('input/manifest.json');require(saved==manifest,'Input manifest is stale')
    summary=read('exports/workspace_complete.json');rows=read('exports/function_index.json')
    require(summary['function_count']==len(rows),'Function index count mismatch')
    require(summary['decompiled']+summary['failed']==len(rows),'Decompilation totals mismatch')
    require(summary['missing_annotations']==0,'Some project annotations are missing')
    audit=read('diagnostics/project_audit.json')
    require(audit['passed'] and audit['stock_sha256']==manifest['sha256'],'Saved-project audit failed')
    require(audit['function_count']==len(rows),'Export does not match the audited program function count')
    require(summary['language']==audit['language']=='ARCompact:LE:32:kodak','Wrong analysis model')
    for section in saved['sections']:
        data=(ROOT/section['path']).read_bytes()
        require(len(data)==section['size'],'Extracted section size mismatch')
        require(hashlib.sha256(data).hexdigest()==section['sha256'],'Extracted section differs from stock')
    unique=set();expected_files=set()
    for row in rows:
        require(row['address'] not in unique,'Duplicate function address');unique.add(row['address'])
        stem=row['export_stem'];asm=ROOT/'exports/functions'/(stem+'.asm')
        require(asm.is_file(),'Missing assembly: '+stem);expected_files.add(asm.name)
        cfile=asm.with_suffix('.c')
        if row['status']=='decompiled':require(cfile.is_file(),'Missing pseudocode: '+stem);expected_files.add(cfile.name)
        else:require(not cfile.exists(),'Stale pseudocode remains for a failed function')
        require((ROOT/'report/functions'/(row['address'][2:]+'.js')).is_file(),'Offline function detail missing')
    actual={p.name for p in (ROOT/'exports/functions').iterdir() if p.suffix in ('.c','.asm')}
    require(actual==expected_files,'Stale or extra generated function files remain')
    for item in read('exports/annotations.json'):
        require(item['comment_present'] and item['label_present'],'Annotation persistence failed')
    coverage=summary['coverage']
    require(coverage['instruction_bytes']+coverage['defined_data_bytes']+coverage['unclassified_bytes']==coverage['section_bytes'],'Coverage classification does not sum to code section size')
    require(coverage['unclassified_zero_bytes']+coverage['unclassified_nonzero_bytes']==coverage['unclassified_bytes'],'Unclassified-byte totals mismatch')
    sources=read('annotations/sources.json')
    for source in sources.values():
        path=ROOT/source['path'];require(hashlib.sha256(path.read_bytes()).hexdigest()==source['sha256'],'Research source snapshot differs from recorded hash')
    # Historical vendor-disassembly evidence is not distributed in the public repo.
    # Current discovery/analysis evidence is generated from the user's local input.
    for evidence in ['diagnostics/function_discovery.json']:
        require((ROOT/evidence).is_file(),'Missing annotation evidence: '+evidence)
    for index in ['exports/INDEX.md','exports/ALL_FUNCTIONS.md','README.md']:
        for link in re.findall(r'\]\(([^)]+)\)',(ROOT/index).read_text()):
            if '://' not in link:require(((ROOT/index).parent/link).is_file(),'Broken Markdown link: '+link)
    for name in ['report/index.html','report/data.js','report/assets/atlas.js','report/assets/atlas.css','projects/KodakC713.gpr']:
        require((ROOT/name).is_file(),'Missing workspace artifact: '+name)
    require(not (ROOT/'projects/KodakC713.lock').exists(),'Project is still locked by another process')
    regressions=read('diagnostics/delay_slot_regressions.json');require(len(regressions)==6 and all(r['completed'] for r in regressions),'Delay-slot regression checks did not pass')
    report={'passed':True,'function_count':len(rows),'decompiled':summary['decompiled'],'failed':summary['failed'],
            'annotation_count':summary['annotation_count'],'stock_sha256':manifest['sha256'],
            'checks':['Pinned stock identity and extracted sections','Saved program mapped bytes and model','All annotation labels/comments and source snapshot hash','Function/assembly/report completeness','No stale generated functions','All Markdown export links','Coverage accounting','Six conditional-delay regressions']}
    (ROOT/'diagnostics/workspace_verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f"Workspace audit passed: {len(rows):,} functions, {summary['annotation_count']} annotations, stock input unchanged.")

if __name__=='__main__':
    try:main()
    except (RuntimeError,OSError,KeyError) as error:raise SystemExit(f'Workspace audit failed: {error}')
