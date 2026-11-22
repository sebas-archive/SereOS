; boot/boot.s - entrada de SereOS (NASM, i386) con cabecera Multiboot v1
; Solicita a GRUB: alineacion de modulos, mapa de memoria y framebuffer lineal.
BITS 32

MB_MAGIC    equ 0x1BADB002
MB_FLAGS    equ (1 << 0) | (1 << 1) | (1 << 2)   ; align | meminfo | video
MB_CHECKSUM equ -(MB_MAGIC + MB_FLAGS)

section .multiboot
align 4
	dd MB_MAGIC
	dd MB_FLAGS
	dd MB_CHECKSUM
	; campos del "a.out kludge" (sin usar, en cero)
	dd 0, 0, 0, 0, 0
	; peticion de video (multiboot v1)
	dd 0            ; mode_type = 0 (framebuffer lineal grafico)
	dd 1024         ; width
	dd 768          ; height
	dd 32           ; depth

section .bss
align 16
stack_bottom:
	resb 65536          ; pila inicial de 64 KiB
stack_top:

section .text
global _start
extern kernel_main
_start:
	cli
	mov esp, stack_top
	push ebx                ; puntero a la estructura multiboot_info
	push eax                ; numero magico (0x2BADB002)
	call kernel_main

.halt:                      ; si kernel_main retorna, detener el sistema
	cli
	hlt
	jmp .halt

section .note.GNU-stack noalloc noexec nowrite progbits
