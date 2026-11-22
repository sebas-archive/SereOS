#!/usr/bin/env python3
"""qmp_peek.py - read guest RAM through QEMU QMP (read-only) and/or send keys.

Used by the SereOS verification to observe the audio driver state at runtime
without touching the guest.  Addresses are resolved beforehand with nm on
sereos.bin (the script can do it too with --bin).

Examples:
  qmp_peek.py --sock qmp.sock --bin sereos.bin \
      --symbols g_pcm_chunk,g_pcm_active,sb16_total_plays --count 5 --interval 1
  qmp_peek.py --sock qmp.sock --keys "0:f4" "2000:ret" ...

Reads use the human-monitor-command 'xp /<n>xb <addr>' (big-endian dump of
bytes, same layout as the guest memory).  Nothing in the guest is modified.
"""
import json
import socket
import subprocess
import sys
import time


class QMP:
    def __init__(self, sock_path):
        self.s = socket.socket(socket.AF_UNIX)
        self.s.connect(sock_path)
        self.f = self.s.makefile("rwb", 0)
        self.f.readline()  # greeting
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

    def read_bytes(self, addr, n=8):
        r = self.hmp("xp /%dxb 0x%x" % (n, addr))
        if not r or "return" not in r:
            return None
        out = []
        for tok in r["return"].split():
            if tok.startswith("0x"):
                out.append(int(tok, 16))
        return out

    def close(self):
        try:
            self.f.close()
            self.s.close()
        except Exception:
            pass


def symbol_addrs(bin_path, names):
    """Resolve symbol addresses from `nm -n` of the ELF binary."""
    out = {}
    res = subprocess.run(["nm", "-n", bin_path], capture_output=True, text=True)
    want = set(names)
    for line in res.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[2] in want:
            out[parts[2]] = int(parts[0], 16)
    return out


def main():
    argv = sys.argv[1:]
    sock = None
    bin_path = None
    syms = []
    count = 1
    interval = 1.0
    keys = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--sock":
            sock = argv[i + 1]; i += 2
        elif a == "--bin":
            bin_path = argv[i + 1]; i += 2
        elif a == "--symbols":
            syms = argv[i + 1].split(","); i += 2
        elif a == "--count":
            count = int(argv[i + 1]); i += 2
        elif a == "--interval":
            interval = float(argv[i + 1]); i += 2
        else:
            keys.append(a); i += 1

    addrs = {}
    if bin_path and syms:
        addrs = symbol_addrs(bin_path, syms)
        for name in syms:
            print("SYM %-28s 0x%x" % (name, addrs.get(name, 0)),
                  flush=True)

    q = QMP(sock)
    # send keys ("delay_ms:key")
    for k in keys:
        delay, key = k.split(":", 1)
        if float(delay) > 0:
            time.sleep(float(delay) / 1000.0)
        q.sendkey(key)
        print("KEY %.3f %s" % (time.time(), key), flush=True)

    for c in range(count):
        for name in syms:
            addr = addrs.get(name)
            if not addr:
                continue
            data = q.read_bytes(addr, 4)
            if data is None:
                print("READFAIL %s" % name, flush=True)
                continue
            le = data[0] | (data[1] << 8) | (data[2] << 16) | (data[3] << 24)
            be = (data[0] << 24) | (data[1] << 16) | (data[2] << 8) | data[3]
            print("VAL t=%.3f %-28s le=%d be=%d bytes=%s"
                  % (time.time(), name, le, be,
                     ",".join("%02x" % b for b in data)), flush=True)
        if c + 1 < count:
            time.sleep(interval)
    q.close()


if __name__ == "__main__":
    main()
