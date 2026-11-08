; Four-row native Share menu. Existing scene matrix table is the live film map.
; Sparse object: film action in DNG-header padding, menu in its existing allocation,
; hidden-menu/no-op in the padding immediately after the three film matrices.
        .include "menu_layout.inc"
        .equ BASE,0x1247a0
        .text
        .global film_next,start,init,refresh,toggle_dng,hidden_menu,version,film_end,menu_end,tail_end
film_next:
        push_s blink
        push_s r0
        mov r3,FILM_STATE
        ldb_s r1,[r3,0]
        add_s r1,r1,1
        cmp_s r1,7
        mov.hs r1,0
        stb_s r1,[r3,0]
        mov_s r3,r1
        sub_s r1,r1,1
        cmp_s r3,0
        mov.eq r1,0
        mov r2,0x125780
        mov_s r0,24
fill:
        stb_s r1,[r2,0]
        add_s r2,r2,1
        sub_s r0,r0,1
        brne r0,0,fill
        cmp_s r3,0
        bne_s film_refresh
        mov_s r1,2
        stb r1,[r2,-15]  ; Children, mode 9
        mov_s r1,3
        stb r1,[r2,-7]   ; Museum, mode 17
        mov_s r1,1
        stb r1,[r2,-2]   ; Sunset, mode 22
film_refresh:
        pop_s r0
        bl film_next + (0xebc50 - BASE)
        pop_s blink
        mov_s r0,0
        j_s [blink]
film_end:
        .org 0x1256c0 - BASE
start:
        mov r4,r2
        mov r3,r1
        mov r2,r0
        mov_s r0,0
        mov r1,EVENTS
        b film_next + (0x416f4 - BASE)
init:
        push_s blink
        push_s r13
        mov_s r13,r0
        bl refresh
        mov_s r0,r13
        mov r1,0x4804
        bl film_next + (0x7c460 - BASE)
        mov_s r1,0
        bl film_next + (0x8f26c - BASE)
        pop_s r13
        pop_s blink
        mov_s r0,0
        j_s [blink]
refresh:
        push_s blink
        mov r1,0x4804
        bl film_next + (0x7c460 - BASE)
        cmp_s r0,0
        beq_s refresh_done
        ld_s r0,[r0,0x38]
        mov r1,0x13358c
        ldb_s r1,[r1,0]
        mov r2,DNG_ON
        cmp_s r1,0
        bne_s dng_ready
        mov r2,DNG_OFF
dng_ready:
        st_s r2,[r0,28]
        mov r1,FILM_STATE
        ldb_s r1,[r1,0]
        cmp_s r1,7
        mov.hs r1,0
        mov r2,FILM_LABELS
        ld.as r1,[r2,r1]
        st_s r1,[r0,4]
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
        bl film_next + (0x7bfcc - BASE)
        pop_s blink
        mov_s r0,0
        j_s [blink]
menu_end:
        .org 0x1259e0 - BASE
hidden_menu:
        push_s blink
        mov_s r0,0x3b
        mov_s r1,0
        bl film_next + (0x7c260 - BASE)
        pop_s blink
version:
        mov_s r0,0
        j_s [blink]
tail_end:
