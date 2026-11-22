#!/usr/bin/env python3
"""hmp.py - cliente HMP minimo para el QEMU de la prueba de apagado."""
import socket, sys, time

def connect(path, tries=100):
    last = None
    for _ in range(tries):
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect(path)
            s.settimeout(0.4)
            return s
        except OSError as e:
            last = e
            time.sleep(0.1)
    raise SystemExit(f"no pude conectar al monitor: {last}")

def drain(s, timeout=0.5):
    end = time.time() + timeout
    out = b""
    while time.time() < end:
        try:
            data = s.recv(65536)
            if not data:
                break
            out += data
            end = time.time() + 0.15
        except socket.timeout:
            break
    return out.decode("utf-8", "replace")

sock, *cmds = sys.argv[1:]
s = connect(sock)
drain(s, 0.6)
for cmd in cmds:
    s.sendall((cmd + "\n").encode())
    time.sleep(0.15)
    print(f"$ {cmd}\n{drain(s, 0.5).strip()}")
s.close()
