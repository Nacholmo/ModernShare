; Populate the header BEFORE its write, directly from the active capture record.
; Called only for a main 7096320-byte frame, after r16/r17 hold its size/buffer.
; 0x1324fc points to this capture (stock 0x34430 -> 0x33c2c -> RAW writer).
; Preserve photo ID r1 and all callee-saved registers. Other r0..r12 are scratch.
; Capture offsets come from stock 0x54528; exposure clamp from 0xa3a04.
        .include "metadata_offsets.inc"
        .equ BASE, 0x12ff40
        .equ HEADER, 0x1241a0
        .text
        .global start
start:
        push_s blink
        push_s r13
        sub_s sp,sp,8
        st_s r1,[sp,0]
        mov r13,0x1324fc
        ld r13,[r13,0]
        ld r0,[r13,0xb0]
        mov r1,714
        cmp_s r0,r1
        bhs_s exposure_ok
        mov_s r0,r1
exposure_ok:
        mov r12,HEADER+H_EXPOSURE
        st r0,[r12,0]
        ldw r0,[r13,0xb4]
        mov r12,HEADER+H_ISO
        stw r0,[r12,0]
        ldb r2,[r13,0xf2]
        ldw r0,[r13,0xf4]
        mov r1,480
        cmp_s r0,5
        bhi_s aperture_done
        mov r12,BASE+(apertures-start)
        cmp_s r2,0
        beq_s table_ready
        add r12,r12,12
table_ready:
        add1 r12,r12,r0
        ldw r1,[r12,0]
aperture_done:
        mov r12,HEADER+H_FNUMBER
        st r1,[r12,0]
        mov r0,HEADER+H_DATE
        mov_s r1,20
        mov r2,0x127a08
        add r3,r13,0x64
        bl start + (0x116be4 - BASE)
        ld_s r1,[sp,0]
        add_s sp,sp,8
        pop_s r13
        pop_s blink
        j_s [blink]
        .balign 4
apertures:
        ; Stock 0x5457e..0x545ea: flag=0 first row; nonzero second row.
        .short 270,300,340,380,430,480
        .short 480,540,600,670,760,850
        .global hook_end
hook_end:
