#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
code_tree.py - Visor del árbol de código del workspace SereOS + PAC-MAN SereOS.

Solo librería estándar de Python 3 (>= 3.8). No escribe nada: únicamente lee el
disco e imprime por stdout. Idempotente: el mismo workspace produce la misma
salida.

Proyectos que muestra:
  - "sistema operativo"  (SereOS Desktop, bare-metal x86)
  - "Pac-man SereOS"     (PAC-MAN SereOS, juego arcade)

Uso típico (desde "Entregas tareas/", donde vive tools/):
    python3 tools/code_tree.py
    python3 tools/code_tree.py --depth 2
    python3 tools/code_tree.py --sizes --filter .c,.h
    python3 tools/code_tree.py --dup --sizes --only "Pac-man SereOS"
    python3 tools/code_tree.py --stats
    python3 tools/code_tree.py --markdown > docs/CODE_TREE.md

La raíz del workspace se resuelve por defecto subiendo desde la ubicación del
script hasta la primera carpeta que contenga "sistema operativo" y
"Pac-man SereOS" (así funciona igual en tools/ y en "Entregas tareas/tools/").
Usa --root RUTA para forzarla.

Se excluyen siempre: directorios build/, .git/, __pycache__/ y cualquier
directorio llamado screenshots/ (las capturas de docs/screenshots); los
archivos binarios por extensión (png, jpg, zip, docx, bin, iso, img, o, a,
pyc, wav, ttf, ppm, ...) y los archivos de más de 200 KB que no tengan
extensión de texto conocida. Usa --all para incluirlos.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

PROJECTS = ("sistema operativo", "Pac-man SereOS")

PROJECT_DESCRIPTIONS = {
    "sistema operativo": (
        "SereOS Desktop: sistema operativo propio **bare-metal** para x86 de "
        "32 bits (i686), escrito en C99 y NASM, que arranca con GRUB 2 / "
        "Multiboot 1 y no usa Linux ni librerías del sistema anfitrión. "
        "Incluye escritorio gráfico estilo macOS, aplicaciones nativas "
        "(terminal, gestor de archivos, monitor, acerca de), y el juego "
        "PAC-MAN enlazado como librería freestanding. Subdirectorios: "
        "`boot/`, `kernel/`, `drivers/`, `memory/`, `process/`, "
        "`filesystem/`, `graphics/`, `gui/`, `apps/`, `shell/`, `libc/`, "
        "`include/`, más `docs/`, `tools/`, `assets/`, `audio/`, `isodir/` "
        "y `build/` (este último excluido del árbol por ser artefactos)."
    ),
    "Pac-man SereOS": (
        "PAC-MAN SereOS: videojuego arcade original del proyecto, con una "
        "única lógica de juego compartida y **dos backends**: SereOS nativo "
        "(freestanding, exporta `app_t *app_game(void)`) y Linux/SDL2. "
        "Subdirectorios: `src/core/` (lógica), `src/render/` (dibujo), "
        "`src/platform/sereos/` y `src/platform/linux/` (backends), "
        "`include/`, `assets/` (fuentes/recursos), `tests/`, `tools/`, "
        "`docs/` y `build/` (excluido del árbol por ser artefactos)."
    ),
}

EXCLUDED_DIR_NAMES = {
    "build",
    ".git",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    "node_modules",
    "screenshots",  # cubre docs/screenshots (capturas PNG)
}

# Extensiones que nunca son código: binarios y artefactos de compilación.
BINARY_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".tif", ".tiff",
    ".ppm", ".pgm", ".zip", ".tar", ".gz", ".tgz", ".7z", ".rar",
    ".docx", ".doc", ".xlsx", ".pptx", ".pdf", ".odt",
    ".bin", ".iso", ".img", ".elf", ".exe", ".dll", ".so",
    ".o", ".obj", ".a", ".lib", ".d", ".pyc", ".pyo",
    ".wav", ".mp3", ".ogg", ".flac", ".ttf", ".otf", ".woff", ".woff2",
    ".db", ".sqlite", ".bak",
}

TEXT_EXTS = {
    ".c", ".h", ".s", ".asm", ".inc", ".ld", ".py", ".sh", ".bash",
    ".md", ".txt", ".json", ".cfg", ".conf", ".ini", ".csv", ".tsv",
    ".yml", ".yaml", ".toml", ".mk", ".cmake", ".html", ".css", ".js",
    ".gitignore", ".gitattributes", ".editorconfig",
}

TEXT_NAMES = {
    "Makefile", "makefile", "GNUmakefile", "Kconfig", "Kbuild",
    "LICENSE", "LICENCE", "COPYING", "README", "CHANGELOG", "AUTHORS",
    ".gitignore", ".gitattributes", ".editorconfig",
}

LARGE_FILE_LIMIT = 200 * 1024  # 200 KB

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[1;36m"
YELLOW = "\033[33m"
GREEN = "\033[1;32m"
RED = "\033[31m"

_USE_COLOR = False


def paint(text: str, code: str) -> str:
    """Colorea texto si la salida es una terminal interactiva."""
    return f"{code}{text}{RESET}" if _USE_COLOR else text


# ---------------------------------------------------------------------------
# Modelo de árbol
# ---------------------------------------------------------------------------


class Node:
    """Nodo del árbol (directorio o archivo)."""

    __slots__ = (
        "name", "path", "is_dir", "ext", "size", "lines",
        "children", "files", "total_lines", "binary",
    )

    def __init__(self, name, path, is_dir, *, ext="", size=0, lines=0, binary=False):
        self.name = name
        self.path = path
        self.is_dir = is_dir
        self.ext = ext
        self.size = size
        self.lines = lines
        self.children = []
        self.files = 1 if not is_dir else 0
        self.total_lines = lines if not is_dir else 0
        self.binary = binary


def noun(num: int, singular: str, plural: str) -> str:
    """'1 archivo' / 'N archivos'."""
    return f"{num} {singular if num == 1 else plural}"


def human_size(num: int) -> str:
    if num < 1024:
        return f"{num} B"
    value = float(num)
    for unit in ("KB", "MB", "GB"):
        value /= 1024.0
        if value < 1024.0 or unit == "GB":
            return f"{value:.1f} {unit}"
    return f"{value:.1f} GB"


def count_lines(path: Path) -> int:
    """Cuenta líneas de un archivo de texto sin cargarlo entero en memoria."""
    try:
        data = path.read_bytes()
    except OSError:
        return 0
    if not data:
        return 0
    total = data.count(b"\n")
    if not data.endswith(b"\n"):
        total += 1
    return total


def is_text_like(path: Path, ext: str) -> bool:
    return ext in TEXT_EXTS or path.name in TEXT_NAMES


def is_excluded_file(path: Path, ext: str, include_all: bool) -> bool:
    if include_all:
        return False
    if ext in BINARY_EXTS:
        return True
    try:
        size = path.stat().st_size
    except OSError:
        return True
    if size > LARGE_FILE_LIMIT and not is_text_like(path, ext):
        return True
    return False


def scan_dir(path: Path, include_all: bool, hidden: list) -> Node:
    """Construye recursivamente el árbol de un directorio."""
    node = Node(path.name, path, True)
    try:
        with os.scandir(path) as it:
            entries = list(it)
    except OSError as exc:
        print(f"aviso: no se pudo leer {path}: {exc}", file=sys.stderr)
        return node

    def sort_key(entry):
        try:
            is_dir = entry.is_dir(follow_symlinks=False)
        except OSError:
            is_dir = False
        return (not is_dir, entry.name.casefold())

    entries.sort(key=sort_key)

    for entry in entries:
        child_path = Path(entry.path)
        try:
            is_dir = entry.is_dir(follow_symlinks=False)
        except OSError:
            continue

        if is_dir:
            if entry.name in EXCLUDED_DIR_NAMES:
                continue
            child = scan_dir(child_path, include_all, hidden)
            if child.children:  # se podan directorios que quedan vacíos
                node.children.append(child)
                node.files += child.files
                node.total_lines += child.total_lines
            continue

        ext = child_path.suffix.lower()
        if is_excluded_file(child_path, ext, include_all):
            hidden.append(child_path)
            continue

        try:
            size = child_path.stat().st_size
        except OSError:
            size = 0

        binary = ext in BINARY_EXTS
        lines = 0 if binary else count_lines(child_path)
        node.children.append(
            Node(entry.name, child_path, False, ext=ext, size=size,
                 lines=lines, binary=binary)
        )
        node.files += 1
        node.total_lines += lines

    return node


def collect_basenames(node: Node, out: set) -> None:
    if node.is_dir:
        for child in node.children:
            collect_basenames(child, out)
    else:
        out.add(node.name)


# ---------------------------------------------------------------------------
# Filtro --filter EXT
# ---------------------------------------------------------------------------


def parse_filters(raw: str):
    tokens = []
    for chunk in raw.replace(";", ",").split(","):
        token = chunk.strip().lower()
        if not token:
            continue
        if token.startswith("*."):
            token = token[1:]
        tokens.append(token)
    return tokens


def matches_filter(name: str, tokens) -> bool:
    lowered = name.lower()
    for token in tokens:
        if token.startswith("."):
            if lowered.endswith(token):
                return True
        else:
            if lowered.endswith("." + token) or lowered == token:
                return True
    return False


def recount(node: Node) -> None:
    if not node.is_dir:
        node.files = 1
        return
    node.files = 0
    node.total_lines = 0
    for child in node.children:
        if child.is_dir:
            recount(child)
        node.files += child.files
        node.total_lines += child.total_lines


def apply_filter(node: Node, tokens):
    """Devuelve una copia podada del árbol o None si no queda nada."""
    if not tokens:
        return node
    if not node.is_dir:
        return node if matches_filter(node.name, tokens) else None
    kept = []
    for child in node.children:
        result = apply_filter(child, tokens)
        if result is not None:
            kept.append(result)
    if not kept:
        return None
    node.children = kept
    recount(node)
    return node


# ---------------------------------------------------------------------------
# Render de árbol
# ---------------------------------------------------------------------------


def _dir_suffix(node: Node, show_sizes: bool, truncated: bool) -> str:
    suffix = ""
    if show_sizes:
        detail = (
            f"{noun(node.files, 'archivo', 'archivos')}, "
            f"{noun(node.total_lines, 'línea', 'líneas')}"
        )
        suffix += paint(f"  ({detail})", DIM)
    if truncated:
        suffix += paint("  …", DIM)
    return suffix


def render_tree(node: Node, max_depth, show_sizes: bool, dup_names: set):
    """Devuelve la lista de líneas del árbol (sin la cabecera del proyecto)."""
    lines = []

    def walk(current: Node, prefix: str, depth: int) -> None:
        children = current.children
        last_index = len(children) - 1
        for index, child in enumerate(children):
            is_last = index == last_index
            connector = "└── " if is_last else "├── "
            if child.is_dir:
                truncated = (
                    max_depth is not None
                    and depth >= max_depth
                    and bool(child.children)
                )
                label = paint(f"{child.name}/", CYAN)
                label += _dir_suffix(child, show_sizes, truncated)
                lines.append(prefix + connector + label)
                if not truncated:
                    extension = "    " if is_last else "│   "
                    walk(child, prefix + extension, depth + 1)
                continue

            label = child.name
            if show_sizes:
                if child.binary:
                    label += paint(f"  ({human_size(child.size)})", DIM)
                else:
                    label += paint(
                        f"  ({noun(child.lines, 'línea', 'líneas')})", DIM
                    )
            if child.name in dup_names:
                label += paint("  ⚠ dup", YELLOW)
            lines.append(prefix + connector + label)

    walk(node, "", 1)
    return lines


# ---------------------------------------------------------------------------
# Estadísticas
# ---------------------------------------------------------------------------


def stats_rows(node: Node, prefix: str = ""):
    label = f"{prefix}/" if prefix else "./"
    rows = [(label, node.files, node.total_lines)]
    for child in node.children:
        if child.is_dir:
            child_prefix = f"{prefix}/{child.name}" if prefix else child.name
            rows.extend(stats_rows(child, child_prefix))
    return rows


def print_stats_terminal(projects_data, show_sizes: bool) -> None:
    for entry in projects_data:
        node = entry["node"]
        rows = stats_rows(node)
        print(paint(f"{entry['name']}/", BOLD))
        name_width = max(len(row[0]) for row in rows)
        files_width = max(6, max(len(str(row[1])) for row in rows))
        lines_width = max(7, max(len(str(row[2])) for row in rows))
        header = (
            f"  {'directorio'.ljust(name_width)}  "
            f"{'archivos'.rjust(files_width)}  "
            f"{'líneas'.rjust(lines_width)}"
        )
        print(paint(header, DIM))
        for label, files, total_lines in rows:
            print(
                f"  {label.ljust(name_width)}  "
                f"{str(files).rjust(files_width)}  "
                f"{str(total_lines).rjust(lines_width)}"
            )
        print(
            paint(
                f"  {'TOTAL'.ljust(name_width)}  "
                f"{str(node.files).rjust(files_width)}  "
                f"{str(node.total_lines).rjust(lines_width)}",
                BOLD,
            )
        )
        print()


def markdown_stats_table(entry) -> list:
    node = entry["node"]
    rows = stats_rows(node)
    out = [
        f"### `{entry['name']}/`",
        "",
        "| Directorio | Archivos | Líneas |",
        "|---|---:|---:|",
    ]
    for label, files, total_lines in rows:
        out.append(f"| `{label}` | {files} | {total_lines} |")
    out.append("")
    out.append(
        "> Conteos acumulados (incluyen subdirectorios); la fila raíz es el "
        "total del proyecto."
    )
    out.append("")
    return out


# ---------------------------------------------------------------------------
# Documento Markdown
# ---------------------------------------------------------------------------


def emit_markdown(projects_data, args, depth, dup_enabled) -> None:
    out = []
    out.append("# Árbol de código — SereOS + PAC-MAN SereOS")
    out.append("")
    out.append(
        "Documento generado automáticamente por [`tools/code_tree.py`]"
        "(../tools/code_tree.py) (Python 3, solo librería estándar). "
        "No editar a mano: se regenera con el comando de abajo."
    )
    out.append("")
    out.append("## Qué es cada proyecto")
    out.append("")
    for name in PROJECTS:
        out.append(f"### `{name}/`")
        out.append("")
        out.append(PROJECT_DESCRIPTIONS[name])
        out.append("")

    out.append("## Cómo regenerar este documento")
    out.append("")
    out.append("```bash")
    out.append("# desde la raíz del workspace (donde están Makefile y README.md)")
    out.append("python3 tools/code_tree.py --markdown > docs/CODE_TREE.md")
    out.append("```")
    out.append("")
    out.append("Vistas rápidas en la terminal (sin generar archivo):")
    out.append("")
    out.append("```bash")
    out.append("python3 tools/code_tree.py                      # árbol, 3 niveles")
    out.append("python3 tools/code_tree.py --depth 2            # más compacto")
    out.append("python3 tools/code_tree.py --sizes              # líneas por archivo")
    out.append("python3 tools/code_tree.py --filter .c,.h       # solo C")
    out.append("python3 tools/code_tree.py --dup --sizes --only \"Pac-man SereOS\"")
    out.append("python3 tools/code_tree.py --stats              # tabla por directorio")
    out.append("python3 tools/code_tree.py --only \"sistema operativo\" --depth 2")
    out.append("```")
    out.append("")

    out.append("## Estadísticas por directorio")
    out.append("")
    for entry in projects_data:
        out.extend(markdown_stats_table(entry))
    out.append("## Árbol completo")
    out.append("")
    for entry in projects_data:
        out.append(f"### `{entry['name']}/`")
        out.append("")
        out.append("```text")
        out.append(f"{entry['name']}/")
        out.extend(render_tree(entry["node"], depth, True, entry["dups"]))
        out.append("```")
        out.append("")

    out.append("## Notas")
    out.append("")
    out.append(
        "- **Exclusiones:** `build/`, `.git/`, `__pycache__/`, `docs/screenshots/` "
        "(capturas), archivos binarios por extensión (`.png`, `.jpg`, `.zip`, "
        "`.docx`, `.bin`, `.iso`, `.img`, `.o`, `.a`, `.d`, `.pyc`, `.wav`, "
        "`.ttf`, `.ppm`, …) y archivos de más de 200 KB sin extensión de texto "
        "conocida. Por eso los totales pueden ser menores que `find | wc -l`."
    )
    out.append(
        "- **`--sizes`** cuenta líneas reales (`\\n`) de cada archivo de texto; "
        "los binarios (solo visibles con `--all`) muestran su tamaño."
    )
    out.append(
        "- **`⚠ dup`** marca archivos cuyo nombre también existe en el otro "
        "proyecto (p. ej. `Makefile`, `README.md`, `text_data.c`)."
    )
    out.append(
        "- Este documento no incluye la raíz del workspace (`README.md`, "
        "`QA_REPORT.md`, `.docx`, `.zip` de la entrega): muestra los dos "
        "proyectos de código."
    )
    out.append("")

    sys.stdout.write("\n".join(out) + "\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def resolve_root(raw_root) -> Path:
    if raw_root:
        return Path(raw_root).expanduser().resolve()
    # El script puede vivir en tools/ de la raíz del workspace o en
    # "Entregas tareas/tools/": se busca hacia arriba la primera carpeta que
    # contenga AMBOS proyectos.
    here = Path(__file__).resolve().parent.parent
    for candidate in (here, *here.parents):
        if all((candidate / name).is_dir() for name in PROJECTS):
            return candidate
    return here


def select_projects(only: str):
    if not only:
        return list(PROJECTS)
    wanted = only.strip().casefold()
    for name in PROJECTS:
        if name.casefold() == wanted:
            return [name]
    for name in PROJECTS:
        if wanted in name.casefold():
            return [name]
    return []


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="code_tree.py",
        description=(
            "Imprime el árbol de código de los dos proyectos del workspace "
            "(SereOS y PAC-MAN SereOS), con topes de profundidad, tamaños, "
            "filtros de extensión, detección de duplicados y estadísticas."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ejemplos:\n"
            "  python3 tools/code_tree.py\n"
            "  python3 tools/code_tree.py --depth 2\n"
            "  python3 tools/code_tree.py --sizes --filter .c,.h\n"
            "  python3 tools/code_tree.py --dup --sizes --only \"Pac-man SereOS\"\n"
            "  python3 tools/code_tree.py --stats\n"
            "  python3 tools/code_tree.py --markdown > docs/CODE_TREE.md\n"
        ),
    )
    parser.add_argument(
        "--depth", type=int, default=None, metavar="N",
        help="profundidad máxima mostrada (default: 3; sin límite con --markdown)",
    )
    parser.add_argument(
        "--sizes", action="store_true",
        help="añade 'N líneas' a cada archivo de texto y totales a cada directorio",
    )
    parser.add_argument(
        "--filter", default=None, metavar="EXT",
        help="solo extensiones indicadas, separadas por comas (ej. .c,.h,.py)",
    )
    parser.add_argument(
        "--only", default=None, metavar="PROYECTO",
        help='muestra solo un proyecto: "sistema operativo" o "Pac-man SereOS"',
    )
    parser.add_argument(
        "--dup", action="store_true",
        help="marca con '⚠ dup' los archivos cuyo basename existe en el otro árbol",
    )
    parser.add_argument(
        "--stats", action="store_true",
        help="en vez del árbol, tabla de archivos/líneas por directorio",
    )
    parser.add_argument(
        "--markdown", action="store_true",
        help="emite el documento Markdown completo (para docs/CODE_TREE.md)",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="incluye binarios, capturas y artefactos normalmente excluidos",
    )
    parser.add_argument(
        "--root", default=None, metavar="RUTA",
        help="raíz del workspace (default: directorio padre de tools/)",
    )
    parser.add_argument(
        "--version", action="version", version="code_tree.py 1.0",
    )
    return parser


def main(argv=None) -> int:
    global _USE_COLOR

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.depth is not None and args.depth < 1:
        parser.error("--depth debe ser un entero >= 1")
    if args.depth is not None and args.markdown:
        parser.error("--depth no aplica con --markdown (el documento es completo)")

    _USE_COLOR = (
        not args.markdown
        and sys.stdout.isatty()
        and os.environ.get("NO_COLOR") is None
    )

    root = resolve_root(args.root)
    if not root.is_dir():
        print(f"error: la raíz no existe o no es un directorio: {root}", file=sys.stderr)
        return 2

    selected = select_projects(args.only)
    if not selected:
        available = ", ".join(f'"{name}"' for name in PROJECTS)
        print(
            f"error: proyecto desconocido: {args.only!r}. Disponibles: {available}",
            file=sys.stderr,
        )
        return 2

    filters = parse_filters(args.filter) if args.filter else []

    # Escanea TODOS los proyectos: --dup necesita los basenames de ambos.
    scanned = {}
    for name in PROJECTS:
        project_path = root / name
        if not project_path.is_dir():
            print(
                f"aviso: no se encontró el proyecto {project_path}",
                file=sys.stderr,
            )
            continue
        hidden: list = []
        node = scan_dir(project_path, args.all, hidden)
        basenames: set = set()
        collect_basenames(node, basenames)
        scanned[name] = {
            "name": name,
            "node": node,
            "hidden": hidden,
            "basenames": basenames,
            "dups": set(),
        }

    if not scanned:
        print(f"error: no se encontró ningún proyecto en {root}", file=sys.stderr)
        return 2

    all_selected = [scanned[name] for name in selected if name in scanned]
    if not all_selected:
        print(
            "error: los proyectos seleccionados no existen en la raíz indicada",
            file=sys.stderr,
        )
        return 2

    # Duplicados: un basename compartido por ambos árboles.
    for entry in all_selected:
        other_names = set()
        for other in scanned.values():
            if other["name"] != entry["name"]:
                other_names |= other["basenames"]
        entry["dups"] = (
            entry["basenames"] & other_names if (args.dup or args.markdown) else set()
        )

    # Filtro de extensiones (poda ramas sin coincidencias).
    if filters:
        filtered = []
        for entry in all_selected:
            node = apply_filter(entry["node"], filters)
            if node is None:
                print(
                    paint(
                        f"aviso: ningún archivo coincide con --filter {args.filter} "
                        f"en \"{entry['name']}\"",
                        YELLOW,
                    ),
                    file=sys.stderr,
                )
                continue
            entry["node"] = node
            filtered.append(entry)
        all_selected = filtered
        if not all_selected:
            return 0

    depth = args.depth if args.depth is not None else (None if args.markdown else 3)

    if args.markdown:
        emit_markdown(all_selected, args, depth, args.dup)
        return 0

    if args.stats:
        print_stats_terminal(all_selected, args.sizes)
        return 0

    for index, entry in enumerate(all_selected):
        if index:
            print()
        node = entry["node"]
        hidden = len(entry["hidden"])
        header = (
            paint(f"{entry['name']}/", BOLD)
            + paint(
                f"  ·  {noun(node.files, 'archivo', 'archivos')}, "
                f"{noun(node.total_lines, 'línea', 'líneas')}",
                GREEN,
            )
        )
        if hidden:
            header += paint(f"  ·  {hidden} excluidos (binarios/build)", DIM)
        print(header)
        for line in render_tree(node, depth, args.sizes, entry["dups"]):
            print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
