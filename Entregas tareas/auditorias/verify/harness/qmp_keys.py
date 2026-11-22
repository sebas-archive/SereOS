#!/usr/bin/env python3
"""Send a scripted sequence of key presses to QEMU via QMP.
Usage: qmp_keys.py <qmp_sock> <wait_s> <keyspec...>
keyspec: "<delay_ms>:<key>" e.g. 15000:f4 1000:ret
Uses human-monitor-command sendkey (works for guest i8042).
"""
import socket, json, sys, time

sock_path = sys.argv[1]
wait_s = float(sys.argv[2])
keys = sys.argv[3:]

s = socket.socket(socket.AF_UNIX)
s.connect(sock_path)
f = s.makefile('rwb', 0)
f.readline()  # greeting
def cmd(d):
    f.write((json.dumps(d) + "\n").encode())
    while True:
        line = f.readline()
        if not line:
            return None
        m = json.loads(line)
        if 'return' in m or 'error' in m:
            return m
cmd({"execute": "qmp_capabilities"})
time.sleep(wait_s)
for k in keys:
    delay, key = k.split(':', 1)
    time.sleep(float(delay) / 1000.0)
    r = cmd({"execute": "human-monitor-command",
             "arguments": {"command-line": "sendkey %s" % key}})
    print("%.3f sendkey %s -> %s" % (time.time(), key, "ok" if r and 'return' in r else r))
    sys.stdout.flush()
f.close(); s.close()
