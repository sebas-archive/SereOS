#!/usr/bin/env python3
import socket, struct, subprocess, time, zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ISO=ROOT/"sistema operativo"/"sereos.iso"
OUT=ROOT/"docs/screenshots/raw/power-fix"; OUT.mkdir(parents=True, exist_ok=True)
RUND=Path(__file__).resolve().parent/"iso-run5"; RUND.mkdir(exist_ok=True)
MON,SER=RUND/"monitor.sock",RUND/"serial.log"
for p in (MON,SER):
    try:p.unlink()
    except FileNotFoundError:pass
proc=subprocess.Popen(["qemu-system-i386","-display","none","-m","256M","-vga","std",
 "-cdrom",str(ISO),"-monitor",f"unix:{MON},server,nowait","-serial",f"file:{SER}",
 "-rtc","base=localtime","-no-reboot"])
def sr():
    try:return SER.read_text(errors="replace")
    except FileNotFoundError:return ""
end=time.time()+90
while "GUI_READY" not in sr() and time.time()<end: time.sleep(0.1)
time.sleep(0.4)
def conn():
    for _ in range(300):
        try:
            s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);s.connect(str(MON));s.settimeout(0.3);return s
        except OSError:time.sleep(0.1)
s=conn();time.sleep(0.2)
try:
    while True:s.recv(65536)
except socket.timeout:pass
def cmd(c,st):
    s.sendall((c+"\n").encode());time.sleep(st)
    try:
        while True:s.recv(65536)
    except socket.timeout:pass
cmd("mouse_move -415 -366",0.12);cmd("mouse_button 1",0.06);cmd("mouse_button 0",0.35)
cmd("mouse_move 53 273",0.12)
t0=time.time();cmd("mouse_button 1",0.05);cmd("mouse_button 0",0.01)
time.sleep(0.45)
try: s.sendall((f"screendump {RUND/'a.ppm'}\n").encode())
except BrokenPipeError: pass
time.sleep(0.25)
try: s.sendall((f"screendump {RUND/'b.ppm'}\n").encode())
except BrokenPipeError: pass
lat=time.time()-t0
try: code=proc.wait(timeout=25)
except subprocess.TimeoutExpired: proc.kill();code=-9
# esperar flush de ficheros
time.sleep(0.3)
shots=[p for p in (RUND/'a.ppm',RUND/'b.ppm') if p.exists() and p.stat().st_size>1000]
def conv(src,dst):
    with open(src,'rb') as f:
        assert f.readline().strip()==b'P6'
        line=f.readline()
        while line.startswith(b'#'):line=f.readline()
        w,h=map(int,line.split());f.readline();data=f.read()
    def ch(t,d):return struct.pack(">I",len(d))+t+d+struct.pack(">I",zlib.crc32(t+d)&0xffffffff)
    png=b"\x89PNG\r\n\x1a\n"+ch(b"IHDR",struct.pack(">IIBBBBB",w,h,8,2,0,0,0))
    raw=b"".join(b"\x00"+data[y*w*3:(y+1)*w*3] for y in range(h))
    png+=ch(b"IDAT",zlib.compress(raw,6))+ch(b"IEND",b"")
    Path(dst).write_bytes(png); print("PNG",dst,w,h)
print(f"QEMU_EXIT={code} lat={lat:.2f}s shots={[p.name for p in shots]}")
print("SERIAL:",[l for l in sr().splitlines() if "POWEROFF" in l or "acpi" in l or "SHUTDOWN" in l])
if shots: conv(shots[-1], OUT/"apagando.png")
