; Native UI event callbacks for the repurposed Share screen (ID 0xa8).
; Entry ABI r0=root widget, r1=event, r2=event payload. DNG defaults ON at boot.
        .include "menu_layout.inc"
        .equ BASE,0x1256c0
        .text
        .global start,init,refresh,toggle_dng,hidden_menu,hook_end
start:
        mov r4,r2
        mov r3,r1
        mov r2,r0
        mov_s r0,0
        mov r1,EVENTS
        b start + (0x416f4 - BASE)
init:
        push_s blink
        push_s r13
        mov_s r13,r0
        bl refresh
        mov_s r0,r13
        mov r1,0x4804
        bl start + (0x7c460 - BASE)
        mov_s r1,0
        bl start + (0x8f26c - BASE)
        pop_s r13
        pop_s blink
        mov_s r0,0
        j_s [blink]
refresh:
        push_s blink
        mov r1,0x4804
        bl start + (0x7c460 - BASE)
        cmp_s r0,0
        beq_s refresh_done
        ld_s r0,[r0,0x38]
        mov r1,0x13358c
        ldb_s r1,[r1,0]
        mov r2,DNG_ON
        cmp_s r1,0
        bne_s label_ready
        mov r2,DNG_OFF
label_ready:
        st_s r2,[r0,4]
refresh_done:
        pop_s blink
        mov_s r0,0
        j_s [blink]
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
hidden_menu:
        push_s blink
        mov_s r0,0x3b
        mov_s r1,0
        bl start + (0x7c260 - BASE)
        pop_s blink
        mov_s r0,0
        j_s [blink]
hook_end:
