import sys,os,time,subprocess,collections
sys.path.insert(0,'.')
import numpy as np
from PIL import Image
import drv
v=drv.vb
MAZE=[
"oooooooooooooooooooooooooooo","o............OO............o","o.OOOO.OOOOO.OO.OOOOO.OOOO.o","o+OOOO.OOOOO.OO.OOOOO.OOOO+o",
"o.OOOO.OOOOO.OO.OOOOO.OOOO.o","o..........................o","o.OOOO.OO.OOOOOOOO.OO.OOOO.o","o.OOOO.OO.OOOOOOOO.OO.OOOO.o",
"o......OO....OO....OO......o","oooooo.OOOOO OO OOOOO.oooooo","XXXXXo.OOOOO OO OOOOO.oXXXXX","XXXXXo.OO          OO.oXXXXX",
"XXXXXo.OO oooppooo OO.oXXXXX","oooooo.OO oPPPPPPo OO.oooooo","TTTTTT.   oPPPPPPo   .TTTTTT","oooooo.OO oPPPPPPo OO.oooooo",
"XXXXXo.OO oooooooo OO.oXXXXX","XXXXXo.OO          OO.oXXXXX","XXXXXo.OO OOOOOOOO OO.oXXXXX","oooooo.OO OOOOOOOO OO.oooooo",
"o............OO............o","o.OOOO.OOOOO.OO.OOOOO.OOOO.o","o.OOOO.OOOOO.OO.OOOOO.OOOO.o","o+..OO.......  .......OO..+o",
"oOO.OO.OO.OOOOOOOO.OO.OO.OOo","oOO.OO.OO.OOOOOOOO.OO.OO.OOo","o......OO....OO....OO......o","o.OOOOOOOOOO.OO.OOOOOOOOOO.o",
"o.OOOOOOOOOO.OO.OOOOOOOOOO.o","o..........................o","oooooooooooooooooooooooooooo"]
R,C=31,28
OX,OY=256,114
def passable(r,c):
    if r<0 or r>=R: return False
    c%=C if MAZE[r][c%C]=='T' else C
    if not (0<=c<C): return False
    return MAZE[r][c] in ".+ T"
DIRS={'up':(-1,0),'down':(1,0),'left':(0,-1),'right':(0,1)}
def nbrs(r,c):
    for k,(dr,dc) in DIRS.items():
        nr,nc=r+dr,c+dc
        if nc<0 or nc>=C:
            if MAZE[r][c]=='T': nc%=C
            else: continue
        if passable(nr,nc): yield k,(nr,nc)
def bfs(src,blocked=set()):
    d={src:0};first={src:None};q=collections.deque([src])
    while q:
        u=q.popleft()
        for k,w in nbrs(*u):
            if w in d or w in blocked: continue
            d[w]=d[u]+1; first[w]=first[u] or k; q.append(w)
    return d,first
def near(m,tol=5):
    return m
def analyse(path):
    a=np.asarray(Image.open(path).convert('RGB')).astype(int)
    sub=a[OY:OY+496,OX:OX+448]
    r,g,b=sub[...,0],sub[...,1],sub[...,2]
    def blob(mask):
        ys,xs=np.nonzero(mask)
        return (int(xs.mean()),int(ys.mean()),len(xs)) if len(xs)>=6 else None
    pac=blob((abs(r-255)<4)&(abs(g-203)<5)&(abs(b-57)<8))
    ghosts={}
    ghosts['red']=blob((r>240)&(g<40)&(b<40))
    ghosts['pink']=blob((r>240)&(abs(g-190)<8)&(b>240))
    ghosts['cyan']=blob((r<40)&(g>240)&(b>240))
    ghosts['orange']=blob((r>240)&(abs(g-190)<8)&(abs(b-99)<10))
    fr=(r<60)&(g<60)&(b>235)
    # tiles with many blue pixels = frightened ghost
    frt=[]
    for tr in range(R):
        for tc in range(C):
            if fr[tr*16:(tr+1)*16,tc*16:(tc+1)*16].sum()>45: frt.append((tr,tc))
    pills=[(tr,tc) for tr in (3,23) for tc in (1,26) if (abs(sub[tr*16+8,tc*16+8]-np.array([255,212,71]))<10).all()]
    return pac,ghosts,frt,pills,sub
def tile(p): return (p[1]//16,p[0]//16)
def key(k): v.key(k,0.0)
def run(outdir,maxt=90,stop_on=('GAME_OVER',),frames_prefix='f'):
    os.makedirs(outdir,exist_ok=True)
    base=len(drv.ser().strip().splitlines())
    t0=time.time();n=0;last=None;log=[];lastk=None
    while time.time()-t0<maxt:
        p=f"{outdir}/{frames_prefix}{n:04d}.png"
        subprocess.run(["VBoxManage","controlvm",v.VM,"screenshotpng",p],capture_output=True)
        s=drv.ser().strip().splitlines()[base:]; tag=s[-1] if s else ''
        if tag!=last: log.append((n,round(time.time()-t0,1),tag)); print(n,round(time.time()-t0,1),tag,flush=True); last=tag
        if any(tag.startswith(x) for x in stop_on): break
        try:
            pac,gh,frt,pills,sub=analyse(p)
        except Exception as e:
            n+=1; continue
        n+=1
        if not pac: continue
        pt=tile(pac)
        act=[tile(g) for g in gh.values() if g and tile(g) not in frt and not (12<=tile(g)[0]<=15 and 9<=tile(g)[1]<=18)]
        blocked=set()
        for gt in act:
            dd,_=bfs(gt)
            for t,x in dd.items():
                if x<=3 and t!=pt: blocked.add(t)
        dist,first=bfs(pt,blocked)
        goal=None
        if frt:
            c=[(dist[t],t) for t in frt if t in dist]
            if c: goal=min(c)[1]
        if goal is None and pills:
            c=[(dist[t],t) for t in pills if t in dist]
            if c: goal=min(c)[1]
        if goal is None:
            # nearest dot: tile centre light pixel
            best=None
            for t,x in dist.items():
                if x==0 or MAZE[t[0]][t[1]] not in '.+': continue
                py,px=t[0]*16+8,t[1]*16+8
                if sub[py,px].sum()>600 and (best is None or x<best[0]): best=(x,t)
            if best: goal=best[1]
        if goal and first.get(goal):
            k=first[goal]
        else:
            # flee: neighbour maximizing distance to nearest active ghost
            opts=[(k,w) for k,w in nbrs(*pt)]
            def score(w): return min([abs(w[0]-g[0])+abs(w[1]-g[1]) for g in act] or [99])
            k=max(opts,key=lambda o:score(o[1]))[0] if opts else None
        if k: key(k)
    return log
if __name__=="__main__":
    out=sys.argv[1]; mt=float(sys.argv[2])
    run(out,mt)
