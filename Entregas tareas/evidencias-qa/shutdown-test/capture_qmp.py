#!/usr/bin/env python3
"""captura unica (QMP) de la pantalla nueva de apagado + salida ACPI"""
import json, socket, struct, subprocess, time, zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ISO=ROOT/"sistema operativo"/"sereos.iso"
OUT=ROOT/"docs/screenshots/raw/power-fix"; OUT.mkdir(parents=True, exist_ok=True)
RUND=Path(__file__).resolve().parent/"iso-run7"; RUND.mkdir(exist_ok=True)
MON,QMP,SER=RUND/"monitor.sock",RUND/"qmp.sock",RUND/"serial.log"
for p in (MON,QMP,SER):
    try:p.unlink()
    except FileNotFoundError:pass
proc=subprocess.Popen(["qemu-system-i386","-display","none","-m","256M","-vga","std",
 "-cdrom",str(ISO),"-monitor",f"unix:{MON},server,nowait","-qmp",f"unix:{QMP},server,nowait",
 "-serial",f"file:{SER}","-no-reboot"])
def ser():
    try:return SER.read_text(errors="replace")
    except FileNotFoundError:return ""
end=time.time()+90
while "GUI_READY" not in ser() and time.time()<end: time.sleep(0.1)
time.sleep(0.4)
s=None
for _ in range(300):
    try: s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);s.connect(str(QMP));break
    except OSError: time.sleep(0.1)
s.settimeout(1.0)
f=s.makefile("rwb")
def rd():
    return json.loads(f.readline())
rd()  # greeting
def ex(cmd,args=None):
    d={"execute":cmd}
    if args: d["arguments"]=args
    f.write((json.dumps(d)+"\n").encode()); f.flush()
    while True:
        r=rd()
        if "return" in r or "error" in r: return r
ex("qmp_capabilities")
def rel(dx,dy):
    ex("input-send-event",{"events":[{"type":"rel","data":{"axis":"x","value":dx}},
                                      {"type":"rel","data":{"axis":"y","value":dy}}]})
def btn(down):
    ex("input-send-event",{"events":[{"type":"btn","data":{"down":down,"button":"left"}}]})
rel(-415,-366); time.sleep(0.12); btn(True); time.sleep(0.05); btn(False); time.sleep(0.35)
rel(53,273); time.sleep(0.15)
t0=time.time(); btn(True); time.sleep(0.05); btn(False); time.sleep(0.30)
shot=RUND/"apagando.ppm"
r=ex("screendump",{"filename":str(shot)})
time.sleep(0.05)
try: code=proc.wait(timeout=25)
except subprocess.TimeoutExpired: proc.kill(); code=-9
lat=time.time()-t0
ok=shot.exists() and shot.stat().st_size>1000
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
print(f"QEMU_EXIT={code} lat={lat:.2f}s shot={ok} qmp_screendump={r}")
print("SERIAL:",[l for l in ser().splitlines() if "POWEROFF" in l or "acpi" in l or "SHUTDOWN" in l])
if ok: conv(shot,OUT/"apagando.png")
