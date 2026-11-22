#!/usr/bin/env python3
"""Scenario probe: drives the native Pac-Man app through START -> power pellet
-> deaths -> GAME_OVER, sampling kernel audio globals through QMP and recording
the mixed output through the PulseAudio null sink.

usage: python3 scenario_probe.py <tag> [nob16]
"""
import json
import os
import re
import socket
import subprocess
import sys
import time

BASE = os.path.dirname(os.path.abspath(__file__))
ISO = os.path.abspath(os.path.join(BASE, "..", "..", "sistema operativo", "sereos.iso"))
tag = sys.argv[1]
nob16 = len(sys.argv) > 2 and sys.argv[2] == "nob16"
SERIAL = os.path.join(BASE, "serial-%s.log" % tag)
QMP_SOCK = os.path.join(BASE, "qmp-%s.sock" % tag)
RAWF = os.path.join(BASE, "capture-%s.raw" % tag)
OUT = os.path.join(BASE, "scenario-%s.tsv" % tag)
for p in (SERIAL, QMP_SOCK, RAWF, OUT):
    try:
        os.unlink(p)
    except FileNotFoundError:
        pass

ADDR = {
    "audio_ready": 0x360034, "backend": 0x360030, "play_counter": 0x36002c,
    "lost": 0x360028, "queue_count": 0x36001c, "loop_sfx": 0x360018,
    "loop_playing": 0x360014, "pcspk_active": 0x360008,
    "sb16_total_plays": 0x37a148, "sb16_playing": 0x37a154, "sb16_present": 0x37a158,
    "sb16_last_rate": 0x37a15c, "sb16_dsp": 0x37a162, "sb16_base": 0x37a164,
    "g_pcm_slot": 0x35814c, "g_pcm_active": 0x15acf90,
    "g_pcm_loop": 0x15acf94, "g_pcm_chunk": 0x15acf98,
}

# ---- audio capture through PulseAudio null sink ---------------------------
env = dict(os.environ, PULSE_SINK="sereos_audit", XDG_RUNTIME_DIR="/run/user/1000")
rec = subprocess.Popen(
    ["parec", "-d", "sereos_audit.monitor", "--raw", "--rate=44100",
     "--channels=2", "--format=s16le"], stdout=open(RAWF, "wb"),
    stderr=subprocess.DEVNULL, env=env)
time.sleep(0.8)

cmd = ["qemu-system-i386", "-m", "256M", "-vga", "std", "-display", "none",
       "-boot", "d", "-cdrom", ISO, "-serial", "file:" + SERIAL,
       "-qmp", "unix:%s,server=on,wait=off" % QMP_SOCK, "-no-reboot",
       "-audiodev", "pa,id=snd", "-machine", "pcspk-audiodev=snd"]
if not nob16:
    cmd += ["-device", "sb16,audiodev=snd"]
proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
t0 = time.time()


def ts(m):
    print("[%6.2fs] %s" % (time.time() - t0, m), flush=True)


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
            raise RuntimeError("qmp")
        self.f = self.s.makefile("rwb")
        self._read()
        self.cmd("qmp_capabilities")

    def _read(self):
        line = self.f.readline()
        if not line:
            raise RuntimeError("closed")
        return json.loads(line)

    def cmd(self, name, **a):
        self.f.write((json.dumps({"execute": name, "arguments": a}) + "\n").encode())
        self.f.flush()
        while True:
            m = self._read()
            if "return" in m or "error" in m:
                return m

    def hmp(self, line):
        return self.cmd("human-monitor-command", **{"command-line": line})


def wait_serial(n, timeout=120):
    end = time.time() + timeout
    while time.time() < end:
        try:
            if n in open(SERIAL, errors="replace").read():
                return True
        except FileNotFoundError:
            pass
        if proc.poll() is not None:
            return False
        time.sleep(0.4)
    return False


def rd(q, addr, words=1):
    r = q.hmp("xp /%dxw 0x%x" % (words, addr))
    return [int(v, 16) for v in re.findall(r"0x([0-9a-fA-F]+)", r.get("return", ""))]


rows = []


def snap(q, label):
    g = rd(q, 0x360000, 16)
    s = rd(q, 0x37a140, 12)
    p1 = rd(q, 0x15acf90, 4)
    slot = rd(q, 0x35814c, 1)[0]
    def s32(v):
        return v - 0x100000000 if v & 0x80000000 else v
    r = {
        "t": round(time.time() - t0, 2), "label": label,
        "ready": g[13] & 0xFF, "backend": g[12], "plays": s32(g[11]),
        "lost": s32(g[10]), "queue": g[7], "loop_sfx": s32(g[6]),
        "loop_playing": g[5] & 0xFF, "pcspk": g[2] & 0xFF,
        "sb_present": s[6] & 0xFF, "sb_playing": s[5] & 0xFF,
        "sb_plays": s[2], "sb_rate": s[7], "sb_dsp": (s[8] >> 16) & 0xFFFF,
        "sb_base": s[9] & 0xFFFF, "slot": s32(slot), "pcm_active": s32(p1[0]),
        "pcm_loop": s32(p1[1]), "pcm_chunk": s32(p1[2]),
    }
    rows.append(r)
    print("t=%6.2f %-16s backend=%d plays=%d slot=%d pcm(active=%d loop=%d chunk=%d) "
          "sb_plays=%d sb_playing=%d loop_sfx=%d pcspk=%d queue=%d"
          % (r["t"], label, r["backend"], r["plays"], r["slot"], r["pcm_active"],
             r["pcm_loop"], r["pcm_chunk"], r["sb_plays"], r["sb_playing"],
             r["loop_sfx"], r["pcspk"], r["queue"]), flush=True)


q = None
shots = []


def shot(name):
    path = os.path.join(BASE, "shot-%s-%s.ppm" % (tag, name))
    try:
        q.hmp("screendump " + path)
        shots.append(path)
    except Exception:
        pass


try:
    ts("boot")
    assert wait_serial("GUI_READY", 150)
    q = Qmp(QMP_SOCK)
    ts("ready")
    q.hmp("sendkey f4")
    time.sleep(2.0)
    q.hmp("sendkey ret")
    time.sleep(1.2)
    q.hmp("sendkey ret")
    snap(q, "game-start")
    time.sleep(2.2)
    snap(q, "ready-done")
    ts("move left towards bottom-left power pellet")
    q.hmp("sendkey left")
    for i in range(14):
        time.sleep(0.4)
        snap(q, "left+%.1fs" % ((i + 1) * 0.4))
    shot("power")
    q.hmp("sendkey up")
    for i in range(10):
        time.sleep(0.4)
        snap(q, "up+%.1fs" % ((i + 1) * 0.4))
    shot("chase")
    # wander and die: stand still after a few moves so ghosts can catch pac
    for i in range(60):
        if i % 8 == 0:
            q.hmp("sendkey " + ["left", "up", "right", "down"][i // 8 % 4])
        time.sleep(0.4)
        snap(q, "wait+%.1fs" % ((i + 1) * 0.4))
    shot("late")
    ts("game over? screenshot")
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
    time.sleep(0.5)
    rec.terminate()
    try:
        rec.wait(timeout=5)
    except subprocess.TimeoutExpired:
        rec.kill()
    if rows:
        k = list(rows[0].keys())
        with open(OUT, "w") as f:
            f.write("\t".join(k) + "\n")
            for r in rows:
                f.write("\t".join(str(r[x]) for x in k) + "\n")
    ts("done")
