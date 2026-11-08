#!/usr/bin/env python3
"""Search the saved export, resolve addresses, and inspect calls without Ghidra."""
import argparse
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('query',help='Function name, hex RAM address, or annotation text')
    parser.add_argument('--assembly',action='store_true',help='Print assembly instead of pseudocode')
    parser.add_argument('--calls',action='store_true',help='Show direct callers and callees')
    parser.add_argument('--limit',type=int,default=20)
    args=parser.parse_args();rows=json.loads((ROOT/'exports/function_index.json').read_text())
    query=args.query.lower().removeprefix('ram:');address=None
    try:address=int(query,16)
    except ValueError:pass
    matches=[row for row in rows if query in (row['name']+' '+(row.get('comment') or '')).lower() or
             (address is not None and any(int(r['start'],16)<=address<=int(r['end'],16) for r in row['body_ranges']))]
    if not matches:
        symbols=json.loads((ROOT/'exports/annotations.json').read_text())
        found=[s for s in symbols if query in (s.get('name','')+' '+s['address']+' '+s['comment']).lower() or (address is not None and int(s['address'],16)==address)]
        for symbol in found[:args.limit]:print(json.dumps(symbol,indent=2))
        if not found:parser.exit(1,'No matching function or annotation.\n')
        return
    for row in matches[:args.limit]:
        print(f"{row['address']} {row['name']} · {row['body_bytes']} bytes · {row['status']}")
    if len(matches)!=1:
        if len(matches)>args.limit:print(f'… {len(matches)-args.limit} more matches')
        return
    row=matches[0]
    if address is not None:
        manifest=json.loads((ROOT/'input/manifest.json').read_text())
        for section in manifest['sections']:
            if section['mapped'] and section['ram_address']<=address<section['ram_address']+section['size']:
                print(f"Firmware file offset: 0x{section['file_offset']+address-section['ram_address']:x} ({section['name']})")
    if args.calls:
        by_address={r['address']:r for r in rows};edges=json.loads((ROOT/'exports/call_graph.json').read_text())
        for title,selected,key in [('Callers',[e for e in edges if e['to']==row['address']],'from'),('Callees',row['calls'],'to')]:
            print(title+':')
            for edge in selected:print(' ',edge[key],by_address.get(edge[key],{}).get('name','(unresolved)'), '@',edge['site'])
    else:
        suffix='.asm' if args.assembly else '.c';path=ROOT/'exports/functions'/(row['export_stem']+suffix)
        if path.exists():print(path.read_text())
        else:print('No pseudocode available; use --assembly.')

if __name__=='__main__':main()
