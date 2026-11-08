; Compose the selected capture film's relative RGB transform with preview CCMs.
; Input to stock 0x62a28: r0=packed destination, r1=3x4 Q16 source.
        .equ BASE,0xebc50
        .equ TRANSFORMS,0x168324
        .text
        .global start,body_end,guard,tail,tail_end,refresh,stock,refresh_end
refresh:
        push_s blink
        push_s r0
        mov r0,0x132904
        ldb_s r0,[r0,0]
        cmp_s r0,1
        bne_s refreshed
        mov r0,0x1334de
        ldb_s r0,[r0,0]
        cmp_s r0,3
        bhs_s refreshed
        bl refresh + (0x62a9c - BASE)
refreshed:
        pop_s r0
        bl refresh + (0x7bfcc - BASE)
        pop_s blink
        j_s [blink]
        .balign 4
stock:
        push_s blink
        bl.d refresh + (0x11ade8 - BASE)
        mov_s r2,r0
        b refresh + (0x62a30 - BASE)
refresh_end:
        .org 0x125c24 - BASE
start:
        mov r2,0x1328ff
        ldb_s r2,[r2,0]
        cmp_s r2,24
        mov.hs r2,0
        mov r3,0x125780
        ldb r2,[r3,r2]
        cmp_s r2,0
        beq stock
        cmp_s r2,4
        bhs stock
        push_s blink
        bl refresh + (0x11adc8 - BASE) ; save r13..r22
        sub_s sp,sp,48
        mov_s r13,r0
        mov_s r14,r1
        sub_s r2,r2,1
        asl r3,r2,4
        asl r2,r2,1
        add r15,r2,r3
        add r15,r15,TRANSFORMS
        mov r16,sp
        mov r22,3
row:
        mov r17,0
column:
        mov r19,r15
        add r20,r14,r17
        mov r18,0
        mov r21,3
inner:
        ldw.x r0,[r19,0]
        add r19,r19,2
        ld r1,[r20,0]
        asr r1,r1,6
        add r20,r20,16
        bl refresh + (0x11b114 - BASE)
        add r18,r18,r0
        sub r21,r21,1
        brne r21,0,inner
        b tail
body_end:
        .org 0x12fe98 - BASE
guard:
        ; Review must show each file's own preview, without another current-film pass.
        mov r2,0x132904
        ldb_s r2,[r2,0]
        cmp_s r2,1
        bne stock
        ; 0x62fc0 already uses the hooked capture CCM: do not apply the film twice.
        cmp blink,0x62ff8
        beq stock
        b start
tail:
        asr r18,r18,6
        st r18,[r16,0]
        add r16,r16,4
        add r17,r17,4
        cmp r17,16
        bne column
        add r15,r15,6
        sub r22,r22,1
        cmp r22,0
        bne row
        mov_s r0,r13
        mov r1,sp
        bl stock
        add_s sp,sp,48
        b refresh + (0x11ae14 - BASE) ; restore r13..r22 (see save helper above)
tail_end:
