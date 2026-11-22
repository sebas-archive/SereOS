#!/usr/bin/env python3
"""qemu_ctrl.py - controlador de QEMU para las pruebas de SereOS.

Lanza sereos.iso en QEMU i386 sin ventana, espera a los marcadores que el
kernel escribe por el puerto serie COM1 (``-serial file:...``), envia teclas
por el monitor humano de QEMU (``sendkey``), captura la pantalla con
``screendump`` y cierra QEMU de forma ordenada.

Contrato de marcadores del log serie (uno por linea):
    SEREOS_BOOT_OK mem=<MiB>
    DESKTOP_READY            (gui_init)
    SPLASH_DONE              (splash_run)
    GUI_READY                (bucle del escritorio)
    APP_OPEN:<id> / APP_CLOSE:<id>
    GAME_MENU / GAME_START / GAME_PAUSE / GAME_OVER / GAME_WIN / GAME_EXIT
    SEREOS_TEXT_MODE         (fallback VGA)
    SEREOS_EXCEPTION ... / SEREOS_PANIC ...   (nunca deben aparecer)

Uso directo (diagnostico):
    python3 tools/qemu_ctrl.py                    # arranca, espera y sale
    python3 tools/qemu_ctrl.py --keys "f2" --shot /tmp/term.ppm
    python3 tools/qemu_ctrl.py --text-mode        # elige la 2a entrada GRUB
    python3 tools/qemu_ctrl.py --kvm off

El modulo tambien se importa desde tools/run_tests.py.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

DEFAULT_QEMU = "qemu-system-i386"

# ---------------------------------------------------------------------------
# Nombres de tecla del monitor de QEMU
# ---------------------------------------------------------------------------
# QEMU usa nombres propios para teclas que no son letras/digitos. Los
# modificadores se combinan con '-' (p.ej. "shift-a", "ctrl-alt-f1").
SPECIAL_KEYS: dict[str, str] = {
    "enter": "ret", "return": "ret", "ret": "ret",
    "esc": "esc", "escape": "esc",
    "space": "spc", "spc": "spc",
    "tab": "tab", "backspace": "backspace", "delete": "delete", "insert": "insert",
    "home": "home", "end": "end",
    "pageup": "pgup", "pgdn": "pgdn", "pagedown": "pgdn", "pgup": "pgup",
    "up": "up", "down": "down", "left": "left", "right": "right",
    "shift": "shift", "ctrl": "ctrl", "control": "ctrl", "alt": "alt",
    "pause": "pause", "print": "print", "sysrq": "sysrq",
    "capslock": "caps_lock", "numlock": "num_lock", "scrolllock": "scroll_lock",
    "minus": "minus", "equal": "equal",
    "bracket_left": "bracket_left", "bracket_right": "bracket_right",
    "semicolon": "semicolon", "apostrophe": "apostrophe",
    "grave_accent": "grave_accent", "backslash": "backslash",
    "comma": "comma", "dot": "dot", "slash": "slash",
}
for _i in range(1, 13):
    SPECIAL_KEYS[f"f{_i}"] = f"f{_i}"

# Caracter imprimible -> nombre de tecla QEMU (con modificadores si aplica).
CHAR_KEYS: dict[str, str] = {}
for _c in "abcdefghijklmnopqrstuvwxyz":
    CHAR_KEYS[_c] = _c
for _c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    CHAR_KEYS[_c] = f"shift-{_c.lower()}"
for _c in "0123456789":
    CHAR_KEYS[_c] = _c
CHAR_KEYS.update({
    " ": "spc", "\n": "ret", "\r": "ret", "\t": "tab", "\b": "backspace",
    "-": "minus", "=": "equal", "[": "bracket_left", "]": "bracket_right",
    "\\": "backslash", ";": "semicolon", "'": "apostrophe", "`": "grave_accent",
    ",": "comma", ".": "dot", "/": "slash",
    "!": "shift-1", "@": "shift-2", "#": "shift-3", "$": "shift-4",
    "%": "shift-5", "^": "shift-6", "&": "shift-7", "*": "shift-8",
    "(": "shift-9", ")": "shift-0", "_": "shift-minus", "+": "shift-equal",
    "{": "shift-bracket_left", "}": "shift-bracket_right", "|": "shift-backslash",
    ":": "shift-semicolon", '"': "shift-apostrophe", "~": "shift-grave_accent",
    "<": "shift-comma", ">": "shift-dot", "?": "shift-slash",
})


# ---------------------------------------------------------------------------
# Excepciones
# ---------------------------------------------------------------------------
_DEBUG = bool(os.environ.get("SEREOS_QEMU_DEBUG"))
_DEBUG_STREAM = sys.stderr


def _dbg(msg: str) -> None:
    if _DEBUG:
        print(f"[qemu-debug] {msg}", file=_DEBUG_STREAM, flush=True)


class QemuError(RuntimeError):
    """Fallo controlando QEMU."""


class MarkerTimeout(QemuError):
    """No aparecio un marcador en el log serie dentro del tiempo dado."""

    def __init__(self, marker: str, timeout: float, serial_tail: str):
        self.marker = marker
        self.timeout = timeout
        self.serial_tail = serial_tail
        super().__init__(
            f"timeout de {timeout:.1f}s esperando el marcador {marker!r}; "
            f"ultimas lineas del log serie:\n{serial_tail}"
        )


@dataclass
class MarkerHit:
    marker: str
    offset: int          # posicion en bytes dentro del log
    line_no: int         # numero de linea (1-based)
    line: str            # linea completa del log


# ---------------------------------------------------------------------------
# Monitor humano de QEMU (socket unix)
# ---------------------------------------------------------------------------
class HumanMonitor:
    """Cliente del monitor QEMU en modo humano (prompt ``(qemu)``)."""

    PROMPT = b"(qemu)"

    def __init__(self, path: Path, connect_timeout: float = 15.0,
                 timeout: float = 10.0):
        self.path = Path(path)
        self.connect_timeout = connect_timeout
        self.timeout = timeout
        self.sock: socket.socket | None = None
        self._buf = b""

    def connect(self) -> "HumanMonitor":
        deadline = time.time() + self.connect_timeout
        last_err: Exception | None = None
        while time.time() < deadline:
            try:
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.settimeout(2.0)
                sock.connect(str(self.path))
                self.sock = sock
                self._read_until_prompt(self.timeout)
                return self
            except (FileNotFoundError, ConnectionRefusedError,
                    ConnectionResetError, socket.timeout, OSError) as exc:
                last_err = exc
                time.sleep(0.05)
        raise QemuError(
            f"no se pudo conectar al monitor de QEMU en {self.path}: {last_err}"
        )

    def _read_until_prompt(self, timeout: float) -> str:
        if self.sock is None:
            raise QemuError("monitor no conectado")
        deadline = time.time() + timeout
        while self.PROMPT not in self._buf:
            remaining = deadline - time.time()
            if remaining <= 0:
                raise QemuError(
                    f"timeout esperando el prompt del monitor; recibido: "
                    f"{self._buf[-200:]!r}"
                )
            self.sock.settimeout(min(0.2, remaining))
            try:
                chunk = self.sock.recv(65536)
            except socket.timeout:
                continue
            except OSError as exc:
                raise QemuError(f"monitor desconectado: {exc}") from exc
            if not chunk:
                raise QemuError("el monitor de QEMU cerro la conexion")
            self._buf += chunk
        idx = self._buf.find(self.PROMPT)
        text = self._buf[:idx]
        self._buf = self._buf[idx + len(self.PROMPT):]
        # el prompt va seguido de un espacio que descartamos
        if self._buf.startswith(b" "):
            self._buf = self._buf[1:]
        return text.decode("utf-8", "replace")

    def cmd(self, command: str, timeout: float = 10.0) -> str:
        """Envia una orden al monitor y devuelve la salida (sin el eco)."""
        if self.sock is None:
            raise QemuError("monitor no conectado")
        try:
            self.sock.sendall(command.encode("utf-8") + b"\n")
        except OSError as exc:
            raise QemuError(
                f"no se pudo enviar al monitor ({exc}); conexion perdida"
            ) from exc
        out = self._read_until_prompt(timeout)
        lines = out.splitlines()
        if lines and lines[0].strip() == command.strip():
            lines = lines[1:]
        return "\n".join(lines)

    def close(self) -> None:
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None

    def __enter__(self) -> "HumanMonitor":
        return self.connect()

    def __exit__(self, *exc_info) -> None:
        self.close()


# ---------------------------------------------------------------------------
# Cliente QMP (solo para inyeccion de raton)
# ---------------------------------------------------------------------------
class QmpClient:
    """Cliente QMP minimo: handshake y ``input-send-event``.

    En SereOS el raton es PS/2 (relativo). Los eventos absolutos de QMP
    (``abs``) solo funcionan con tabletas USB, asi que ``mouse_move_abs``
    puede no mover el cursor real; ``mouse_move_rel`` si funciona con PS/2.
    Las pruebas automatizadas usan atajos de teclado, no el raton.
    """

    def __init__(self, path: Path, connect_timeout: float = 10.0,
                 timeout: float = 5.0):
        self.path = Path(path)
        self.connect_timeout = connect_timeout
        self.timeout = timeout
        self.sock: socket.socket | None = None
        self._buf = b""

    def connect(self) -> "QmpClient":
        deadline = time.time() + self.connect_timeout
        last_err: Exception | None = None
        while time.time() < deadline:
            try:
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.settimeout(2.0)
                sock.connect(str(self.path))
                self.sock = sock
                greeting = self._recv_json()
                if "QMP" not in greeting:
                    raise QemuError(f"saludo QMP inesperado: {greeting!r}")
                self._send({"execute": "qmp_capabilities"})
                self._recv_until_return()
                return self
            except (FileNotFoundError, ConnectionRefusedError,
                    ConnectionResetError, socket.timeout, OSError) as exc:
                last_err = exc
                time.sleep(0.05)
        raise QemuError(f"no se pudo conectar a QMP en {self.path}: {last_err}")

    def _recv_json(self) -> dict:
        if self.sock is None:
            raise QemuError("QMP no conectado")
        while True:
            nl = self._buf.find(b"\n")
            if nl >= 0:
                line = self._buf[:nl]
                self._buf = self._buf[nl + 1:]
                if line.strip():
                    try:
                        return json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise QemuError(f"JSON QMP invalido: {line!r}") from exc
                continue
            try:
                chunk = self.sock.recv(65536)
            except socket.timeout as exc:
                raise QemuError("timeout esperando mensaje QMP") from exc
            if not chunk:
                raise QemuError("QMP cerro la conexion")
            self._buf += chunk

    def _send(self, obj: dict) -> None:
        if self.sock is None:
            raise QemuError("QMP no conectado")
        self.sock.sendall(json.dumps(obj).encode("utf-8") + b"\n")

    def _recv_until_return(self, timeout: float | None = None) -> dict:
        deadline = time.time() + (timeout or self.timeout)
        while time.time() < deadline:
            msg = self._recv_json()
            if "error" in msg:
                raise QemuError(f"error QMP: {msg['error']}")
            if "return" in msg:
                return msg
        raise QemuError("timeout esperando respuesta QMP")

    def execute(self, command: str, arguments: dict | None = None,
                timeout: float | None = None) -> dict:
        payload: dict = {"execute": command}
        if arguments is not None:
            payload["arguments"] = arguments
        self._send(payload)
        return self._recv_until_return(timeout)

    def close(self) -> None:
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None

    def __enter__(self) -> "QmpClient":
        return self.connect()

    def __exit__(self, *exc_info) -> None:
        self.close()


# ---------------------------------------------------------------------------
# Controlador de QEMU
# ---------------------------------------------------------------------------
class QemuController:
    """Arranca sereos.iso en QEMU y lo controla desde Python.

    Ejemplo:
        with QemuController(iso="sereos.iso", workdir="docs/screenshots/raw/run") as vm:
            vm.wait_marker("GUI_READY", 60)
            vm.sendkey("f2")
            vm.wait_marker("APP_OPEN:terminal", 10)
            vm.screendump("docs/screenshots/raw/terminal.ppm")
    """

    def __init__(
        self,
        iso: str | Path,
        workdir: str | Path,
        *,
        qemu_bin: str | None = None,
        memory: str = "256M",
        vga: str = "std",
        display: str = "none",
        use_kvm: bool | None = None,
        width: int = 1024,
        height: int = 768,
        monitor_timeout: float = 15.0,
        extra_args: list[str] | None = None,
        cwd: str | Path | None = None,
    ):
        self.iso = Path(iso).resolve()
        self.workdir = Path(workdir).resolve()
        self.qemu_bin = qemu_bin or DEFAULT_QEMU
        self.memory = memory
        self.vga = vga
        self.display = display
        self.use_kvm = use_kvm
        self.width = width
        self.height = height
        self.monitor_timeout = monitor_timeout
        self.extra_args = list(extra_args or [])
        self.cwd = Path(cwd).resolve() if cwd else self.workdir

        self.log_path = self.workdir / "serial.log"
        self.monitor_path = self.workdir / "monitor.sock"
        self.qmp_path = self.workdir / "qmp.sock"
        self.stderr_path = self.workdir / "qemu-stderr.log"

        self.proc: subprocess.Popen | None = None
        self.monitor: HumanMonitor | None = None
        self.qmp: QmpClient | None = None
        self.used_kvm = False
        self.cmdline: list[str] = []

    # -- ciclo de vida ------------------------------------------------------
    @staticmethod
    def kvm_available() -> bool:
        try:
            return os.access("/dev/kvm", os.W_OK)
        except OSError:
            return False

    def _build_cmd(self, kvm: bool) -> list[str]:
        cmd = [
            self.qemu_bin,
            "-name", "sereos-qa",
            "-display", self.display,
            "-m", self.memory,
            "-vga", self.vga,
            "-cdrom", str(self.iso),
            "-monitor", f"unix:{self.monitor_path},server,nowait",
            "-serial", f"file:{self.log_path}",
            "-qmp", f"unix:{self.qmp_path},server,nowait",
            "-rtc", "base=localtime",
            "-no-reboot",
        ]
        if kvm:
            cmd += ["-enable-kvm", "-cpu", "host"]
        cmd += self.extra_args
        return cmd

    def _clean_paths(self) -> None:
        self.workdir.mkdir(parents=True, exist_ok=True)
        for p in (self.log_path, self.monitor_path, self.qmp_path, self.stderr_path):
            try:
                p.unlink()
            except FileNotFoundError:
                pass
            except PermissionError:
                pass

    def start(self, connect_monitor: bool = True) -> "QemuController":
        if not self.iso.is_file():
            raise QemuError(
                f"no existe la imagen ISO {self.iso}; ejecuta 'make' antes de probar"
            )
        if self.proc is not None and self.proc.poll() is None:
            return self

        self._clean_paths()

        want_kvm = self.use_kvm
        if want_kvm is None:
            want_kvm = self.kvm_available()
        attempts = [bool(want_kvm)]
        # Auto-fallback: si KVM estaba activado y QEMU muere, reintentar sin KVM.
        if want_kvm and self.use_kvm is None:
            attempts.append(False)

        last_err: Exception | None = None
        for kvm in attempts:
            self._clean_paths()
            cmd = self._build_cmd(kvm)
            self.cmdline = cmd
            with open(self.stderr_path, "wb") as err:
                self.proc = subprocess.Popen(
                    cmd,
                    cwd=str(self.cwd),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=err,
                    start_new_session=True,
                )
            # Comprobar que QEMU no muere inmediatamente (p.ej. KVM no usable).
            time.sleep(0.25)
            if self.proc.poll() is not None:
                stderr = self.stderr_text()
                last_err = QemuError(
                    f"QEMU termino al arrancar (rc={self.proc.returncode}); "
                    f"stderr:\n{stderr[-2000:]}"
                )
                self.proc = None
                continue
            self.used_kvm = kvm
            if connect_monitor:
                try:
                    self.monitor = HumanMonitor(
                        self.monitor_path, self.monitor_timeout
                    ).connect()
                except QemuError:
                    self.stop()
                    raise
            if self.kvm_available() and not kvm and self.use_kvm is None:
                # solo informativo: el fallback silencioso no debe ocultar nada
                pass
            return self
        raise last_err or QemuError("no se pudo arrancar QEMU")

    def is_running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def stop(self, timeout: float = 5.0) -> int | None:
        """Cierra QEMU de forma ordenada (monitor 'quit', luego terminate/kill)."""
        rc: int | None = None
        if _DEBUG and self.proc is not None:
            import traceback
            _dbg(f"stop() pid={self.proc.pid} rc={self.proc.poll()} "
                 f"caller={' < '.join(f'{f.name}:{f.lineno}' for f in traceback.extract_stack(limit=4)[:-1])}")
        if self.proc is not None:
            if self.proc.poll() is None:
                try:
                    if self.monitor is not None:
                        self.monitor.cmd("quit", timeout=1.5)
                except (QemuError, OSError):
                    pass
            try:
                rc = self.proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                try:
                    self.proc.terminate()
                    rc = self.proc.wait(timeout=3.0)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    rc = self.proc.wait()
            except Exception:
                pass
        if self.monitor is not None:
            self.monitor.close()
            self.monitor = None
        if self.qmp is not None:
            self.qmp.close()
            self.qmp = None
        self.proc = None
        return rc

    def __enter__(self) -> "QemuController":
        return self.start()

    def __exit__(self, *exc_info) -> None:
        self.stop()

    def __del__(self):
        try:
            if self.proc is not None:
                self.stop(timeout=2.0)
        except Exception:
            pass

    # -- monitor ------------------------------------------------------------
    def reconnect_monitor(self) -> None:
        if self.monitor is not None:
            self.monitor.close()
        self.monitor = HumanMonitor(
            self.monitor_path, self.monitor_timeout).connect()

    def monitor_cmd(self, command: str, timeout: float = 10.0) -> str:
        """Envia una orden al monitor; si la conexion se pierde pero QEMU
        sigue vivo, reconecta una vez y reintenta (robustez ante EPIPE)."""
        if self.monitor is None:
            if not self.is_running():
                raise QemuError("QEMU no esta en ejecucion")
            self.reconnect_monitor()
        try:
            return self.monitor.cmd(command, timeout=timeout)
        except QemuError as exc:
            rc = self.proc.returncode if self.proc else "?"
            _dbg(f"monitor EPIPE cmd={command!r} pid="
                 f"{self.proc.pid if self.proc else '?'} rc={rc} "
                 f"alive={self.is_running()} sock={self.monitor_path.exists()} "
                 f"err={exc}")
            if not self.is_running():
                raise QemuError(
                    f"QEMU termino (rc={rc}) "
                    f"mientras se enviaba '{command}': {exc}\n"
                    f"stderr:\n{self.stderr_text()[-1200:]}"
                ) from exc
            try:
                self.reconnect_monitor()
                return self.monitor.cmd(command, timeout=timeout)
            except QemuError as exc2:
                raise QemuError(
                    f"monitor no recuperable tras reconectar ({command}): "
                    f"{exc2}; QEMU vivo={self.is_running()}"
                ) from exc2

    # -- log serie ----------------------------------------------------------
    def serial_text(self) -> str:
        try:
            return self.log_path.read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            return ""

    def serial_lines(self) -> list[str]:
        return [ln for ln in self.serial_text().splitlines() if ln.strip()]

    def serial_tail(self, n: int = 25) -> str:
        lines = self.serial_lines()
        return "\n".join(lines[-n:])

    @staticmethod
    def _marker_at_line(text: str, marker: str, start: int) -> int:
        idx = text.find(marker, start)
        while idx != -1:
            at_line_start = idx == 0 or text[idx - 1] == "\n"
            end = idx + len(marker)
            boundary = end >= len(text) or text[end] in "\r\n \t"
            if at_line_start and boundary:
                return idx
            idx = text.find(marker, idx + 1)
        return -1

    def marker_offset(self) -> int:
        """Offset actual del log (para esperar marcadores *nuevos*)."""
        return len(self.serial_text())

    def has_marker(self, marker: str, since: int = 0) -> bool:
        return self._marker_at_line(self.serial_text(), marker, since) != -1

    def find_marker(self, marker: str, since: int = 0) -> MarkerHit | None:
        text = self.serial_text()
        idx = self._marker_at_line(text, marker, since)
        if idx == -1:
            return None
        line_no = text.count("\n", 0, idx) + 1
        line_end = text.find("\n", idx)
        line = text[idx:line_end if line_end != -1 else len(text)]
        return MarkerHit(marker=marker, offset=idx, line_no=line_no, line=line)

    def wait_marker(self, marker: str, timeout: float = 30.0,
                    since: int | None = None, poll: float = 0.05) -> MarkerHit:
        """Espera un marcador en el log serie.

        ``since`` permite ignorar marcadores antiguos (por defecto, todo el
        log). Usa ``vm.marker_offset()`` antes de una accion para esperar solo
        los marcadores nuevos producidos por esa accion.
        """
        start = 0 if since is None else since
        deadline = time.time() + timeout
        while time.time() < deadline:
            hit = self.find_marker(marker, start)
            if hit is not None:
                return hit
            if not self.is_running():
                stderr = self.stderr_text()
                raise QemuError(
                    f"QEMU termino mientras se esperaba {marker!r} "
                    f"(rc={self.proc.returncode if self.proc else '?'}); "
                    f"stderr:\n{stderr[-1500:]}\nlog serie:\n{self.serial_tail()}"
                )
            time.sleep(poll)
        raise MarkerTimeout(marker, timeout, self.serial_tail())

    def try_wait_marker(self, marker: str, timeout: float = 5.0,
                        since: int | None = None) -> MarkerHit | None:
        try:
            return self.wait_marker(marker, timeout, since)
        except MarkerTimeout:
            return None

    def wait_marker_prefix(self, prefix: str, timeout: float = 30.0,
                           since: int | None = None) -> MarkerHit:
        """Espera una linea que empiece por ``prefix`` (p.ej. ``APP_OPEN:``)."""
        start = 0 if since is None else since
        deadline = time.time() + timeout
        while time.time() < deadline:
            text = self.serial_text()
            pos = start
            while True:
                pos = text.find(prefix, pos)
                if pos == -1:
                    break
                line_start = pos == 0 or text[pos - 1] == "\n"
                line_end = text.find("\n", pos)
                line = text[pos:line_end if line_end != -1 else len(text)]
                if line_start:
                    return MarkerHit(
                        marker=line.strip(), offset=pos,
                        line_no=text.count("\n", 0, pos) + 1, line=line.strip()
                    )
                pos += len(prefix)
            if not self.is_running():
                raise QemuError(
                    f"QEMU termino mientras se esperaba el prefijo {prefix!r}; "
                    f"log serie:\n{self.serial_tail()}"
                )
            time.sleep(0.05)
        raise MarkerTimeout(prefix, timeout, self.serial_tail())

    def fatal_markers(self) -> list[str]:
        """Devuelve las lineas de excepcion/panico presentes en el log."""
        return [
            ln for ln in self.serial_lines()
            if ln.startswith("SEREOS_EXCEPTION") or ln.startswith("SEREOS_PANIC")
        ]

    def stderr_text(self) -> str:
        try:
            return self.stderr_path.read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            return ""

    # -- teclado ------------------------------------------------------------
    def sendkey(self, keys: str, hold_ms: int | None = None,
                timeout: float = 10.0) -> None:
        """Envia una combinacion de teclas (formato del monitor QEMU).

        Acepta modificadores separados por '+' o '-' (p.ej. ``ctrl+w`` y
        ``ctrl-w`` son equivalentes); QEMU espera los nombres unidos por '-'.
        """
        if self.monitor is None:
            raise QemuError("el monitor de QEMU no esta conectado")
        parts = [p for p in keys.replace("+", "-").split("-") if p]
        if not parts:
            raise QemuError(f"combinacion de teclas vacia: {keys!r}")
        combo = "-".join(
            SPECIAL_KEYS.get(part.lower(), part) for part in parts
        )
        cmd = f"sendkey {combo}"
        if hold_ms is not None:
            cmd += f" {int(hold_ms)}"
        out = self.monitor_cmd(cmd, timeout=timeout)
        lowered = out.lower()
        if "invalid" in lowered or "unknown" in lowered or "error" in lowered:
            raise QemuError(f"QEMU rechazo sendkey {combo!r}: {out.strip()}")

    def press(self, key: str, delay: float = 0.06, hold_ms: int = 40) -> None:
        """Pulsa una tecla y espera ``delay`` segundos."""
        self.sendkey(key, hold_ms=hold_ms)
        time.sleep(delay)

    def sendkeys(self, keys: list[str], delay: float = 0.08,
                 hold_ms: int = 40) -> None:
        for key in keys:
            self.press(key, delay=delay, hold_ms=hold_ms)

    @staticmethod
    def text_to_keys(text: str) -> list[str]:
        """Traduce texto ASCII a una lista de teclas QEMU."""
        keys: list[str] = []
        for ch in text:
            if ch not in CHAR_KEYS:
                raise ValueError(
                    f"caracter no soportado por el teclado de pruebas: {ch!r}"
                )
            keys.append(CHAR_KEYS[ch])
        return keys

    def type_text(self, text: str, delay: float = 0.04,
                  hold_ms: int = 25) -> None:
        """Escribe texto con el teclado (minusculas, mayusculas y simbolos)."""
        combo_all = self.text_to_keys(text)
        for i, key in enumerate(combo_all):
            self.sendkey(key, hold_ms=hold_ms)
            if i != len(combo_all) - 1:
                time.sleep(delay)

    def type_line(self, text: str, delay: float = 0.04,
                  settle: float = 0.35) -> None:
        """Escribe una linea y pulsa Enter, dejando tiempo a la app."""
        self.type_text(text, delay=delay)
        self.press("ret", delay=settle)

    # -- video --------------------------------------------------------------
    def screendump(self, path: str | Path, timeout: float = 8.0) -> Path:
        """Captura la pantalla a un fichero PPM (P6) y espera a que este listo."""
        if self.monitor is None:
            raise QemuError("el monitor de QEMU no esta conectado")
        path = Path(path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        self.monitor_cmd(f"screendump {path}", timeout=timeout)
        deadline = time.time() + timeout
        last_size = -1
        stable = 0
        while time.time() < deadline:
            try:
                size = path.stat().st_size
            except FileNotFoundError:
                time.sleep(0.03)
                continue
            if size > 0 and size == last_size:
                stable += 1
                if stable >= 2:
                    with open(path, "rb") as fh:
                        if fh.read(2) != b"P6":
                            raise QemuError(f"captura no es PPM P6: {path}")
                    return path
            else:
                stable = 0
            last_size = size
            time.sleep(0.04)
        raise QemuError(f"timeout esperando la captura {path}")

    # -- raton (limitado: el kernel usa raton PS/2 relativo) ----------------
    def connect_qmp(self) -> QmpClient:
        if self.qmp is None:
            self.qmp = QmpClient(self.qmp_path).connect()
        return self.qmp

    def mouse_move_rel(self, dx: int, dy: int) -> None:
        events = [
            {"type": "rel", "data": {"axis": "x", "value": int(dx)}},
            {"type": "rel", "data": {"axis": "y", "value": int(dy)}},
        ]
        self.connect_qmp().execute("input-send-event", {"events": events})

    def mouse_button(self, button: str = "left", down: bool = True) -> None:
        events = [{"type": "btn", "data": {"down": bool(down), "button": button}}]
        self.connect_qmp().execute("input-send-event", {"events": events})

    def mouse_move_abs(self, x: int, y: int,
                       width: int | None = None,
                       height: int | None = None) -> None:
        """Mueve el raton en coordenadas absolutas (0..ancho, 0..alto).

        Solo funciona si QEMU expone una tableta absoluta; con el raton PS/2
        de SereOS puede no tener efecto. Se documenta como best-effort.
        """
        w = width or self.width
        h = height or self.height
        ax = max(0, min(0x7FFF, round(x * 0x7FFF / max(1, w - 1))))
        ay = max(0, min(0x7FFF, round(y * 0x7FFF / max(1, h - 1))))
        events = [
            {"type": "abs", "data": {"axis": "x", "value": ax}},
            {"type": "abs", "data": {"axis": "y", "value": ay}},
        ]
        self.connect_qmp().execute("input-send-event", {"events": events})

    def mouse_click(self, x: int, y: int, button: str = "left",
                    settle: float = 0.1) -> None:
        self.mouse_move_abs(x, y)
        time.sleep(settle)
        self.mouse_button(button, True)
        time.sleep(0.05)
        self.mouse_button(button, False)


# ---------------------------------------------------------------------------
# Uso directo como herramienta de diagnostico
# ---------------------------------------------------------------------------
def _main(argv: list[str]) -> int:
    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description="Lanza SereOS en QEMU y ejecuta acciones de diagnostico.")
    parser.add_argument("--iso", default=str(root / "sereos.iso"))
    parser.add_argument("--workdir", default=str(root / "docs/screenshots/raw/manual"))
    parser.add_argument("--kvm", choices=["auto", "on", "off"], default="auto")
    parser.add_argument("--timeout", type=float, default=60.0,
                        help="timeout para esperar el escritorio")
    parser.add_argument("--keys", default="", help="teclas a enviar; ';' separa secuencias")
    parser.add_argument("--text", default="", help="texto a escribir (con Enter final)")
    parser.add_argument("--shot", default="", help="captura PPM antes de salir")
    parser.add_argument("--text-mode", action="store_true",
                        help="selecciona la 2a entrada del menu GRUB")
    parser.add_argument("--marker", action="append", default=[],
                        help="marcadores adicionales que esperar (repetible)")
    args = parser.parse_args(argv)

    use_kvm = None if args.kvm == "auto" else (args.kvm == "on")
    vm = QemuController(args.iso, args.workdir, use_kvm=use_kvm)
    rc = 0
    try:
        vm.start()
        print(f"QEMU arrancado (KVM={'si' if vm.used_kvm else 'no'}), "
              f"log: {vm.log_path}")
        if args.text_mode:
            time.sleep(1.0)
            vm.sendkey("down")
            time.sleep(0.15)
            vm.sendkey("ret")
            try:
                hit = vm.wait_marker("SEREOS_TEXT_MODE", 20)
                print(f"modo texto detectado: {hit.line}")
            except QemuError as exc:
                print(f"aviso: {exc}", file=sys.stderr)
                rc = 1
        else:
            try:
                vm.wait_marker("GUI_READY", args.timeout)
                print("escritorio listo (GUI_READY)")
            except MarkerTimeout:
                try:
                    vm.wait_marker("SEREOS_BOOT_OK", 5)
                    print("SEREOS_BOOT_OK visto, pero no GUI_READY")
                    rc = 1
                except QemuError as exc:
                    print(f"error: {exc}", file=sys.stderr)
                    rc = 1
        for seq in filter(None, args.keys.split(";")):
            keys = [k.strip() for k in seq.split(",") if k.strip()]
            vm.sendkeys(keys)
            print(f"teclas enviadas: {keys}")
        if args.text:
            vm.type_line(args.text)
            print(f"texto escrito: {args.text!r}")
        for marker in args.marker:
            hit = vm.wait_marker(marker, args.timeout)
            print(f"marcador: {hit.line}")
        if args.shot:
            path = vm.screendump(args.shot)
            print(f"captura: {path}")
        fatals = vm.fatal_markers()
        if fatals:
            print("EXCEPCION/PANICO detectado:", *fatals, sep="\n  ", file=sys.stderr)
            rc = 1
    except QemuError as exc:
        print(f"error: {exc}", file=sys.stderr)
        rc = 1
    finally:
        vm.stop()
    return rc


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
