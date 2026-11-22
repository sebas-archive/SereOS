#!/usr/bin/env python3
"""SereOS native audio audit: headless QEMU boot + keyboard automation + WAV capture.

Boots sistema operativo/sereos.iso with an SB16 (and pcspk routed to the same
wav audiodev), opens the Pac-Man app through the desktop (F4), starts a game
(Enter, Enter), presses arrows to eat dots, and screendumps the guest.
All artefacts land next to this script.
"""
import json
import os
import socket
import subprocess
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
ISO = os.path.abspath(os.path.join(BASE, "..", "..", "sistema operativo", "sereos.iso"))
SERIAL = os.path.join(BASE, "serial.log")
WAV = os.path.join(BASE, "capture.wav")
QMP_SOCK = os.path.join(BASE, "qmp.sock")
QEMU_LOG = os.path.join(BASE, "qemu.log")
tag = sys.argv[1] if len(sys.argv) > 1 else "sb16"
if tag != "sb16":
    SERIAL = os.path.join(BASE, "serial-%s.log" % tag)
    WAV = os.path.join(BASE, "capture-%s.wav" % tag)
    QMP_SOCK = os.path.join(BASE, "qmp-%s.sock" % tag)
    QEMU_LOG = os.path.join(BASE, "qemu-%s.log" % tag)

for p in (SERIAL, WAV, QMP_SOCK, QEMU_LOG):
    try:
        os.unlink(p)
    except FileNotFoundError:
        pass

cmd = [
    "qemu-system-i386",
    "-m", "256M",
    "-vga", "std",
    "-display", "none",
    "-boot", "d",
    "-cdrom", ISO,
    "-serial", "file:" + SERIAL,
    "-audiodev", os.environ.get("AUDIODEV", "wav,id=snd,path=" + WAV),
    "-qmp", "unix:%s,server=on,wait=off" % QMP_SOCK,
    "-no-reboot",
]
if tag != "pcspk":
    cmd += ["-device", "sb16,audiodev=snd"]
if tag != "sb16only":
    cmd += ["-machine", "pcspk-audiodev=snd"]
SKIP = tag.startswith("boot")
INITTEST = tag == "inittest"
log = open(QEMU_LOG, "wb")
t_start = time.time()
proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)


def ts(msg):
    print("[%7.2fs] %s" % (time.time() - t_start, msg), flush=True)


def serial_text():
    try:
        with open(SERIAL, "r", errors="replace") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def wait_serial(needle, timeout=120.0):
    end = time.time() + timeout
    while time.time() < end:
        if needle in serial_text():
            return True
        if proc.poll() is not None:
            return False
        time.sleep(0.5)
    return False


# ---- QMP client -----------------------------------------------------------
class Qmp:
    def __init__(self, path, timeout=30.0):
        end = time.time() + timeout
        while time.time() < end:
            try:
                self.s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self.s.connect(path)
                break
            except (FileNotFoundError, ConnectionRefusedError):
                time.sleep(0.2)
        else:
            raise RuntimeError("QMP socket not ready")
        self.f = self.s.makefile("rwb")
        self._read()
        self.cmd("qmp_capabilities")

    def _read(self):
        line = self.f.readline()
        if not line:
            raise RuntimeError("QMP closed")
        return json.loads(line)

    def cmd(self, name, **args):
        self.f.write((json.dumps({"execute": name, "arguments": args}) + "\n").encode())
        self.f.flush()
        while True:
            msg = self._read()
            if "return" in msg or "error" in msg:
                return msg

    def hmp(self, line):
        return self.cmd("human-monitor-command", **{"command-line": line})


q = None
shots = []


def shot(name):
    path = os.path.join(BASE, "shot-%s-%s.ppm" % (tag, name))
    try:
        q.hmp("screendump " + path)
        shots.append(path)
        ts("screendump " + name)
    except Exception as e:  # noqa: BLE001
        ts("screendump failed: %r" % (e,))


def key(k, wait=0.15):
    q.hmp("sendkey " + k)
    time.sleep(wait)


try:
    ts("qemu started, waiting for GUI_READY")
    ok = wait_serial("GUI_READY", 150)
    ts("GUI_READY=%s" % ok)
    if not ok:
        raise SystemExit("boot failed")
    q = Qmp(QMP_SOCK)
    ts("QMP connected")

    if SKIP:
        raise SystemExit("boot-only mode, no interaction")
    if INITTEST:
        key("f3", 5.0)
        shot("inittest-monitor")
        raise SystemExit("init-only mode")
    # monitor app shows audio backend (calls audio_init)
    key("f3", 2.0)
    shot("02-monitor")
    key("alt-w", 1.0)

    key("f4", 3.0)
    shot("03-game-attract")
    key("ret", 1.2)
    shot("04-menu")
    key("ret", 1.0)
    ts("game started (second Enter)")
    shot("05-playing-start")
    # let the START clip / siren develop
    time.sleep(3.0)
    shot("06-playing-3s")

    # move around to eat dots: alternate directions, 0.35 s per press
    dirs = ["right", "right", "down", "down", "left", "left", "up", "up"]
    for i in range(56):
        key(dirs[i % len(dirs)], 0.35)
    shot("07-playing-moved")
    time.sleep(2.5)
    shot("08-playing-end")
    ts("capture done, quitting")
finally:
    if q is not None:
        try:
            q.hmp("quit")
        except Exception:
            pass
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
    log.close()
    ts("qemu exit code %r" % proc.returncode)

print("wav exists:", os.path.exists(WAV), os.path.getsize(WAV) if os.path.exists(WAV) else 0)
print("shots:", shots)
