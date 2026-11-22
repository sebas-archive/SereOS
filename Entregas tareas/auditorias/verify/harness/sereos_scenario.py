#!/usr/bin/env python3
"""sereos_scenario.py - drive the SereOS Pac-Man game in QEMU via QMP and
sample audio-driver globals from guest RAM (read-only).

Timeline: wait for desktop, F4 opens the game app, two Enters (menu -> start),
then periodic arrow keys + periodic RAM sampling of the requested symbols.

Output: TSV-ish lines on stdout:
  SYM <name> 0xADDR
  VAL <t> <name> <le> <bytes...>
  KEY <t> <key>
  SERIAL? (serial is captured separately by the caller with -serial file:)

Symbols are resolved with nm on the ELF binary (sereos.bin).
"""
import argparse
import json
import socket
import subprocess
import sys
import time


class QMP:
    def __init__(self, path):
        self.s = socket.socket(socket.AF_UNIX)
        self.s.connect(path)
        self.f = self.s.makefile("rwb", 0)
        self.f.readline()
        self.cmd({"execute": "qmp_capabilities"})

    def cmd(self, d):
        self.f.write((json.dumps(d) + "\n").encode())
        while True:
            line = self.f.readline()
            if not line:
                return None
            m = json.loads(line)
            if "return" in m or "error" in m:
                return m

    def hmp(self, line):
        return self.cmd({"execute": "human-monitor-command",
                         "arguments": {"command-line": line}})

    def sendkey(self, key):
        return self.hmp("sendkey %s" % key)

    def read_bytes(self, addr, n):
        r = self.hmp("xp /%dxb 0x%x" % (n, addr))
        if not r or "return" not in r:
            return None
        return [int(t, 16) for t in r["return"].split() if t.startswith("0x")]

    def close(self):
        try:
            self.f.close(); self.s.close()
        except Exception:
            pass


def sym_addrs(bin_path, names):
    out = {}
    try:
        res = subprocess.run(["nm", "-n", bin_path], capture_output=True, text=True)
    except FileNotFoundError:
        return out
    want = set(names)
    for line in res.stdout.splitlines():
        p = line.split()
        if len(p) >= 3 and p[2] in want:
            out[p[2]] = int(p[0], 16)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sock", required=True)
    ap.add_argument("--bin", required=True)
    ap.add_argument("--symbols", default="")
    ap.add_argument("--boot-wait", type=float, default=14.0)
    ap.add_argument("--total", type=float, default=50.0)
    ap.add_argument("--interval", type=float, default=0.5)
    args = ap.parse_args()

    names = [n for n in args.symbols.split(",") if n]
    addrs = sym_addrs(args.bin, names)
    for n in names:
        print("SYM %s 0x%x" % (n, addrs.get(n, 0)), flush=True)

    q = QMP(args.sock)
    t0 = time.time()

    def at(t):
        d = t0 + t - time.time()
        if d > 0:
            time.sleep(d)

    # boot -> open game -> start game
    at(args.boot_wait)
    q.sendkey("f4"); print("KEY f4", flush=True)
    at(args.boot_wait + 2.0)
    q.sendkey("ret"); print("KEY ret", flush=True)
    at(args.boot_wait + 4.5)
    q.sendkey("ret"); print("KEY ret", flush=True)

    # play: move occasionally, sample globals every interval
    moves = [(8.0, "Right"), (10.0, "Right"), (12.0, "Up"), (14.0, "Left"),
             (16.0, "Down"), (18.0, "Right"), (20.0, "Right"), (22.0, "Up"),
             (24.0, "Left"), (26.0, "Down"), (28.0, "Right")]
    mi = 0
    next_move = args.boot_wait + 6.0
    while time.time() - t0 < args.total:
        now = time.time() - t0
        if mi < len(moves) and now >= moves[mi][0] + args.boot_wait - 6.0:
            q.sendkey(moves[mi][1])
            print("KEY %s t=%.2f" % (moves[mi][1], now), flush=True)
            mi += 1
        for n in names:
            a = addrs.get(n)
            if not a:
                continue
            data = q.read_bytes(a, 4)
            if data and len(data) == 4:
                le = data[0] | data[1] << 8 | data[2] << 16 | data[3] << 24
                print("VAL t=%.2f %s %d %02x%02x%02x%02x"
                      % (now, n, le, data[0], data[1], data[2], data[3]),
                      flush=True)
        time.sleep(args.interval)
    q.close()


if __name__ == "__main__":
    main()
