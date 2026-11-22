import sys,os,re,subprocess,shutil
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from engine import *
import content_a,content_b,content_c,content_d
OUT="/tmp/claude-1000/-home-t1an-Descargas-sereos02/26e41c39-e2c2-4130-931a-cf0e262874c1/scratchpad/doc/out"
os.makedirs(OUT,exist_ok=True)
FINAL=OUT+"/ProyectoFinal_sistemas_operativos_FINAL.docx"
def make(pages):
    D=Doc(); D.pages=pages
    content_a.build_a(D); content_b.build_b(D); content_c.build_c(D); content_d.build_d(D)
    D.build(FINAL); return D
def to_pdf():
    subprocess.run(["soffice","--headless","--convert-to","pdf","--outdir",OUT,FINAL],capture_output=True,timeout=300)
    return OUT+"/ProyectoFinal_sistemas_operativos_FINAL.pdf"
def pages_of(pdf,D):
    n=int(re.search(r'Pages:\s+(\d+)',subprocess.run(["pdfinfo",pdf],capture_output=True,text=True).stdout).group(1))
    txt=[subprocess.run(["pdftotext","-f",str(i),"-l",str(i),"-layout",pdf,"-"],capture_output=True,text=True).stdout for i in range(1,n+1)]
    norm=lambda t:re.sub(r'\s+',' ',t).strip()
    pg={}
    lines=[[norm(l) for l in t.split('\n')] for t in txt]
    for lv,t,nm in D.heads:
        tt=norm(t); last=None
        for i,ls in enumerate(lines,1):
            if tt in ls: last=i
        pg[nm]=last or 0
    for k,t in enumerate(D.figs,1):
        last=0
        for i,ls in enumerate(lines,1):
            if any(l.startswith(f"Figura {k}. ") and not re.search(r'\.{3,}',l) for l in ls): last=i
        pg[f"_Fig{k}"]=last
    for k,t in enumerate(D.tabs,1):
        last=0
        for i,ls in enumerate(lines,1):
            if any(l.startswith(f"Tabla {k}. ") and not re.search(r'\.{3,}',l) for l in ls): last=i
        pg[f"_Tab{k}"]=last
    return pg,n
if __name__=="__main__":
    D=make({}); pdf=to_pdf(); pg,n=pages_of(pdf,D); print("pass1 pages",n)
    D=make(pg); pdf=to_pdf(); pg2,n=pages_of(pdf,D)
    diff=[k for k in pg2 if pg2[k]!=pg.get(k)]
    print("pass2 pages",n,"diffs",len(diff))
    if diff:
        D=make(pg2); pdf=to_pdf(); pg3,n=pages_of(pdf,D); print("pass3 pages",n,"diffs",len([k for k in pg3 if pg3[k]!=pg2.get(k)]))
    zero=[k for k,v in pg2.items() if not v]; print("sin pagina:",zero[:10])
    print("figs",len(D.figs),"tabs",len(D.tabs),"heads",len(D.heads))
