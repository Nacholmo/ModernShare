; Full-screen boot image guard for Kodak C713/CD703 fw 1.30.
; Entered from a branch replacing the first 4 bytes of UI DrawImage 0x789f8
; (sub_s sp,sp,8; push_s blink). r0 = x, r1 = y, r2 = image id.
; Tile ids 246..250 read their RLE data from the English language buffer
; (0x183330 + 0x5c00). If the magic word is not there (other language loaded,
; or not loaded yet) the id is replaced by 0, which DrawImage ignores safely.
        .equ BASE,   0x12ff00
        .equ MAGICP, 0x188f30
        .equ MAGIC,  0x534f4c43         ; "CLOS"
        .text
start:  sub     r12, r2, 246
        cmp     r12, 5
        bhs     1f
        mov     r12, MAGICP
        ld      r12, [r12]
        mov     r11, MAGIC
        cmp     r12, r11
        mov.ne  r2, 0
1:      sub_s   sp, sp, 8
        push_s  blink
        b       start + (0x789fc - BASE)
