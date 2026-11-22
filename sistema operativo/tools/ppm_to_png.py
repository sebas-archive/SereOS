#!/usr/bin/env python3
"""ppm_to_png.py - Conversion PPM (P6) -> PNG y analisis de imagenes de SereOS.

SereOS captura la pantalla de QEMU con el comando de monitor ``screendump``,
que genera ficheros PPM binarios (P6). Este script:

  * lee PPM P6 (incluye comentarios y maxval != 255),
  * escribe PNG RGB de 8 bits usando SOLO la biblioteca estandar (zlib),
    sin depender de PIL ni de ninguna otra libreria externa,
  * analiza la imagen para detectar capturas en negro o vacias (numero de
    colores distintos, proporcion de pixeles no negros, luminancia media),
  * compara dos capturas (proporcion de pixeles distintos), util para
    comprobar que una tecla/orden realmente cambio la pantalla.

Uso:
    python3 tools/ppm_to_png.py entrada.ppm [salida.png]
    python3 tools/ppm_to_png.py --stats entrada.ppm
    python3 tools/ppm_to_png.py --check entrada.ppm      # exit 1 si esta negra
    python3 tools/ppm_to_png.py --diff a.ppm b.ppm
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
import zlib
from dataclasses import dataclass
from pathlib import Path

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

# Nivel por debajo del cual un pixel se considera "negro" (cada canal).
BLACK_LEVEL = 16


class PPMError(ValueError):
    """Formato PPM invalido o fichero truncado."""


@dataclass
class PPMImage:
    """Imagen PPM normalizada a 8 bits por canal (RGB entrelazado)."""

    width: int
    height: int
    maxval: int
    pixels: bytes

    @property
    def n_pixels(self) -> int:
        return self.width * self.height


@dataclass
class ImageStats:
    """Resultado del analisis de una captura."""

    width: int
    height: int
    distinct_colors: int
    non_black_ratio: float
    mean_luma: float
    mean_rgb: tuple[float, float, float]
    black_level: int = BLACK_LEVEL

    def as_dict(self) -> dict:
        return {
            "width": self.width,
            "height": self.height,
            "distinct_colors": self.distinct_colors,
            "non_black_ratio": round(self.non_black_ratio, 6),
            "mean_luma": round(self.mean_luma, 3),
            "mean_rgb": [round(c, 2) for c in self.mean_rgb],
            "black_level": self.black_level,
        }


# ---------------------------------------------------------------------------
# Lectura / escritura
# ---------------------------------------------------------------------------

def _skip_ws_comments(data: bytes, pos: int) -> int:
    n = len(data)
    while pos < n:
        c = data[pos]
        if c in b" \t\r\n":
            pos += 1
        elif c == ord("#"):
            while pos < n and data[pos] not in b"\r\n":
                pos += 1
        else:
            break
    return pos


def _read_token(data: bytes, pos: int) -> tuple[bytes, int]:
    pos = _skip_ws_comments(data, pos)
    n = len(data)
    start = pos
    while pos < n and data[pos] not in b" \t\r\n#":
        pos += 1
    if start == pos:
        raise PPMError("cabecera PPM incompleta")
    return data[start:pos], pos


def read_ppm(path: str | Path) -> PPMImage:
    """Lee un fichero PPM P6 y lo normaliza a 8 bits por canal."""
    path = Path(path)
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise PPMError(f"no se puede leer {path}: {exc}") from exc

    if len(data) < 2 or data[:2] != b"P6":
        magic = data[:2].decode("latin-1", "replace")
        raise PPMError(f"{path}: se esperaba PPM P6, encontrado {magic!r}")

    pos = 2
    w_tok, pos = _read_token(data, pos)
    h_tok, pos = _read_token(data, pos)
    m_tok, pos = _read_token(data, pos)
    try:
        width = int(w_tok)
        height = int(h_tok)
        maxval = int(m_tok)
    except ValueError as exc:
        raise PPMError(f"{path}: cabecera PPM invalida") from exc

    if width <= 0 or height <= 0:
        raise PPMError(f"{path}: dimensiones invalidas {width}x{height}")
    if not 0 < maxval <= 65535:
        raise PPMError(f"{path}: maxval invalido {maxval}")

    # Un unico caracter de espacio separa la cabecera del raster.
    if pos >= len(data) or data[pos] not in b" \t\r\n":
        raise PPMError(f"{path}: falta el separador tras la cabecera")
    if data[pos:pos + 2] == b"\r\n":
        pos += 2
    else:
        pos += 1

    bpp = 2 if maxval > 255 else 1
    need = width * height * 3 * bpp
    raster = data[pos:pos + need]
    if len(raster) < need:
        raise PPMError(
            f"{path}: raster truncado ({len(raster)} de {need} bytes esperados)"
        )

    if maxval != 255:
        scale = 255.0 / maxval
        out = bytearray(width * height * 3)
        if bpp == 1:
            for i in range(len(out)):
                out[i] = min(255, int(raster[i] * scale + 0.5))
        else:
            for i in range(len(out)):
                v = (raster[2 * i] << 8) | raster[2 * i + 1]
                out[i] = min(255, int(v * scale + 0.5))
        raster = bytes(out)
    elif len(raster) > need:
        raster = raster[:need]

    return PPMImage(width=width, height=height, maxval=maxval, pixels=raster)


def _chunk(tag: bytes, payload: bytes) -> bytes:
    crc = zlib.crc32(tag + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", crc)


def write_png(path: str | Path, img: PPMImage, level: int = 6) -> Path:
    """Escribe un PNG RGB de 8 bits. Crea los directorios necesarios."""
    path = Path(path)
    if img.maxval != 255:
        raise PPMError("write_png requiere una imagen normalizada a 8 bits")
    if len(img.pixels) != img.width * img.height * 3:
        raise PPMError("write_png: tamano de raster incoherente con las dimensiones")

    stride = img.width * 3
    raw = bytearray()
    for y in range(img.height):
        raw.append(0)  # filtro PNG "None"
        raw += img.pixels[y * stride:(y + 1) * stride]

    ihdr = struct.pack(">IIBBBBB", img.width, img.height, 8, 2, 0, 0, 0)
    png = (
        PNG_SIGNATURE
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(bytes(raw), level))
        + _chunk(b"IEND", b"")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)
    return path


# ---------------------------------------------------------------------------
# Lectura de PNG y operaciones de imagen (para comparativas y crops)
# ---------------------------------------------------------------------------

def read_png(path: str | Path) -> PPMImage:
    """Lee un PNG RGB/RGBA de 8 bits y devuelve un PPMImage RGB."""
    path = Path(path)
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise PPMError(f"no se puede leer {path}: {exc}") from exc
    if data[:8] != PNG_SIGNATURE:
        raise PPMError(f"{path}: no es un PNG")
    pos = 8
    width = height = None
    bit_depth = color_type = interlace = None
    idat = bytearray()
    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        tag = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if tag == b"IHDR":
            width, height, bit_depth, color_type, _comp, _filt, interlace = \
                struct.unpack(">IIBBBBB", body)
        elif tag == b"IDAT":
            idat += body
        elif tag == b"IEND":
            break
    if width is None or bit_depth != 8 or color_type not in (2, 6) or interlace != 0:
        raise PPMError(f"{path}: solo se soportan PNG RGB/RGBA de 8 bits sin entrelazar")
    try:
        raw = zlib.decompress(bytes(idat))
    except zlib.error as exc:
        raise PPMError(f"{path}: IDAT corrupto: {exc}") from exc
    bpp = 3 if color_type == 2 else 4
    stride = width * bpp
    out = bytearray(width * height * 3)
    prev = bytearray(stride)
    p = 0
    for y in range(height):
        if p >= len(raw):
            raise PPMError(f"{path}: PNG truncado")
        ft = raw[p]
        p += 1
        line = bytearray(raw[p:p + stride])
        p += stride
        if len(line) != stride:
            raise PPMError(f"{path}: PNG truncado")
        if ft == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif ft == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ft == 3:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif ft == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                pp = a + b - c
                pa = abs(pp - a)
                pb = abs(pp - b)
                pc = abs(pp - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        elif ft != 0:
            raise PPMError(f"{path}: filtro PNG desconocido {ft}")
        if bpp == 3:
            out[y * width * 3:(y + 1) * width * 3] = line
        else:
            for x in range(width):
                out[(y * width + x) * 3:(y * width + x) * 3 + 3] = line[x * 4:x * 4 + 3]
        prev = line
    return PPMImage(width=width, height=height, maxval=255, pixels=bytes(out))


def crop(img: PPMImage, x: int, y: int, w: int, h: int) -> PPMImage:
    """Recorta una region de la imagen (coordenadas en pixeles, con clipping)."""
    x = max(0, min(img.width, x))
    y = max(0, min(img.height, y))
    w = max(1, min(img.width - x, w))
    h = max(1, min(img.height - y, h))
    stride = img.width * 3
    out = b"".join(
        img.pixels[(y + r) * stride + x * 3:(y + r) * stride + (x + w) * 3]
        for r in range(h)
    )
    return PPMImage(width=w, height=h, maxval=255, pixels=out)


def scale_nearest(img: PPMImage, new_w: int, new_h: int) -> PPMImage:
    """Escala por vecino mas cercano (suficiente para comparativas)."""
    new_w = max(1, new_w)
    new_h = max(1, new_h)
    stride = img.width * 3
    out = bytearray(new_w * new_h * 3)
    for y in range(new_h):
        sy = min(img.height - 1, y * img.height // new_h)
        row = sy * stride
        for x in range(new_w):
            sx = min(img.width - 1, x * img.width // new_w)
            si = row + sx * 3
            di = (y * new_w + x) * 3
            out[di:di + 3] = img.pixels[si:si + 3]
    return PPMImage(width=new_w, height=new_h, maxval=255, pixels=bytes(out))


def vstack(images: list[PPMImage], gap: int = 0,
           gap_color: tuple[int, int, int] = (0, 0, 0)) -> PPMImage:
    """Apila imagenes verticalmente (mismo ancho; se usa el maximo)."""
    if not images:
        raise PPMError("vstack sin imagenes")
    width = max(im.width for im in images)
    height = sum(im.height for im in images) + gap * (len(images) - 1)
    out = bytearray(width * height * 3)
    gap_row = bytes(gap_color) * width
    y = 0
    for idx, im in enumerate(images):
        for r in range(im.height):
            src = im.pixels[r * im.width * 3:(r + 1) * im.width * 3]
            di = (y + r) * width * 3
            out[di:di + len(src)] = src
        y += im.height
        if idx != len(images) - 1 and gap:
            for _ in range(gap):
                di = y * width * 3
                out[di:di + len(gap_row)] = gap_row
                y += 1
    return PPMImage(width=width, height=height, maxval=255, pixels=bytes(out))


def hstack(images: list[PPMImage], gap: int = 0,
           gap_color: tuple[int, int, int] = (0, 0, 0)) -> PPMImage:
    """Pone imagenes en fila (misma alto; se usa el maximo)."""
    if not images:
        raise PPMError("hstack sin imagenes")
    height = max(im.height for im in images)
    width = sum(im.width for im in images) + gap * (len(images) - 1)
    out = bytearray(width * height * 3)
    x = 0
    for idx, im in enumerate(images):
        for r in range(im.height):
            src = im.pixels[r * im.width * 3:(r + 1) * im.width * 3]
            di = (r * width + x) * 3
            out[di:di + len(src)] = src
        x += im.width
        if idx != len(images) - 1 and gap:
            for r in range(height):
                di = (r * width + x) * 3
                out[di:di + gap * 3] = bytes(gap_color) * gap
            x += gap
    return PPMImage(width=width, height=height, maxval=255, pixels=bytes(out))


# ---------------------------------------------------------------------------
# Analisis
# ---------------------------------------------------------------------------

def analyze(img: PPMImage, black_level: int = BLACK_LEVEL) -> ImageStats:
    """Calcula colores distintos, proporcion no negra y luminancia media."""
    px = img.pixels
    total = img.n_pixels
    colors: set[bytes] = set()
    non_black = 0
    sum_r = sum_g = sum_b = 0

    for i in range(0, len(px), 3):
        r = px[i]
        g = px[i + 1]
        b = px[i + 2]
        colors.add(px[i:i + 3])
        if r > black_level or g > black_level or b > black_level:
            non_black += 1
        sum_r += r
        sum_g += g
        sum_b += b

    if total == 0:
        return ImageStats(0, 0, 0, 0.0, 0.0, (0.0, 0.0, 0.0), black_level)
    return ImageStats(
        width=img.width,
        height=img.height,
        distinct_colors=len(colors),
        non_black_ratio=non_black / total,
        mean_luma=(0.2126 * sum_r + 0.7152 * sum_g + 0.0722 * sum_b) / total,
        mean_rgb=(sum_r / total, sum_g / total, sum_b / total),
        black_level=black_level,
    )


def is_blackish(
    stats: ImageStats,
    min_colors: int = 4,
    min_non_black: float = 0.001,
    min_luma: float = 0.5,
) -> bool:
    """True si la captura parece negra/vacia con los umbrales indicados."""
    return (
        stats.distinct_colors < min_colors
        or stats.non_black_ratio < min_non_black
        or stats.mean_luma < min_luma
    )


def diff_ratio(
    img_a: PPMImage,
    img_b: PPMImage,
    region: tuple[int, int, int, int] | None = None,
) -> float:
    """Proporcion de pixeles distintos entre dos imagenes (0.0 .. 1.0).

    ``region`` = (x, y, w, h) limita la comparacion a una zona; sirve para
    ignorar elementos que cambian solos (p.ej. el reloj de la barra superior).
    """
    if (img_a.width, img_a.height) != (img_b.width, img_b.height):
        return 1.0

    x0, y0, w, h = 0, 0, img_a.width, img_a.height
    if region is not None:
        rx, ry, rw, rh = region
        x0 = max(0, min(img_a.width, rx))
        y0 = max(0, min(img_a.height, ry))
        w = max(0, min(img_a.width - x0, rw))
        h = max(0, min(img_a.height - y0, rh))

    if w == 0 or h == 0:
        return 0.0

    a = img_a.pixels
    b = img_b.pixels
    stride = img_a.width * 3
    changed = 0
    for y in range(y0, y0 + h):
        base = y * stride + x0 * 3
        end = base + w * 3
        for i in range(base, end, 3):
            if a[i] != b[i] or a[i + 1] != b[i + 1] or a[i + 2] != b[i + 2]:
                changed += 1
    return changed / (w * h)


def diff_files(path_a: str | Path, path_b: str | Path) -> float:
    return diff_ratio(read_ppm(path_a), read_ppm(path_b))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Convierte capturas PPM de QEMU a PNG y las analiza.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("input", nargs="?", help="PPM de entrada")
    parser.add_argument("output", nargs="?", help="PNG de salida (por defecto .png)")
    parser.add_argument("--stats", action="store_true", help="mostrar analisis")
    parser.add_argument("--check", action="store_true",
                        help="exit 1 si la imagen esta en negro/vacia")
    parser.add_argument("--diff", metavar="OTRO_PPM",
                        help="comparar con otra captura y mostrar la diferencia")
    parser.add_argument("--json", action="store_true", help="salida JSON")
    parser.add_argument("--min-colors", type=int, default=4,
                        help="colores distintos minimos para --check")
    parser.add_argument("--min-nonblack", type=float, default=0.001,
                        help="proporcion minima de pixeles no negros para --check")
    parser.add_argument("--level", type=int, default=6, help="compresion zlib (0-9)")
    parser.add_argument("--quiet", "-q", action="store_true", help="no imprimir resumen")
    args = parser.parse_args(argv)

    if not args.input:
        parser.print_help()
        return 2

    try:
        if args.diff:
            ratio = diff_files(args.input, args.diff)
            if args.json:
                print(json.dumps({"diff_ratio": round(ratio, 6)}))
            elif not args.quiet:
                print(f"diferencia: {ratio * 100:.2f}% de pixeles distintos")
            return 0

        img = read_ppm(args.input)

        if args.stats or args.check or not args.output:
            stats = analyze(img)
            black = is_blackish(stats, args.min_colors, args.min_nonblack)
            if args.json:
                out = stats.as_dict()
                out["blackish"] = black
                print(json.dumps(out))
            elif not args.quiet:
                print(f"imagen : {img.width}x{img.height} "
                      f"({img.n_pixels} px, maxval={img.maxval})")
                print(f"colores distintos : {stats.distinct_colors}")
                print(f"pixeles no negros : {stats.non_black_ratio * 100:.2f}%")
                print(f"luminancia media  : {stats.mean_luma:.2f}")
                print(f"estado            : "
                      f"{'NEGRA/VACIA' if black else 'con contenido'}")
            if args.check and black:
                return 1

        if args.output:
            write_png(args.output, img, args.level)
            if not args.quiet:
                print(f"PNG escrito: {args.output}")
        return 0
    except PPMError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
