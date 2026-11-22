import subprocess,sys,time,os
VM="SereOS Final"
CAP="/home/t1an/Descargas/sereos02/documentacion/capturas"
SC={'esc':[0x01],'enter':[0x1c],'space':[0x39],'up':[0xe0,0x48],'down':[0xe0,0x50],'left':[0xe0,0x4b],'right':[0xe0,0x4d],
    'f1':[0x3b],'f2':[0x3c],'f3':[0x3d],'f4':[0x3e],'f5':[0x3f],'f6':[0x40],'f7':[0x41],'f8':[0x42],'bs':[0x0e],'tab':[0x0f]}
def vb(*a):
    return subprocess.run(["VBoxManage",*a],capture_output=True,text=True).stdout
def key(name,wait=0.4):
    codes=SC[name]
    rel=[codes[0]|0x80] if len(codes)==1 else [codes[0],codes[1]|0x80]
    seq=[hex(c)[2:] for c in codes+rel]
    if name=='esc':
        vb('controlvm',VM,'keyboardputscancode','01'); time.sleep(0.15); vb('controlvm',VM,'keyboardputscancode','81'); time.sleep(wait); return
    vb('controlvm',VM,'keyboardputscancode',*seq); time.sleep(wait)
def ctrl(ch,wait=0.4):
    m={'w':0x11}
    c=m[ch]; vb("controlvm",VM,"keyboardputscancode","1d",hex(c)[2:],hex(c|0x80)[2:],"9d"); time.sleep(wait)
def text(s,wait=0.3):
    vb("controlvm",VM,"keyboardputstring",s); time.sleep(wait)
def shot(rel):
    p=os.path.join(CAP,rel); os.makedirs(os.path.dirname(p),exist_ok=True)
    vb("controlvm",VM,"screenshotpng",p); print("shot",rel,os.path.getsize(p) if os.path.exists(p) else "FAIL")
if __name__=="__main__":
    cmd=sys.argv[1]
    if cmd=="key": 
        for k in sys.argv[2:]: key(k)
    elif cmd=="text": text(sys.argv[2])
    elif cmd=="shot": shot(sys.argv[2])
    elif cmd=="ctrl": ctrl(sys.argv[2])
    elif cmd=="sleep": time.sleep(float(sys.argv[2]))
