; startup.s - arranque multiboot minimo SOLO para la prueba de apagado
[bits 32]
section .multiboot
align 4
dd 0x1BADB002
dd 0x00000003
dd -(0x1BADB002 + 0x00000003)

section .bss
align 16
stack_bottom:
    resb 32768
stack_top:

section .text
global _start
extern diag_entry
_start:
    mov esp, stack_top
    xor ebp, ebp
    call diag_entry
.hang:
    cli
    hlt
    jmp .hang
