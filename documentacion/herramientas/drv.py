import sys,time,subprocess,os
sys.path.insert(0,os.path.dirname(__file__) or '.')
import vb
vb.SC.update({'r':[0x13],'p':[0x19]})
SER=os.path.join(os.path.dirname(os.path.abspath(__file__)),'serial_vbox.log')
def ser():
    try: return open(SER,errors='ignore').read()
    except: return ''
def boot():
    subprocess.run(["VBoxManage","startvm",vb.VM,"--type","headless"],capture_output=True)
    time.sleep(2.4)
    for _ in range(8): vb.key('up',0.25)
    vb.key('enter',0.2)
def frames(prefix,n,dt,outdir='raw'):
    os.makedirs(outdir,exist_ok=True)
    tags=[]
    for i in range(n):
        p=f"{outdir}/{prefix}{i:03d}.png"
        subprocess.run(["VBoxManage","controlvm",vb.VM,"screenshotpng",p],capture_output=True)
        s=ser().strip().splitlines()
        tags.append((i,s[-1] if s else ''))
        time.sleep(dt)
    return tags
