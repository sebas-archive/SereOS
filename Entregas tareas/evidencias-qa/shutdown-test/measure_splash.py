import socket, subprocess, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
RUND=Path(__file__).resolve().parent/"iso-run4"; RUND.mkdir(exist_ok=True)
MON,SER=RUND/"monitor.sock",RUND/"serial.log"
for p in (MON,SER):
    try:p.unlink()
    except FileNotFoundError:pass
proc=subprocess.Popen(["qemu-system-i386","-display","none","-m","256M","-vga","std",
 "-cdrom",str(ROOT/"sistema operativo"/"sereos.iso"),"-monitor",f"unix:{MON},server,nowait",
 "-serial",f"file:{SER}","-no-reboot"])
def rd():
    try:return SER.read_text(errors="replace")
    except FileNotFoundError:return ""
end=time.time()+90
while "GUI_READY" not in rd() and time.time()<end: time.sleep(0.1)
time.sleep(0.5)
def conn():
    for _ in range(200):
        try:
            s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);s.connect(str(MON));s.settimeout(0.3);return s
        except OSError:time.sleep(0.1)
s=conn();time.sleep(0.2)
def cmd(c,st=0.06):
    s.sendall((c+"\n").encode());time.sleep(st)
    try:
        while True: s.recv(65536)
    except socket.timeout: pass
cmd("mouse_move -415 -366",0.12);cmd("mouse_button 1",0.05);cmd("mouse_button 0",0.3)
cmd("mouse_move 53 273",0.12)
t0=time.time()
cmd("mouse_button 1",0.05);cmd("mouse_button 0",0.02)
marks={}
end=time.time()+10
while time.time()<end:
    txt=rd()
    for m in ("SEREOS_POWEROFF","PWR:SPLASH_BEGIN","PWR:SPLASH_END"):
        if m in txt and m not in marks: marks[m]=time.time()-t0
    if "PWR:SPLASH_END" in txt: break
    if proc.poll() is not None: break
    time.sleep(0.005)
code=proc.wait(timeout=10) if proc.poll() is None else proc.returncode
print("marcas:",{k:round(v,3) for k,v in marks.items()},"exit",code,"total",round(time.time()-t0,3))
