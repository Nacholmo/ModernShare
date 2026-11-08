.text
.global start
start:
 ld_s r0,[r13,0x14]
 cmp_s r0,107
 blt_s fallback
 cmp r0,137
 ble_s done
fallback:
 mov_s r0,r13
 mov r1,0x1284ac
 mov_s r2,24
 bl start + (0x54010 - 0xeae58)
done:
 .fill (36-(.-start))/2,2,0x78e0
