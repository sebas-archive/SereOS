#!/usr/bin/env python3
"""capture_power.py - captura la pantalla nueva de apagado en la ISO real.

Abre el menu del logo con el raton (PS/2 relativo), pulsa "Apagar" y, para no
depender de la latencia de lectura del puerto serie, pausa la VM con el
monitor de QEMU durante la animacion, captura y la reanuda. Al final verifica
que QEMU termina solo por ACPI. Evidencia: docs/screenshots/raw/power-fix/
"""
import socket, struct, subprocess, sys, time, zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ISO = ROOT / "sistema operativo" / "sereos.iso"
OUT = ROOT / "docs" / "screenshots" / "raw" / "power-fix"
RUND = Path(__file__).resolve().parent / "iso-run2"
OUT.mkdir(parents=True, exist_ok=True); RUND.mkdir(parents=True, exist_ok=True)
MON, SER = RUND / "monitor.sock", RUND / "serial.log"
for p in (MON, SER):
    try: p.unlink()
    except FileNotFoundError: pass

proc = subprocess.Popen(["qemu-system-i386", "-name", "sereos-powerfix",
    "-display", "none", "-m", "256M", "-vga", "std", "-cdrom", str(ISO),
    "-monitor", f"unix:{MON},server,nowait", "-serial", f"file:{SER}",
    "-rtc", "base=localtime", "-no-reboot"])

def serial():
    try: return SER.read_text(errors="replace")
    except FileNotFoundError: return ""

def wait_serial(marker, timeout=90):
    end = time.time() + timeout
    while time.time() < end:
        if proc.poll() is not None: raise SystemExit(f"QEMU murio antes de {marker}")
        if marker in serial(): return
        time.sleep(0.2)
    raise SystemExit(f"timeout esperando {marker}")

def connect():
    for _ in range(300):
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect(str(MON)); s.settimeout(0.3); return s
        except OSError: time.sleep(0.1)
    raise SystemExit("sin monitor")

def drain(s, t=0.15):
    end = time.time() + t
    while time.time() < end:
        try:
            if not s.recv(65536): break
            end = time.time() + 0.05
        except socket.timeout: break

def cmd(s, c, settle=0.05):
    s.sendall((c + "\n").encode()); time.sleep(settle); drain(s)

def ppm_to_png(src, dst):
    with open(src, "rb") as f:
        assert f.readline().strip() == b"P6"
        line = f.readline()
        while line.startswith(b"#"): line = f.readline()
        w, h = map(int, line.split()); f.readline(); data = f.read()
    assert len(data) == w * h * 3, (len(data), w, h)
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    raw = b"".join(b"\x00" + data[y * w * 3:(y + 1) * w * 3] for y in range(h))
    png += chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b"")
    Path(dst).write_bytes(png); return w, h

def snap(s, name):
    """pausa la VM, captura y la reanuda (best effort)"""
    path = RUND / name
    try:
        s.sendall(b"stop\n"); time.sleep(0.1); print("stop ->", drain(s, 0.1)[:200])
        s.sendall((f"screendump {path}\n").encode()); time.sleep(0.2)
        print("dump ->", drain(s, 0.15)[:200], "exists=", path.exists())
        end = time.time() + 1.5
        while time.time() < end:
            if path.exists() and path.stat().st_size > 1000:
                time.sleep(0.08); break
            time.sleep(0.02)
        s.sendall(b"cont\n"); time.sleep(0.06); drain(s, 0.05)
    except BrokenPipeError:
        return None
    return path if path.exists() and path.stat().st_size > 1000 else None

wait_serial("GUI_READY")
time.sleep(0.5)
s = connect(); drain(s, 0.6)
# 1) menu del logo (cursor parte del centro 512,384)
cmd(s, "mouse_move -415 -366", 0.12)
cmd(s, "mouse_button 1", 0.06); cmd(s, "mouse_button 0", 0.3)
snap(s, "menu.ppm")
# 2) bajar al item "Apagar" (150,291) y pulsarlo
cmd(s, "mouse_move 53 273", 0.12)
t_click = time.time()
cmd(s, "mouse_button 1", 0.05); cmd(s, "mouse_button 0", 0.02)
# 3) pausar durante la animacion (sin fundido) y capturar
time.sleep(0.34)
shot_a = snap(s, "apagando_a.ppm")
time.sleep(0.18)
shot_b = snap(s, "apagando_b.ppm")
# 4) QEMU debe apagarse solo por ACPI
try:
    code = proc.wait(timeout=30)
except subprocess.TimeoutExpired:
    proc.kill(); code = -9
s.close()
print(f"QEMU_EXIT={code} (latencia tras clic: {time.time()-t_click:.2f}s)")
print("--- SERIAL (tail) ---")
print("\n".join(serial().splitlines()[-4:]))
shots = [p for p in (shot_a, shot_b) if p is not None]
for name, src in (("menu", RUND / "menu.ppm"), ("apagando", shots[-1] if shots else None)):
    if src is not None and src.exists():
        w, h = ppm_to_png(src, OUT / f"{name}.png")
        print(f"captura {OUT/(name+'.png')} ({w}x{h}) desde {src.name}")
print("CAPTURA_OK" if shots else "CAPTURA_FALLIDA")
sys.exit(0 if code == 0 and shots else 1)
