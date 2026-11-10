; UI8: native brightness shortcut, saved Review boost and hardware-only override.
; Code occupies the retired image-1 stream and the previous custom Share code.
        .include "review_layout.inc"
        .equ BASE,0x125520
        .equ OPTION,0x1683a8
        .equ RETURN_ROW,0x1683a9
        .equ MODE,0x132904
        .equ NORMAL_BRIGHTNESS,0x13295f
        .text
        .global start,init,refresh,toggle_dng,open_brightness,toggle_review
        .global mode_set,backlight,refresh_backlight,brightness_init,code_end
start:
        mov r4,r2
        mov r3,r1
        mov r2,r0
        mov_s r0,0
        mov r1,0x1682d4
        b start + (0x416f4 - BASE)
        .balign 4
init:
        push_s blink
        push_s r13
        mov_s r13,r0
        bl refresh
        mov_s r0,r13
        mov r1,0x4804
        bl start + (0x7c460 - BASE)
        mov r2,RETURN_ROW
        ldb_s r1,[r2,0]
        mov_s r3,0
        stb_s r3,[r2,0]
        cmp_s r1,0
        mov.ne r1,2
        bl start + (0x8f26c - BASE)
        pop_s r13
        pop_s blink
        mov_s r0,0
        j_s [blink]
        .balign 4
refresh:
        push_s blink
        mov r1,0x4804
        bl start + (0x7c460 - BASE)
        cmp_s r0,0
        beq refresh_done
        ld_s r0,[r0,0x38]
        mov r1,0x13358c
        ldb_s r1,[r1,0]
        mov r2,DNG_OFF
        cmp_s r1,0
        mov.ne r2,DNG_ON
        st_s r2,[r0,28]
        mov r1,0x1682d0
        ldb_s r1,[r1,0]
        cmp_s r1,7
        mov.hs r1,0
        mov r2,0x16832c
        ld.as r1,[r2,r1]
        st_s r1,[r0,4]
        mov r1,NORMAL_BRIGHTNESS
        ldb_s r1,[r1,0]
        mov r2,0x1e0
        cmp_s r1,1
        mov.eq r2,0x1e1
        st_s r2,[r0,52]
        mov r1,OPTION
        ldb_s r1,[r1,0]
        mov r2,REVIEW_NORMAL
        cmp_s r1,0
        mov.ne r2,0x1e1
        st_s r2,[r0,76]
refresh_done:
        pop_s blink
        mov_s r0,0
        j_s [blink]
        .balign 4
toggle_dng:
        push_s blink
        mov r12,0x13358c
        ldb r1,[r12,0]
        xor r1,r1,1
        stb r1,[r12,0]
        bl start + (0x7bfcc - BASE)
        pop_s blink
        mov_s r0,0
        j_s [blink]
        .balign 4
open_brightness:
        push_s blink
        mov r1,RETURN_ROW
        mov_s r0,1
        stb_s r0,[r1,0]
        mov_s r0,0xa8
        bl start + (0x3c998 - BASE)
        pop_s blink
        mov_s r0,0x9e
        mov_s r1,0
        b start + (0x7c260 - BASE)
        .balign 4
toggle_review:
        push_s blink
        push_s r13
        mov_s r13,r0
        mov r2,OPTION
        ldb_s r1,[r2,0]
        xor r1,r1,1
        stb_s r1,[r2,0]
        bl start + (0xec130 - BASE)
        bl refresh_backlight
        mov_s r0,r13
        bl start + (0x7bfcc - BASE)
        pop_s r13
        pop_s blink
        mov_s r0,0
        j_s [blink]
        .balign 4
mode_set:
        ; Replay stock 3c4e0, then apply the active preference for the new mode.
        push_s blink
        mov r1,MODE
        stb_s r0,[r1,0]
        mov r1,RETURN_ROW
        mov_s r2,0
        stb_s r2,[r1,0]
        cmp_s r0,2
        blne start + (0x7b860 - BASE)
        push_s r0
        mov r1,MODE
        ldb_s r1,[r1,0]
        cmp_s r1,2
        beq_s mode_needs_load
        cmp_s r1,4
        bne mode_loaded
mode_needs_load:
        ; Review-button startup can precede the capture-init loader. Root zero
        ; deliberately suppresses repaint; load_once/apply safely accept it.
        mov r1,0x16839c
        ld_s r1,[r1,0]
        cmp_s r1,0
        bne mode_loaded
        mov_s r0,0
        bl start + (0xebf2c - BASE)
mode_loaded:
        mov r1,OPTION
        ldb_s r1,[r1,0]
        cmp_s r1,0
        blne refresh_backlight
        pop_s r0
        pop_s blink
        j_s [blink]
        .balign 4
backlight:
        ; Do not write NORMAL_BRIGHTNESS: only override the physical request.
        mov r1,OPTION
        ldb_s r1,[r1,0]
        cmp_s r1,0
        beq backlight_original
        mov r1,MODE
        ldb_s r1,[r1,0]
        cmp_s r1,2
        beq_s force_high
        cmp_s r1,4
        bne_s backlight_original
force_high:
        mov_s r0,1
backlight_original:
        push_s blink
        bl start + (0x11ade8 - BASE)
        b start + (0x40246 - BASE)
        .balign 4
refresh_backlight:
        mov r0,NORMAL_BRIGHTNESS
        ldb_s r0,[r0,0]
        b start + (0x40240 - BASE)
        .balign 4
brightness_init:
        ; Native OK uses each item's +0x10 screen target, independently of
        ; the Menu/Cancel handler. Set both targets for this opening context.
        mov_s r3,0x9c
        mov r4,RETURN_ROW
        ldb r5,[r4,0]
        cmp r5,0
        mov.ne r3,0xa8
        cmp r2,0x168370
        mov.eq r3,0xa8
        mov r4,0x166a68
        stw r3,[r4,0]
        stw r3,[r4,24]
        cmp_s r3,0xa8
        bne_s brightness_original_init
        mov r4,0x132919
        stb r3,[r4,0]
        mov r4,RETURN_ROW
        mov_s r3,1
        stb r3,[r4,0]
brightness_original_init:
        b start + (0xeab28 - BASE)
code_end:
