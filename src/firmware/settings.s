; SD-backed DNG/film preferences. A/B records: magic, config, generation, ~xor.
; Defaults: DNG OFF, By mode. Write inactive slot, commit RAM state after close.
        .include "settings_layout.inc"
        .equ BASE,0xebecc
        .text
        .global capture_init,menu_init,changed,load_once,save,read_slot,validate,apply,status,code_end
capture_init:
        push_s blink
        bl capture_init + (0x11ade8 - BASE)
        mov_s r13,r0
        bl capture_init + (0xcabfc - BASE)
        mov_s r14,r0
        cmp_s r0,0
        bne_s capture_done
        mov_s r0,r13
        bl load_once
capture_done:
        mov_s r0,r14
        b capture_init + (0x11ae54 - BASE)
        .balign 4
menu_init:
        push_s blink
        push_s r13
        mov_s r13,r0
        bl load_once
        mov_s r0,r13
        pop_s r13
        pop_s blink
        b capture_init + (0x1256da - BASE)
        .balign 4
changed:
        push_s blink
        push_s r13
        mov_s r13,r0
        cmp r1,0x5000
        beq_s changed_film
        bl capture_init + (0x125758 - BASE)
        b_s changed_save
changed_film:
        bl capture_init + (0x1247a0 - BASE)
changed_save:
        bl save
        mov_s r0,r13
        bl capture_init + (0x7bfcc - BASE)
        pop_s r13
        pop_s blink
        mov_s r0,0
        j_s [blink]
        .balign 4
load_once:
        push_s blink
        bl capture_init + (0x11addc - BASE)
        sub_s sp,sp,32
        mov_s r13,r0
        mov r17,STATE
        ld r0,[r17,0]
        brne r0,0,load_done
        mov_s r0,1
        st r0,[r17,0]
        mov r0,PATH0
        mov r1,sp
        bl read_slot
        mov_s r14,r0
        mov r0,PATH1
        add r1,sp,16
        bl read_slot
        mov_s r15,r0
        or r0,r14,r15
        breq r0,0,load_default
        mov r16,sp
        mov_s r2,0
        breq r14,0,load_second
        breq r15,0,load_selected
        ld_s r0,[sp,24]
        ld_s r1,[sp,8]
        sub_s r0,r0,r1
        cmp_s r0,0
        ble_s load_selected
load_second:
        add r16,sp,16
        mov_s r2,1
load_selected:
        ld r0,[r16,4]
        and r1,r0,1
        mov r3,0x13358c
        stb_s r1,[r3,0]
        lsr r0,r0,8
        and r0,r0,255
        mov r3,0x1682d0
        stb_s r0,[r3,0]
        ld r0,[r16,8]
        st r0,[r17,4]
        st r2,[r17,8]
        mov r0,LABEL_LOADED
        bl status
        b_s load_apply
load_default:
        mov r0,LABEL_DEFAULT
        bl status
load_apply:
        mov_s r0,r13
        bl apply
load_done:
        add_s sp,sp,32
        mov_s r0,0
        b capture_init + (0x11ae3c - BASE)
        .balign 4
apply:
        ; Replay the existing table-fill/preview refresh without advancing the film.
        mov r1,0x1682d0
        ldb_s r1,[r1,0]
        push_s blink
        push_s r0
        b capture_init + (0x1247b8 - BASE)
        .balign 4
status:
        mov r1,0x168204
        st_s r0,[r1,0]
        j_s [blink]
        .global first_end
first_end:
        .org 0xec088 - BASE
read_slot:
        push_s blink
        bl capture_init + (0x11ade8 - BASE)
        sub_s sp,sp,8
        mov_s r13,r1
        mov_s r1,0
        mov_s r2,0
        mov r3,sp
        st_s r1,[sp,4]
        bl capture_init + (0x73224 - BASE)
        brne r0,0,read_invalid
        ld_s r0,[sp,0]
        mov_s r1,r13
        mov_s r2,16
        mov_s r3,1
        add r4,sp,4
        bl capture_init + (0x73234 - BASE)
        mov_s r14,r0
        ld_s r0,[sp,4]
        cmp_s r0,16
        mov.ne r14,-1
        mov r0,sp
        bl capture_init + (0x7324c - BASE)
        or r0,r0,r14
        brne r0,0,read_invalid
        mov_s r0,r13
        bl validate
        b_s read_done
read_invalid:
        mov_s r0,0
read_done:
        add_s sp,sp,8
        b capture_init + (0x11ae54 - BASE)
        .balign 4
validate:
        ld_s r1,[r0,0]
        cmp r1,0x444f4d4b
        bne_s invalid
        ld_s r2,[r0,4]
        ld_s r3,[r0,8]
        xor r1,r1,r2
        xor r1,r1,r3
        ld_s r3,[r0,12]
        xor r1,r1,r3
        cmp r1,-1
        bne_s invalid
        lsr r1,r2,8
        and r1,r1,255
        cmp_s r1,7
        bhs_s invalid
        and r2,r2,0xfffff8fe
        cmp r2,0x10000
        mov_s r0,0
        mov.eq r0,1
        j_s [blink]
invalid:
        mov_s r0,0
        j_s [blink]
        .balign 4
save:
        push_s blink
        bl capture_init + (0x11addc - BASE)
        sub_s sp,sp,24
        mov r13,STATE
        ld_s r14,[r13,4]
        add_s r14,r14,1
        ld_s r15,[r13,8]
        xor r15,r15,1
        mov r0,0x444f4d4b
        st_s r0,[sp,8]
        mov r1,0x1682d0
        ldb_s r1,[r1,0]
        asl_s r1,r1,8
        mov r2,0x13358c
        ldb_s r2,[r2,0]
        or r1,r1,r2
        or r1,r1,0x10000
        st_s r1,[sp,12]
        st_s r14,[sp,16]
        xor r2,r0,r1
        xor r2,r2,r14
        not r2,r2
        st_s r2,[sp,20]
        mov r0,PATH0
        cmp_s r15,0
        mov.ne r0,PATH1
        mov_s r1,1
        mov_s r2,1
        mov r3,sp
        mov r16,0
        st r16,[sp,4]
        bl capture_init + (0x73224 - BASE)
        brne r0,0,save_failed
        ld_s r0,[sp,0]
        add r1,sp,8
        mov_s r2,16
        mov_s r3,0
        add r4,sp,4
        bl capture_init + (0x73240 - BASE)
        mov r16,r0
        brne r16,0,save_close
        ld_s r0,[sp,4]
        cmp_s r0,16
        mov.ne r16,-1
save_close:
        mov r0,sp
        bl capture_init + (0x7324c - BASE)
        or r0,r0,r16
        brne r0,0,save_failed
        st_s r14,[r13,4]
        st_s r15,[r13,8]
        mov r0,LABEL_SAVED
        b_s save_status
save_failed:
        mov r0,LABEL_ERROR
save_status:
        bl status
        add_s sp,sp,24
        b capture_init + (0x11ae3c - BASE)
code_end:
