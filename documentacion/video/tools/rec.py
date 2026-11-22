"""Grabador y controlador de SereOS en QEMU (real, sin mockups).

- Arranca QEMU headless con monitor por socket UNIX y log serie.
- Un hilo captura la pantalla con `screendump` continuamente, guardando
  marca de tiempo real de cada fotograma (para reproducir a velocidad real).
- Las acciones (teclas, raton relativo, clic) usan el mismo monitor,
  serializado con un lock, de modo que nunca se pisan.
"""
import os, socket, subprocess, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
VIDEO = os.path.dirname(HERE)
OS_DIR = "/home/t1an/Descargas/sereos02/sistema operativo"
RAW = os.path.join(VIDEO, "raw")
SOCK = os.path.join(HERE, "qmon.sock")
SERIAL = os.path.join(HERE, "serial_rec.log")

KEYS = {
    "enter": "ret", "esc": "esc", "space": "spc", "up": "up", "down": "down",
    "left": "left", "right": "right", "bs": "backspace", "tab": "tab",
    "f11": "f11",
}


class Mon:
    def __init__(self):
        self.lock = threading.Lock()
        self.s = None
        self.x, self.y = 512, 392  # posición inicial del puntero tras el arranque

    def connect(self, timeout=20):
        end = time.time() + timeout
        while time.time() < end:
            if os.path.exists(SOCK):
                try:
                    s = socket.socket(socket.AF_UNIX)
                    s.connect(SOCK)
                    s.settimeout(3)
                    self.s = s
                    self._drain()
                    return
                except OSError:
                    pass
            time.sleep(0.2)
        raise RuntimeError("no hay socket del monitor de QEMU")

    def _drain(self):
        buf = b""
        end = time.time() + 3
        while time.time() < end and b"(qemu)" not in buf:
            try:
                buf += self.s.recv(65536)
            except socket.timeout:
                break
        return buf

    def cmd(self, text):
        with self.lock:
            self.s.send((text + "\n").encode())
            return self._drain()

    def key(self, name, wait=0.12):
        k = KEYS.get(name, name)
        self.cmd(f"sendkey {k}")
        time.sleep(wait)

    def type_text(self, text, wait=0.10):
        for ch in text:
            if ch == "\n":
                self.key("enter", wait)
            elif ch == " ":
                self.key("space", wait)
            else:
                self.key(ch, wait)

    def goto(self, x, y, dur=0.8):
        """Lleva el puntero a (x, y) absolutos, con movimiento suave."""
        dx, dy = x - self.x, y - self.y
        self.move_rel(dx, dy, dur)

    def move_rel(self, dx, dy, dur=0.6):
        """Movimiento relativo suave; `dur` es la duración total del gesto."""
        self.x += dx
        self.y += dy
        steps = max(1, int(max(abs(dx), abs(dy)) / 6))
        sx, sy = dx / steps, dy / steps
        acc_x = acc_y = 0.0
        t = dur / steps
        for _ in range(steps):
            acc_x += sx
            acc_y += sy
            ix, iy = int(round(acc_x)), int(round(acc_y))
            acc_x -= ix
            acc_y -= iy
            if ix or iy:
                self.cmd(f"mouse_move {ix} {iy}")
            time.sleep(t)

    def click(self, button=1, hold=0.08):
        self.cmd(f"mouse_button {button}")
        time.sleep(hold)
        self.cmd("mouse_button 0")
        time.sleep(0.12)

    def dclick(self, button=1):
        """Doble clic rápido (<350 ms) para maximizar/restaurar desde la barra de título."""
        self.cmd(f"mouse_button {button}")
        time.sleep(0.05)
        self.cmd("mouse_button 0")
        time.sleep(0.06)
        self.cmd(f"mouse_button {button}")
        time.sleep(0.05)
        self.cmd("mouse_button 0")
        time.sleep(0.12)

    def dump(self, path):
        self.cmd(f"screendump {path}")


class Recorder(threading.Thread):
    """Captura continua de fotogramas con marcas de tiempo reales."""

    def __init__(self, mon, prefix="f"):
        super().__init__(daemon=True)
        self.mon = mon
        self.prefix = prefix
        self.frames = []  # (t, path)
        self.running = False
        self.n = 0
        self.t0 = None
        os.makedirs(RAW, exist_ok=True)

    def run(self):
        self.running = True
        while self.running:
            path = os.path.join(RAW, f"{self.prefix}{self.n:06d}.ppm")
            t = time.monotonic()
            self.mon.dump(path)
            if os.path.exists(path) and os.path.getsize(path) > 0:
                self.frames.append((t, path))
                self.n += 1
            # limita a ~25 fps: el tiempo real queda registrado en cada fotograma
            time.sleep(max(0.0, 0.04 - (time.monotonic() - t)))

    def stop(self):
        self.running = False
        self.join(timeout=5)


def start_qemu():
    """Arranca QEMU (KVM) con el ISO real; devuelve el proceso."""
    for p in (SOCK,):
        if os.path.exists(p):
            os.remove(p)
    if os.path.exists(SERIAL):
        os.remove(SERIAL)
    kvm = ["-enable-kvm", "-cpu", "host"] if os.access("/dev/kvm", os.W_OK) else []
    cmd = ["qemu-system-i386", *kvm, "-m", "256M", "-vga", "std",
           "-serial", f"file:{SERIAL}", "-rtc", "base=localtime",
           "-display", "none", "-monitor", f"unix:{SOCK},server,nowait",
           "-cdrom", os.path.join(OS_DIR, "sereos.iso")]
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def serial_text():
    try:
        return open(SERIAL, errors="ignore").read()
    except OSError:
        return ""


def wait_serial(marker, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        if marker in serial_text():
            return True
        time.sleep(0.1)
    return False
