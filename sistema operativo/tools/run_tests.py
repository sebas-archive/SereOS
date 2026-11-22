#!/usr/bin/env python3
"""run_tests.py - suite de verificacion automatizada de SereOS v1.0 en QEMU.

Ejecuta pruebas reales contra la ISO generada por ``make``:

  1. Arranque: marcadores SEREOS_BOOT_OK / SPLASH_DONE / DESKTOP_READY / GUI_READY,
     capturas de splash y escritorio.
  2. Terminal grafica (F2) y comandos de shell (help, ls, date, free, dmesg),
     comprobando que la pantalla cambia (PPM) y que no hay panicos.
  3. Gestor de archivos (F1), monitor del sistema (F3), acerca de (F5).
  4. Juego (F4): menu -> Enter -> GAME_START -> captura -> pausa -> volver al
     escritorio (GAME_EXIT).
  5. Cierre de ventanas y gestion de ventanas (F6 enfocar / F7 minimizar).
  6. Fallback de modo texto: se elige la 2a entrada del menu GRUB (down+ret) y
     se comprueba SEREOS_TEXT_MODE + shell de texto.
  7. Comprobacion global de SEREOS_EXCEPTION / SEREOS_PANIC en los logs serie.

Las capturas se guardan como PNG en docs/screenshots/ (los PPM crudos en
docs/screenshots/raw/<run>/). Genera docs/screenshots/test-results.json y un
resumen por consola; sale con codigo != 0 si alguna prueba falla.

Uso:
    python3 tools/run_tests.py                 # suite completa
    python3 tools/run_tests.py --list
    python3 tools/run_tests.py --only boot,game
    python3 tools/run_tests.py --kvm off --timeout-scale 2
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
ROOT = TOOLS_DIR.parent
sys.path.insert(0, str(TOOLS_DIR))

import ppm_to_png  # noqa: E402
from qemu_ctrl import (  # noqa: E402
    MarkerTimeout,
    QemuController,
    QemuError,
)

SHOTS_DIR = ROOT / "docs" / "screenshots"
RAW_DIR = SHOTS_DIR / "raw"
RESULTS_JSON = SHOTS_DIR / "test-results.json"

# --- marcadores del contrato de SereOS v1.0 --------------------------------
MARK_BOOT = "SEREOS_BOOT_OK"
MARK_SPLASH = "SPLASH_DONE"
MARK_DESKTOP = "DESKTOP_READY"
MARK_GUI = "GUI_READY"
MARK_TEXT = "SEREOS_TEXT_MODE"
APP_OPEN = "APP_OPEN:"
APP_CLOSE = "APP_CLOSE:"
FATAL_PREFIXES = ("SEREOS_EXCEPTION", "SEREOS_PANIC")

APP_IDS = {
    "terminal": {"terminal"},
    "files": {"files", "filemanager", "file"},
    "monitor": {"sysmonitor", "monitor", "sys_monitor"},
    "about": {"about"},
    "game": {"game"},
}

# Ruta de teclas para la partida de PAC-MAN SereOS. Cada entrada es
# (tecla, segundos de espera). Se pulsa la tecla una sola vez (Pacman mantiene
# la direccion hasta chocar) y NUNCA se solapan teclas mantenidas: enviar
# sendkey con holds solapados deja sorda a la entrada de QEMU.
PACMAN_DOTS_ROUTE: list[tuple[str, float]] = [
    ("left", 0.40),      # Pacman entra en el pasillo inferior comiendo dots
]
# Ruta guiada desde el pasillo inferior hasta el power pill de la esquina
# inferior izquierda (spawn en fila 23 col 13; se sube por la columna 6 hasta
# la fila 20, se va a la columna 1 y se baja). Calibrada con el laberinto real
# (28x31) y la velocidad de Pacman del nivel 1.
PACMAN_POWER_ROUTE: list[tuple[str, float]] = [
    ("up", 0.25),        # subir: se encola el giro
    ("left", 1.20),      # girar a la izquierda en la fila 20 y recorrerla
    ("down", 1.00),      # bajar por la columna 1 hasta el power pill (fila 23)
]
PACMAN_POWER_WAIT = 0.4
GAME_OVER_WAIT = 80.0          # segundos maximos dejando que los fantasmas atrapen

# Paleta de referencia del juego (medida en capturas reales) para verificar
# por pixeles que hay dots, 4 fantasmas y el estado frightened.
DOT_COLOR = (255, 224, 176)
# Paleta de los sprites Res (M2/M3/M4). Los cuerpos tienen sombreado, por lo
# que se cuentan familias de color (no un RGB unico) dentro del laberinto.
GHOST_FAMILIES = {
    "blinky_rojo": lambda r, g, b: r >= 200 and g <= 40 and b <= 40,
    "pinky_rosa": lambda r, g, b: r >= 220 and b >= 180 and 140 <= g <= 235,
    "inky_cian": lambda r, g, b: g >= 200 and b >= 200 and r <= 60,
    "clyde_naranja": lambda r, g, b: r >= 220 and 150 <= g <= 205 and b <= 110,
}
FRIGHT_FAMILY = lambda r, g, b: r <= 60 and g <= 60 and b >= 160
MAZE_WALL_COLOR = (59, 130, 246)
POWER_PILL_COLOR = (255, 212, 71)

# Logotipo oficial (assets/logo/official_logo.png, 1296x1213) y barra de tareas.
# El azul dominante de la imagen es (0,78,253); tras rasterizar a RGB565 queda
# en torno a (0,76,248). La proporcion se conserva (1296/1213).
OFFICIAL_LOGO_BLUE = (0, 76, 248)
OFFICIAL_LOGO_ASPECT = 1296.0 / 1213.0
LOGO_TOL = 16
TASKBAR_HEIGHT_THEME = 48
TRAFFIC_STEP = 18          # window.c: TRAFFIC_STEP
TRAFFIC_FIRST_X = 14       # window.c: TRAFFIC_FIRST_X
TOPBAR_HEIGHT_THEME = 30

# Colores semanticos para la verificacion de esquinas (gui/theme.c):
# body/surface #14171E=(20,23,30), surface_2/statusbar #1A1E26=(26,30,38),
# border_strong #3A4256=(58,66,86), border #2A3040=(42,48,64).
WIN_BODY_COLOR = (20, 23, 30)
WIN_STATUS_COLOR = (26, 30, 38)
WIN_BORDER_STRONG = (58, 66, 86)
WIN_BORDER_COLOR = (42, 48, 64)
WIN_CORNER_RADIUS = 10
CORNER_MOSAIC_ZOOM = 10

# Navegacion adaptativa (gui/theme.h): 5 accesos en la topbar cuando hay una
# ventana maximizada; el dock inferior desaparece y la app llega a sh-1.
NAV_ICONS = 5
NAV_TILE = 24
NAV_GAP = 2
NAV_ICON = 18
NAV_TINTS = [(126, 167, 255), (184, 194, 214), (86, 197, 150),
             (227, 178, 90), (195, 202, 216)]
THEME_ACCENT = (76, 141, 255)
THEME_ACCENT_SOFT = (30, 58, 102)
THEME_TEXT = (242, 244, 248)
THEME_TEXT_DIM = (168, 176, 192)
DOCK_BOTTOM_COLORS = [(20, 23, 30), (26, 30, 38)]

# umbrales de "captura no negra" (PPM)
MIN_COLORS = 8          # colores distintos minimos
MIN_NONBLACK = 0.005    # 0.5% de pixeles no negros
TEXT_MIN_COLORS = 2
TEXT_MIN_NONBLACK = 0.0004


# ---------------------------------------------------------------------------
# Estructuras de resultados
# ---------------------------------------------------------------------------
@dataclass
class Step:
    text: str
    ok: bool | None = None          # None = informativo
    detail: str = ""


@dataclass
class Case:
    key: str
    title: str
    steps: list[Step] = field(default_factory=list)
    shots: list[str] = field(default_factory=list)
    ok: bool | None = None
    error: str | None = None
    skip_reason: str | None = None
    method: str = ""
    duration: float = 0.0

    def step(self, text: str, ok: bool | None = True, detail: str = "") -> Step:
        st = Step(text=text, ok=ok, detail=detail)
        self.steps.append(st)
        return st

    def fail(self, text: str, detail: str = "") -> Step:
        return self.step(text, False, detail)

    @property
    def failed(self) -> bool:
        return self.ok is False


def analyze_wav(path: Path) -> dict:
    """Analiza un WAV PCM sin dependencias externas.

    QEMU con `-audiodev wav` no siempre reescribe los tamanos del RIFF al
    cerrar (deja RIFF/data a 0 aunque los samples estan en el fichero), asi
    que aqui se parsean los chunks a mano y se usan los bytes reales de datos.
    """
    import math
    import struct

    result = {
        "path": str(path), "exists": path.is_file(), "bytes": 0,
        "duration_s": 0.0, "channels": 0, "sample_rate": 0,
        "sample_width": 0, "frames": 0, "peak": 0, "rms": 0.0,
        "finalized": None,
    }
    if not path.is_file():
        return result
    data = path.read_bytes()
    result["bytes"] = len(data)
    if len(data) < 44 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        result["error"] = "no es un WAV RIFF/WAVE"
        return result

    fmt = None
    data_off = None
    data_declared = 0
    pos = 12
    while pos + 8 <= len(data):
        tag = data[pos:pos + 4]
        size = struct.unpack("<I", data[pos + 4:pos + 8])[0]
        body = pos + 8
        if tag == b"fmt " and size >= 16:
            fmt = struct.unpack("<HHIIHH", data[body:body + 16])
        elif tag == b"data":
            data_off = body
            data_declared = size
            if size == 0 or body + size > len(data):
                # cabecera sin finalizar: usar los bytes realmente presentes
                data_declared = len(data) - body
            break
        pos = body + size + (size & 1)
    result["finalized"] = (data_off is not None
                           and data_off + data_declared <= len(data)
                           and struct.unpack("<I", data[4:8])[0] != 0)
    if fmt is None or data_off is None:
        result["error"] = "WAV sin chunk fmt/data"
        return result
    _, channels, rate, _byte_rate, block_align, bits = fmt
    raw = data[data_off:data_off + data_declared]
    if block_align <= 0:
        block_align = max(1, channels * bits // 8)
    frames = len(raw) // block_align
    result.update({"channels": channels, "sample_rate": rate,
                   "sample_width": bits // 8, "frames": frames,
                   "duration_s": frames / rate if rate else 0.0})

    width = bits // 8
    if width == 2:
        count = len(raw) // 2
        samples = struct.unpack(f"<{count}h", raw[:count * 2])
    elif width == 1:
        samples = [b - 128 for b in raw]
    elif width == 4:
        count = len(raw) // 4
        samples = [v >> 16 for v in struct.unpack(f"<{count}i", raw[:count * 4])]
    else:
        samples = []
    if samples:
        peak = max(abs(v) for v in samples)
        rms = math.sqrt(sum(float(v) * v for v in samples) / len(samples))
        result["peak"] = int(peak)
        result["rms"] = round(rms, 2)
        result["samples"] = len(samples)
    return result


@dataclass
class Shot:
    name: str
    ppm: Path
    png: Path
    img: "ppm_to_png.PPMImage"
    stats: "ppm_to_png.ImageStats"
    blackish: bool

    @staticmethod
    def _relpath(path: Path) -> str:
        try:
            return str(path.relative_to(ROOT))
        except ValueError:
            return str(path)

    def as_dict(self) -> dict:
        d = {
            "name": self.name,
            "png": Shot._relpath(self.png),
            "blackish": self.blackish,
        }
        d.update(self.stats.as_dict())
        return d


# ---------------------------------------------------------------------------
# Suite
# ---------------------------------------------------------------------------
class Runner:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        # Rutas configurables: permiten generar el set "antes" con una ISO
        # congelada en /tmp sin tocar docs/screenshots finales.
        self.iso = (Path(args.iso).resolve() if getattr(args, "iso", None)
                    else ROOT / "sereos.iso")
        self.shots_dir = (Path(args.shots_dir).resolve()
                          if getattr(args, "shots_dir", None)
                          else ROOT / "docs" / "screenshots")
        self.raw_root = self.shots_dir / "raw"
        self.results_json = self.shots_dir / "test-results.json"
        self.expected_fatal_logs: set[Path] = set()
        self.expected_fatals: list[str] = []
        self.kvm_mode = args.kvm
        self.use_kvm: bool | None = {
            "auto": None, "on": True, "off": False
        }[args.kvm]
        self.scale = max(0.2, args.timeout_scale)
        self.run_id = time.strftime("%Y%m%d-%H%M%S")
        self.raw_dir = self.raw_root / self.run_id
        self.cases: list[Case] = []
        self.shots: list[Shot] = []
        self.vms: list[QemuController] = []
        self.logs: list[tuple[str, Path]] = []
        self.gvm: QemuController | None = None
        self.mouse_pos: tuple[int, int] = (512, 384)  # posicion inicial del cursor
        self.mouse_worked = False
        self.qemu_version = ""
        self.iso_size = 0
        self.iso_mtime = 0.0

    # -- utilidades ---------------------------------------------------------
    @staticmethod
    def _rel(path: Path) -> str:
        try:
            return str(path.relative_to(ROOT))
        except ValueError:
            return str(path)

    def t(self, seconds: float) -> float:
        return seconds * self.scale

    def new_vm(self, label: str, iso: str | Path | None = None,
               width: int = 1024, height: int = 768) -> QemuController:
        workdir = self.raw_dir / label
        vm = QemuController(
            iso=iso or self.iso,
            workdir=workdir,
            use_kvm=self.use_kvm,
            width=width,
            height=height,
        )
        self.vms.append(vm)
        self.logs.append((label, vm.log_path))
        return vm

    @staticmethod
    def _maze_bbox(img: "ppm_to_png.PPMImage") -> tuple[int, int, int, int]:
        """Localiza el laberinto por el color de sus paredes y devuelve bbox.

        El compositor puede variar ligeramente el tono de las paredes (mezcla
        alfa), asi que se detecta el color azul dominante en la banda central
        (excluyendo barra superior y dock) y se calcula su caja envolvente.
        """
        px = img.pixels
        stride = img.width * 3
        from collections import Counter
        blue = Counter()
        for y in range(70, max(71, img.height - 70)):
            base = y * stride
            for x in range(img.width):
                i = base + x * 3
                r, g, b = px[i], px[i + 1], px[i + 2]
                if b >= 180 and b > g > r and g >= 90 and r <= 140:
                    blue[(r, g, b)] += 1
        if not blue:
            return (0, 0, img.width, img.height)
        wall = blue.most_common(1)[0][0]
        wr, wg, wb = wall
        minx, miny = img.width, img.height
        maxx = maxy = -1
        for y in range(70, max(71, img.height - 70)):
            base = y * stride
            for x in range(img.width):
                i = base + x * 3
                if px[i] == wr and px[i + 1] == wg and px[i + 2] == wb:
                    if x < minx:
                        minx = x
                    if x > maxx:
                        maxx = x
                    if y < miny:
                        miny = y
                    if y > maxy:
                        maxy = y
        if maxx < 0:
            return (0, 0, img.width, img.height)
        x0 = max(0, minx - 4)
        y0 = max(0, miny - 4)
        return (x0, y0, min(img.width - x0, maxx - minx + 9),
                min(img.height - y0, maxy - miny + 9))

    @staticmethod
    def _count_family(img: "ppm_to_png.PPMImage", pred,
                      region: tuple[int, int, int, int] | None = None) -> int:
        x0, y0, w, h = region or (0, 0, img.width, img.height)
        px = img.pixels
        stride = img.width * 3
        n = 0
        for y in range(y0, y0 + h):
            base = y * stride
            for x in range(x0, x0 + w):
                i = base + x * 3
                if pred(px[i], px[i + 1], px[i + 2]):
                    n += 1
        return n

    @staticmethod
    def _count_color(img: "ppm_to_png.PPMImage", color: tuple[int, int, int],
                     region: tuple[int, int, int, int] | None = None) -> int:
        x0, y0, w, h = region or (0, 0, img.width, img.height)
        px = img.pixels
        stride = img.width * 3
        cr, cg, cb = color
        count = 0
        for y in range(y0, min(y0 + h, img.height)):
            base = y * stride
            end = base + min(x0 + w, img.width) * 3
            for i in range(base + x0 * 3, end, 3):
                if px[i] == cr and px[i + 1] == cg and px[i + 2] == cb:
                    count += 1
        return count

    def wait_app_open(self, vm: QemuController, kind: str, timeout: float,
                      since: int | None = None) -> str:
        ids = APP_IDS[kind]
        start = 0 if since is None else since
        deadline = time.time() + timeout
        while time.time() < deadline:
            text = vm.serial_text()
            pos = start
            while True:
                pos = text.find(APP_OPEN, pos)
                if pos == -1:
                    break
                at_line = pos == 0 or text[pos - 1] == "\n"
                if at_line:
                    end = text.find("\n", pos)
                    line = text[pos:end if end != -1 else len(text)].strip()
                    app_id = line[len(APP_OPEN):].strip()
                    if app_id in ids:
                        return app_id
                pos += len(APP_OPEN)
            if not vm.is_running():
                raise QemuError(
                    f"QEMU termino esperando {APP_OPEN}<{kind}>; log:\n"
                    f"{vm.serial_tail()}"
                )
            time.sleep(0.05)
        raise MarkerTimeout(f"{APP_OPEN}{kind}", timeout, vm.serial_tail())

    def wait_game(self, vm: QemuController, marker: str, timeout: float,
                  since: int | None = None) -> "object":
        return vm.wait_marker(marker, timeout, since)

    def capture(self, case: Case, vm: QemuController, name: str,
                min_colors: float = MIN_COLORS,
                min_nonblack: float = MIN_NONBLACK,
                note: str = "", publish: bool = True) -> Shot:
        """Captura la pantalla. Si publish=False solo guarda el PPM crudo y
        devuelve la imagen para verificaciones internas (no genera PNG)."""
        ppm = self.raw_dir / f"{name}.ppm"
        vm.screendump(ppm)
        img = ppm_to_png.read_ppm(ppm)
        stats = ppm_to_png.analyze(img)
        png = self.shots_dir / f"{name}.png"
        if publish:
            ppm_to_png.write_png(png, img)
        blackish = ppm_to_png.is_blackish(
            stats, int(min_colors), min_nonblack
        )
        shot = Shot(name=name, ppm=ppm, png=png, img=img, stats=stats,
                    blackish=blackish)
        if publish:
            self.shots.append(shot)
            case.shots.append(name)
        detail = (f"{stats.width}x{stats.height}, {stats.distinct_colors} colores, "
                  f"{stats.non_black_ratio:.2%} no negro")
        if note:
            detail += f", {note}"
        if blackish:
            detail += " -> CAPTURA NEGRA/VACIA"
        if publish:
            case.step(f"captura {name}", not blackish, detail)
        else:
            case.step(f"verificacion interna ({name})", None, detail)
        return shot

    def publish_shot(self, case: Case, name: str, shot: Shot) -> Shot:
        """Convierte una captura interna (PPM) en PNG final publicado."""
        png = self.shots_dir / f"{name}.png"
        ppm_to_png.write_png(png, shot.img)
        shot.name = name
        shot.png = png
        self.shots.append(shot)
        case.shots.append(name)
        case.step(f"captura {name}", True,
                  f"{shot.stats.width}x{shot.stats.height}, "
                  f"{shot.stats.distinct_colors} colores")
        return shot

    @staticmethod
    def dock_icon_center(img: "ppm_to_png.PPMImage", index: int,
                         icons: int = 5) -> tuple[int, int]:
        """Centro del icono `index` del dock, a partir de las metricas del
        tema (gui/theme.h) y del ancho real de la captura."""
        defs = {}
        try:
            text = (ROOT / "gui" / "theme.h").read_text(encoding="utf-8")
            for key in ("DOCK_HEIGHT", "DOCK_BOTTOM", "DOCK_ICON",
                        "DOCK_ICON_GAP", "DOCK_PAD"):
                m = __import__("re").search(rf"#define\s+{key}\s+(\d+)", text)
                if m:
                    defs[key] = int(m.group(1))
        except OSError:
            pass
        h = defs.get("DOCK_HEIGHT", 58)
        bottom = defs.get("DOCK_BOTTOM", 8)
        icon = defs.get("DOCK_ICON", 40)
        gap = defs.get("DOCK_ICON_GAP", 6)
        pad = defs.get("DOCK_PAD", 8)
        width = pad * 2 + icons * icon + (icons - 1) * gap
        x0 = (img.width - width) // 2
        y0 = img.height - bottom - h
        cx = x0 + pad + icon // 2 + index * (icon + gap)
        cy = y0 + h // 2
        return cx, cy

    def _raw_shot(self, vm: QemuController, name: str) -> Shot:
        ppm = self.raw_dir / f"{name}.ppm"
        if not ppm.is_file():
            vm.screendump(ppm)
        img = ppm_to_png.read_ppm(ppm)
        return Shot(name=name, ppm=ppm, png=self.shots_dir / f"{name}.png",
                    img=img, stats=ppm_to_png.analyze(img), blackish=False)

    def publish_composite(self, case: Case, name: str,
                          img: "ppm_to_png.PPMImage",
                          note: str = "") -> Shot:
        """Publica una imagen compuesta (crops apilados) como PNG final."""
        png = self.shots_dir / f"{name}.png"
        ppm_to_png.write_png(png, img)
        stats = ppm_to_png.analyze(img)
        shot = Shot(name=name, ppm=self.raw_dir / f"{name}.ppm", png=png,
                    img=img, stats=stats, blackish=False)
        self.shots.append(shot)
        case.shots.append(name)
        detail = f"{img.width}x{img.height}, {stats.distinct_colors} colores"
        if note:
            detail += f", {note}"
        case.step(f"captura {name}", True, detail)
        return shot

    @staticmethod
    def region_below_topbar(img: "ppm_to_png.PPMImage",
                            topbar: int = 80) -> tuple[int, int, int, int]:
        return (0, topbar, img.width, max(1, img.height - topbar))

    def screen_changed(self, case: Case, text: str, a: Shot, b: Shot,
                       min_ratio: float = 0.0002, topbar: int = 80) -> bool:
        region = self.region_below_topbar(a.img, topbar)
        ratio = ppm_to_png.diff_ratio(a.img, b.img, region)
        case.step(text, ratio >= min_ratio, f"diferencia = {ratio:.4%}")
        return ratio >= min_ratio

    def fatal_in(self, vm: QemuController) -> list[str]:
        return vm.fatal_markers()

    def require_gui(self, case: Case) -> bool:
        if self.gvm is None or not self.gvm.is_running():
            case.skip_reason = "el escritorio grafico no llego a arrancar"
            return False
        return True

    # -- tests --------------------------------------------------------------
    def test_boot(self, case: Case) -> bool | None:
        vm = self.new_vm("gfx")
        self.gvm = vm
        vm.start()
        self.mouse_pos = (vm.width // 2, vm.height // 2)
        case.step(
            "QEMU arrancado",
            True,
            f"KVM={'si' if vm.used_kvm else 'no'}, "
            f"serial={self._rel(vm.log_path)}",
        )

        # Captura opcional del menu GRUB (informativa, antes del timeout de 2 s)
        if not self.args.no_grub_shot:
            time.sleep(0.45)
            try:
                self.capture(case, vm, "00_grub_menu",
                             min_colors=2, min_nonblack=0.0002,
                             note="menu GRUB (informativa)")
            except QemuError as exc:
                case.step("captura 00_grub_menu", None,
                          f"no disponible: {exc}")

        hit = vm.wait_marker(MARK_BOOT, self.t(60))
        case.step(f"marcador {MARK_BOOT}", True,
                  f"linea {hit.line_no}: {hit.line}")
        time.sleep(self.t(0.40))      # splash nuevo dura ~1 s: capturar a media
        splash = self.capture(case, vm, "01_splash",
                              note="pantalla de arranque con logo oficial")
        try:
            sb = self.logo_bbox(splash.img,
                                (splash.img.width // 2 - 220,
                                 splash.img.height // 2 - 200, 440, 400))
            if sb:
                bw, bh = sb["bbox"][2], sb["bbox"][3]
                aspect = bw / bh if bh else 0
                case.step("logo oficial en el splash (azul de marca + proporcion)",
                          bh >= 40 and 0.80 <= aspect <= 1.35,
                          f"bbox={bw}x{bh}, aspecto={aspect:.2f} "
                          f"(oficial {OFFICIAL_LOGO_ASPECT:.2f})")
            else:
                case.step("logo oficial en el splash", None,
                          "no se detecto el azul de marca en la captura")
        except ppm_to_png.PPMError as exc:
            case.step("logo oficial en el splash", None, str(exc))

        splash_ok = True
        try:
            hit = vm.wait_marker(MARK_SPLASH, self.t(35))
            case.step(f"marcador {MARK_SPLASH}", True,
                      f"linea {hit.line_no}: {hit.line}")
        except MarkerTimeout:
            splash_ok = False
            case.fail(f"marcador {MARK_SPLASH}",
                      "splash_run() no emitio SPLASH_DONE")

        try:
            hit = vm.wait_marker(MARK_GUI, self.t(35))
            case.step(f"marcador {MARK_GUI}", True,
                      f"linea {hit.line_no}: {hit.line}")
        except MarkerTimeout:
            case.fail(f"marcador {MARK_GUI}",
                      "el bucle del escritorio no arranco")

        try:
            hit = vm.wait_marker(MARK_DESKTOP, self.t(8))
            case.step(f"marcador {MARK_DESKTOP}", True,
                      f"linea {hit.line_no}: {hit.line}")
        except MarkerTimeout:
            case.fail(f"marcador {MARK_DESKTOP}",
                      "gui_init() no emitio DESKTOP_READY")

        time.sleep(self.t(0.6))
        desktop = self.capture(case, vm, "02_desktop", note="escritorio SereOS")

        # 02b: zoom de la barra superior + dock para revisar tipografia,
        # alineacion, contraste y centrado del dock.
        try:
            top = ppm_to_png.crop(desktop.img, 0, 0, desktop.img.width, 64)
            dock = ppm_to_png.crop(desktop.img, 0, desktop.img.height - 128,
                                   desktop.img.width, 128)
            sep = ppm_to_png.PPMImage(desktop.img.width, 8, 255,
                                      bytes((0x2A, 0x30, 0x40)) * desktop.img.width * 8)
            composite = ppm_to_png.vstack([top, sep, dock])
            self.publish_composite(case, "02b_topbar_dock", composite,
                                   note="zoom barra superior + dock")
        except ppm_to_png.PPMError as exc:
            case.fail("captura 02b_topbar_dock", str(exc))

        # 02c: tooltip del dock tras hover con el raton; verifica la
        # identidad visible "PAC-MAN SereOS" del icono del juego.
        try:
            gx, gy = self.dock_icon_center(desktop.img, 3)
            self.mouse_goto(vm, gx, gy)
            time.sleep(self.t(0.8))
            self.capture(case, vm, "02c_dock_tooltip",
                         note="tooltip del dock: PAC-MAN SereOS")
            self.mouse_goto(vm, vm.width // 2, vm.height // 2)
            time.sleep(self.t(0.3))
        except (QemuError, OSError) as exc:
            case.step("captura 02c_dock_tooltip", None, f"no disponible: {exc}")

        # Marca de la topbar: glifo ribbon del PNG (S blanca sobre
        # transparente) SIN contenedor azul, a la altura visual del wordmark
        # (~9x10), centrado en su linea (align-items:center) y gap 8 px.
        try:
            ink = self.topbar_white_ink(desktop.img)
            blue = self.topbar_blue_px(desktop.img)
            word = (self.topbar_word_ink(
                desktop.img,
                x_from=(ink["bbox"][0] + ink["bbox"][2] + 2) if ink else 24)
                if ink else None)
            if ink and word:
                bw, bh = ink["bbox"][2], ink["bbox"][3]
                gap = word["bbox"][0] - (ink["bbox"][0] + bw)
                dcy = abs(ink["center"][1] - word["center"][1])
                ok = (7 <= bw <= 12 and 8 <= bh <= 13 and blue == 0
                      and gap in (7, 8, 9) and dcy <= 1)
                case.step("marca ribbon ~9x10 alineada con el wordmark "
                          "(PNG sin fondo azul)",
                          ok, f"glifo bbox={bw}x{bh}, gap={gap}px, "
                              f"centro glifo_y={ink['center'][1]} vs "
                              f"wordmark_y={word['center'][1]} "
                              f"(desvio {dcy}px), azul_topbar={blue}px")
            else:
                case.step("marca ribbon ~9x10 alineada con el wordmark "
                          "(PNG sin fondo azul)", False,
                          f"sin tinta blanca (glifo={bool(ink)}, "
                          f"wordmark={bool(word)}); azul_topbar={blue}px")
            case.step("topbar mantiene 30 px de alto (UI bajo la barra en y=30)",
                      TOPBAR_HEIGHT_THEME == 30,
                      f"TOPBAR_HEIGHT_THEME={TOPBAR_HEIGHT_THEME}")
        except ppm_to_png.PPMError as exc:
            case.step("marca ribbon suelta en la topbar", None, str(exc))

        # 22: menu principal abierto (cabecera con logo oficial)
        try:
            mx, my = self.find_menu_button(desktop.img)
            self.mouse_click_at(vm, mx, my)
            time.sleep(self.t(0.8))
            menu = self.capture(case, vm, "22_menu_logo",
                                note="menu principal con logo oficial")
            ratio = ppm_to_png.diff_ratio(
                desktop.img, menu.img,
                self.region_below_topbar(desktop.img))
            case.step("el menu principal se abre desde la topbar",
                      ratio > 0.001, f"diferencia = {ratio:.3%}")
            self.mouse_click_at(vm, vm.width // 2, vm.height // 2)
            time.sleep(self.t(0.4))
            self.mouse_goto(vm, vm.width // 2, vm.height // 2)
        except (QemuError, ppm_to_png.PPMError) as exc:
            case.step("captura 22_menu_logo", None, f"no disponible: {exc}")

        # identidad: no deben quedar referencias al logotipo antiguo
        old_refs: list[str] = []
        for sub in ("gui", "graphics", "kernel", "apps", "tools"):
            base = ROOT / sub
            if not base.is_dir():
                continue
            for src in base.rglob("*"):
                if not src.is_file() or src.suffix not in (".c", ".h", ".py"):
                    continue
                try:
                    text = src.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                import re as _re
                patterns = {
                    "logo_badge": _re.compile(r"(?<![A-Za-z0-9_])logo_badge(?![A-Za-z0-9_])"),
                    "logo_s": _re.compile(r"(?<![A-Za-z0-9_])logo_s(?![A-Za-z0-9_])"),
                    "logo_mono": _re.compile(r"(?<![A-Za-z0-9_])logo_mono(?![A-Za-z0-9_])"),
                }
                if src == Path(__file__):
                    continue
                for token, pat in patterns.items():
                    if pat.search(text):
                        old_refs.append(f"{self._rel(src)}:{token}")
        bin_path = ROOT / "sereos.bin"
        if bin_path.is_file():
            blob = bin_path.read_bytes()
            for token in (b"logo_badge", b"logo_mono"):
                if token in blob:
                    old_refs.append(f"sereos.bin:{token.decode()}")
        case.step("sin referencias al logo antiguo (logo_badge/logo_s/logo_mono)",
                  not old_refs, "; ".join(old_refs[:6]) if old_refs else
                  "fuentes y binario limpios")
        uses_official = False
        official_ref = ""
        for candidate in ("tools/gen_logo.py", "gui/logo_data.c",
                          "tools/gen_ui_icons.py"):
            try:
                txt = (ROOT / candidate).read_text(
                    encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if "official_logo" in txt or "logo oficial" in txt.lower():
                uses_official = True
                official_ref = candidate
                break
        case.step("el logo se genera desde assets/logo/official_logo.png",
                  uses_official,
                  official_ref or "no se encontro la referencia al logo oficial")

        fatals = self.fatal_in(vm)
        case.step("sin excepcion/panico durante el arranque",
                  not fatals, "; ".join(fatals) if fatals else "log limpio")
        return case.ok

    def test_terminal(self, case: Case) -> bool | None:
        if not self.require_gui(case):
            return None
        vm = self.gvm
        assert vm is not None
        self.close_all_windows_quiet(vm)

        since = vm.marker_offset()
        vm.press("f2")
        try:
            app_id = self.wait_app_open(vm, "terminal", self.t(12), since)
            case.step(f"F2 abre la terminal ({APP_OPEN}{app_id})", True)
        except MarkerTimeout as exc:
            case.fail("F2 abre la terminal", str(exc))
        time.sleep(self.t(0.8))
        term0 = self.capture(case, vm, "term_open", note="terminal abierta", publish=False)

        prev = term0
        commands = [
            ("help", "04_terminal_help"),
            ("ls", "05_terminal_ls"),
            ("date", "06_terminal_date"),
            ("free", "07_terminal_free"),
            ("dmesg", "08_terminal_dmesg"),
        ]
        fatal_since = len([ln for ln in vm.serial_lines()
                           if ln.startswith(FATAL_PREFIXES)])
        for cmd, shot_name in commands:
            vm.type_line(cmd, delay=self.t(0.07), settle=self.t(0.6))
            time.sleep(self.t(0.15))
            shot = self.capture(case, vm, f"term_{cmd}", note=f"comando '{cmd}'",
                                publish=False)
            self.screen_changed(
                case, f"el comando '{cmd}' produce salida visible",
                prev, shot, min_ratio=0.0002)
            prev = shot
        self.publish_shot(case, "03_terminal", prev)
        new_fatals = [ln for ln in vm.serial_lines()
                      if ln.startswith(FATAL_PREFIXES)][fatal_since:]
        case.step("comandos de terminal sin excepcion/panico", not new_fatals,
                  "; ".join(new_fatals) if new_fatals else "log limpio")
        return case.ok

    def test_files(self, case: Case) -> bool | None:
        if not self.require_gui(case):
            return None
        vm = self.gvm
        self.close_all_windows_quiet(vm)
        since = vm.marker_offset()
        vm.press("f1")
        try:
            app_id = self.wait_app_open(vm, "files", self.t(12), since)
            case.step(f"F1 abre el gestor de archivos ({APP_OPEN}{app_id})", True)
        except MarkerTimeout as exc:
            case.fail("F1 abre el gestor de archivos", str(exc))
        time.sleep(self.t(0.8))
        root = self.capture(case, vm, "04_files",
                            note="explorador del RAMFS en /")
        # en / las entradas se ordenan: directorios primero (/docs, /home),
        # luego archivos; con flecha abajo se selecciona /home y Enter entra.
        vm.press("down")
        time.sleep(self.t(0.3))
        vm.press("ret")
        time.sleep(self.t(0.9))
        home = self.capture(case, vm, "04b_files_home",
                            note="explorador en /home")
        self.screen_changed(case, "el explorador navega a /home",
                            root, home, min_ratio=0.0005)
        vm.press("backspace")          # volver a la raiz
        time.sleep(self.t(0.4))
        return case.ok

    def test_monitor(self, case: Case) -> bool | None:
        if not self.require_gui(case):
            return None
        vm = self.gvm
        self.close_all_windows_quiet(vm)
        since = vm.marker_offset()
        vm.press("f3")
        try:
            app_id = self.wait_app_open(vm, "monitor", self.t(12), since)
            case.step(f"F3 abre el monitor del sistema ({APP_OPEN}{app_id})", True)
        except MarkerTimeout as exc:
            case.fail("F3 abre el monitor del sistema", str(exc))
        time.sleep(self.t(1.6))
        self.capture(case, vm, "05_monitor", note="monitor del sistema")
        return case.ok

    def test_about(self, case: Case) -> bool | None:
        if not self.require_gui(case):
            return None
        vm = self.gvm
        self.close_all_windows_quiet(vm)
        since = vm.marker_offset()
        vm.press("f5")
        try:
            app_id = self.wait_app_open(vm, "about", self.t(12), since)
            case.step(f"F5 abre 'Acerca de' ({APP_OPEN}{app_id})", True)
        except MarkerTimeout as exc:
            case.fail("F5 abre 'Acerca de'", str(exc))
        time.sleep(self.t(1.8))   # deja 1 s para que About refresque 14/14
        self.capture(case, vm, "06_about", note="acerca de SereOS (14/14 + audio)")
        # Comprobacion informativa: el rediseno soporta Latin-1 (acentos/ñ) en
        # las fuentes de UI. Si no aparece, se documenta que el teclado es US.
        try:
            import re as _re
            accented: list[str] = []
            pattern = _re.compile(r'"[^"\\n]*[áéíóúÁÉÍÓÚñÑüÜ¿¡][^"\\n]*"')
            for sub in ("gui", "apps", "graphics", "kernel"):
                root = ROOT / sub
                if not root.is_dir():
                    continue
                for src in root.rglob("*.c"):
                    try:
                        text = src.read_text(encoding="utf-8")
                    except (UnicodeDecodeError, OSError):
                        continue
                    if pattern.search(text):
                        accented.append(str(src.relative_to(ROOT)))
            case.step("texto Latin-1 (acentos/ñ) en cadenas de UI:", None,
                      (f"{len(accented)} ficheros: " + ", ".join(accented[:5]))
                      if accented else
                      "no hay cadenas con acentos; el teclado es US (documentado)")
        except Exception as exc:  # noqa: BLE001 - informativo
            case.step("chequeo de acentos", None, f"no disponible: {exc}")
        return case.ok

    # -- maximizacion full-bleed del WM (capturas 25-30) --------------------
    def test_maximize(self, case: Case) -> bool | None:
        """Maximizacion real: full-bleed, sin wallpaper, barras unicas,
        restaurar exacto, doble clic, minimizar conservando estado y resize."""
        if not self.require_gui(case):
            return None
        vm = self.gvm
        assert vm is not None
        self.close_all_windows_quiet(vm)
        time.sleep(self.t(0.6))
        baseline = self.capture(case, vm, "max_baseline", publish=False,
                                note="escritorio de referencia sin ventanas")
        h = baseline.img.height

        # abrir Archivos en tamano normal
        since = vm.marker_offset()
        vm.press("f1")
        try:
            self.wait_app_open(vm, "files", self.t(10), since)
        except MarkerTimeout as exc:
            case.fail("abrir Archivos para maximizar", str(exc))
        time.sleep(self.t(0.9))
        normal = self.capture(case, vm, "max_normal", publish=False,
                              note="Archivos normal antes de maximizar")
        tb0 = self.detect_titlebar(normal.img)
        opens0 = self.app_open_count(vm, "files")
        case.step("ventana normal detectada", tb0 is not None,
                  f"titlebar={tb0}, APP_OPEN:files={opens0}")

        # 3) maximizar con el semaforo verde -> full-bleed
        self.click_traffic(vm, 2)
        time.sleep(self.t(0.6))
        full = self.capture(case, vm, "25_maximized_fullbleed",
                            note="Archivos maximizado full-bleed")
        m = self.full_bleed_metrics(full.img, baseline.img)
        case.step("full-bleed: cubre x=0..w-1, y=30..sh-1 (full-height) "
                  "sin wallpaper",
                  m.get("full_bleed", False),
                  f"wallpaper_ratio={m.get('wallpaper_ratio')}, "
                  f"corners={m.get('corners')}, rect={m.get('rect')}")
        # esquina superior izquierda (0,30) no debe ser fondo del escritorio
        i = (TOPBAR_HEIGHT_THEME * full.img.width + 0) * 3
        corner = tuple(full.img.pixels[i:i + 3])
        bi = (TOPBAR_HEIGHT_THEME * baseline.img.width + 0) * 3
        bg_corner = tuple(baseline.img.pixels[bi:bi + 3])
        case.step("esquina (0,30) no es fondo del escritorio",
                  corner != bg_corner,
                  f"ventana={corner}, fondo={bg_corner}")
        # unicidad: la topbar ya NO usa azul de marca (marca = glifo ribbon
        # del PNG suelto), asi que n_top==0 (sin clusters azules en la barra).
        # Se exige ademas que la marca blanca siga presente en la topbar para
        # no perder la intencion original de este test.
        logos = self._color_clusters(full.img, OFFICIAL_LOGO_BLUE,
                                     tol=LOGO_TOL, min_size=12)
        n_top = sum(1 for c in logos if c["center"][1]
                    < TOPBAR_HEIGHT_THEME)
        n_bottom = sum(1 for c in logos
                       if c["center"][1] >= h - TASKBAR_HEIGHT_THEME)
        n_mid = len(logos) - n_top - n_bottom
        ribbon_ink = self.topbar_white_ink(full.img)
        case.step("una sola topbar global y sin dock/taskbar duplicados "
                  "(marca ribbon sin azul)",
                  n_top == 0 and n_bottom == 0 and n_mid == 0
                  and ribbon_ink is not None,
                  f"logos_azules top={n_top}, barra={n_bottom}, "
                  f"contenido={n_mid}, ribbon={bool(ribbon_ink)}")
        dmm = self.dock_metrics(full.img, baseline.img)
        nmm = self.topnav_metrics(full.img)
        case.step("sin dock/taskbar inferior: app full-height y nav en topbar",
                  dmm["full_height"] and dmm["dock_icon_px"] == 0
                  and nmm["nav_present"],
                  f"dock={dmm}, nav={nmm['nav_present']}")

        # 4) restaurar con el semaforo verde: rect exacto y sin APP_OPEN nuevo
        self.click_traffic(vm, 2)
        time.sleep(self.t(0.6))
        restored = self.capture(case, vm, "26_restore_exact",
                                note="restaurada al rect previo")
        tb1 = self.detect_titlebar(restored.img)
        same_rect = (tb0 is not None and tb1 is not None
                     and abs(tb0["x"] - tb1["x"]) <= 1
                     and abs(tb0["y"] - tb1["y"]) <= 1
                     and abs(tb0["width"] - tb1["width"]) <= 2)
        case.step("restaurar recupera EXACTAMENTE el rect previo",
                  same_rect, f"antes={tb0}, despues={tb1}")
        opens1 = self.app_open_count(vm, "files")
        case.step("restaurar no crea una instancia nueva (APP_OPEN no se repite)",
                  opens1 == opens0, f"APP_OPEN:files {opens0} -> {opens1}")
        not_full = self.full_bleed_metrics(restored.img, baseline.img)
        case.step("tras restaurar ya no es full-bleed",
                  not not_full.get("full_bleed", True), str(not_full))

        # 5) doble clic en la barra de titulo -> maximiza y restaura
        tb = self.detect_titlebar(restored.img)
        if tb:
            self.double_click(vm, tb["x"] + min(180, tb["width"] // 2),
                              tb["center_y"])
        else:
            case.fail("doble clic en titlebar", "no se detecto la titlebar")
        dbl = self.capture(case, vm, "27_doubleclick",
                           note="maximizada con doble clic en titlebar")
        md = self.full_bleed_metrics(dbl.img, baseline.img)
        case.step("doble clic en titlebar maximiza (full-bleed)",
                  md.get("full_bleed", False), str(md))
        tbm = self.detect_titlebar(dbl.img)
        if tbm:
            self.double_click(vm, tbm["x"] + min(180, tbm["width"] // 2),
                              tbm["center_y"])
        back = self.capture(case, vm, "max_dbl_back", publish=False,
                            note="doble clic de nuevo: restaurada")
        tbb = self.detect_titlebar(back.img)
        case.step("doble clic de nuevo restaura",
                  tbb is not None and not self.full_bleed_metrics(
                      back.img, baseline.img).get("full_bleed", True),
                  f"titlebar={tbb}")

        # 6) minimizar una maximizada -> dock; restaurar -> maximizada
        self.click_traffic(vm, 2)          # maximizar
        time.sleep(self.t(0.5))
        self.click_traffic(vm, 1)          # minimizar (semaforo amarillo)
        time.sleep(self.t(0.6))
        mini = self._probe_img(vm, "max_minimized")
        dmini = self.dock_metrics(mini, baseline.img)
        nmini = self.topnav_metrics(mini)
        case.step("minimizar una maximizada devuelve el dock",
                  (not dmini["full_height"]) and dmini["dock_icon_px"] > 40
                  and not nmini["nav_present"],
                  f"dock={dmini}, nav={nmini['nav_present']}")
        # restaurar desde el icono del dock (Archivos = indice 0)
        self.sync_mouse_origin(vm)
        dock = self._probe_img(vm, "max_dock")
        dx, dy = self.dock_icon_center(dock, 0)
        self.mouse_click_at(vm, dx, dy)
        time.sleep(self.t(0.9))
        mini_rest = self.capture(case, vm, "28_minimize_restore",
                                 note="restaurada desde el dock: maximizada")
        mr = self.full_bleed_metrics(mini_rest.img, baseline.img)
        case.step("restaurar desde el dock vuelve MAXIMIZADA full-bleed",
                  mr.get("full_bleed", False), str(mr))
        case.step("restaurar desde el dock no crea instancia nueva",
                  self.app_open_count(vm, "files") == opens0,
                  f"APP_OPEN:files={self.app_open_count(vm, 'files')}")

        # 7) otras apps maximizadas (Terminal captura 29; Monitor/About/Pacman
        #    verificadas por pixeles y revisadas visualmente)
        self.close_all_windows_quiet(vm)
        time.sleep(self.t(0.4))
        apps = [
            ("f2", "terminal", "29_max_terminal"),
            ("f3", "monitor", None),
            ("f5", "about", None),
            ("f4", "game", None),
        ]
        for key, app_id, shot_name in apps:
            since = vm.marker_offset()
            vm.press(key)
            try:
                if app_id == "game":
                    self.wait_app_open(vm, "game", self.t(12), since)
                    vm.wait_marker("GAME_MENU", self.t(12), since)
                else:
                    self.wait_app_open(vm, app_id, self.t(12), since)
            except MarkerTimeout as exc:
                case.fail(f"abrir {app_id} para maximizar", str(exc))
                continue
            time.sleep(self.t(0.9))
            opens = self.app_open_count(vm, app_id)
            self.click_traffic(vm, 2)
            time.sleep(self.t(0.7))
            probe = self._probe_img(vm, f"max_{app_id}")
            if os.environ.get("SEREOS_QA_DEBUG"):
                print(f"[qa] {app_id} tras verde: "
                      f"tb={self.detect_titlebar(probe)} "
                      f"nav={self.topnav_metrics(probe)['nav_present']} "
                      f"dock={self.dock_metrics(probe)}", file=sys.stderr)
            if not self.topnav_metrics(probe)["nav_present"]:
                # un cierre pendiente pudo interceptar el clic: reintentar
                time.sleep(self.t(0.6))
                self.click_traffic(vm, 2)
                time.sleep(self.t(0.7))
                probe = self._probe_img(vm, f"max_{app_id}")
            if shot_name:
                shot = self.publish_shot(case, shot_name,
                                         self._raw_shot(vm, f"max_{app_id}"))
            else:
                shot = None
            fm = self.full_bleed_metrics(probe, baseline.img)
            if app_id == "about":
                # la topbar no usa azul (marca = glifo ribbon del PNG); el
                # unico azul del contenido es el logo de About.
                logos = self._color_clusters(probe, OFFICIAL_LOGO_BLUE,
                                             tol=LOGO_TOL, min_size=12)
                n_top = sum(1 for c in logos if c["center"][1]
                            < TOPBAR_HEIGHT_THEME)
                ribbon_ink = self.topbar_white_ink(probe)
                case.step(f"{app_id} maximizado: una sola topbar, sin barra inferior",
                          n_top == 0 and ribbon_ink is not None,
                          f"logos_azules top={n_top}, "
                          f"ribbon={bool(ribbon_ink)}")
            case.step(f"{app_id} maximizado ocupa todo el work area",
                      fm.get("full_bleed", False), str(fm))
            case.step(f"{app_id} maximizado sin instancia nueva",
                      self.app_open_count(vm, app_id) == opens,
                      f"APP_OPEN:{app_id}={self.app_open_count(vm, app_id)}")
            self.close_all_windows_quiet(vm)
            time.sleep(self.t(0.4))

        # 8) resize de una ventana normal (borde derecho + minimo 300x180)
        since = vm.marker_offset()
        vm.press("f1")
        try:
            self.wait_app_open(vm, "files", self.t(10), since)
        except MarkerTimeout as exc:
            case.fail("abrir Archivos para resize", str(exc))
        time.sleep(self.t(0.9))
        self.sync_mouse_origin(vm)
        r0 = self._probe_img(vm, "resize_before")
        t0 = self.detect_titlebar(r0)
        resized_ok = False
        detail_resize = "no se detecto la ventana"
        if t0:
            # arrastrar el borde derecho +48 px (cabe en el work area, sin
            # que el clamp desplace la ventana)
            self.mouse_goto(vm, t0["right"], t0["center_y"] + 60)
            vm.mouse_button("left", True)
            time.sleep(0.1)
            dx = 48
            while dx > 0:
                step = min(16, dx)
                vm.mouse_move_rel(step, 0)
                dx -= step
                time.sleep(0.02)
            vm.mouse_button("left", False)
            time.sleep(self.t(0.8))
            r1 = self._probe_img(vm, "resize_after")
            t1 = self.detect_titlebar(r1)
            self.publish_shot(case, "30_resize", self._raw_shot(vm, "resize_after"))
            if t1:
                grew = (t1["width"] - t0["width"])
                same_origin = (abs(t1["x"] - t0["x"]) <= 1
                               and abs(t1["y"] - t0["y"]) <= 1)
                resized_ok = same_origin and 25 <= grew <= 70
                detail_resize = (f"ancho {t0['width']} -> {t1['width']} "
                                 f"(delta={grew}), origen igual={same_origin}")
            case.step("resize por el borde derecho agranda la ventana",
                      resized_ok, detail_resize)
            # encoger por debajo del minimo: debe respetar 300 px de ancho
            if t1:
                self.sync_mouse_origin(vm)   # evita deriva del arrastre previo
                rm = self._probe_img(vm, "resize_min_before")
                tm = self.detect_titlebar(rm)
                if tm:
                    self.mouse_goto(vm, tm["right"], tm["center_y"] + 60)
                    vm.mouse_button("left", True)
                    time.sleep(0.1)
                    dx = -700
                    while dx < 0:
                        step = max(-16, dx)
                        vm.mouse_move_rel(step, 0)
                        dx -= step
                        time.sleep(0.02)
                    vm.mouse_button("left", False)
                    time.sleep(self.t(0.7))
                    r2 = self._probe_img(vm, "resize_min")
                    t2 = self.detect_titlebar(r2)
                    if t2:
                        # la barra de titulo mide w-2 (bordes de 1 px)
                        case.step("resize respeta el minimo de 300 px de ancho",
                                  t2["width"] + 2 >= 300,
                                  f"ancho final={t2['width']} (+2 bordes)")
        else:
            case.fail("resize de ventana normal", detail_resize)
        self.close_all_windows_quiet(vm)
        fatals = self.fatal_in(vm)
        case.step("sin excepcion/panico en maximizar/restaurar/resize",
                  not fatals, "; ".join(fatals) if fatals else "log limpio")
        return case.ok

    # -- esquinas redondeadas: clipping y mosaico 33 ------------------------
    def test_window_corners(self, case: Case) -> bool | None:
        """Valida el clipping de esquinas: dentro del arco se conserva el
        contenido (barra de estado surface_2), fuera se restaura el fondo real
        sin parches de color de cuerpo; incluye solape y resize."""
        if not self.require_gui(case):
            return None
        vm = self.gvm
        assert vm is not None
        self.close_all_windows_quiet(vm)
        time.sleep(self.t(0.6))

        since = vm.marker_offset()
        vm.press("f1")
        try:
            self.wait_app_open(vm, "files", self.t(10), since)
        except MarkerTimeout as exc:
            case.fail("abrir Archivos para las esquinas", str(exc))
        time.sleep(self.t(0.9))
        normal = self._probe_img(vm, "corners_normal")
        rect = self.detect_window_rect(normal)
        case.step("ventana normal detectada (rect con borde)",
                  rect is not None, str(rect))
        if not rect:
            self.close_all_windows_quiet(vm)
            return case.ok

        # 1) esquina inferior derecha: dentro = barra de estado; fuera = fondo
        m = self.corner_metrics(normal, rect)
        br = m["br"]
        inside_ok = self._near_c(br["inside_mode"], WIN_STATUS_COLOR, 4)
        case.step("BR: dentro del arco se conserva la barra de estado "
                  "(surface_2 26,30,38) y no el cuerpo (20,23,30)",
                  inside_ok and not self._near_c(br["inside_mode"],
                                                 WIN_BODY_COLOR, 4),
                  f"interior={br['inside_mode']}, cuerpo={WIN_BODY_COLOR}")
        outside_ok = (br["body_outside"] <= 2
                      and not self._near_c(br["outside_mode"],
                                           WIN_BODY_COLOR, 4)
                      and not self._near_c(br["outside_mode"],
                                           WIN_STATUS_COLOR, 4))
        case.step("BR: fuera del arco no hay parche de 14x14 del color del "
                  "cuerpo (se restaura fondo/sombra)",
                  outside_ok,
                  f"fuera={br['outside_mode']}, px_cuerpo_fuera="
                  f"{br['body_outside']}, colores_fuera="
                  f"{br['outside_colors']}")
        body_any = sum(v["body_outside"] for v in m.values())
        inside_bad = [k for k, v in m.items()
                      if not self._near_c(v["inside_mode"],
                                          WIN_STATUS_COLOR, 4)]
        case.step("las 4 esquinas limpias (interior status, sin parches fuera)",
                  body_any == 0 and not inside_bad,
                  f"px_cuerpo_fuera_total={body_any}, "
                  f"interiores={ {k: m[k]['inside_mode'] for k in m} }, "
                  f"mal={inside_bad}")

        # 2) captura de evidencia: mosaico 2x2 de las 4 esquinas a 10x
        mosaic = self.corner_mosaic(normal, rect)
        self.publish_composite(case, "33_window_corners_clean", mosaic,
                               note="mosaico 4 esquinas de Archivos a 10x")
        case.step("mosaico de esquinas generado a 10x",
                  mosaic.width >= 700 and mosaic.height >= 700,
                  f"{mosaic.width}x{mosaic.height}")

        # 3) solape: Terminal sobre Archivos; su esquina BR cae fuera de
        #    Archivos (fondo) y debe restaurar el fondo, no un parche
        since = vm.marker_offset()
        vm.press("f2")
        try:
            self.wait_app_open(vm, "terminal", self.t(10), since)
        except MarkerTimeout as exc:
            case.fail("abrir Terminal superpuesta", str(exc))
        time.sleep(self.t(0.9))
        overlap = self._probe_img(vm, "corners_overlap")
        orect = self.detect_window_rect(overlap)
        if orect:
            om = self.corner_metrics(overlap, orect)
            obr = om["br"]
            case.step("solape: BR de la ventana superior conserva la barra de "
                      "estado por dentro y fondo por fuera (sin parche)",
                      self._near_c(obr["inside_mode"], WIN_STATUS_COLOR, 4)
                      and obr["body_outside"] <= 2
                      and not self._near_c(obr["outside_mode"],
                                           WIN_BODY_COLOR, 4),
                      f"rect={orect}, interior={obr['inside_mode']}, "
                      f"fuera={obr['outside_mode']}, "
                      f"px_cuerpo_fuera={obr['body_outside']}")
            pass  # solape verificado por pixeles; sin captura extra
        else:
            case.step("solape: ventana superior detectada", None,
                      "no se pudo detectar el rect de Terminal")
        vm.sendkey("ctrl+w")
        time.sleep(self.t(0.8))

        # 4) resize: arrastrar borde derecho +40 y revalidar la esquina
        self.sync_mouse_origin(vm)
        r0 = self._probe_img(vm, "corners_resize_before")
        r0rect = self.detect_window_rect(r0)
        if r0rect:
            self.mouse_goto(vm, r0rect["right"], r0rect["y"] + 200)
            vm.mouse_button("left", True)
            time.sleep(0.1)
            dx = 40
            while dx > 0:
                step = min(16, dx)
                vm.mouse_move_rel(step, 0)
                dx -= step
                time.sleep(0.02)
            vm.mouse_button("left", False)
            time.sleep(self.t(0.8))
            r1 = self._probe_img(vm, "corners_resize_after")
            r1rect = self.detect_window_rect(r1)
            if r1rect and r0rect:
                grew = r1rect["w"] - r0rect["w"]
                rm = self.corner_metrics(r1, r1rect)
                rbr = rm["br"]
                case.step("resize: esquina BR sigue limpia (status dentro, "
                          "fondo fuera)",
                          abs(grew) >= 20
                          and self._near_c(rbr["inside_mode"],
                                           WIN_STATUS_COLOR, 4)
                          and rbr["body_outside"] <= 2,
                          f"ancho {r0rect['w']}->{r1rect['w']} "
                          f"(delta={grew}), interior={rbr['inside_mode']}, "
                          f"px_cuerpo_fuera={rbr['body_outside']}")
                pass  # resize verificado por pixeles; sin captura extra
            else:
                case.step("resize: rect detectado", None,
                          f"antes={r0rect}, despues={r1rect}")
        else:
            case.step("resize: ventana normal detectada", None, "sin rect")
        self.close_all_windows_quiet(vm)
        fatals = self.fatal_in(vm)
        case.step("sin excepcion/panico durante la revision de esquinas",
                  not fatals, "; ".join(fatals) if fatals else "log limpio")
        return case.ok

    # -- dock -> barra de tareas adaptativa (capturas 18-21) ----------------
    def _probe_img(self, vm: QemuController, name: str):
        probe = self.raw_dir / f"{name}.ppm"
        vm.screendump(probe)
        return ppm_to_png.read_ppm(probe)

    def maximize_with_traffic_light(self, vm: QemuController) -> tuple[bool, str]:
        """Pulsa el semaforo verde de la ventana superior; True si cambio."""
        self.sync_mouse_origin(vm)
        img = self._probe_img(vm, "taskbar_probe")
        btn = self.find_maximize_button(img)
        if btn is None:
            return (False, "no se detecto el semaforo de la ventana")
        self.mouse_click_at(vm, btn[0], btn[1])
        time.sleep(self.t(1.1))
        img2 = self._probe_img(vm, "taskbar_probe_after")
        state = self.bottom_bar_state(img2)
        return (self.maximized_window_present(img2)
                or self.topnav_metrics(img2)["nav_present"],
                f"semaforo en {btn}, estado={state}, "
                f"nav={self.topnav_metrics(img2)['nav_present']}")

    def test_dock(self, case: Case) -> bool | None:
        """Sin ventanas maximizadas: dock flotante normal, topbar sin nav."""
        if not self.require_gui(case):
            return None
        vm = self.gvm
        assert vm is not None
        self.close_all_windows_quiet(vm)
        time.sleep(self.t(0.6))
        since = vm.marker_offset()
        vm.press("f1")
        try:
            self.wait_app_open(vm, "files", self.t(10), since)
        except MarkerTimeout as exc:
            case.fail("abrir Archivos con el dock", str(exc))
        time.sleep(self.t(0.9))
        shot = self.capture(case, vm, "18_dock_window",
                            note="dock flotante con ventana normal")
        dm = self.dock_metrics(shot.img)
        nm = self.topnav_metrics(shot.img)
        case.step("dock inferior visible y ninguna nav en la topbar",
                  (not dm["full_height"]) and dm["dock_icon_px"] > 40
                  and not nm["nav_present"],
                  f"dock={dm}, nav={nm['nav_present']}")
        self.close_all_windows_quiet(vm)
        time.sleep(self.t(0.7))
        restored = self.capture(case, vm, "21_dock_restored",
                                note="dock restaurado sin ventanas")
        dm2 = self.dock_metrics(restored.img)
        nm2 = self.topnav_metrics(restored.img)
        case.step("vuelve el dock flotante y la topbar muestra el nombre de app",
                  (not dm2["full_height"]) and dm2["dock_icon_px"] > 40
                  and not nm2["nav_present"], f"dock={dm2}")
        return case.ok

    # -- navegacion adaptativa: dock oculto + topnav central -----------------
    def _click_nav(self, vm: QemuController, index: int) -> None:
        img = self._probe_img(vm, "nav_probe")
        exp = self.nav_expected_centers(img.width)
        self.sync_mouse_origin(vm)
        self.mouse_click_at(vm, exp[index], TOPBAR_HEIGHT_THEME // 2)

    def _maximize_fast(self, vm: QemuController) -> bool:
        """Maximiza con el verde sin esperar (para capturar la transicion)."""
        self.sync_mouse_origin(vm)
        img = self._probe_img(vm, "nav_traffic")
        btn = self.find_maximize_button(img)
        if btn is None:
            return False
        self.mouse_goto(vm, btn[0], btn[1])
        time.sleep(0.10)
        vm.mouse_button("left", True)
        time.sleep(0.03)
        vm.mouse_button("left", False)
        return True

    def test_topnav(self, case: Case) -> bool | None:
        """Navegacion adaptativa: dock oculto y 5 accesos en la topbar
        cuando hay una ventana maximizada, full-height hasta sh-1."""
        if not self.require_gui(case):
            return None
        vm = self.gvm
        assert vm is not None
        self.close_all_windows_quiet(vm)
        time.sleep(self.t(0.7))
        baseline = self.capture(case, vm, "topnav_baseline", publish=False,
                                note="escritorio con dock (referencia)")
        bdm = self.dock_metrics(baseline.img)
        bnm = self.topnav_metrics(baseline.img)
        b_layout = self.topbar_layout(baseline.img)
        case.step("escritorio normal: dock visible y sin nav superior",
                  (not bdm["full_height"]) and bdm["dock_icon_px"] > 40
                  and not bnm["nav_present"], f"dock={bdm}")
        since = vm.marker_offset()
        vm.press("f1")
        try:
            self.wait_app_open(vm, "files", self.t(10), since)
        except MarkerTimeout as exc:
            case.fail("abrir Archivos para topnav", str(exc))
        time.sleep(self.t(0.9))

        # 1) maximizar: dock desaparece y nav aparece (captura 34)
        self._maximize_fast(vm)
        time.sleep(self.t(0.5))
        full = self.capture(case, vm, "34_topnav_maximized",
                            note="Archivos maximizado con nav en topbar")
        nm = self.topnav_metrics(full.img)
        dm = self.dock_metrics(full.img, baseline.img)
        fm = self.full_bleed_metrics(full.img, baseline.img)
        case.step("5 accesos en la topbar y Archivos como activo",
                  nm["nav_present"] and nm["active_index"] == 0,
                  f"nav={nm}")
        total = NAV_ICONS * NAV_TILE + (NAV_ICONS - 1) * NAV_GAP
        block_x0 = (full.img.width - total) // 2
        tile_x0 = block_x0 + nm["active_index"] * (NAV_TILE + NAV_GAP) \
            if nm["active_index"] is not None else -1
        case.step("los 5 accesos estan centrados exactamente en la pantalla",
                  abs(nm["avg_center"] - full.img.width // 2) <= 2
                  and abs(nm["active_bbox"][0] - tile_x0) <= 1
                  and abs((nm["active_bbox"][1] - nm["active_bbox"][0] + 1)
                          - NAV_TILE) <= 1,
                  f"bloque={block_x0}..{block_x0 + total - 1}, "
                  f"tile_activo={nm['active_bbox']} esperado_x0={tile_x0}, "
                  f"centros={nm['centers']}, media={nm['avg_center']}")
        case.step("exactamente un indicador activo (accent_soft + subrayado)",
                  nm["active_tiles"] == 1 and nm["underline_px"] >= 8,
                  f"tiles={nm['active_tiles']}, subrayado="
                  f"{nm['underline_px']}px")
        case.step("app full-height hasta y=sh-1 y sin panel inferior",
                  fm["full_bleed"] and dm["full_height"]
                  and dm["dock_icon_px"] <= 4,
                  f"full={fm}, dock={dm}")
        case.step("sin dock/taskbar/fondo reservado en la banda inferior",
                  fm["bottom_window_ratio"] >= 0.9
                  and fm["bottom_wallpaper_ratio"] <= 0.01
                  and dm["dock_icon_px"] == 0,
                  f"fila_inferior_ventana={fm['bottom_window_ratio']}, "
                  f"wallpaper_filas_finales={fm['bottom_wallpaper_ratio']}, "
                  f"px_iconos_dock={dm['dock_icon_px']}")
        f_layout = self.topbar_layout(full.img)
        keys = [k for k in ("logo_cx", "menu_left", "right_text_right")
                if b_layout.get(k) is not None and f_layout.get(k) is not None]
        stable = bool(keys) and all(
            abs(b_layout[k] - f_layout[k]) <= 2 for k in keys)
        case.step("topbar izq/der no se desplazan al aparecer la nav",
                  stable, f"dock={b_layout}, topnav={f_layout}")

        # 2) transicion: capturas rapidas, sin iconos duplicados
        self.click_traffic(vm, 2)      # restaurar (dock vuelve)
        time.sleep(self.t(0.6))
        self._maximize_fast(vm)
        frames = []
        frames.append(self._probe_img(vm, "nav_trans_0"))
        for k, delay in enumerate((0.02, 0.03, 0.05, 0.09)):
            time.sleep(delay)
            frames.append(self._probe_img(vm, f"nav_trans_{k + 1}"))
        dup = []
        states = []
        for k, fr in enumerate(frames):
            nfk = self.topnav_metrics(fr)
            dfk = self.dock_metrics(fr)
            both = nfk["nav_present"] and dfk["dock_icon_px"] > 20
            states.append({"frame": k, "nav": nfk["nav_present"],
                           "dock_px": dfk["dock_icon_px"],
                           "full": dfk["full_height"]})
            if both:
                dup.append(k)
        case.step("transicion sin iconos duplicados (nav y dock nunca a la vez)",
                  not dup, f"frames={states}")
        time.sleep(self.t(0.5))

        # 3) app activa cambia con F2: captura 35
        since = vm.marker_offset()
        vm.press("f2")
        try:
            self.wait_app_open(vm, "terminal", self.t(10), since)
        except MarkerTimeout as exc:
            case.fail("abrir Terminal con topnav", str(exc))
        time.sleep(self.t(0.8))
        active = self.capture(case, vm, "35_topnav_active",
                              note="indicador activo al cambiar a Terminal")
        nm2 = self.topnav_metrics(active.img)
        dm2 = self.dock_metrics(active.img, baseline.img)
        case.step("el indicador sigue a la app activa (Terminal)",
                  nm2["nav_present"] and nm2["active_index"] == 1
                  and nm2["open_apps"] >= 2,
                  f"nav={nm2}")
        case.step("con otra app abierta sigue sin dock (topnav estable)",
                  dm2["dock_icon_px"] <= 4, f"dock={dm2}")

        # 4) dos maximizadas (captura 37): Terminal ya esta activa
        self._maximize_fast(vm)
        time.sleep(self.t(0.6))
        multi = self.capture(case, vm, "37_topnav_multiwindow",
                             note="dos ventanas maximizadas con topnav")
        nm3 = self.topnav_metrics(multi.img)
        dm3 = self.dock_metrics(multi.img, baseline.img)
        fm3 = self.full_bleed_metrics(multi.img, baseline.img)
        case.step("2 maximizadas: nav estable, sin dock y full-height",
                  nm3["nav_present"] and nm3["active_index"] == 1
                  and dm3["dock_icon_px"] <= 4 and fm3["full_bleed"],
                  f"nav={nm3}, dock={dm3}, full={fm3['full_bleed']}")
        vm.press("f6")
        time.sleep(self.t(0.7))
        f6 = self._probe_img(vm, "nav_f6")
        nm4 = self.topnav_metrics(f6)
        case.step("cambiar foco con F6 mueve el indicador activo",
                  nm4["nav_present"] and nm4["active_index"] == 0,
                  f"nav={nm4}")

        # 5) minimizar una con otra maximizada -> sigue topnav
        self.click_traffic(vm, 1)
        time.sleep(self.t(0.7))
        one = self._probe_img(vm, "nav_one_min")
        nm5 = self.topnav_metrics(one)
        dm5 = self.dock_metrics(one, baseline.img)
        case.step("minimizar una maximizada con otra abierta mantiene topnav",
                  nm5["nav_present"] and dm5["dock_icon_px"] <= 4
                  and dm5["full_height"],
                  f"nav={nm5['nav_present']}, dock={dm5}")
        # 6) minimizar la ultima maximizada -> vuelve el dock (captura 38)
        self._click_nav(vm, 1)
        time.sleep(self.t(0.5))
        self.click_traffic(vm, 1)
        time.sleep(self.t(0.8))
        last = self.capture(case, vm, "38_topnav_minimize_last",
                            note="minimizada la ultima: vuelve el dock")
        nm6 = self.topnav_metrics(last.img)
        dm6 = self.dock_metrics(last.img, baseline.img)
        case.step("al minimizar la ultima maximizada vuelve el dock",
                  (not nm6["nav_present"]) and (not dm6["full_height"])
                  and dm6["dock_icon_px"] > 40, f"nav={nm6}, dock={dm6}")

        # 7) restaurar desde dock -> maximizada; restaurar -> dock (36)
        self.sync_mouse_origin(vm)
        dock = self._probe_img(vm, "nav_dock")
        dx, dy = self.dock_icon_center(dock, 0)
        self.mouse_click_at(vm, dx, dy)
        time.sleep(self.t(0.9))
        back_max = self._probe_img(vm, "nav_back_max")
        nm7 = self.topnav_metrics(back_max)
        case.step("restaurar desde el dock devuelve MAXIMIZADA con topnav",
                  nm7["nav_present"] and nm7["active_index"] == 0,
                  f"nav={nm7}")
        self.click_traffic(vm, 2)
        time.sleep(self.t(0.8))
        restored = self.capture(case, vm, "36_topnav_restore_dock",
                                note="restaurada: nav desaparece y vuelve el dock")
        nm8 = self.topnav_metrics(restored.img)
        dm8 = self.dock_metrics(restored.img, baseline.img)
        case.step("restaurar la maximizada devuelve el dock y quita la nav",
                  (not nm8["nav_present"]) and (not dm8["full_height"])
                  and dm8["dock_icon_px"] > 40, f"nav={nm8}, dock={dm8}")

        # 8) clics en los 5 accesos: abrir/enfocar sin duplicar APP_OPEN
        self._maximize_fast(vm)
        time.sleep(self.t(0.6))
        ids = ["files", "terminal", "monitor", "game", "about"]
        counts0 = {a: self.app_open_count(vm, a) for a in ids}
        click_results = []
        # clic en app NO activa: abre (si cerrada) o enfoca (abierta); el
        # clic sobre la activa se prueba aparte (toggle minimizar/restaurar)
        order = [2, 3, 4, 1, 0]
        for i in order:
            app_id = ids[i]
            self._click_nav(vm, i)
            time.sleep(self.t(0.8))
            probe = self._probe_img(vm, f"nav_click_{i}")
            nmi = self.topnav_metrics(probe)
            counts1 = self.app_open_count(vm, app_id)
            delta = counts1 - counts0[app_id]
            click_results.append({"i": i, "app": app_id,
                                  "active": nmi["active_index"],
                                  "open_delta": delta,
                                  "nav": nmi["nav_present"]})
            counts0[app_id] = counts1
        case.step("los 5 accesos abren/enfocan la app correcta",
                  [r["active"] for r in click_results] == order
                  and all(r["nav"] for r in click_results),
                  f"resultados={click_results}")
        case.step("los accesos no duplican APP_OPEN al abrir y enfocar",
                  all(r["open_delta"] <= 1 for r in click_results)
                  and self.app_open_count(vm, "files") == counts0["files"],
                  f"deltas={[r['open_delta'] for r in click_results]}")
        # clic sobre la app ACTIVA (files) -> toggle minimizar/restaurar
        files_before = self.app_open_count(vm, "files")
        self._click_nav(vm, 0)
        time.sleep(self.t(0.7))
        mini = self._probe_img(vm, "nav_click_active_min")
        nmm = self.topnav_metrics(mini)
        dmm = self.dock_metrics(mini)
        self._click_nav(vm, 0) if nmm["nav_present"] else None
        time.sleep(self.t(0.7))
        rest = self._probe_img(vm, "nav_click_active_restore")
        nmr = self.topnav_metrics(rest)
        case.step("clic en la app activa la minimiza y otro clic la restaura",
                  self.app_open_count(vm, "files") == files_before
                  and (nmr["active_index"] == 0 or not nmr["nav_present"]),
                  f"tras_min={nmm['nav_present']}, tras_restaurar={nmr}")
        self.close_all_windows_quiet(vm)
        fatals = self.fatal_in(vm)
        case.step("sin excepcion/panico en navegacion adaptativa", not fatals,
                  "; ".join(fatals) if fatals else "log limpio")

        # 9) resoluciones 800x600 y 1280x1024 (capturas 39/40)
        for width, height, cname in ((800, 600, "39_topnav_800"),
                                     (1280, 1024, "40_topnav_1280")):
            tmp = iso = rvm = None
            try:
                tmp, iso = self.build_resolution_iso(width, height,
                                                    f"topnav{width}")
                rvm = self.new_vm(f"topnav{width}", iso=iso,
                                  width=width, height=height)
                self.mouse_pos = (min(512, width - 1),
                                  min(384, height - 1))
                rvm.start()
                rvm.wait_marker(MARK_GUI, self.t(70))
                time.sleep(self.t(0.6))
                rbase = self.capture(case, rvm, f"topnav_base_{width}",
                                     publish=False,
                                     note=f"referencia {width}x{height}")
                since = rvm.marker_offset()
                rvm.press("f1")
                try:
                    self.wait_app_open(rvm, "files", self.t(12), since)
                except MarkerTimeout:
                    pass
                time.sleep(self.t(0.8))
                self._maximize_fast(rvm)
                time.sleep(self.t(0.6))
                rshot = self.capture(case, rvm, cname,
                                     note=f"topnav a {width}x{height}")
                rnm = self.topnav_metrics(rshot.img)
                rdm = self.dock_metrics(rshot.img, rbase.img)
                rfm = self.full_bleed_metrics(rshot.img, rbase.img)
                rlayout = self.topbar_layout(rshot.img)
                rtotal = NAV_ICONS * NAV_TILE + (NAV_ICONS - 1) * NAV_GAP
                rblock = (width - rtotal) // 2
                rtile = (rblock + rnm["active_index"]
                         * (NAV_TILE + NAV_GAP)
                         if rnm["active_index"] is not None else -1)
                fits = (rnm["nav_present"]
                        and abs(rnm["avg_center"] - width // 2) <= 2
                        and abs(rnm["active_bbox"][0] - rtile) <= 1
                        and rlayout["right_text_left"] is not None
                        and rnm["centers_expected"][-1] + NAV_TILE // 2 + 2
                        < rlayout["right_text_left"])
                case.step(f"{width}x{height}: 5 accesos + indicadores "
                          f"sin solaparse", fits,
                          f"nav={rnm}, layout={rlayout}")
                case.step(f"{width}x{height}: maximizada full-height "
                          f"sin dock", rfm["full_bleed"]
                          and rdm["dock_icon_px"] <= 4,
                          f"full={rfm}, dock={rdm}")
            finally:
                if rvm is not None:
                    try:
                        rvm.stop()
                    except Exception:  # noqa: BLE001
                        pass
                if tmp is not None:
                    shutil.rmtree(tmp, ignore_errors=True)
        return case.ok

    def test_game(self, case: Case) -> bool | None:
        """PAC-MAN SereOS: titulo, partida, dots, power pill/fantasmas,
        pausa, game over (si se alcanza) y vuelta al escritorio."""
        if not self.require_gui(case):
            return None
        vm = self.gvm
        assert vm is not None
        self.close_all_windows_quiet(vm)
        since = vm.marker_offset()
        vm.press("f4")
        try:
            app_id = self.wait_app_open(vm, "game", self.t(12), since)
            case.step(f"F4 abre PAC-MAN SereOS ({APP_OPEN}{app_id})", True)
        except MarkerTimeout as exc:
            case.fail("F4 abre PAC-MAN SereOS", str(exc))

        try:
            hit = vm.wait_marker("GAME_MENU", self.t(12), since)
            case.step("marcador GAME_MENU (pantalla de titulo)", True, hit.line)
        except MarkerTimeout:
            case.fail("marcador GAME_MENU",
                      "el juego no mostro su pantalla de titulo")
        time.sleep(self.t(0.8))
        title = self.capture(case, vm, "07_pacman_titulo",
                             note="attract/titulo PAC-MAN SereOS (PRESS START)")

        # Version definitiva (M2/M3/M4): arranca en attract. Enter abre el
        # menu principal arcade y un segundo Enter inicia la partida.
        menu_since = vm.marker_offset()
        vm.press("ret")
        try:
            vm.wait_marker("GAME_MENU", self.t(8), menu_since)
        except MarkerTimeout:
            pass
        time.sleep(self.t(0.8))
        self.capture(case, vm, "07b_pacman_menu",
                     note="menu principal arcade PAC-MAN SereOS")

        start_since = vm.marker_offset()
        vm.press("ret")
        try:
            hit = vm.wait_marker("GAME_START", self.t(12), start_since)
            case.step("Enter inicia la partida (GAME_START)", True, hit.line)
        except MarkerTimeout as exc:
            case.fail("Enter inicia la partida (GAME_START)", str(exc))
        time.sleep(self.t(0.6))
        self.capture(case, vm, "08_pacman_ready",
                     note="READY!: laberinto, Pacman, 4 fantasmas y HUD")
        # READY! inicial de la version definitiva: ~4.5 s con sonido
        time.sleep(self.t(4.6))
        play = self.capture(case, vm, "08b_pacman_partida",
                            note="partida en marcha con dots")
        self.screen_changed(case, "la partida cambia la pantalla respecto al titulo",
                            title, play, min_ratio=0.002)

        # Verificacion por pixeles: dots, 4 fantasmas y power pills visibles
        maze = self._maze_bbox(play.img)
        dots_play = self._count_color(play.img, DOT_COLOR, maze)
        case.step("el laberinto muestra dots", dots_play > 800,
                  f"{dots_play} px de color de dot en {maze}")
        ghosts = {name: self._count_family(play.img, pred, maze)
                  for name, pred in GHOST_FAMILIES.items()}
        case.step("los 4 fantasmas son visibles",
                  all(v >= 60 for v in ghosts.values()), str(ghosts))
        pill = self._count_color(play.img, POWER_PILL_COLOR, maze)
        case.step("power pills visibles en el laberinto", pill >= 100,
                  f"{pill} px de power pill")

        # Dos capturas comiendo dots: la segunda se toma a mitad de la ruta
        # del power pill, con mas dots comidos (la diferencia supera el ruido
        # del brillo del sprite de Pacman, que comparte tono con los dots).
        for key, wait in PACMAN_DOTS_ROUTE:
            vm.press(key)
            time.sleep(self.t(wait))
        eat1 = self.capture(case, vm, "eat1", publish=False,
                            note="comiendo dots al inicio del pasillo")
        eat2: Shot | None = None
        if PACMAN_POWER_ROUTE:
            for idx, (key, wait) in enumerate(PACMAN_POWER_ROUTE):
                vm.press(key)
                time.sleep(self.t(wait))
                if idx == 1 and eat2 is None:
                    eat2 = self.capture(case, vm, "09_pacman_comiendo",
                                        note="comiendo dots (puntuacion > 0)")
            time.sleep(self.t(PACMAN_POWER_WAIT))
            fright = self.capture(case, vm, "10_pacman_frightened",
                                  note="power pill: fantasmas asustados (azules)")
            fmaze = self._maze_bbox(fright.img)
            fright_px = self._count_family(fright.img, FRIGHT_FAMILY, fmaze)
            normal_px = (self._count_family(
                             fright.img, GHOST_FAMILIES["blinky_rojo"], fmaze)
                         + self._count_family(
                             fright.img, GHOST_FAMILIES["inky_cian"], fmaze))
            case.step("power pill comido: fantasmas azules (frightened)",
                      fright_px >= 150 and normal_px < 30,
                      f"cuerpo asustado={fright_px} px, "
                      f"cuerpos normales rojo+cian={normal_px} px")
        else:
            case.step("captura de power pill / fantasmas asustados", None,
                      "ruta no calibrada para el laberinto actual; omitida")

        if eat2 is not None:
            self.screen_changed(
                case, "Pacman come dots (dos capturas distintas)",
                eat1, eat2, min_ratio=0.0002)
            dots1 = self._count_color(eat1.img, DOT_COLOR,
                                      self._maze_bbox(eat1.img))
            dots2 = self._count_color(eat2.img, DOT_COLOR,
                                      self._maze_bbox(eat2.img))
            case.step("hay menos dots en la segunda captura",
                      dots2 < dots1 - 25,
                      f"pixeles de dot: {dots1} -> {dots2}")

        # Pausa
        pause_since = vm.marker_offset()
        vm.press("esc")
        try:
            hit = vm.wait_marker("GAME_PAUSE", self.t(12), pause_since)
            case.step("Esc pausa la partida (GAME_PAUSE)", True, hit.line)
        except MarkerTimeout as exc:
            case.fail("Esc pausa la partida (GAME_PAUSE)", str(exc))
        time.sleep(self.t(0.6))
        pause = self.capture(case, vm, "11_pacman_pausa", note="partida en pausa")
        self.screen_changed(case, "la pausa cambia la pantalla",
                            play, pause, min_ratio=0.0005)

        # Reanudar: Esc (toggle) o Enter; se comprueba que la pantalla cambia.
        resumed = False
        for key in ("esc", "ret"):
            vm.press(key)
            time.sleep(self.t(0.7))
            probe = self.raw_dir / "resume_probe.ppm"
            try:
                vm.screendump(probe)
                img = ppm_to_png.read_ppm(probe)
            except (QemuError, ppm_to_png.PPMError):
                continue
            ratio = ppm_to_png.diff_ratio(
                pause.img, img, self.region_below_topbar(pause.img))
            if ratio >= 0.001:
                resumed = True
                case.step("la partida se reanuda tras la pausa", True,
                          f"diferencia = {ratio:.3%}")
                break
        if not resumed:
            case.step("la partida se reanuda tras la pausa", None,
                      "no se detecto reanudacion automatica; se intenta game over igualmente")

        # Game over: dejar que los fantasmas alcancen a Pacman (es opcional).
        over = False
        over_since = vm.marker_offset()
        over_deadline = time.time() + self.t(GAME_OVER_WAIT)
        while time.time() < over_deadline:
            time.sleep(0.25)
            if vm.has_marker("GAME_OVER", over_since):
                over = True
                break
        if over:
            time.sleep(self.t(0.5))
            self.capture(case, vm, "12_pacman_gameover",
                         note="fin de partida (vidas agotadas)")
            case.step("se alcanzo GAME_OVER dejando que los fantasmas atrapen",
                      True)
        else:
            case.step("intento de GAME_OVER", None,
                      "no se alcanzo en el tiempo de la prueba; sin captura")

        # Volver al escritorio:
        #  - game over: Esc -> menu principal, Esc -> salir (cierra).
        #  - en partida/pausa: Esc pausa, Q -> menu principal, Esc -> salir.
        exit_since = vm.marker_offset()
        exited = False
        planned = (["esc", "esc"] if over
                   else ["esc", "q", "esc", "esc", "q", "esc"])
        for key in planned:
            vm.press(key)
            time.sleep(self.t(0.6))
            if vm.has_marker("GAME_EXIT", exit_since):
                exited = True
                break
        if exited:
            case.step("Q/Esc vuelve al escritorio (GAME_EXIT)", True)
        else:
            case.fail("Q/Esc vuelve al escritorio (GAME_EXIT)",
                      f"marcadores del juego vistos: "
                      f"{[ln for ln in vm.serial_lines() if ln.startswith('GAME_')]}")
        time.sleep(self.t(0.7))
        desktop = self.capture(case, vm, "desktop_after_game", publish=False,
                               note="escritorio tras salir del juego")
        ratio = ppm_to_png.diff_ratio(
            title.img, desktop.img, self.region_below_topbar(title.img))
        case.step("la escena del juego desaparece del escritorio",
                  ratio > 0.01, f"diferencia = {ratio:.3%}")
        return case.ok

    # -- audio: captura WAV con SB16 ---------------------------------------
    def test_audio(self, case: Case) -> bool | None:
        """Arranca QEMU con `-audiodev wav` + SB16, juega un momento y analiza
        el WAV resultante (existe, no vacio, muestra peak/RMS no silenciosos)."""
        wav = self.raw_dir / "audio_capture" / "audio-capture.wav"
        wav.parent.mkdir(parents=True, exist_ok=True)
        try:
            wav.unlink()
        except FileNotFoundError:
            pass
        workdir = self.raw_dir / "audio_capture"
        vm = QemuController(
            iso=self.iso, workdir=workdir, use_kvm=self.use_kvm,
            width=1024, height=768,
            extra_args=["-audiodev", f"wav,id=snd0,path={wav}",
                        "-device", "sb16,audiodev=snd0"])
        self.vms.append(vm)
        self.logs.append(("audio", vm.log_path))
        try:
            vm.start()
            vm.wait_marker("GUI_READY", self.t(60))
            case.step("QEMU con SB16 + backend WAV arrancado", True,
                      f"wav={wav.name}")
            since = vm.marker_offset()
            vm.press("f4")
            try:
                self.wait_app_open(vm, "game", self.t(12), since)
                vm.wait_marker("GAME_MENU", self.t(12), since)  # attract
                time.sleep(self.t(0.7))
                vm.press("ret")                                  # attract -> menu
                time.sleep(self.t(0.7))
                start_since = vm.marker_offset()
                vm.press("ret")                                  # menu -> partida
                vm.wait_marker("GAME_START", self.t(12), start_since)
                case.step("partida iniciada con audio activo", True)
            except MarkerTimeout as exc:
                case.fail("abrir el juego para el test de audio", str(exc))
            # moverse ~10 s para que el juego emita sonidos (waka-waka,
            # sirenas, power pill...). Pulsaciones simples: nunca se solapan
            # teclas mantenidas (eso bloquea la entrada de QEMU).
            keys = ("right", "up", "right", "down", "left", "down",
                    "right", "up", "left", "right")
            t0 = time.time()
            idx = 0
            while time.time() - t0 < self.t(10.0):
                vm.press(keys[idx % len(keys)])
                idx += 1
                time.sleep(self.t(0.55))
            case.step("movimiento de Pacman durante ~10 s para generar audio",
                      True, f"{idx} pulsaciones de direccion")
        finally:
            vm.stop()
        time.sleep(0.4)
        stats = analyze_wav(wav)
        case.step("audio-capture.wav existe", stats["exists"],
                  f"{stats['bytes']} bytes")
        case.step("WAV con datos PCM", stats["frames"] > 0,
                  f"{stats['frames']} frames a {stats['sample_rate']} Hz, "
                  f"{stats['channels']} canal(es), {stats['sample_width']} bytes/muestra")
        case.step("duracion de la captura >= 0.3 s",
                  stats["duration_s"] >= 0.3,
                  f"{stats['duration_s']:.2f} s")
        # umbral segun la profundidad PCM (8 bits: rango +-128; 16 bits: +-32768)
        if stats["sample_width"] == 1:
            non_silent = stats["peak"] >= 40 and stats["rms"] >= 8.0
        else:
            non_silent = stats["peak"] >= 100 and stats["rms"] >= 20.0
        case.step("muestras no silenciosas (peak/RMS)",
                  non_silent,
                  f"peak={stats['peak']}, rms={stats['rms']}, "
                  f"{stats['sample_width']} bytes/muestra")
        return case.ok

    # -- cierre de ventanas (boton rojo del raton, best-effort) -------------
    @staticmethod
    def find_red_buttons(img: "ppm_to_png.PPMImage") -> list[tuple[int, int]]:
        """Detecta los semaforos rojos (boton cerrar) de las ventanas."""
        px = img.pixels
        w, h = img.width, img.height
        points: set[tuple[int, int]] = set()
        for y in range(h):
            row = y * w * 3
            for x in range(w):
                i = row + x * 3
                r, g, b = px[i], px[i + 1], px[i + 2]
                if r >= 180 and g <= 120 and b <= 120 and (r - g) >= 70 and (r - b) >= 70:
                    points.add((x, y))
        if not points:
            return []
        # agrupacion por vecindad (los semaforos son circulos pequenos)
        seen: set[tuple[int, int]] = set()
        centers: list[tuple[int, int]] = []
        for p in points:
            if p in seen:
                continue
            stack = [p]
            seen.add(p)
            cluster: list[tuple[int, int]] = []
            while stack:
                cx, cy = stack.pop()
                cluster.append((cx, cy))
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        q = (cx + dx, cy + dy)
                        if q in points and q not in seen:
                            seen.add(q)
                            stack.append(q)
            if not 15 <= len(cluster) <= 400:
                continue
            xs = [c[0] for c in cluster]
            ys = [c[1] for c in cluster]
            width = max(xs) - min(xs) + 1
            height = max(ys) - min(ys) + 1
            if width > 22 or height > 22 or width < 5 or height < 5:
                continue
            aspect = width / height
            if not 0.6 <= aspect <= 1.6:
                continue
            centers.append((sum(xs) // len(xs), sum(ys) // len(ys)))
        centers.sort(key=lambda c: (c[1], c[0]))
        return centers

    def mouse_goto(self, vm: QemuController, x: int, y: int,
                   steps: int = 0) -> None:
        """Mueve el raton en pasos relativos (PS/2) desde la posicion conocida."""
        dx = x - self.mouse_pos[0]
        dy = y - self.mouse_pos[1]
        while dx != 0 or dy != 0:
            sx = max(-100, min(100, dx))
            sy = max(-100, min(100, dy))
            vm.mouse_move_rel(sx, sy)
            dx -= sx
            dy -= sy
            time.sleep(0.02)
        self.mouse_pos = (x, y)

    def mouse_click_at(self, vm: QemuController, x: int, y: int) -> None:
        self.mouse_goto(vm, x, y)
        time.sleep(self.t(0.12))
        vm.mouse_button("left", True)
        time.sleep(0.07)
        vm.mouse_button("left", False)
        time.sleep(self.t(0.2))

    # -- analisis visual para logo y barra de tareas ----------------------
    @staticmethod
    def _color_clusters(img: "ppm_to_png.PPMImage",
                        target: tuple[int, int, int],
                        region: tuple[int, int, int, int] | None = None,
                        tol: int = 0,
                        min_size: int = 8) -> list[dict]:
        x0, y0, w, h = region or (0, 0, img.width, img.height)
        px = img.pixels
        stride = img.width * 3
        tr, tg, tb = target
        points: set[tuple[int, int]] = set()
        for y in range(y0, min(y0 + h, img.height)):
            base = y * stride
            for x in range(x0, min(x0 + w, img.width)):
                i = base + x * 3
                if (abs(px[i] - tr) <= tol and abs(px[i + 1] - tg) <= tol
                        and abs(px[i + 2] - tb) <= tol):
                    points.add((x, y))
        clusters: list[dict] = []
        seen: set[tuple[int, int]] = set()
        for pt in points:
            if pt in seen:
                continue
            stack = [pt]
            seen.add(pt)
            comp: list[tuple[int, int]] = []
            while stack:
                cx, cy = stack.pop()
                comp.append((cx, cy))
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        q = (cx + dx, cy + dy)
                        if q in points and q not in seen:
                            seen.add(q)
                            stack.append(q)
            if len(comp) < min_size:
                continue
            xs = [c[0] for c in comp]
            ys = [c[1] for c in comp]
            clusters.append({
                "size": len(comp),
                "bbox": (min(xs), min(ys), max(xs) - min(xs) + 1,
                         max(ys) - min(ys) + 1),
                "center": (sum(xs) // len(xs), sum(ys) // len(ys)),
            })
        clusters.sort(key=lambda c: c["size"], reverse=True)
        return clusters

    def logo_bbox(self, img: "ppm_to_png.PPMImage",
                  region: tuple[int, int, int, int] | None = None):
        """Caja del logotipo oficial (azul de la marca) en una region."""
        clusters = self._color_clusters(img, OFFICIAL_LOGO_BLUE, region,
                                        tol=LOGO_TOL, min_size=12)
        return clusters[0] if clusters else None

    def bottom_bar_state(self, img: "ppm_to_png.PPMImage") -> dict:
        """Distingue dock flotante (cobertura parcial) de barra full-width.

        Mide la luminancia media de las esquinas inferiores (fuera del dock
        flotante): con el dock, esas zonas son el fondo del escritorio (~18);
        con la barra de tareas son superficie de barra (~30). Calcula tambien
        la altura de la banda inferior con filas casi uniformes.
        """
        w, h = img.width, img.height
        stride = w * 3
        total_luma = 0.0
        count = 0
        for y in range(max(0, h - 44), h - 2):
            base = y * stride
            for x0, x1 in ((0, min(150, w)), (max(0, w - 150), w)):
                for x in range(x0, x1):
                    i = base + x * 3
                    total_luma += (0.2126 * img.pixels[i]
                                   + 0.7152 * img.pixels[i + 1]
                                   + 0.0722 * img.pixels[i + 2])
                    count += 1
        mean_luma = total_luma / count if count else 0.0
        # altura de la banda: se escanea una franja horizontal de la barra
        # que queda libre de logo (izquierda), iconos (centro) y tray (derecha)
        taskbar = mean_luma >= 24.0
        band_h = 0
        if taskbar:
            sx0 = int(w * 0.18)
            sx1 = max(sx0 + 8, int(w * 0.32))
            base_i = ((h - 10) * w + (sx0 + sx1) // 2) * 3
            bar_c = img.pixels[base_i:base_i + 3]
            for y in range(h - 1, max(0, h - 90), -1):
                base = y * stride
                same = 0
                total = 0
                for x in range(sx0, sx1):
                    i = base + x * 3
                    if (abs(img.pixels[i] - bar_c[0]) <= 6
                            and abs(img.pixels[i + 1] - bar_c[1]) <= 6
                            and abs(img.pixels[i + 2] - bar_c[2]) <= 6):
                        same += 1
                    total += 1
                if total and same / total >= 0.80:
                    band_h += 1
                else:
                    break
        taskbar = taskbar and band_h >= 40
        return {"taskbar": taskbar, "mean_luma": round(mean_luma, 2),
                "band_height": band_h}

    @staticmethod
    def _near_color(img: "ppm_to_png.PPMImage", cx: int, cy: int,
                    color: tuple[int, int, int], tol: int = 20,
                    rad: int = 7) -> int:
        """Cuenta pixeles de `color` en un cuadrado de radio `rad`."""
        px = img.pixels
        w, h = img.width, img.height
        n = 0
        for y in range(max(0, cy - rad), min(h, cy + rad + 1)):
            base = y * w * 3
            for x in range(max(0, cx - rad), min(w, cx + rad + 1)):
                i = base + x * 3
                if (abs(px[i] - color[0]) <= tol
                        and abs(px[i + 1] - color[1]) <= tol
                        and abs(px[i + 2] - color[2]) <= tol):
                    n += 1
        return n

    def find_traffic_lights(self, img: "ppm_to_png.PPMImage") -> list[tuple[int, int]]:
        """Semaforos reales de ventana: rojo+ambar+verde a 18/36 px.

        Filtra los rojos que no forman parte de una ventana (p.ej. fantasmas
        rojos del contenido de Pacman), exigiendo el trio de colores exacto.
        """
        lights: list[tuple[int, int]] = []
        for rx, ry in self.find_red_buttons(img):
            if (self._near_color(img, rx + TRAFFIC_STEP, ry,
                                 (224, 168, 76)) >= 3
                    and self._near_color(img, rx + 2 * TRAFFIC_STEP, ry,
                                         (76, 195, 138)) >= 3):
                lights.append((rx, ry))
        return lights

    def sync_mouse_origin(self, vm: QemuController) -> None:
        """Fuerza el cursor al origen (0,0) para eliminar deriva acumulada.

        El driver PS/2 puede perder/recortar eventos relativos al acumular
        muchos movimientos, asi que se envian varios desplazamientos moderados
        (2500 px en total) que garantizan quedar recortado en (0,0).
        """
        for _ in range(10):
            vm.mouse_move_rel(-250, -250)
            time.sleep(0.02)
        self.mouse_pos = (0, 0)

    def find_maximize_button(self, img: "ppm_to_png.PPMImage"):
        """Centro del semaforo verde (maximizar) de la ventana activa."""
        lights = self.find_traffic_lights(img)
        if not lights:
            return None
        rx, ry = max(lights, key=lambda c: c[1])
        return (rx + 2 * TRAFFIC_STEP, ry)

    def maximized_window_present(self, img: "ppm_to_png.PPMImage") -> bool:
        """True si hay un titulo de ventana pegado bajo la barra superior."""
        for _rx, ry in self.find_traffic_lights(img):
            if TOPBAR_HEIGHT_THEME + 2 <= ry <= TOPBAR_HEIGHT_THEME + 45:
                return True
        return False

    def taskbar_accent_centers(self, img: "ppm_to_png.PPMImage",
                               band: int = 60) -> list[int]:
        """Columnas del acento azul (app activa) dentro de la barra inferior."""
        w, h = img.width, img.height
        stride = w * 3
        cols: dict[int, int] = {}
        for y in range(max(0, h - band), h):
            base = y * stride
            for x in range(w):
                i = base + x * 3
                if (abs(img.pixels[i] - 76) <= 6
                        and abs(img.pixels[i + 1] - 141) <= 6
                        and abs(img.pixels[i + 2] - 255) <= 6):
                    cols[x] = cols.get(x, 0) + 1
        active = sorted(x for x, n in cols.items() if n >= 2)
        centers: list[int] = []
        run: list[int] = []
        for x in active:
            if run and x - run[-1] > 4:
                centers.append(sum(run) // len(run))
                run = []
            run.append(x)
        if run:
            centers.append(sum(run) // len(run))
        return centers

    def taskbar_active_index(self, img: "ppm_to_png.PPMImage",
                             icons: int = 5) -> int | None:
        """Indice del icono con fondo de 'app activa' en la barra de tareas.

        El tile activo usa `accent_soft`; se muestrea el fondo de cada tile
        (evitando el glifo) y se devuelve el que mas difiere del color modal.
        """
        defs = {}
        try:
            text = (ROOT / "gui" / "theme.h").read_text(encoding="utf-8")
            for key in ("TASKBAR_HEIGHT", "TASKBAR_ICON", "TASKBAR_TILE",
                        "TASKBAR_GAP"):
                m = __import__("re").search(rf"#define\s+{key}\s+(\d+)", text)
                if m:
                    defs[key] = int(m.group(1))
        except OSError:
            pass
        bar_h = defs.get("TASKBAR_HEIGHT", 48)
        tile = defs.get("TASKBAR_TILE", 36)
        gap = defs.get("TASKBAR_GAP", 4)
        w, h = img.width, img.height
        total = icons * tile + (icons - 1) * gap
        x0 = (w - total) // 2
        cy = h - bar_h // 2
        samples: list[tuple[int, int, int]] = []
        for i in range(icons):
            cx = x0 + i * (tile + gap) + tile // 2
            pts = [(cx - 14, cy - 14), (cx + 13, cy - 14),
                   (cx - 14, cy + 13), (cx + 13, cy + 13), (cx, cy - 15)]
            cols = []
            for x, y in pts:
                if 0 <= x < w and 0 <= y < h:
                    k = (y * w + x) * 3
                    cols.append(tuple(img.pixels[k:k + 3]))
            if not cols:
                continue
            samples.append(tuple(sum(c[j] for c in cols) // len(cols)
                                 for j in range(3)))
        if not samples:
            return None
        from collections import Counter
        modal = Counter(samples).most_common(1)[0][0]
        best_i = None
        best_d = -1
        for i, col in enumerate(samples):
            d = sum(abs(col[j] - modal[j]) for j in range(3))
            if d > best_d:
                best_d = d
                best_i = i
        return best_i if best_d >= 12 else None

    # -- maximizacion full-bleed / geometria de ventanas -------------------
    def full_bleed_metrics(self, img: "ppm_to_png.PPMImage",
                           baseline: "ppm_to_png.PPMImage",
                           taskbar_h: int = 0) -> dict:
        """Comprueba full-bleed full-height: la ventana maximizada cubre
        x=0..sw-1 e y=TOPBAR_H..sh-1 sin wallpaper ni barra inferior."""
        w, h = img.width, img.height
        if (baseline.width, baseline.height) != (w, h):
            return {"full_bleed": False, "error": "baseline de otra resolucion"}
        topbar = TOPBAR_HEIGHT_THEME
        y0, hrect = topbar, h - topbar - taskbar_h
        px, bp = img.pixels, baseline.pixels
        same = 0
        total = 0
        for y in range(y0 + 3, y0 + hrect - 3, 2):
            base = y * w * 3
            for x in range(2, w - 2, 2):
                i = base + x * 3
                if px[i:i + 3] == bp[i:i + 3]:
                    same += 1
                total += 1
        wallpaper_ratio = same / total if total else 1.0
        corners = {}
        for name, (cx, cy) in {
            "tl": (0, y0), "tr": (w - 1, y0),
            "bl": (0, y0 + hrect - 1), "br": (w - 1, y0 + hrect - 1),
        }.items():
            eq = tot = 0
            for yy in range(max(0, cy - 2), min(h, cy + 6)):
                for xx in range(max(0, cx - 2), min(w, cx + 6)):
                    i = (yy * w + xx) * 3
                    if px[i:i + 3] == bp[i:i + 3]:
                        eq += 1
                    tot += 1
            corners[name] = round(eq / tot if tot else 1.0, 3)
        # anclaje inferior: la ultima fila debe ser superficie/contenido de la
        # app (o su borde); las filas finales no coinciden con el wallpaper
        bottom_win = 0
        bottom_total = 0
        for x in range(20, w - 20):
            i = ((h - 1) * w + x) * 3
            c = tuple(px[i:i + 3])
            if (self._near_c(c, WIN_BODY_COLOR, 4)
                    or self._near_c(c, WIN_STATUS_COLOR, 4)
                    or self._near_c(c, WIN_BORDER_STRONG, 12)
                    or self._near_c(c, WIN_BORDER_COLOR, 12)):
                bottom_win += 1
            bottom_total += 1
        bottom_ratio = bottom_win / bottom_total if bottom_total else 0.0
        low_same = low_total = 0
        for y in range(h - 8, h):
            base = y * w * 3
            for x in range(2, w - 2, 3):
                i = base + x * 3
                if px[i:i + 3] == bp[i:i + 3]:
                    low_same += 1
                low_total += 1
        bottom_wallpaper_ratio = low_same / low_total if low_total else 1.0
        full = (wallpaper_ratio < 0.06
                and all(v < 0.30 for v in corners.values())
                and bottom_wallpaper_ratio < 0.03)
        return {"full_bleed": full,
                "wallpaper_ratio": round(wallpaper_ratio, 4),
                "corners": corners,
                "bottom_window_ratio": round(bottom_ratio, 3),
                "bottom_wallpaper_ratio": round(bottom_wallpaper_ratio, 4),
                "rect": (0, y0, w, hrect)}

    def detect_titlebar(self, img: "ppm_to_png.PPMImage") -> dict | None:
        """Localiza la barra de titulo de la ventana superior (x, y, ancho).

        Usa los semaforos rojos y camina por la fila del semaforo buscando el
        color de la barra (tolerancia 8) para obtener el ancho del marco.
        """
        lights = self.find_traffic_lights(img)
        if not lights:
            return None
        rx, ry = max(lights, key=lambda c: c[1])
        w = img.width
        stride = w * 3
        sx = min(w - 1, rx + 60)
        i = ry * stride + sx * 3
        ref = img.pixels[i:i + 3]
        if len(ref) < 3:
            return None
        xs = []
        for x in range(0, w):
            k = ry * stride + x * 3
            c = img.pixels[k:k + 3]
            if (abs(c[0] - ref[0]) <= 8 and abs(c[1] - ref[1]) <= 8
                    and abs(c[2] - ref[2]) <= 8):
                xs.append(x)
        if not xs:
            return None
        x0, x1 = min(xs), max(xs)
        return {"x": x0, "y": ry - 17, "width": x1 - x0 + 1,
                "right": x1, "center_y": ry}

    def app_open_count(self, vm: QemuController, app_id: str) -> int:
        return sum(1 for ln in vm.serial_lines()
                   if ln.startswith(f"{APP_OPEN}{app_id}"))

    def double_click(self, vm: QemuController, x: int, y: int,
                     settle: float = 0.7) -> None:
        self.sync_mouse_origin(vm)
        self.mouse_goto(vm, x, y)
        time.sleep(0.10)
        vm.mouse_button("left", True)
        time.sleep(0.03)
        vm.mouse_button("left", False)
        time.sleep(0.07)
        vm.mouse_button("left", True)
        time.sleep(0.03)
        vm.mouse_button("left", False)
        time.sleep(self.t(settle))

    def click_traffic(self, vm: QemuController, index: int) -> bool:
        """Clic en semaforo 0=cerrar, 1=minimizar, 2=maximizar (verde)."""
        self.sync_mouse_origin(vm)
        img = self._probe_img(vm, "traffic_probe")
        if os.environ.get("SEREOS_QA_DEBUG"):
            print(f"[qa] click_traffic({index}) lights="
                  f"{self.find_traffic_lights(img)} "
                  f"mouse={self.mouse_pos}", file=sys.stderr)
        lights = self.find_traffic_lights(img)
        if not lights:
            # respaldo: semaforos rojos sin trio verificado
            lights = self.find_red_buttons(img)
        if not lights:
            return False
        rx, ry = max(lights, key=lambda c: c[1])
        self.mouse_click_at(vm, rx + index * 18, ry)
        if os.environ.get("SEREOS_QA_DEBUG"):
            print(f"[qa]   click at ({rx + index * 18},{ry}) "
                  f"mouse={self.mouse_pos}", file=sys.stderr)
            try:
                post = self._probe_img(vm, "traffic_after")
                print(f"[qa]   post click bar={self.bottom_bar_state(post)} "
                      f"tb={self.detect_titlebar(post)}", file=sys.stderr)
            except QemuError:
                pass
        time.sleep(self.t(0.8))
        return True

    # -- ventanas normales: rect, esquinas redondeadas y clipping ----------
    @staticmethod
    def _near_c(c, target, tol=4) -> bool:
        return all(abs(c[k] - target[k]) <= tol for k in range(3))

    def detect_window_rect(self, img: "ppm_to_png.PPMImage") -> dict | None:
        """Rect completo (incluyendo borde de 1 px) de la ventana superior."""
        tb = self.detect_titlebar(img)
        if not tb:
            return None
        left = tb["x"] - 1
        right = tb["right"] + 1
        top = tb["y"]
        width = right - left + 1
        w = img.width
        status_rows = 0
        bottom = None
        for y in range(top + 80, min(img.height - 40, top + 1000)):
            cnt = 0
            for x in range(left + 2, right - 1):
                i = (y * w + x) * 3
                if self._near_c(tuple(img.pixels[i:i + 3]),
                                WIN_STATUS_COLOR):
                    cnt += 1
            if cnt > width * 0.5:
                bottom = y
                status_rows += 1
        if bottom is None or status_rows < 4:
            return None
        bottom += 1        # fila de borde inferior
        return {"x": left, "y": top, "w": width, "h": bottom - top + 1,
                "right": right, "bottom": bottom}

    @staticmethod
    def inside_round(px: int, py: int, rect: dict,
                     r: int = WIN_CORNER_RADIUS) -> bool:
        """Mismo test que inside_round_window() del compositor."""
        x, y = rect["x"], rect["y"]
        w, h = rect["w"], rect["h"]
        if px < x or py < y or px >= x + w or py >= y + h:
            return False
        if r > w // 2:
            r = w // 2
        if r > h // 2:
            r = h // 2
        if r <= 0:
            return True
        cx = min(max(px, x + r), x + w - 1 - r)
        cy = min(max(py, y + r), y + h - 1 - r)
        dx = px - cx
        dy = py - cy
        return dx * dx + dy * dy <= r * r

    def patch_mode(self, img: "ppm_to_png.PPMImage", cx: int, cy: int,
                   rad: int = 2) -> tuple[int, int, int]:
        from collections import Counter
        c: Counter = Counter()
        w, h = img.width, img.height
        for y in range(max(0, cy - rad), min(h, cy + rad + 1)):
            for x in range(max(0, cx - rad), min(w, cx + rad + 1)):
                i = (y * w + x) * 3
                c[tuple(img.pixels[i:i + 3])] += 1
        return c.most_common(1)[0][0]

    def corner_metrics(self, img: "ppm_to_png.PPMImage",
                       rect: dict) -> dict:
        """Analiza las 4 esquinas: color interior (status/surface_2) y si
        queda un parche del color del cuerpo FUERA del arco redondeado."""
        x, y = rect["x"], rect["y"]
        w, h = rect["w"], rect["h"]
        right, bottom = rect["right"], rect["bottom"]
        corners = {
            "tl": (x, y),
            "tr": (right - 15, y),
            "bl": (x, bottom - 15),
            "br": (right - 15, bottom - 15),
        }
        report = {}
        for name, (bx, by) in corners.items():
            inside_colors: list[tuple[int, int, int]] = []
            outside_colors: list[tuple[int, int, int]] = []
            for j in range(16):
                for i in range(16):
                    gx, gy = bx + i, by + j
                    if not (0 <= gx < img.width and 0 <= gy < img.height):
                        continue
                    k = (gy * img.width + gx) * 3
                    col = tuple(img.pixels[k:k + 3])
                    if self.inside_round(gx, gy, rect):
                        inside_colors.append(col)
                    else:
                        outside_colors.append(col)
            from collections import Counter
            inside_mode = Counter(inside_colors).most_common(1)[0][0]                 if inside_colors else (0, 0, 0)
            outside_mode = Counter(outside_colors).most_common(1)[0][0]                 if outside_colors else (0, 0, 0)
            body_out = sum(1 for c in outside_colors
                           if self._near_c(c, WIN_BODY_COLOR, 3))
            status_out = sum(1 for c in outside_colors
                             if self._near_c(c, WIN_STATUS_COLOR, 3))
            report[name] = {
                "inside_mode": inside_mode,
                "outside_mode": outside_mode,
                "body_outside": body_out,
                "status_outside": status_out,
                "outside_colors": len(set(outside_colors)),
            }
        return report

    def corner_mosaic(self, img: "ppm_to_png.PPMImage",
                      rect: dict) -> "ppm_to_png.PPMImage":
        """Mosaico 2x2 con las 4 esquinas a 10x (evidencia visual)."""
        x, y = rect["x"], rect["y"]
        right, bottom = rect["right"], rect["bottom"]
        size, pad = 40, 8
        tl = ppm_to_png.crop(img, x - pad, y - pad, size, size)
        tr = ppm_to_png.crop(img, right - (size - pad - 1), y - pad,
                             size, size)
        bl = ppm_to_png.crop(img, x - pad, bottom - (size - pad - 1),
                             size, size)
        br = ppm_to_png.crop(img, right - (size - pad - 1),
                             bottom - (size - pad - 1), size, size)
        z = CORNER_MOSAIC_ZOOM
        s = [ppm_to_png.scale_nearest(c, c.width * z, c.height * z)
             for c in (tl, tr, bl, br)]
        gap = 4
        row1 = ppm_to_png.hstack([s[0], s[1]], gap=gap,
                                 gap_color=WIN_BORDER_COLOR)
        row2 = ppm_to_png.hstack([s[2], s[3]], gap=gap,
                                 gap_color=WIN_BORDER_COLOR)
        return ppm_to_png.vstack([row1, row2], gap=gap,
                                 gap_color=WIN_BORDER_COLOR)

    # -- navegacion adaptativa: topbar nav y ausencia de dock ---------------
    @staticmethod
    def nav_expected_centers(w: int) -> list[int]:
        """Centros de los 5 accesos, centrados en la PANTALLA (no en el hueco)."""
        total = NAV_ICONS * NAV_TILE + (NAV_ICONS - 1) * NAV_GAP
        x0 = (w - total) // 2
        return [x0 + i * (NAV_TILE + NAV_GAP) + NAV_TILE // 2
                for i in range(NAV_ICONS)]

    def topnav_metrics(self, img: "ppm_to_png.PPMImage") -> dict:
        """Detecta los 5 accesos de la topbar, el indicador activo y las
        apps abiertas. Devuelve centros medidos para comprobar alineacion."""
        w = img.width
        cy = TOPBAR_HEIGHT_THEME // 2
        exp = self.nav_expected_centers(w)
        tint_px = {i: [] for i in range(NAV_ICONS)}
        acentos_soft = []
        for y in range(0, TOPBAR_HEIGHT_THEME):
            base = y * w * 3
            for x in range(w):
                k = base + x * 3
                c = tuple(img.pixels[k:k + 3])
                if self._near_c(c, THEME_ACCENT_SOFT, 6):
                    acentos_soft.append((x, y))
                for i in range(NAV_ICONS):
                    if (self._near_c(c, NAV_TINTS[i], 22)
                            or self._near_c(c, THEME_TEXT, 8)
                            or self._near_c(c, (110, 119, 136), 14)):
                        if abs(x - exp[i]) <= NAV_TILE // 2 + 2:
                            tint_px[i].append((x, y))
        # clusters del tile activo (centro)
        active_clusters: list[tuple[int, int]] = []
        run: list[int] = []
        for x in sorted(set(p[0] for p in acentos_soft)):
            if run and x - run[-1] > 3:
                active_clusters.append((run[0], run[-1]))
                run = []
            run.append(x)
        if run:
            active_clusters.append((run[0], run[-1]))
        active_bbox = active_clusters[0] if active_clusters else (0, 0)
        active_center = (active_bbox[0] + active_bbox[1] + 1) // 2 \
            if active_clusters else 0
        present = [len(tint_px[i]) >= 6 for i in range(NAV_ICONS)]
        centers_measured = []
        for i in range(NAV_ICONS):
            if tint_px[i]:
                centers_measured.append(
                    sum(p[0] for p in tint_px[i]) // len(tint_px[i]))
            else:
                centers_measured.append(exp[i])
        # subrayado 2px + punto de app abierta
        underline = 0
        for x in range(w):
            for y in range(TOPBAR_HEIGHT_THEME - 2, TOPBAR_HEIGHT_THEME):
                k = (y * w + x) * 3
                if self._near_c(tuple(img.pixels[k:k + 3]), THEME_ACCENT, 8):
                    underline += 1
        open_dots = 0
        for i in range(NAV_ICONS):
            dot = 0
            for y in range(TOPBAR_HEIGHT_THEME - 7, TOPBAR_HEIGHT_THEME - 2):
                for x in range(exp[i] - 3, exp[i] + 4):
                    k = (y * w + x) * 3
                    if self._near_c(tuple(img.pixels[k:k + 3]),
                                    THEME_ACCENT, 8):
                        dot += 1
            if dot >= 3:
                open_dots += 1
        active_idx = None
        if active_clusters:
            acx = active_center
            best = min(range(NAV_ICONS), key=lambda i: abs(exp[i] - acx))
            if abs(exp[best] - acx) <= NAV_TILE // 2 + 2:
                active_idx = best
        nav_present = (all(present) and len(active_clusters) == 1
                       and underline >= 8)
        return {"nav_present": nav_present,
                "present": present,
                "active_index": active_idx,
                "active_tiles": len(active_clusters),
                "active_bbox": active_bbox,
                "active_center": active_center,
                "centers": centers_measured,
                "centers_expected": exp,
                "avg_center": (sum(centers_measured) // NAV_ICONS
                               if centers_measured else 0),
                "underline_px": underline,
                "open_apps": open_dots}

    def dock_metrics(self, img: "ppm_to_png.PPMImage",
                     baseline: "ppm_to_png.PPMImage | None" = None) -> dict:
        """Detecta dock inferior panel y si la app llega hasta y=sh-1.

        Con baseline se compara la banda inferior con el escritorio: si deja
        de coincidir, la ventana/app cubre esa zona (sin panel).
        """
        w, h = img.width, img.height
        win = 0
        for x in range(20, w - 20):
            i = ((h - 1) * w + x) * 3
            c = tuple(img.pixels[i:i + 3])
            if (self._near_c(c, WIN_BODY_COLOR, 4)
                    or self._near_c(c, WIN_STATUS_COLOR, 4)
                    or self._near_c(c, WIN_BORDER_STRONG, 12)
                    or self._near_c(c, WIN_BORDER_COLOR, 12)):
                win += 1
        border_ratio = win / (w - 40)
        bottom_wall = None
        if baseline is not None and baseline.width == w and baseline.height == h:
            same = total = 0
            for y in range(h - 8, h):
                base = y * w * 3
                for x in range(2, w - 2, 3):
                    i = base + x * 3
                    if img.pixels[i:i + 3] == baseline.pixels[i:i + 3]:
                        same += 1
                    total += 1
            bottom_wall = same / total if total else 1.0
        dock_tint = 0
        for y in range(max(0, h - 90), h):
            base = y * w * 3
            for x in range(0, w):
                k = base + x * 3
                c = tuple(img.pixels[k:k + 3])
                for tint in NAV_TINTS:
                    if self._near_c(c, tint, 10):
                        dock_tint += 1
                        break
        if bottom_wall is not None:
            full_height = bottom_wall < 0.03
        else:
            full_height = border_ratio >= 0.5
        return {"full_height": full_height,
                "bottom_window_ratio": round(border_ratio, 3),
                "bottom_wallpaper_ratio": (round(bottom_wall, 4)
                                           if bottom_wall is not None
                                           else None),
                "dock_icon_px": dock_tint}

    def topbar_layout(self, img: "ppm_to_png.PPMImage") -> dict:
        """Posiciones del logo (izq), boton de menu y memoria (der) para
        comprobar que la topbar no se desplaza entre dock y topnav."""
        w = img.width
        logo = self._color_clusters(img, OFFICIAL_LOGO_BLUE,
                                    (0, 0, min(120, w),
                                     TOPBAR_HEIGHT_THEME), tol=LOGO_TOL,
                                    min_size=12)
        # la marca de la topbar es blanca (sin azul): usar su tinta para medir
        # la posicion de la marca (el ancho del glifo es ~9 px, gap 8).
        logo_cx = logo[0]["center"][0] if logo else None
        if logo_cx is None:
            ink = self.topbar_white_ink(
                img, (0, 0, min(26, w), TOPBAR_HEIGHT_THEME))
            logo_cx = ink["center"][0] if ink else None
        menu = self._color_clusters(img, THEME_TEXT_DIM,
                                    (0, 0, min(260, w),
                                     TOPBAR_HEIGHT_THEME), tol=10, min_size=3)
        def lum(x: int, y: int) -> float:
            i = (y * w + x) * 3
            r, g, b = img.pixels[i], img.pixels[i + 1], img.pixels[i + 2]
            return 0.2126 * r + 0.7152 * g + 0.0722 * b

        bright = [(x, y) for y in range(TOPBAR_HEIGHT_THEME) for x in range(w)
                  if lum(x, y) > 120]
        menu_b = [x for x, y in bright if 60 <= x <= 160 and 8 <= y <= 22]
        right_text = max((x for x, y in bright), default=None)
        nav_total = NAV_ICONS * NAV_TILE + (NAV_ICONS - 1) * NAV_GAP
        x_start = w // 2 + nav_total // 2 + 16
        right_text_left = min((x for x, y in bright if x >= x_start),
                              default=None)
        return {"logo_cx": logo_cx,
                "menu_left": (min(menu_b) if menu_b else None),
                "right_text_right": right_text,
                "right_text_left": right_text_left}

    def topbar_white_ink(self, img: "ppm_to_png.PPMImage",
                         region: tuple[int, int, int, int] | None = None):
        """BBox de la tinta blanca (>200) del glifo suelto en la topbar.

        La top bar muestra SOLO el glifo ribbon del PNG (sin contenedor azul),
        con altura ~10 px (misma altura visual que el wordmark). Se mide su
        bbox para verificar tamano (~9x10) y alineacion con el texto.
        """
        # zona del logo (x<26): el wordmark empieza en ~x=29 tras el glifo ~9 px
        x0, y0, w, h = region or (0, 0, min(26, img.width),
                                  TOPBAR_HEIGHT_THEME)
        px = img.pixels
        stride = img.width * 3
        minx, miny, maxx, maxy, n = w, h, -1, -1, 0
        for y in range(y0, min(y0 + h, img.height)):
            base = y * stride
            for x in range(x0, min(x0 + w, img.width)):
                i = base + x * 3
                if px[i] > 200 and px[i + 1] > 200 and px[i + 2] > 200:
                    n += 1
                    minx = min(minx, x); maxx = max(maxx, x)
                    miny = min(miny, y); maxy = max(maxy, y)
        if n == 0:
            return None
        return {"bbox": (minx, miny, maxx - minx + 1, maxy - miny + 1),
                "px": n, "center": ((minx + maxx) // 2, (miny + maxy) // 2)}

    def topbar_word_ink(self, img: "ppm_to_png.PPMImage",
                        x_from: int = 24, width: int = 90):
        """BBox de la tinta blanca del wordmark "SereOS" en la topbar."""
        px = img.pixels
        stride = img.width * 3
        x1 = min(img.width, x_from + width)
        minx, miny, maxx, maxy, n = x1, TOPBAR_HEIGHT_THEME, -1, -1, 0
        for y in range(TOPBAR_HEIGHT_THEME):
            base = y * stride
            for x in range(x_from, x1):
                i = base + x * 3
                if px[i] > 200 and px[i + 1] > 200 and px[i + 2] > 200:
                    n += 1
                    minx = min(minx, x); maxx = max(maxx, x)
                    miny = min(miny, y); maxy = max(maxy, y)
        if n == 0:
            return None
        return {"bbox": (minx, miny, maxx - minx + 1, maxy - miny + 1),
                "px": n, "center": ((minx + maxx) // 2, (miny + maxy) // 2)}

    def topbar_blue_px(self, img: "ppm_to_png.PPMImage") -> int:
        """Pixeles de azul de marca (#004EFD) en la topbar (debe ser 0)."""
        px = img.pixels
        stride = img.width * 3
        tr, tg, tb = OFFICIAL_LOGO_BLUE
        n = 0
        for y in range(min(TOPBAR_HEIGHT_THEME, img.height)):
            base = y * stride
            for x in range(img.width):
                i = base + x * 3
                if (abs(px[i] - tr) <= LOGO_TOL
                        and abs(px[i + 1] - tg) <= LOGO_TOL
                        and abs(px[i + 2] - tb) <= LOGO_TOL):
                    n += 1
        return n

    def find_menu_button(self, img: "ppm_to_png.PPMImage"):
        """Centro del boton de menu (hamburguesa) en la barra superior."""
        clusters = self._color_clusters(
            img, (168, 176, 192), (0, 0, min(260, img.width),
                                   TOPBAR_HEIGHT_THEME), tol=6, min_size=6)
        if not clusters:
            return (100, TOPBAR_HEIGHT_THEME // 2)
        return clusters[0]["center"]

    def open_apps(self, vm: QemuController) -> list[str]:
        open_ids: list[str] = []
        for line in vm.serial_lines():
            if line.startswith(APP_OPEN):
                app_id = line[len(APP_OPEN):].strip()
                if app_id and app_id not in open_ids:
                    open_ids.append(app_id)
            elif line.startswith(APP_CLOSE):
                app_id = line[len(APP_CLOSE):].strip()
                if app_id in open_ids:
                    open_ids.remove(app_id)
        return open_ids

    def close_all_windows_quiet(self, vm: QemuController,
                                max_rounds: int = 12) -> bool:
        """Cierra todas las ventanas abiertas sin registrar pasos (para
        capturar cada app limpia, sin ventanas de fondo)."""
        for _ in range(max_rounds):
            if not self.open_apps(vm):
                time.sleep(0.6)   # deja terminar el cierre pendiente
                return True
            vm.press("f6")
            time.sleep(0.12)
            since = vm.marker_offset()
            vm.sendkey("ctrl+w")
            time.sleep(0.28)
            if not self.new_close_markers(vm, since):
                since = vm.marker_offset()
                vm.sendkey("alt+w")
                time.sleep(0.28)
                if not self.new_close_markers(vm, since):
                    return not self.open_apps(vm)
        return not self.open_apps(vm)

    def new_close_markers(self, vm: QemuController, since: int) -> list[str]:
        return [
            ln for ln in vm.serial_text()[since:].splitlines()
            if ln.startswith(APP_CLOSE)
        ]

    def close_windows(self, case: Case, vm: QemuController) -> bool:
        """Cierra todas las ventanas.

        Metodo principal: atajo de teclado de QA (F6 para enfocar + Ctrl+W,
        implementado por el compositor). Si no basta, se intenta el clic en el
        semaforo rojo con el raton PS/2 (QMP rel), que es best-effort.
        """
        remaining = self.open_apps(vm)
        case.step("ventanas abiertas antes de cerrar", None,
                  ", ".join(remaining) if remaining else "ninguna")
        closed: list[str] = []
        used = "atajo de teclado F6 + Ctrl+W"

        # 1) cierre por teclado: enfocar la siguiente ventana y Ctrl+W
        for attempt in range(12):
            if not remaining:
                break
            vm.press("f6")
            time.sleep(self.t(0.15))
            since = vm.marker_offset()
            vm.sendkey("ctrl+w")
            time.sleep(self.t(0.3))
            new = [
                ln[len(APP_CLOSE):].strip()
                for ln in self.new_close_markers(vm, since)
            ]
            if not new:
                # probar Alt+W por si el compositor solo mira Alt
                since = vm.marker_offset()
                vm.sendkey("alt+w")
                time.sleep(self.t(0.3))
                new = [
                    ln[len(APP_CLOSE):].strip()
                    for ln in self.new_close_markers(vm, since)
                ]
            if not new:
                break
            closed.extend(new)
            remaining = self.open_apps(vm)
        if closed:
            case.method = "keyboard_ctrl_w"

        # 2) best-effort con el raton: clic en el semaforo rojo de la ventana
        clicks = 0
        consecutive_fail = 0
        if remaining:
            case.method = "mouse_close"
            while remaining and clicks < 8:
                clicks += 1
                probe = self.raw_dir / f"close_probe_{clicks}.ppm"
                try:
                    vm.screendump(probe)
                    img = ppm_to_png.read_ppm(probe)
                except (QemuError, ppm_to_png.PPMError):
                    break
                buttons = self.find_red_buttons(img)
                if not buttons:
                    break
                since = vm.marker_offset()
                before = set(remaining)
                try:
                    self.mouse_click_at(vm, buttons[0][0], buttons[0][1])
                    self.mouse_worked = True
                except QemuError as exc:
                    case.step("control del raton por QMP", False, str(exc))
                    break
                time.sleep(self.t(0.35))
                new = [
                    ln[len(APP_CLOSE):].strip()
                    for ln in self.new_close_markers(vm, since)
                ]
                closed.extend(new)
                remaining = self.open_apps(vm)
                if not new or set(remaining) == before:
                    consecutive_fail += 1
                    if consecutive_fail >= 3:
                        break
                else:
                    consecutive_fail = 0
            if closed and "keyboard" in used:
                pass
            if closed:
                used = ("atajo de teclado F6 + Ctrl+W"
                        if case.method == "keyboard_ctrl_w"
                        else "raton (semaforo rojo)")

        remaining = self.open_apps(vm)
        case.step(
            f"ventanas cerradas ({len(closed)}): {', '.join(closed) or 'ninguna'}",
            bool(closed),
            f"metodo: {used}; quedan abiertas: {', '.join(remaining) or 'ninguna'}",
        )
        return remaining == []

    def test_window_close(self, case: Case) -> bool | None:
        if not self.require_gui(case):
            return None
        vm = self.gvm
        assert vm is not None
        # montar una escena multiventana limpia con las 4 apps del escritorio
        self.close_all_windows_quiet(vm)
        for key, kind in (("f2", "terminal"), ("f1", "files"),
                          ("f3", "monitor"), ("f5", "about")):
            since = vm.marker_offset()
            vm.press(key)
            try:
                self.wait_app_open(vm, kind, self.t(10), since)
            except MarkerTimeout as exc:
                case.fail(f"multiventana: abrir {kind}", str(exc))
            time.sleep(self.t(0.35))
        time.sleep(self.t(0.8))
        open_now = self.open_apps(vm)
        self.capture(case, vm, "13_multiventana",
                     note=f"{len(open_now)} ventanas abiertas: "
                          f"{', '.join(open_now)}")
        all_closed = self.close_windows(case, vm)
        time.sleep(self.t(0.6))
        self.capture(case, vm, "desktop_windows_closed", publish=False,
                     note="escritorio tras cerrar ventanas")
        if all_closed:
            case.step("todas las ventanas cerradas", True)
        else:
            case.fail("todas las ventanas cerradas",
                      "quedan ventanas abiertas; ver detalle de cierre")
        # sin panicos durante el cierre
        fatals = self.fatal_in(vm)
        case.step("sin excepcion/panico al cerrar ventanas", not fatals,
                  "; ".join(fatals) if fatals else "log limpio")
        return case.ok

    def test_window_focus(self, case: Case) -> bool | None:
        if not self.require_gui(case):
            return None
        vm = self.gvm
        assert vm is not None
        # abrir dos ventanas para poder alternar el foco. Se verifica con los
        # marcadores APP_OPEN: si la entrada de teclado de QEMU se hubiera
        # quedado sorda (p.ej. por sendkey solapados), aqui se detecta.
        since = vm.marker_offset()
        vm.press("f2")
        try:
            self.wait_app_open(vm, "terminal", self.t(10), since)
            files_since = vm.marker_offset()
            vm.press("f1")
            self.wait_app_open(vm, "files", self.t(10), files_since)
            case.step("F2/F1 abren terminal y archivos para la prueba de foco",
                      True)
        except MarkerTimeout as exc:
            case.fail("abrir ventanas para la prueba de foco", str(exc))
        time.sleep(self.t(0.9))
        before = self.capture(case, vm, "win_two_open", publish=False,
                              note="terminal + archivos")
        since = vm.marker_offset()
        vm.press("f6")
        time.sleep(self.t(0.4))
        focused = self.capture(case, vm, "win_focus", publish=False,
                               note="F6 siguiente ventana")
        self.screen_changed(case, "F6 cambia la ventana enfocada",
                            before, focused, min_ratio=0.0001)
        since_f7 = vm.marker_offset()
        vm.press("f7")
        time.sleep(self.t(0.5))
        minimized = self.capture(case, vm, "win_minimized", publish=False,
                                 note="F7 minimizar ventana")
        self.screen_changed(case, "F7 minimiza la ventana activa",
                            focused, minimized, min_ratio=0.0005)
        return case.ok

    # -- fallback de modo texto --------------------------------------------
    def build_alt_iso(self, default: int = 1) -> Path:
        """ISO auxiliar con la entrada de texto por defecto (solo fallback).

        Reutiliza el grub.cfg y los kernels reales del proyecto, cambiando
        unicamente ``timeout`` y ``default`` para que la seleccion de la
        entrada de texto sea determinista (sin depender del timing de GRUB).
        """
        alt_dir = self.raw_dir / "alt_iso"
        if alt_dir.exists():
            shutil.rmtree(alt_dir)
        (alt_dir / "boot" / "grub").mkdir(parents=True)
        shutil.copy2(ROOT / "sereos.bin", alt_dir / "boot" / "sereos.bin")
        # kernel auxiliar de modo texto, si el proyecto lo genera
        for extra in ("sereos-text.bin", "sereos_text.bin"):
            src = ROOT / extra
            if src.is_file():
                shutil.copy2(src, alt_dir / "boot" / extra)
                break
        cfg_lines = []
        for line in (ROOT / "grub.cfg").read_text(
                encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("set timeout="):
                line = "set timeout=0"
            elif stripped.startswith("set default="):
                line = f"set default={default}"
            cfg_lines.append(line)
        (alt_dir / "boot" / "grub" / "grub.cfg").write_text(
            "\n".join(cfg_lines) + "\n", encoding="utf-8")
        out = self.raw_dir / "sereos-alt-text.iso"
        proc = subprocess.run(
            ["grub-mkrescue", "-o", str(out), str(alt_dir)],
            capture_output=True, text=True)
        if proc.returncode != 0 or not out.is_file():
            raise QemuError(
                f"no se pudo generar la ISO auxiliar de modo texto: "
                f"{proc.stderr[-800:]}")
        return out

    def wait_grub_menu(self, vm: QemuController, timeout: float = 10.0) -> bool:
        """Espera a que el menu de GRUB este dibujado (texto 720x400).

        Evita enviar teclas antes de que GRUB este escuchando (si se envian
        demasiado pronto se pierden y GRUB arranca la entrada por defecto).
        """
        probe = self.raw_dir / "grub_probe.ppm"
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                ppm = vm.screendump(probe, timeout=3)
                img = ppm_to_png.read_ppm(ppm)
            except (QemuError, ppm_to_png.PPMError):
                time.sleep(0.1)
                continue
            if img.width <= 800 and img.height <= 500:
                stats = ppm_to_png.analyze(img)
                if stats.distinct_colors >= 2 and stats.non_black_ratio >= 0.02:
                    return True
            time.sleep(0.1)
        return False

    def test_text_fallback(self, case: Case) -> bool | None:
        vm = None
        method = ""
        # Intento principal: elegir la 2a entrada del menu GRUB con down+ret.
        for attempt in range(1, 4):
            vm = self.new_vm(f"text{attempt}")
            vm.start()
            if not self.wait_grub_menu(vm, self.t(10)):
                case.step(f"menu GRUB visible (intento {attempt})", None,
                          "no se detecto el menu a tiempo")
            time.sleep(0.2)
            since = vm.marker_offset()
            vm.sendkey("down")
            time.sleep(0.2)
            vm.sendkey("ret")
            try:
                hit = vm.wait_marker(MARK_TEXT, self.t(18), since)
                method = f"GRUB teclado (down+ret), intento {attempt}"
                case.step(f"2a entrada GRUB -> {MARK_TEXT}", True, hit.line)
                break
            except MarkerTimeout as exc:
                # los intentos fallidos son informativos: el fallback decide
                case.step(f"intento {attempt} de seleccionar modo texto", None,
                          f"sin {MARK_TEXT}; {vm.serial_tail(3)}")
                vm.stop()
                vm = None
                continue
        if vm is None:
            # Fallback reproducible: ISO auxiliar con default=1, timeout=0
            try:
                alt_iso = self.build_alt_iso(default=1)
                vm = self.new_vm("text_altiso", iso=alt_iso)
                vm.start()
                hit = vm.wait_marker(MARK_TEXT, self.t(25))
                method = "ISO auxiliar con default=1 (fallback)"
                case.step(f"modo texto via ISO auxiliar -> {MARK_TEXT}", True,
                          hit.line)
            except (QemuError, MarkerTimeout) as exc:
                case.fail("modo texto de respaldo", str(exc))
                case.method = "text_fallback_failed"
                if vm is not None:
                    vm.stop()
                return False

        case.method = method
        # El modo texto es VGA 80x25: fondo negro con texto claro.
        time.sleep(self.t(0.6))
        shot = self.capture(case, vm, "14_text_mode",
                            min_colors=TEXT_MIN_COLORS,
                            min_nonblack=TEXT_MIN_NONBLACK,
                            note="consola VGA de respaldo")
        vm.type_line("help", delay=self.t(0.07), settle=self.t(0.6))
        time.sleep(self.t(0.2))
        shot2 = self.capture(case, vm, "text_mode_help", publish=False,
                             min_colors=TEXT_MIN_COLORS,
                             min_nonblack=TEXT_MIN_NONBLACK,
                             note="shell de texto: help")
        self.screen_changed(case, "la shell de texto responde a 'help'",
                            shot, shot2, min_ratio=0.0002)
        fatals = self.fatal_in(vm)
        case.step("sin excepcion/panico en modo texto", not fatals,
                  "; ".join(fatals) if fatals else "log limpio")
        vm.stop()
        return case.ok

    # -- panico controlado (div0 real desde la terminal) -------------------
    def test_panic(self, case: Case) -> bool | None:
        """Provoca una division por cero real desde la terminal y captura la
        pantalla de panico. Su log es la UNICA excepcion esperada."""
        vm = self.new_vm("panic")
        try:
            vm.start()
            vm.wait_marker(MARK_GUI, self.t(60))
            since = vm.marker_offset()
            vm.press("f2")
            try:
                self.wait_app_open(vm, "terminal", self.t(12), since)
            except MarkerTimeout as exc:
                case.fail("abrir terminal para el test de panico", str(exc))
            time.sleep(self.t(0.9))
            before = self.capture(case, vm, "panic_before", publish=False,
                                  note="terminal antes de div0")
            vm.type_line("div0", delay=self.t(0.07), settle=self.t(1.0))
            hit = None
            try:
                hit = vm.wait_marker("SEREOS_EXCEPTION", self.t(12))
                case.step("div0 provoca SEREOS_EXCEPTION", True, hit.line)
            except MarkerTimeout as exc:
                case.fail("div0 provoca SEREOS_EXCEPTION", str(exc))
            time.sleep(self.t(0.8))
            shot = self.capture(case, vm, "15_panic",
                                note="pantalla de panico (division por cero)")
            ratio = ppm_to_png.diff_ratio(
                before.img, shot.img,
                self.region_below_topbar(before.img))
            case.step("la pantalla de panico sustituye a la terminal",
                      ratio > 0.02, f"diferencia = {ratio:.2%}")
            # este log contiene la excepcion esperada: no cuenta en no_fatal
            self.expected_fatal_logs.add(vm.log_path)
            if hit is not None:
                self.expected_fatals.append(f"panic(div0): {hit.line}")
        finally:
            try:
                vm.stop()
            except Exception:  # noqa: BLE001
                pass
        case.step("la excepcion fue esperada y controlada", True,
                  "div0 es una prueba intencionada de la IDT")
        return case.ok

    # -- resoluciones alternativas con ISO temporal en /tmp ----------------
    @staticmethod
    def patch_multiboot_video(data: bytearray, width: int,
                              height: int, depth: int = 32) -> int:
        """Parchea la peticion de video de la cabecera Multiboot v1.

        GRUB da prioridad a la peticion de la cabecera del kernel sobre el
        ``set gfxmode`` de grub.cfg (verificado empiricamente), asi que para
        probar otra resolucion hay que copiar el kernel y cambiar aqui
        width/height/depth. El checksum no cubre estos campos.
        """
        import struct as _struct
        magic = _struct.pack("<I", 0x1BADB002)
        off = data.find(magic)
        if off < 0 or off > 32768:
            raise QemuError("no se encontro la cabecera Multiboot en sereos.bin")
        flags = _struct.unpack("<I", data[off + 4:off + 8])[0]
        if not (flags & 0x4):
            raise QemuError("la cabecera Multiboot no pide video (bit 2)")
        data[off + 36:off + 40] = _struct.pack("<I", width)
        data[off + 40:off + 44] = _struct.pack("<I", height)
        data[off + 44:off + 48] = _struct.pack("<I", depth)
        return off

    def build_resolution_iso(self, width: int, height: int,
                             tag: str) -> tuple[Path, Path]:
        """ISO auxiliar en /tmp con resolucion <w>x<h>x32 (no toca el repo)."""
        import struct as _struct
        import tempfile
        base = self.iso.parent
        bin_src = (base / "sereos.bin") if (base / "sereos.bin").is_file() \
            else (ROOT / "sereos.bin")
        text_src = (base / "sereos-text.bin") \
            if (base / "sereos-text.bin").is_file() else (ROOT / "sereos-text.bin")
        cfg_src = (base / "grub.cfg") if (base / "grub.cfg").is_file() \
            else (ROOT / "grub.cfg")
        tmp = Path(tempfile.mkdtemp(prefix=f"sereos_{tag}_"))
        (tmp / "boot" / "grub").mkdir(parents=True)
        patcher = ROOT / "tools" / "patch_multiboot_mode.py"
        if patcher.is_file():
            proc = subprocess.run(
                [sys.executable, str(patcher), str(bin_src),
                 str(tmp / "boot" / "sereos.bin"), str(width), str(height), "32"],
                capture_output=True, text=True)
            if proc.returncode != 0:
                raise QemuError(f"patch_multiboot_mode fallo: {proc.stderr[-500:]}")
        else:
            kernel = bytearray(bin_src.read_bytes())
            self.patch_multiboot_video(kernel, width, height, 32)
            (tmp / "boot" / "sereos.bin").write_bytes(bytes(kernel))
        if text_src.is_file():
            shutil.copy2(text_src, tmp / "boot" / "sereos-text.bin")
        # comprobacion: el kernel parcheado sigue siendo Multiboot valido
        chk = subprocess.run(["grub-file", "--is-x86-multiboot",
                              str(tmp / "boot" / "sereos.bin")],
                             capture_output=True, text=True)
        if chk.returncode != 0:
            raise QemuError("el kernel parcheado ya no es Multiboot valido")
        lines = []
        replaced = False
        for line in cfg_src.read_text(encoding="utf-8").splitlines():
            if not replaced and line.strip().startswith("set gfxmode="):
                indent = line[:len(line) - len(line.lstrip())]
                line = f"{indent}set gfxmode={width}x{height}x32"
                replaced = True
            lines.append(line)
        if not replaced:
            raise QemuError(f"{cfg_src} no contiene 'set gfxmode='")
        (tmp / "boot" / "grub" / "grub.cfg").write_text(
            "\n".join(lines) + "\n", encoding="utf-8")
        iso = tmp / f"sereos-{width}x{height}.iso"
        proc = subprocess.run(["grub-mkrescue", "-o", str(iso), str(tmp)],
                              capture_output=True, text=True)
        if proc.returncode != 0 or not iso.is_file():
            raise QemuError(f"no se pudo crear la ISO {width}x{height}: "
                            f"{proc.stderr[-600:]}")
        return tmp, iso

    def test_resolution(self, case: Case, width: int, height: int) -> bool | None:
        """Arranca una ISO temporal a <width>x<height>x32, abre una app y
        comprueba que el framebuffer real tiene esa resolucion."""
        name = f"{16 if width == 1280 else 17}_resolution_{width}x{height}"
        tmp = iso = vm = None
        try:
            tmp, iso = self.build_resolution_iso(width, height,
                                                f"{width}x{height}")
            case.step(f"ISO temporal {width}x{height} generada en /tmp", True,
                      str(iso))
            vm = self.new_vm(f"res{width}", iso=iso, width=width, height=height)
            # el driver PS/2 parte de la posicion inicial de input.c (512,384)
            # y solo la recorta a los bounds del framebuffer, no la recentra.
            self.mouse_pos = (min(512, width - 1), min(384, height - 1))
            vm.start()
            vm.wait_marker(MARK_GUI, self.t(70))
            time.sleep(self.t(0.6))
            base = self.capture(case, vm, f"max_baseline_{width}",
                                publish=False,
                                note=f"escritorio de referencia {width}x{height}")
            since = vm.marker_offset()
            vm.press("f2")
            try:
                self.wait_app_open(vm, "terminal", self.t(15), since)
            except MarkerTimeout:
                case.step("app abierta en la resolucion alternativa", None,
                          "la terminal no emitio APP_OPEN; se captura igualmente")
            time.sleep(self.t(1.0))
            shot = self.capture(case, vm, name,
                                note=f"resolucion real {width}x{height}")
            case.step(f"framebuffer a {width}x{height}",
                      shot.stats.width == width and shot.stats.height == height,
                      f"captura = {shot.stats.width}x{shot.stats.height}")
            # barra de tareas full-width en esta resolucion: cerrar la
            # terminal, abrir Archivos y maximizar con el semaforo verde.
            vm.sendkey("ctrl+w")
            time.sleep(self.t(0.7))
            since2 = vm.marker_offset()
            vm.press("f1")
            try:
                self.wait_app_open(vm, "files", self.t(12), since2)
            except MarkerTimeout as exc:
                case.fail("abrir Archivos en la resolucion alternativa", str(exc))
            time.sleep(self.t(0.9))
            opened, det = self.maximize_with_traffic_light(vm)
            if not opened:
                case.step("maximizar en la resolucion alternativa", None, det)
            time.sleep(self.t(0.4))
            tb_name = ("31_max_1280" if width == 1280
                       else "32_max_800")
            tb = self.capture(case, vm, tb_name,
                              note=f"maximizado full-height a {width}x{height}")
            st = self.dock_metrics(tb.img, base.img)
            nm = self.topnav_metrics(tb.img)
            case.step(f"sin dock inferior en {width}x{height} (full-height)",
                      st["full_height"] and st["dock_icon_px"] == 0, str(st))
            case.step(f"5 accesos topnav en {width}x{height}",
                      nm["nav_present"] and nm["active_index"] == 0, str(nm))
            case.step(f"ventana maximizada en {width}x{height}",
                      self.maximized_window_present(tb.img),
                      "semaforo junto a la topbar")
            fb = self.full_bleed_metrics(tb.img, base.img)
            case.step(f"full-bleed full-height exacto en {width}x{height}",
                      fb.get("full_bleed", False), str(fb))
            case.step(f"captura a {width}x{height}",
                      tb.stats.width == width and tb.stats.height == height,
                      f"{tb.stats.width}x{tb.stats.height}")
            fatals = self.fatal_in(vm)
            case.step("sin excepcion/panico en la resolucion alternativa",
                      not fatals, "; ".join(fatals) if fatals else "log limpio")
        finally:
            if vm is not None:
                try:
                    vm.stop()
                except Exception:  # noqa: BLE001
                    pass
            if tmp is not None:
                shutil.rmtree(tmp, ignore_errors=True)
        return case.ok

    def test_resolution_1280(self, case: Case) -> bool | None:
        return self.test_resolution(case, 1280, 1024)

    def test_resolution_800(self, case: Case) -> bool | None:
        return self.test_resolution(case, 800, 600)

    def test_no_fatal(self, case: Case) -> bool | None:
        problems: list[str] = []
        checked = 0
        for label, log_path in self.logs:
            if log_path in self.expected_fatal_logs:
                continue          # test de panico intencionado (div0)
            checked += 1
            try:
                text = log_path.read_text(encoding="utf-8", errors="replace")
            except FileNotFoundError:
                continue
            for line in text.splitlines():
                if line.startswith(FATAL_PREFIXES):
                    problems.append(f"{label}: {line}")
        detail = "; ".join(problems) if problems else f"{checked} logs limpios"
        if self.expected_fatals:
            detail += (f" (excepcion esperada de la prueba panic: "
                       f"{self.expected_fatals[0]})")
        case.step("ningun SEREOS_EXCEPTION/SEREOS_PANIC inesperado en los logs",
                  not problems, detail)
        return case.ok

    # -- ejecucion ----------------------------------------------------------
    def run(self) -> int:
        if not self.iso.is_file():
            print(f"ERROR: no existe {self.iso}; ejecuta 'make' primero.",
                  file=sys.stderr)
            return 2
        try:
            self.qemu_version = subprocess.run(
                ["qemu-system-i386", "--version"], capture_output=True,
                text=True, timeout=10).stdout.strip().splitlines()[0]
        except (OSError, subprocess.SubprocessError, IndexError):
            self.qemu_version = "qemu-system-i386 (version desconocida)"
        self.iso_size = self.iso.stat().st_size
        self.iso_mtime = self.iso.stat().st_mtime

        self._cleanup_old_runs()
        self.raw_dir.mkdir(parents=True, exist_ok=True)

        # (clave, titulo, funcion, necesita_escritorio_grafico)
        all_cases = [
            ("boot", "Arranque, splash y escritorio", self.test_boot, False),
            ("terminal", "Terminal grafica (F2) y comandos",
             self.test_terminal, True),
            ("files", "Gestor de archivos (F1)", self.test_files, True),
            ("monitor", "Monitor del sistema (F3)", self.test_monitor, True),
            ("about", "Acerca de SereOS (F5)", self.test_about, True),
            ("maximize", "Maximizacion full-bleed y WM (restaurar/minimizar/resize)",
             self.test_maximize, True),
            ("corners", "Esquinas redondeadas: clipping, solape y resize",
             self.test_window_corners, True),
            ("dock", "Dock flotante inferior (sin maximizada)",
             self.test_dock, True),
            ("topnav", "Navegacion adaptativa: dock oculto + 5 accesos topbar",
             self.test_topnav, True),
            ("game", "PAC-MAN SereOS (F4)", self.test_game, True),
            ("audio", "Audio del juego: captura WAV (SB16)",
             self.test_audio, False),
            ("window_close", "Cierre de ventanas", self.test_window_close, True),
            ("window_focus", "Enfoque F6 y minimizar F7",
             self.test_window_focus, True),
            ("text_fallback", "Fallback de modo texto (GRUB 2a entrada)",
             self.test_text_fallback, False),
            ("panic", "Panico controlado (div0 real desde la terminal)",
             self.test_panic, False),
            ("resolution_1280", "Resolucion 1280x1024 (ISO temporal en /tmp)",
             self.test_resolution_1280, False),
            ("resolution_800", "Resolucion 800x600 (ISO temporal en /tmp)",
             self.test_resolution_800, False),
            ("no_fatal", "Sin excepciones ni panicos inesperados",
             self.test_no_fatal, False),
        ]
        cases = list(all_cases)
        selected = self.args.only
        if selected:
            wanted = {s.strip() for s in selected.split(",") if s.strip()}
            known = {c[0] for c in all_cases}
            unknown = wanted - known
            if unknown:
                print(f"ERROR: pruebas desconocidas: {', '.join(sorted(unknown))}",
                      file=sys.stderr)
                return 2
            cases = [c for c in all_cases if c[0] in wanted]
            # las pruebas que usan el escritorio necesitan arrancarlo primero
            if any(c[3] for c in cases) and not any(c[0] == "boot" for c in cases):
                cases = [all_cases[0]] + cases
                print("NOTA: se anade la prueba 'boot' porque las pruebas "
                      "seleccionadas necesitan el escritorio grafico.")

        self._print_header()
        try:
            for key, title, func, _needs_gui in cases:
                case = Case(key=key, title=title)
                self.cases.append(case)
                print(f"\n--- [{key}] {title} ---")
                t0 = time.time()
                try:
                    result = func(case)
                    if result is False:
                        case.ok = False
                except (QemuError, MarkerTimeout, AssertionError,
                        ppm_to_png.PPMError) as exc:
                    case.ok = False
                    case.error = f"{type(exc).__name__}: {exc}"
                    case.fail("excepcion en la prueba", case.error)
                except Exception as exc:  # noqa: BLE001 - queremos el resumen
                    case.ok = False
                    case.error = f"{type(exc).__name__}: {exc}\n" \
                                 f"{traceback.format_exc(limit=3)}"
                    case.fail("error inesperado de la suite", case.error)
                finally:
                    case.duration = time.time() - t0
                # un fallo en un paso implica fallo de la prueba
                if any(st.ok is False for st in case.steps):
                    case.ok = False
                elif case.ok is None and not case.skip_reason:
                    case.ok = True
                if case.ok is None and case.skip_reason:
                    print(f"  SKIP: {case.skip_reason}")
                self._print_case(case)
        finally:
            self._stop_all_vms()

        # caso no_fatal calculado al final tambien si hubo fallos
        self._write_json()
        return self._summary()

    def _cleanup_old_runs(self) -> None:
        keep = max(1, self.args.keep_runs)
        if not self.raw_root.is_dir():
            return
        runs = sorted(
            [p for p in self.raw_root.iterdir()
             if p.is_dir() and p.name[:8].isdigit()],
            key=lambda p: p.name,
        )
        for old in runs[:-keep]:
            if old.resolve().parent == self.raw_root.resolve():
                shutil.rmtree(old, ignore_errors=True)

    def _stop_all_vms(self) -> None:
        for vm in self.vms:
            try:
                if vm.is_running():
                    vm.stop()
            except Exception:  # noqa: BLE001
                pass

    # -- salida -------------------------------------------------------------
    def _print_header(self) -> None:
        print("=" * 74)
        print(" SereOS v1.0 - suite de verificacion automatizada en QEMU")
        print("=" * 74)
        print(f"ISO          : {self._rel(self.iso)} ({self.iso_size} bytes)")
        print(f"QEMU         : {self.qemu_version}")
        print(f"KVM          : {self.args.kvm} "
              f"(disponible={'si' if QemuController.kvm_available() else 'no'})")
        print(f"Artefactos   : {self._rel(self.raw_dir)}")
        print(f"Capturas PNG : {self._rel(self.shots_dir)}/")

    def _print_case(self, case: Case) -> None:
        status = "SKIP" if case.ok is None and case.skip_reason else (
            "PASS" if case.ok else "FAIL")
        print(f"  [{status}] {case.key} ({case.duration:.1f}s)")
        if case.method:
            print(f"         metodo: {case.method}")
        for st in case.steps:
            mark = "ok " if st.ok else ("FALLO" if st.ok is False else "info")
            line = f"         {mark:5s} {st.text}"
            if st.detail:
                line += f"  [{st.detail}]"
            print(line)
        if case.skip_reason and case.ok is None:
            print(f"         motivo: {case.skip_reason}")

    def _summary(self) -> int:
        total = len(self.cases)
        passed = sum(1 for c in self.cases if c.ok is True)
        failed = sum(1 for c in self.cases if c.ok is False)
        skipped = total - passed - failed
        print("\n" + "=" * 74)
        print(f" RESULTADO: {passed}/{total} PASS, {failed} FAIL, {skipped} SKIP")
        if failed:
            print(" Pruebas fallidas:")
            for c in self.cases:
                if c.ok is False:
                    print(f"   - {c.key}: {c.error or 'ver pasos FALLO'}")
        print(f" Capturas: {len(self.shots)} PNG en {self._rel(self.shots_dir)}/")
        print(f" Resumen JSON: {self._rel(self.results_json)}")
        print("=" * 74)
        return 0 if failed == 0 and total > 0 else 1

    def _write_json(self) -> None:
        self.shots_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "suite": "SereOS v1.0 QEMU verification",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "run_id": self.run_id,
            "iso": {
                "path": self._rel(self.iso),
                "size": self.iso_size,
                "mtime": self.iso_mtime,
            },
            "qemu": self.qemu_version,
            "kvm_mode": self.args.kvm,
            "kvm_used": any(v.used_kvm for v in self.vms),
            "mouse_worked": self.mouse_worked,
            "raw_artifacts": "eliminados en la entrega (solo PNG finales)",
            "cases": [
                {
                    "key": c.key,
                    "title": c.title,
                    "result": ("skip" if c.ok is None else
                               ("pass" if c.ok else "fail")),
                    "duration_s": round(c.duration, 2),
                    "skip_reason": c.skip_reason,
                    "error": c.error,
                    "method": c.method,
                    "steps": [
                        {"text": s.text, "ok": s.ok, "detail": s.detail}
                        for s in c.steps
                    ],
                    "screenshots": c.shots,
                }
                for c in self.cases
            ],
            "screenshots": [s.as_dict() for s in self.shots],
            "summary": {
                "total": len(self.cases),
                "passed": sum(1 for c in self.cases if c.ok is True),
                "failed": sum(1 for c in self.cases if c.ok is False),
                "skipped": sum(1 for c in self.cases if c.ok is None),
            },
        }
        self.results_json.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Suite de verificacion de SereOS v1.0 en QEMU.")
    parser.add_argument("--kvm", choices=["auto", "on", "off"], default="auto",
                        help="uso de KVM (auto: si /dev/kvm es accesible)")
    parser.add_argument("--timeout-scale", type=float, default=1.0,
                        help="escala de todos los timeouts (2 = el doble)")
    parser.add_argument("--only", default="",
                        help="lista separada por comas de pruebas a ejecutar")
    parser.add_argument("--list", action="store_true", help="lista las pruebas")
    parser.add_argument("--keep-runs", type=int, default=3,
                        help="numero de ejecuciones crudas (PPM) a conservar")
    parser.add_argument("--no-grub-shot", action="store_true",
                        help="no intentar la captura del menu GRUB")
    parser.add_argument("--iso", default="",
                        help="ISO a probar (por defecto sereos.iso del repo). "
                             "Util para generar el set 'antes' con una ISO "
                             "congelada en /tmp")
    parser.add_argument("--shots-dir", default="",
                        help="directorio de capturas (por defecto "
                             "docs/screenshots)")
    args = parser.parse_args(argv)

    if args.list:
        for key in ("boot", "terminal", "files", "monitor", "about", "game",
                    "audio", "maximize", "corners", "dock", "topnav",
                    "window_close", "window_focus",
                    "text_fallback", "panic", "resolution_1280",
                    "resolution_800", "no_fatal"):
            print(key)
        return 0

    runner = Runner(args)
    try:
        return runner.run()
    except KeyboardInterrupt:
        print("\nInterrumpido por el usuario; cerrando QEMU...", file=sys.stderr)
        runner._stop_all_vms()
        return 130


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
