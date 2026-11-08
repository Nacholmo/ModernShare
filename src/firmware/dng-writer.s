; Direct DNG metadata timing fix, based on v1 for C713/CD703 firmware 1.30, entered instead of 0x67898.
; r0 kind (0 main, 1 black), r1 photo ID, r2 sensor buffer, r3 byte count.
; Only main frames with exactly 3072*2310 bytes use the DNG path. Other calls
; execute the displaced stock prologue and continue at 0x6789e unchanged.
; File API: open(path,1,1,&handle), write(handle,ptr,count,0,&written), close(&handle).
; Returns 0 on success, the first nonzero file error, or -1 for a short write.
; Registers r13..r17 and blink use the stock save helper and explicit restoration.
; Stack: +0 handle, +4 filename[128], +132 written, +136 error, +140 spare.

        .equ BASE,       0x125a00
        .equ HEADER,     0x1241a0
        .equ HEADER_LEN, 1536
        .equ PIXELS,     7096320
        .equ LOG,        0x125cc0
        .text
        .global start
start:
        cmp     r0,0
        bne     stock
        cmp     r3,PIXELS
        bne     stock
        b       native
stock:
        push_s  blink
        bl      start + (0x11addc - BASE)
        b       start + (0x6789e - BASE)

native:
        push_s  blink
        bl      start + (0x11addc - BASE)
        sub     sp,sp,144
        mov     r17,r2
        mov     r16,r3
        bl      start + (0x12ff40 - BASE) ; same-shot EXIF BEFORE header write
        mov     r12,LOG
        mov     r2,0x31474e44          ; 'DNG1' in little-endian memory
        st      r2,[r12,0]
        ld      r2,[r12,4]
        add     r2,r2,1
        st      r2,[r12,4]
        mov     r2,1
        st      r2,[r12,8]
        mov     r2,0
        st      r2,[r12,12]
        st      r2,[r12,20]
        st      r2,[r12,24]
        st      r2,[r12,28]
        st      r16,[r12,16]
        st      r17,[r12,32]
        st      r2,[sp,136]
        st      r2,[sp,0]
        add     r13,sp,4
        mov     r0,r1
        mov     r1,r13
        bl      start + (0x4b724 - BASE) ; construct the normal JPEG path
        cmp     r0,0
        bne     unopened_error
        mov     r0,r13
        bl      start + (0x116930 - BASE) ; strlen
        cmp     r0,12
        blo     invalid_path
        cmp     r0,127
        bhi     invalid_path
        add     r2,r13,r0
        sub     r2,r2,12
        mov     r1,0x43               ; CCDI replaces 100_
        stb     r1,[r2,0]
        stb     r1,[r2,1]
        mov     r1,0x44
        stb     r1,[r2,2]
        mov     r1,0x49
        stb     r1,[r2,3]
        add     r2,r13,r0
        mov     r1,0x44               ; .DNG replaces .JPG
        stb     r1,[r2,-3]
        mov     r1,0x4e
        stb     r1,[r2,-2]
        mov     r1,0x47
        stb     r1,[r2,-1]
        mov     r0,r13
        mov     r1,1
        mov     r2,1
        mov     r3,sp
        bl      start + (0x73224 - BASE)
        cmp     r0,0
        bne     unopened_error

        mov     r13,LOG
        mov     r0,2
        st      r0,[r13,8]            ; open succeeded
        ld      r0,[sp,0]
        mov     r1,HEADER
        mov     r2,HEADER_LEN
        mov     r3,0
        st      r3,[sp,132]
        add     r4,sp,132
        bl      start + (0x73240 - BASE)
        ld      r1,[sp,132]
        st      r1,[r13,20]
        cmp     r0,0
        bne     opened_error
        cmp     r1,HEADER_LEN
        bne     short_write

        mov     r0,3
        st      r0,[r13,8]            ; header completed
        ld      r0,[sp,0]
        mov     r1,r17
        mov     r2,r16
        mov     r3,0
        st      r3,[sp,132]
        add     r4,sp,132
        bl      start + (0x73240 - BASE)
        ld      r1,[sp,132]
        st      r1,[r13,24]
        cmp     r0,0
        bne     opened_error
        cmp     r1,r16
        bne     short_write
        mov     r0,4
        st      r0,[r13,8]            ; payload completed
        b       close_file
short_write:
        mov     r0,-1
opened_error:
        st      r0,[sp,136]
        st      r0,[r13,12]
close_file:
        mov     r0,sp
        bl      start + (0x7324c - BASE)
        st      r0,[r13,28]
        ld      r1,[sp,136]
        cmp     r1,0
        bne     first_error
        cmp     r0,0
        bne     close_error
        mov     r2,5
        st      r2,[r13,8]            ; full success, file closed
        b       done
close_error:
        st      r0,[r13,12]
        b       done
first_error:
        mov     r0,r1
        b       done
invalid_path:
        mov     r0,-1
unopened_error:
        mov     r12,LOG
        st      r0,[r12,12]
done:
        add     sp,sp,144
        ld      r13,[sp,0]
        ld      r14,[sp,4]
        ld      r15,[sp,8]
        ld      r16,[sp,12]
        ld      r17,[sp,16]
        ld      blink,[sp,20]
        add     sp,sp,24
        j       [blink]
        .global hook_end
hook_end:
