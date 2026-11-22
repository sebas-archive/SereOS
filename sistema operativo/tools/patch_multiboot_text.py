#!/usr/bin/env python3
"""tools/patch_multiboot_text.py - genera la variante de SereOS en modo texto.

La cabecera Multiboot de SereOS solicita framebuffer (flag bit 2). GRUB
obedece esa peticion y siempre entrega un modo grafico, por lo que la entrada
"modo texto" del menu no puede conservar VGA. Este script copia el kernel y
borra el bit 2 de los flags de la cabecera Multiboot, recalculando el
checksum, para que GRUB arranque en modo texto y SereOS use su consola VGA
de respaldo.

Uso: patch_multiboot_text.py <kernel.bin> <kernel-text.bin>
"""
import struct
import sys

MAGIC = 0x1BADB002
VIDEO_FLAG = 1 << 2


def patch(src, dst):
    data = bytearray(open(src, "rb").read())
    # busca la cabecera Multiboot (magic + checksum valido) en el binario
    for off in range(0, len(data) - 12, 4):
        magic, flags, checksum = struct.unpack_from("<III", data, off)
        if magic != MAGIC:
            continue
        if (magic + flags + checksum) & 0xFFFFFFFF:
            continue
        if not (flags & VIDEO_FLAG):
            raise SystemExit("el kernel ya esta en modo texto (sin flag de video)")
        new_flags = flags & ~VIDEO_FLAG
        new_checksum = (-(MAGIC + new_flags)) & 0xFFFFFFFF
        struct.pack_into("<III", data, off, MAGIC, new_flags, new_checksum)
        open(dst, "wb").write(data)
        print("multiboot text: flags 0x%x -> 0x%x en offset %d" % (flags, new_flags, off))
        return
    raise SystemExit("no se encontro cabecera Multiboot valida en %s" % src)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    patch(sys.argv[1], sys.argv[2])
