; Ember row renderer. r16 = focused row, r18 = item; all saved registers preserved.
; Known capture/video rows can have string IDs as their value after native init.
; Share's first two rows use pointer names; all other fixed/pointer-name rows stay stock.
        .equ BASE,0x12fd90
        .equ DRAW,0x78ce0
        .equ STRING,0x8a3c0
        .text
start:
        cmp r6,4
        bne single
        sub r12,r18,0x1681b8
        cmp r12,96
        blo dual
        ld r12,[r18,8]
        sub r12,r12,1
        cmp r12,0x344
        bhs single
        ld r12,[r18,4]
        cmp r12,0x345
        bhs dual
        sub r12,r18,0x150aec
        cmp r12,240
        blo dual
        sub r12,r18,0x169528
        cmp r12,96
        bhs single
dual:
        sub_s sp,sp,32
        st blink,[sp,28]
        st_s r0,[sp,0]
        st_s r1,[sp,4]
        st_s r2,[sp,8]
        st_s r3,[sp,12]
        st r4,[sp,16]
        st r5,[sp,20]
        ld r0,[r18,8]
        cmp r0,0x345
        bhs pointer_name
        bl start + (STRING - BASE)
pointer_name:
        mov r4,r0
        ld_s r0,[sp,0]
        ld_s r1,[sp,4]
        ld_s r2,[sp,8]
        ld_s r3,[sp,12]
        ld r5,[sp,20]
        mov r6,4
        bl start + (DRAW - BASE)
        ld_s r0,[sp,0]
        ld_s r1,[sp,4]
        ld_s r2,[sp,8]
        ld_s r3,[sp,12]
        ld r4,[sp,16]
        mov r5,0x00b1bdc4       ; RGB bytes c4 bd b1: secondary value
        cmp r16,0
        mov.ne r5,0x0060bbf2    ; RGB bytes f2 bb 60: focused value
        sub_s r2,r2,24
        sub r12,r2,224
        cmp r2,224
        add.hi r0,r0,r12
        mov.hi r2,224           ; bound long album values to the right-hand column
        mov r6,6
        bl start + (DRAW - BASE)
        ld blink,[sp,28]
        j.d [blink]
        add_s sp,sp,32
single:
        b start + (DRAW - BASE)
code_end:
