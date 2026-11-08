#!/usr/bin/env python3
"""Derive a Kodak-specific language without altering pinned upstream sources."""
import hashlib
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
LANG=ROOT/'tools/ghidra_12.2_PUBLIC/Ghidra/Processors/ARC/data/languages'

def build():
    sleigh=(LANG/'ARCompact.slaspec').read_text()
    assert 'define space auxregs type=ram_space size=2;' in sleigh
    sleigh=sleigh.replace('define space auxregs type=ram_space size=2;',
        '# Kodak ISP uses auxiliary register indices above 0xffff.\ndefine space auxregs type=ram_space size=4;')
    assert sleigh.count('op4_c_src:2 << 2:2')==2
    sleigh=sleigh.replace('op4_c_src:2 << 2:2','op4_c_src << 2:4')
    sleigh=re.sub(r'(\*\[auxregs\]:4 \(0x[0-9a-f]+):2',r'\1:4',sleigh)
    # A local branch to an end label in a delay slot produces invalid relative p-code
    # in six stock functions. Preserve the instruction's exact predicate without a branch:
    # Z=1 keeps the register; Z=0 clears it; flags are unchanged.
    original=""":sub_s.ne s_rb, s_rb_ is s_major_opcode=0x0f & s_u5=0 & s_sub_opcode_b5b6b7=6 & s_rb & s_rb_ {
  if (Z) goto <next>;
  s_rb = 0;
<next>
}"""
    replacement=""":sub_s.ne s_rb, s_rb_ is s_major_opcode=0x0f & s_u5=0 & s_sub_opcode_b5b6b7=6 & s_rb & s_rb_ {
  s_rb = s_rb * zext(Z);
}"""
    assert original in sleigh
    sleigh=sleigh.replace(original,replacement)
    original="""  :sub.^l_cc_not_value op4_a, op4_b_src, op4_c_src is (l_sub_opcode6=0x02 & l_flag=0 & l_op_format=3 & l_cc_not_value & op4_a) ... & op4_b_src & op4_c_src {
    if (l_cc_not_value) goto <next>;
    op4_a = op4_b_src - op4_c_src;
  <next>
  }"""
    replacement="""  :sub.^l_cc_not_value op4_a, op4_b_src, op4_c_src is (l_sub_opcode6=0x02 & l_flag=0 & l_op_format=3 & l_cc_not_value & op4_a) ... & op4_b_src & op4_c_src {
    local keep:4 = zext(l_cc_not_value);
    op4_a = (1:4 - keep) * (op4_b_src - op4_c_src) + keep * op4_a;
  }"""
    assert original in sleigh
    sleigh=sleigh.replace(original,replacement)
    pspec=(LANG/'ARCompact.pspec').read_text().replace('last="0xFFFF"','last="0xFFFFFFFF"')
    cspec=(LANG/'ARCompact.cspec').read_text()
    # r24 is used as a saved register by this firmware's shared prologues.
    assert '<register name="r24"/>' not in cspec
    cspec=cspec.replace('<register name="r25"/>','<register name="r24"/>\n        <register name="r25"/>')
    fixups=[]
    helpers=[]
    for high in range(13,27):
        saved=list(range(high,12,-1))
        save_addr=0x11adec-(high-13)*4
        restore_addr=0x11ae5c-(high-13)*8
        reg=lambda n:'gp' if n==26 else f'r{n}'
        lines=[]
        for n in saved:
            lines += ['sp = sp - 4;', f'*:4 sp = {reg(n)};']
        for kind,address,body in [('save',save_addr,lines),('restore',restore_addr,
            [f'{reg(n)} = *:4 (sp + {(n-13)*4});' for n in saved]+[
             f'sp = sp + {len(saved)*4};','blink = *:4 sp;','sp = sp + 4;','r12 = 4;'])]:
            name=f'kodak_{kind}_r13_r{high}'
            fixups.append(f'  <callfixup name="{name}"><pcode><body><![CDATA[\n'+
                          '\n'.join('    '+line for line in body)+'\n  ]]></body></pcode></callfixup>')
            helpers.append({'address':f'0x{address:08x}','name':name,'kind':kind,
                'registers':[reg(n) for n in saved],
                'stack_delta':-len(saved)*4 if kind=='save' else (len(saved)+1)*4,
                'evidence':'GNU binutils 2.43 disassembly of local stock code; shared suffix helpers at 0x11adb8..0x11ae9a. Restore pops saved blink as well as registers.'})
    cspec=cspec.replace('</compiler_spec>','\n'.join(fixups)+'\n</compiler_spec>')
    ldefs='''<?xml version="1.0" encoding="UTF-8"?>
<language_definitions>
  <language processor="ARCompact" endian="little" size="32" variant="kodak" version="1.0"
      slafile="KodakARCompact.sla" processorspec="KodakARCompact.pspec" id="ARCompact:LE:32:kodak">
    <description>Kodak C713 ARCompact: 32-bit auxiliary addresses and MetaWare shared helpers</description>
    <compiler name="Kodak MetaWare helper model" spec="KodakARCompact.cspec" id="default"/>
  </language>
</language_definitions>
'''
    files={'KodakARCompact.slaspec':sleigh,'KodakARCompact.pspec':pspec,
           'KodakARCompact.cspec':cspec,'KodakARCompact.ldefs':ldefs}
    for name,text in files.items():
        target=LANG/name
        if not target.exists() or target.read_text()!=text:target.write_text(text)
    (ROOT/'annotations/compiler_helpers.json').write_text(json.dumps(helpers,indent=2)+'\n')
    (ROOT/'patches/processor_model.json').write_text(json.dumps({
        'language':'ARCompact:LE:32:kodak','upstream':'ARCompact (PR 3006)',
        'changes':['Widen auxregs address space and lr/sr address expressions to 32 bits.',
                   'Mark full auxiliary range volatile.',
                   'Preserve r24 in the default ABI.',
                   'Model 14 shared save and 14 shared restore helpers with call-fixup p-code.',
                   'Use equivalent branchless semantics for non-flag-setting conditional sub and sub_s.ne in delayed branches.'],
        'generated_files_sha256':{name:hashlib.sha256(text.encode()).hexdigest() for name,text in files.items()},
        'scope':'Static analysis model only; no firmware bytes changed. No claim of full CPU or MetaWare ABI emulation.'},indent=2)+'\n')
    print('Generated Kodak ARCompact model and',len(helpers),'helper fixups')

if __name__=='__main__':build()
