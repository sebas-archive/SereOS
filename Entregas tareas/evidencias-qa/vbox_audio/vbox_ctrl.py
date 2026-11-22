#!/usr/bin/env python3
"""Controlador de VirtualBox para las pruebas de audio de SereOS (task-1).

Envía teclas con `VBoxManage controlvm <vm> keyboardputscancode`, espera los
marcadores que SereOS escribe por COM1 (uartmode1=file) y captura el monitor
del sink por defecto del host con pw-record.

Uso:
    python3 build/vbox_audio/vbox_ctrl.py --wait GUI_READY
    python3 build/vbox_audio/vbox_ctrl.py --press f2
    python3 build/vbox_audio/vbox_ctrl.py --type audiotest
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

VM = "SereOS Audio"
SERIAL = Path("/tmp/sereos_vbox_serial.log")
OUT = Path("/home/t1an/Descargas/sereos02/build/vbox_audio")

# scancode set 1 (make, break = make|0x80)
SCAN = {
    "esc": 0x01,
    "1": 0x02, "2": 0x03, "3": 0x04, "4": 0x05, "5": 0x06,
    "6": 0x07, "7": 0x08, "8": 0x09, "9": 0x0A, "0": 0x0B,
    "minus": 0x0C, "equal": 0x0D, "backspace": 0x0E, "tab": 0x0F,
    "q": 0x10, "w": 0x11, "e": 0x12, "r": 0x13, "t": 0x14,
    "y": 0x15, "u": 0x16, "i": 0x17, "o": 0x18, "p": 0x19,
    "lbracket": 0x1A, "rbracket": 0x1B, "enter": 0x1C, "ret": 0x1C,
    "ctrl": 0x1D, "a": 0x1E, "s": 0x1F, "d": 0x20, "f": 0x21,
    "g": 0x22, "h": 0x23, "j": 0x24, "k": 0x25, "l": 0x26,
    "semicolon": 0x27, "apostrophe": 0x28, "grave": 0x29,
    "shift": 0x2A, "backslash": 0x2B, "z": 0x2C, "x": 0x2D,
    "c": 0x2E, "v": 0x2F, "b": 0x30, "n": 0x31, "m": 0x32,
    "comma": 0x33, "dot": 0x34, "slash": 0x35, "rshift": 0x36,
    "alt": 0x38, "space": 0x39, "capslock": 0x3A,
    "f1": 0x3B, "f2": 0x3C, "f3": 0x3D, "f4": 0x3E, "f5": 0x3F,
    "f6": 0x40, "f7": 0x41, "f8": 0x42, "f9": 0x43, "f10": 0x44,
    "numlock": 0x45, "scrolllock": 0x46,
    "f11": 0x57, "f12": 0x58,
    "up": 0x48, "down": 0x50, "left": 0x4B, "right": 0x4D,
    "home": 0x47, "end": 0x4F, "pageup": 0x49, "pagedown": 0x51,
    "insert": 0x52, "delete": 0x53,
}


def vbox(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    r = subprocess.run(["VBoxManage", *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"VBoxManage {' '.join(args)} falló: {r.stderr.strip()}")
    return r


def key(name: str, hold_ms: int = 35, settle_ms: int = 55) -> None:
    code = SCAN[name.lower()]
    vbox("controlvm", VM, "keyboardputscancode", f"{code:02x}", f"{code | 0x80:02x}")
    time.sleep(max(hold_ms, settle_ms) / 1000.0)


def type_text(text: str, settle_ms: int = 40) -> None:
    for ch in text:
        if ch == " ":
            name = "space"
        elif ch.isalpha() or ch.isdigit():
            name = ch.lower()
        else:
            raise ValueError(f"carácter no soportado: {ch!r}")
        key(name, settle_ms=settle_ms)


def serial_text() -> str:
    try:
        return SERIAL.read_text(errors="replace")
    except FileNotFoundError:
        return ""


def wait_marker(marker: str, timeout: float = 60.0,
                since_offset: int | None = None) -> tuple[int, str]:
    """Espera a que aparezca una línea que empiece por `marker`.
    Devuelve (end_offset, línea)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        txt = serial_text()
        start = since_offset if since_offset is not None else 0
        for line in txt[start:].splitlines():
            if line.startswith(marker):
                end = txt.find(line, start) + len(line)
                return end, line
        time.sleep(0.15)
    tail = "\n".join(serial_text().splitlines()[-12:])
    raise TimeoutError(f"timeout esperando {marker!r} ({timeout}s). Cola del log:\n{tail}")


def marker_offset() -> int:
    return len(serial_text())


def screenshot(path: Path) -> None:
    vbox("controlvm", VM, "screenshotpng", str(path))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wait", default=None)
    ap.add_argument("--since", type=int, default=None)
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--press", default=None)
    ap.add_argument("--type", default=None)
    ap.add_argument("--shot", default=None)
    args = ap.parse_args()
    if args.press:
        key(args.press)
    if args.type:
        type_text(args.type)
    if args.wait:
        off, line = wait_marker(args.wait, args.timeout, args.since)
        print(f"OK [{off}] {line}")
    if args.shot:
        screenshot(Path(args.shot))
        print(f"screenshot: {args.shot}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
