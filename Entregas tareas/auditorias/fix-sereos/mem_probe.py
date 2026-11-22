#!/usr/bin/env python3
"""Runtime memory probe: read SereOS kernel globals through QMP (xp) while the
native Pac-Man app plays, to prove driver state, play counts and the SB16
chunking state machine. Read-only: no guest writes.
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
SERIAL = os.path.join(BASE, "serial-memprobe.log")
QMP_SOCK = os.path.join(BASE, "qmp-memprobe.sock")
OUT = os.path.join(BASE, "memprobe-history.txt")
for p in (SERIAL, QMP_SOCK, OUT):
    try:
        os.unlink(p)
    except FileNotFoundError:
        pass

# addresses from `nm -n sereos.bin`
ADDR = {
    # audio/audio.c
    "audio_ready": 0x360034, "backend": 0x360030, "play_counter": 0x36002c,
    "lost_requests": 0x360028, "queue_count": 0x36001c, "queue_head": 0x360020,
    "loop_playing": 0x360014, "loop_sfx": 0x360018,
    "pcspk_active": 0x360008, "pcspk_is_loop": 0x360004,
    # drivers/sb16.c
    "sb16_total_plays": 0x37a148, "sb16_duration_ticks": 0x37a14c,
    "sb16_start_tick": 0x37a150, "sb16_playing": 0x37a154,
    "sb16_present": 0x37a158, "sb16_last_rate": 0x37a15c,
    "sb16_dsp_version": 0x37a162, "sb16_base_port": 0x37a164,
    # platform/sereos platform_sereos.c
    "g_pcm_slot": 0x35814c, "g_pcm_active": 0x15acf90,
    "g_pcm_loop": 0x15acf94, "g_pcm_chunk": 0x15acf98,
    # audio bounce buffer (for the DMA target)
    "audio_dma": 0x370000,
}

proc = subprocess.Popen([
    "qemu-system-i386", "-m", "256M", "-vga", "std", "-display", "none",
    "-boot", "d", "-cdrom", ISO, "-serial", "file:" + SERIAL,
    "-qmp", "unix:%s,server=on,wait=off" % QMP_SOCK, "-no-reboot",
    "-audiodev", "pa,id=snd", "-device", "sb16,audiodev=snd",
    "-machine", "pcspk-audiodev=snd",
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
   env=dict(os.environ, PULSE_SINK="sereos_audit", XDG_RUNTIME_DIR="/run/user/1000"))
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
            m = self._read()
            if "return" in m or "error" in m:
                return m

    def hmp(self, line):
        return self.cmd("human-monitor-command", **{"command-line": line})


def wait_serial(needle, timeout=120.0):
    end = time.time() + timeout
    while time.time() < end:
        try:
            if needle in open(SERIAL, errors="replace").read():
                return True
        except FileNotFoundError:
            pass
        if proc.poll() is not None:
            return False
        time.sleep(0.4)
    return False


def rd(q, addr, words=1):
    r = q.hmp("xp /%dxw 0x%x" % (words, addr))
    txt = r.get("return", "")
    vals = []
    for line in txt.splitlines():
        vals += re.findall(r"0x([0-9a-fA-F]+)", line)
    return [int(v, 16) for v in vals]


def snap(q, label):
    g = rd(q, 0x360000, 16)      # audio.c block
    s = rd(q, 0x37a140, 12)      # sb16 block
    p1 = rd(q, 0x15acf90, 4)     # g_pcm_active/loop/chunk
    slot = rd(q, 0x35814c, 1)[0]
    # pcspk_off_tick @0x350000, pcspk_is_loop @+4, pcspk_active @+8,
    # loop_playing @+0x14, loop_sfx @+0x18, queue_count @+0x1c,
    # queue_head @+0x20, lost @+0x28, play_counter @+0x2c,
    # backend @+0x30, audio_ready @+0x34
    def s32(v):
        return v - 0x100000000 if v & 0x80000000 else v
    rec = {
        "label": label, "t": round(time.time() - t0, 2),
        "audio_ready": g[13] & 0xFF, "backend": g[12], "play_counter": s32(g[11]),
        "lost_requests": s32(g[10]), "queue_count": g[7], "loop_sfx": s32(g[6]),
        "loop_playing": g[5] & 0xFF, "pcspk_active": g[2] & 0xFF,
        "sb16_present": s[6] & 0xFF, "sb16_playing": s[5] & 0xFF,
        "sb16_total_plays": s[2] & 0xFFFFFFFF,
        "sb16_last_rate": s[7] & 0xFFFFFFFF,
        "sb16_dsp_version": (s[8] >> 16) & 0xFFFF,
        "sb16_base_port": s[9] & 0xFFFF,
        "g_pcm_slot": slot, "g_pcm_active": p1[0], "g_pcm_loop": p1[1],
        "g_pcm_chunk": p1[2],
    }
    line = ("t=%(t)6.2f %(label)-18s backend=%(backend)d ready=%(audio_ready)d "
            "plays=%(play_counter)d lost=%(lost_requests)d playing=%(sb16_playing)d "
            "sb_plays=%(sb16_total_plays)d rate=%(sb16_last_rate)d dsp=0x%(sb16_dsp_version)04x "
            "base=0x%(sb16_base_port)x pcm(slot=%(g_pcm_slot)d active=%(g_pcm_active)d "
            "loop=%(g_pcm_loop)d chunk=%(g_pcm_chunk)d) loop_sfx=%(loop_sfx)d "
            "queue=%(queue_count)d") % rec
    print(line, flush=True)
    st.append(rec)


st = []
q = None
try:
    ts("booting")
    assert wait_serial("GUI_READY", 150), "no GUI_READY"
    q = Qmp(QMP_SOCK)
    ts("QMP up")
    ts("press F4 (open Pac-Man app)")
    q.hmp("sendkey f4")
    time.sleep(2.0)
    snap(q, "game-open")
    ts("Enter (attract->menu)")
    q.hmp("sendkey ret")
    time.sleep(1.2)
    snap(q, "menu")
    ts("Enter (start game -> START clip)")
    q.hmp("sendkey ret")
    # dense sampling through the 4.5 s START hold; chunk0 lasts 2.972 s,
    # chunk1 (13908 samples) is the one that crosses the 64 KiB DMA boundary
    for i in range(40):          # 40 * 0.15 s = 6 s
        time.sleep(0.15)
        snap(q, "start+%.2fs" % ((i + 1) * 0.15))
    for i in range(30):          # press arrows, sample waka/siren
        q.hmp("sendkey " + ["right", "down", "left", "up"][i % 4])
        time.sleep(0.45)
        snap(q, "move+%.2fs" % ((i + 1) * 0.45))
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
    with open(OUT, "w") as f:
        k = list(st[0].keys()) if st else []
        f.write("\t".join(k) + "\n")
        for r in st:
            f.write("\t".join(str(r[x]) for x in k) + "\n")
    ts("done, history in " + OUT)
