#!/usr/bin/env python3
import os, socket, subprocess, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
ISO = ROOT/"sistema operativo"/"sereos.iso"
RUND = Path(__file__).resolve().parent/"iso-run3"; RUND.mkdir(exist_ok=True)
OUT = ROOT/"docs"/"screenshots"/"raw"/"power-fix"; OUT.mkdir(parents=True, exist_ok=True)
MON=RUND/"monitor.sock"; SER=RUND/"serial.log"
for p in (MON,SER):
    try: p.unlink()
    except FileNotFoundError: pass
proc = subprocess.Popen(["qemu-system-i386","-display","none","-m","256M","-vga","std",
  "-cdrom",str(ISO),"-monitor",f"unix:{MON},server,nowait","-serial",f"file:{SER}",
  "-rtc","base=localtime","-no-reboot"])
def wait_serial(m,timeout=90):
    end=time.time()+timeout
    while time.time()<end:
        try:
            if m in SER.read_text(errors="replace"): return
        except FileNotFoundError: pass
        time.sleep(0.2)
    raise SystemExit("timeout "+m)
def connect():
    for _ in range(300):
        try:
            s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM); s.connect(str(MON)); s.settimeout(0.4); return s
        except OSError: time.sleep(0.1)
    raise SystemExit("no monitor")
def drain(s,t=0.2):
    end=time.time()+t
    while time.time()<end:
        try:
            if not s.recv(65536): break
            end=time.time()+0.06
        except socket.timeout: break
def hmp(s,c,st=0.06):
    s.sendall((c+"\n").encode()); time.sleep(st); drain(s)
wait_serial("GUI_READY"); time.sleep(0.4)
s=connect(); drain(s,0.8)
hmp(s,"mouse_move -415 -366"); hmp(s,"mouse_button 1",0.05); hmp(s,"mouse_button 0",0.25)
hmp(s,"mouse_move 53 273"); time.sleep(0.1)
# captura previa para ver posicion del cursor
hmp(s,f"screendump {RUND/'pre.ppm'}",0.2)
t0=time.time()
hmp(s,"mouse_button 1",0.04); hmp(s,"mouse_button 0",0.02)
# intenta capturar lo antes posible y registra cuando muere QEMU
for i,delay in enumerate((0.05,0.2,0.2,0.2,0.2)):
    time.sleep(delay)
    if proc.poll() is not None:
        print(f"QEMU murio a t+{time.time()-t0:.3f}s (antes de captura {i})")
        break
    try:
        hmp(s,f"screendump {RUND/f'shot{i}.ppm'}",0.12)
        print(f"captura {i} a t+{time.time()-t0:.3f}s")
    except BrokenPipeError:
        print(f"pipe roto en captura {i} a t+{time.time()-t0:.3f}s")
        break
try: code=proc.wait(timeout=30)
except subprocess.TimeoutExpired:
    proc.kill(); code=-9
print("QEMU_EXIT=",code,"latencia_total=%.3f"%(time.time()-t0))
print("SERIAL tail:", SER.read_text(errors='replace').splitlines()[-3:])
