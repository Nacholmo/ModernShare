; Wrap the capture JPEG EXIF builder, leaving its inputs/result/ABI intact.
; Entry replaces mov_s r1,r14; bl_s 0xa3a04 at 0xa4290 with a 32-bit call.
; r14 is the JPEG metadata struct. Copy fields AFTER the stock builder, so its
; exposure-time clamp is reflected exactly. Only mutable values in our header change.
; Metadata struct: +0xc struct tm, +0x48 exposure us, +0x4c f-number*100, +0x60 ISO.
        .include "metadata_offsets.inc"
        .equ BASE, 0x12ff40
        .equ HEADER, 0x1241a0
        .text
        .global start
start:
        push_s blink
        push_s r13
        push_s r15
        sub_s sp,sp,4
        mov_s r13,r14
        mov_s r15,r0
        ; Clear prior values first: a failed stock build must never leak previous-shot EXIF.
        mov r12,HEADER+H_EXPOSURE
        mov_s r2,0
        st r2,[r12,0]
        st r2,[r12,H_FNUMBER-H_EXPOSURE]
        mov r12,HEADER+H_ISO
        stw r2,[r12,0]
        ; Unknown date uses the TIFF/EXIF unknown-date string from the template.
        ; The formatter always writes all 20 bytes on a successful build.
        mov r0,HEADER+H_DATE
        mov_s r1,20
clear_date:
        stb r2,[r0,0]
        add_s r0,r0,1
        sub_s r1,r1,1
        cmp_s r1,0
        bne_s clear_date
        mov_s r0,r15
        mov_s r1,r14
        bl start + (0xa3a04 - BASE)
        mov_s r15,r0
        cmp_s r0,0
        beq_s done
        mov r12,HEADER+H_EXPOSURE
        ld r0,[r13,0x48]
        st r0,[r12,0]
        ld r0,[r13,0x4c]
        st r0,[r12,H_FNUMBER-H_EXPOSURE]
        ld r0,[r13,0x60]
        mov r12,HEADER+H_ISO
        stw r0,[r12,0]
        mov r0,HEADER+H_DATE
        mov_s r1,20
        mov r2,0x127a08
        add r3,r13,0xc
        bl start + (0x116be4 - BASE)
done:
        mov_s r0,r15
        add_s sp,sp,4
        pop_s r15
        pop_s r13
        pop_s blink
        j_s [blink]
        .global hook_end
hook_end:
