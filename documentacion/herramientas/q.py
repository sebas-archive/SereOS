import socket,time,sys,os
SP=os.path.dirname(os.path.abspath(__file__))
CAP="/home/t1an/Descargas/sereos02/documentacion/capturas"
def cmd(c,wait=0.15):
    s=socket.socket(socket.AF_UNIX); s.connect(SP+"/qmon.sock"); s.settimeout(1)
    try: s.recv(4096)
    except: pass
    s.send((c+"\n").encode()); time.sleep(wait)
    try: r=s.recv(4096)
    except: r=b''
    s.close(); return r
def key(k,w=0.3): cmd("sendkey "+k,w)
def mv(dx,dy):
    # pasos pequenos para evitar saturar
    while dx or dy:
        sx=max(-60,min(60,dx)); sy=max(-60,min(60,dy))
        cmd(f"mouse_move {sx} {sy}",0.02); dx-=sx; dy-=sy
def click(): cmd("mouse_button 1",0.08); cmd("mouse_button 0",0.15)
def shot(rel):
    p=os.path.join(CAP,rel); os.makedirs(os.path.dirname(p),exist_ok=True)
    ppm=p[:-4]+".ppm"; cmd("screendump "+ppm,0.5)
    os.system(f"magick '{ppm}' '{p}' && rm '{ppm}'"); print("shot",rel)
