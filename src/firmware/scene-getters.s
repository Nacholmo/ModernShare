; UI9 restores the original classic-film getter logic at a separate code address.
; Scene film presets for Kodak C713/CD703 fw 1.30.
; Placed at RAM 0xebd58 in the reclaimed legacy Share region. Two entry points
; replace the colour-matrix getters
; that the capture code calls for every photo (entered with a plain branch, so blink is
; still the getter caller's return address):
;   0xaf508 GetCCM(n):  r0 = illuminant 0..2 -> pointer to a 3x4 int32 Q16 CCM
;   0xaf514 GetYmat(m): r0 = colour mode (3 = B&W, 4 = sepia) -> pointer to the YCbCr matrix
; If the current capture mode (byte 0x1328ff, 0..23) has a film in FILMTAB (1..n), the
; film's own matrices are returned instead. Film k (1-based) = 0xC0 bytes at
; FILMS + (k-1)*0xC0: CCM 0, CCM 1, CCM 2, Ymat (0x30 bytes each).
; Uses r0, r1 and r2 (r2 saved); the stock getters use r0 and r1.
        .equ BASE,    0x125600
        .equ MODEB,   0x1328ff
        .equ FILMTAB, 0x125780
        .equ FILMS,   0x1257a0
        .equ CCMARR,  0x197868          ; stock: struct 0x197844 + 0x24
        .equ PIPE,    0x197844

; r1 = FILMTAB[mode] - 1, or -1 when the mode has no film
        .macro  FILM
        mov     r1, MODEB
        ldb     r1, [r1]
        cmp     r1, 24
        mov.hs  r1, 0                   ; out of range: mode 0 (never has a film)
        add     r1, r1, FILMTAB
        ldb     r1, [r1]
        sub     r1, r1, 1
        .endm

; Diagnostic log (assemble with --defsym DIAG=1): u32 count at LOGCNT, then a ring of 32
; entries {u32 caller (blink), u32 r0 argument, u32 capture mode, u32 tag 1=CCM 2=Ymat}.
        .equ LOGCNT,  0x125a00
        .equ LOG,     0x125a10
        .macro  LOGCALL tag
        .ifdef  DIAG
        push_s  r3
        mov     r2, LOGCNT
        ld      r3, [r2]
        add     r3, r3, 1
        st      r3, [r2]
        and     r3, r3, 31
        asl     r3, r3, 4
        add     r3, r3, LOG
        st      blink, [r3]
        st      r0, [r3, 4]
        mov     r2, MODEB
        ldb     r2, [r2]
        st      r2, [r3, 8]
        mov     r2, \tag
        st      r2, [r3, 12]
        pop_s   r3
        .endif
        .endm

        .text
        .global ccm,ymat,getters_end
ccm:    push_s  r2
        LOGCALL 1
        cmp     r0, 3
        bhs     ccm_stock
        FILM
        brlt    r1, 0, ccm_stock
        asl     r1, r1, 2
        add     r1, r1, r0              ; k = 4*(film-1) + n
        b       addr
ccm_stock:
        pop_s   r2
        mov     r1, CCMARR
        ld.as   r0, [r1, r0]
        j_s     [blink]

ymat:   push_s  r2
        LOGCALL 2
        FILM
        brlt    r1, 0, y_stock
        asl     r1, r1, 2
        add     r1, r1, 3               ; k = 4*(film-1) + 3
        b       addr
y_stock:
        pop_s   r2
        mov     r1, PIPE
        breq    r0, 3, y_bw
        breq    r0, 4, y_sep
        ld      r0, [r1, 0x38]
        j_s     [blink]
y_bw:   ld      r0, [r1, 0x3c]
        j_s     [blink]
y_sep:  ld      r0, [r1, 0x40]
        j_s     [blink]

; r0 = FILMS + k*0x30 (k in r1); restore r2 and return to the getter's caller
addr:   mov     r2, 0xebe6c
        ld.as   r0, [r2,r1]
        pop_s   r2
        j_s     [blink]
getters_end:
