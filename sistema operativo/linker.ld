/* linker.ld - kernel de SereOS en 2 MiB (direccion tradicional de GRUB) */
ENTRY(_start)

SECTIONS
{
	. = 2M;
	kernel_start = .;

	.text BLOCK(4K) : ALIGN(4K)
	{
		*(.multiboot)
		*(.text*)
	}

	.rodata BLOCK(4K) : ALIGN(4K)
	{
		*(.rodata*)
	}

	.data BLOCK(4K) : ALIGN(4K)
	{
		*(.data*)
	}

	.bss BLOCK(4K) : ALIGN(4K)
	{
		*(COMMON)
		*(.bss*)
	}

	kernel_end = .;

	/* deja espacio para que el heap estatico no colisione con nada */
	. = ALIGN(4K);
	_kernel_end_aligned = .;
}
