.text
.global start
 nop_s
start:
 mov_s r0,r1
 mov r1,0x1284ac
 mov_s r2,24
 bl start + (0x54010 - 0xdc45a)
 nop_s
