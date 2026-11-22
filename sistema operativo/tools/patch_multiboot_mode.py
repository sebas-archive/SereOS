#!/usr/bin/env python3
"""tools/patch_multiboot_mode.py - genera una variante del kernel con otra
resolucion solicitada en la cabecera Multiboot.

El kernel principal pide 1024x768x32 (ver boot/boot.s). GRUB obedece la
peticion de la cabecera Multiboot, no `gfxmode`, por lo que para probar el
diseno a otras resoluciones hace falta un binario con la peticion cambiada.
Este script copia sereos.bin y reescribe los campos width/height/depth de la
cabecera (offsets 36/40/44), sin tocar el checksum (que solo cubre
magic+flags+checksum).

Uso:
  patch_multiboot_mode.py <kernel.bin> <salida.bin> <ancho> <alto> [profundidad]
"""
import struct
import sys

MAGIC = 0x1BADB002


def patch(src, dst, width, height, depth=32):
    data = bytearray(open(src, "rb").read())
    for off in range(0, len(data) - 52, 4):
        magic, flags, checksum = struct.unpack_from("<III", data, off)
        if magic != MAGIC:
            continue
        if (magic + flags + checksum) & 0xFFFFFFFF:
            continue
        mode_type = struct.unpack_from("<I", data, off + 32)[0]
        if mode_type != 0:
            raise SystemExit("cabecera sin peticion de framebuffer lineal")
        struct.pack_into("<III", data, off + 36, width, height, depth)
        open(dst, "wb").write(data)
        print("multiboot mode: %dx%dx%d (offset %d)" % (width, height, depth, off))
        return
    raise SystemExit("no se encontro cabecera Multiboot valida en %s" % src)


if __name__ == "__main__":
    if len(sys.argv) not in (5, 6):
        raise SystemExit(__doc__)
    patch(sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]),
          int(sys.argv[5]) if len(sys.argv) == 6 else 32)
