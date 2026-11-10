; UI9 Film chooser: native root/list, no changes until OK; saved current tick.
        .include "chooser_layout.inc"
        .equ BASE,0xebc90
        .text
        .global open,dispatch,init,choose,cancel,noop,code_end
open:
        mov r0,CHOOSER_ROOT
        mov_s r1,0
        b open + (0x7bffc - BASE)
        .balign 4
dispatch:
        mov r4,r2
        mov r3,r1
        mov r2,r0
        mov_s r0,0
        mov r1,CHOOSER_EVENTS
        b open + (0x416f4 - BASE)
        .balign 4
init:
        push_s blink
        push_s r13
        mov r0,0x1682d0
        ldb_s r13,[r0,0]
        cmp_s r13,7
        mov.hs r13,0
        mov r1,CHOOSER_ITEMS
        mov_s r2,0
        mov_s r3,7
clear_ticks:
        st_s r2,[r1,0]
        add_s r1,r1,24
        sub_s r3,r3,1
        cmp_s r3,0
        bne_s clear_ticks
        mov r0,CHOOSER_LIST
        mov_s r1,r13
        bl open + (0x8f26c - BASE)
        asl r1,r13,3
        add1 r1,r1,r1
        add r1,r1,CHOOSER_ITEMS
        ; Applied-film mark uses the padded icon gutter, clear of the rail.
        mov r2,0x005a005a
        st_s r2,[r1,0]
        pop_s r13
        pop_s blink
        mov_s r0,0
        j_s [blink]
        .balign 4
choose:
        sub r1,r1,0x5000
        cmp_s r1,7
        bhs_s noop
        push_s blink
        push_s r13
        mov_s r13,r0
        mov r2,0x1682d0
        ldb_s r3,[r2,0]
        cmp_s r1,r3
        beq_s same_film
        stb_s r1,[r2,0]
        ; Existing apply fills the 24-mode map and refreshes capture preview.
        bl open + (0xebffc - BASE)
        bl open + (0xec130 - BASE)
same_film:
        pop_s r13
        pop_s blink
cancel:
        mov_s r0,0xa8
        mov_s r1,0
        b open + (0x7c260 - BASE)
        .balign 4
noop:
        mov_s r0,0
        j_s [blink]
        .balign 8
code_end:
