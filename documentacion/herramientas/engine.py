# Motor de generacion del DOCX sobre la plantilla institucional
import re,os,shutil,zipfile,subprocess,html,json
from PIL import Image
SP="/tmp/claude-1000/-home-t1an-Descargas-sereos02/26e41c39-e2c2-4130-931a-cf0e262874c1/scratchpad"
TPL=SP+"/main"            # plantilla desempaquetada (solo lectura)
WORK=SP+"/doc/work"
CAPS="/home/t1an/Descargas/sereos02/documentacion/"
NAVY="1F3A5F"; GREY="5B6577"
def esc(t): return html.escape(t,quote=False)

class Doc:
    def __init__(s):
        s.body=[]; s.heads=[]; s.figs=[]; s.tabs=[]; s.imgs=[]; s.bm=100; s.numids=[]; s.pid=1; s.dpid=100
        s.pages={}   # clave -> pagina (segunda pasada)
    # ---------- texto en linea ----------
    def runs(s,text,sz=None,color=None,bold=False,italic=False,font=None):
        out=[]
        parts=re.split(r'(\*\*.+?\*\*|\^\^.+?\^\^|`.+?`)',text)
        for p in parts:
            if not p: continue
            b=bold;i=italic;code=False
            if p.startswith('**') and p.endswith('**') and len(p)>4: p=p[2:-2];b=True
            elif p.startswith('^^') and p.endswith('^^') and len(p)>4: p=p[2:-2];i=True
            elif p.startswith('`') and p.endswith('`') and len(p)>2: p=p[1:-1];code=True
            rp=''
            if code: rp+='<w:rFonts w:ascii="Courier New" w:hAnsi="Courier New" w:cs="Courier New"/>'
            elif font: rp+=f'<w:rFonts w:ascii="{font}" w:hAnsi="{font}" w:cs="{font}"/>'
            if b: rp+='<w:b/><w:bCs/>'
            if i: rp+='<w:i/><w:iCs/>'
            if color: rp+=f'<w:color w:val="{color}"/>'
            if code:
                z=(sz or 24)-2 if (sz or 24)>20 else sz or 20
                rp+=f'<w:sz w:val="{z}"/><w:szCs w:val="{z}"/><w:shd w:val="clear" w:color="auto" w:fill="F1F3F6"/>'
            elif sz: rp+=f'<w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/>'
            rp+='<w:lang w:val="es-CO"/>'
            out.append(f'<w:r><w:rPr>{rp}</w:rPr><w:t xml:space="preserve">{esc(p)}</w:t></w:r>')
        return ''.join(out)
    def para(s,inner,ppr='',style='1104'):
        return f'<w:p><w:pPr><w:pStyle w:val="{style}"/>{ppr}</w:pPr>{inner}</w:p>'
    # ---------- bloques ----------
    def P(s,text,after=120,align='both',keepNext=False,line=360,ind=None,sz=None,color=None,italic=False,bold=False):
        pp=('<w:keepNext/>' if keepNext else '')+f'<w:spacing w:before="0" w:after="{after}" w:line="{line}" w:lineRule="auto"/>'
        if ind: pp+=f'<w:ind w:left="{ind}"/>'
        pp+=f'<w:jc w:val="{align}"/>'
        s.body.append(s.para(s.runs(text,sz=sz,color=color,italic=italic,bold=bold),pp))
    def H(s,level,text,pagebreak=None,toc=True):
        sid={1:'939',2:'940',3:'941'}[level]
        s.bm+=1; name=f"_Toc{s.bm}"
        if pagebreak is None: pagebreak=(level==1)
        pp='<w:keepNext/><w:keepLines/>'+('<w:pageBreakBefore/>' if pagebreak else '')
        if level==1: pp+='<w:spacing w:before="0" w:after="240" w:line="276" w:lineRule="auto"/><w:jc w:val="center"/>'
        elif level==2: pp+='<w:spacing w:before="280" w:after="120" w:line="276" w:lineRule="auto"/><w:jc w:val="left"/>'
        else: pp+='<w:spacing w:before="200" w:after="100" w:line="276" w:lineRule="auto"/><w:jc w:val="left"/>'
        sz={1:30,2:26,3:24}[level]
        col={1:NAVY,2:NAVY,3:'000000'}[level]
        inner=f'<w:bookmarkStart w:id="{s.bm}" w:name="{name}"/>'+s.runs(text,sz=sz,color=col,bold=True,italic=(level==3))+f'<w:bookmarkEnd w:id="{s.bm}"/>'
        s.body.append(s.para(inner,pp,sid))
        if toc: s.heads.append((level,text,name))
    def _num(s,kind):
        if kind=='bul': return 100
        nid=101+len([1 for k in s.numids if k=='num']); s.numids.append('num'); return nid
    def LIST(s,items,kind='bul',after=60):
        nid=s._num(kind)
        for k,it in enumerate(items):
            last=(k==len(items)-1)
            pp=f'<w:numPr><w:ilvl w:val="0"/><w:numId w:val="{nid}"/></w:numPr><w:spacing w:before="0" w:after="{after if not last else 140}" w:line="336" w:lineRule="auto"/><w:ind w:left="720" w:hanging="360"/><w:jc w:val="both"/>'
            s.body.append(s.para(s.runs(it),pp,'1105'))
    def BUL(s,items): s.LIST(items,'bul')
    def NUM(s,items): s.LIST(items,'num')
    def CODE(s,text,title=None):
        lines=text.strip('\n').split('\n')
        if title:
            s.body.append(s.para(s.runs(title,sz=20,color=GREY,italic=True),'<w:keepNext/><w:spacing w:before="60" w:after="40" w:line="240" w:lineRule="auto"/>'))
        for k,l in enumerate(lines):
            bd='<w:pBdr>'
            if k==0: bd+='<w:top w:val="single" w:sz="4" w:space="3" w:color="D5DAE1"/>'
            bd+='<w:left w:val="single" w:sz="18" w:space="6" w:color="2563EB"/>'
            if k==len(lines)-1: bd+='<w:bottom w:val="single" w:sz="4" w:space="3" w:color="D5DAE1"/>'
            bd+='</w:pBdr>'
            pp=('<w:keepNext/>' if k<len(lines)-1 else '')+'<w:keepLines/>'+bd+'<w:shd w:val="clear" w:color="auto" w:fill="F6F8FA"/>'+f'<w:spacing w:before="0" w:after="{120 if k==len(lines)-1 else 0}" w:line="240" w:lineRule="auto"/><w:ind w:left="170"/><w:jc w:val="left"/>'
            r=f'<w:r><w:rPr><w:rFonts w:ascii="Courier New" w:hAnsi="Courier New" w:cs="Courier New"/><w:sz w:val="17"/><w:szCs w:val="17"/><w:lang w:val="en-US"/></w:rPr><w:t xml:space="preserve">{esc(l) if l else " "}</w:t></w:r>'
            s.body.append(s.para(r,pp))
    def TABLE(s,title,headers,rows,widths,note=None,sz=19,keep=True):
        assert sum(widths)==9360,(title,sum(widths))
        s.tabs.append(title); n=len(s.tabs); s.bm+=1; nm=f"_Tab{n}"
        cap=f'<w:bookmarkStart w:id="{s.bm}" w:name="{nm}"/><w:r><w:rPr><w:b/><w:color w:val="{NAVY}"/><w:sz w:val="22"/></w:rPr><w:t xml:space="preserve">Tabla </w:t></w:r><w:r><w:rPr><w:b/><w:color w:val="{NAVY}"/><w:sz w:val="22"/></w:rPr><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:rPr><w:b/><w:color w:val="{NAVY}"/><w:sz w:val="22"/></w:rPr><w:instrText xml:space="preserve"> SEQ Tabla \\* ARABIC </w:instrText></w:r><w:r><w:rPr><w:b/><w:color w:val="{NAVY}"/><w:sz w:val="22"/></w:rPr><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:rPr><w:b/><w:color w:val="{NAVY}"/><w:sz w:val="22"/></w:rPr><w:t>{n}</w:t></w:r><w:r><w:rPr><w:b/><w:color w:val="{NAVY}"/><w:sz w:val="22"/></w:rPr><w:fldChar w:fldCharType="end"/></w:r><w:r><w:rPr><w:b/><w:color w:val="{NAVY}"/><w:sz w:val="22"/></w:rPr><w:t xml:space="preserve">. </w:t></w:r>'+s.runs(title,sz=22,italic=True)+f'<w:bookmarkEnd w:id="{s.bm}"/>'
        s.body.append(s.para(cap,'<w:keepNext/><w:keepLines/><w:spacing w:before="200" w:after="80" w:line="252" w:lineRule="auto"/><w:jc w:val="left"/>','1097'))
        bd=lambda: ''.join(f'<w:{e} w:val="single" w:sz="4" w:space="0" w:color="C3CAD5"/>' for e in ('top','left','bottom','right','insideH','insideV'))
        x=f'<w:tbl><w:tblPr><w:tblW w:w="9360" w:type="dxa"/><w:jc w:val="center"/><w:tblBorders>{bd()}</w:tblBorders><w:tblLayout w:type="fixed"/><w:tblCellMar><w:top w:w="50" w:type="dxa"/><w:left w:w="90" w:type="dxa"/><w:bottom w:w="50" w:type="dxa"/><w:right w:w="90" w:type="dxa"/></w:tblCellMar><w:tblLook w:val="04A0" w:firstRow="1" w:lastRow="0" w:firstColumn="0" w:lastColumn="0" w:noHBand="0" w:noVBand="1"/></w:tblPr><w:tblGrid>'+''.join(f'<w:gridCol w:w="{w}"/>' for w in widths)+'</w:tblGrid>'
        def cell(t,w,head=False,shade=None,last=False):
            fill=f'<w:shd w:val="clear" w:color="auto" w:fill="{"1F3A5F" if head else shade}"/>' if (head or shade) else ''
            kn='<w:keepNext/>' if (keep and not last) else ''
            paras=[]
            for ln in str(t).split('\n'):
                paras.append(f'<w:p><w:pPr><w:pStyle w:val="1106"/>{kn}<w:spacing w:before="0" w:after="0" w:line="248" w:lineRule="auto"/><w:ind w:left="0"/><w:jc w:val="left"/></w:pPr>{s.runs(ln,sz=sz,bold=head,color="FFFFFF" if head else None)}</w:p>')
            return f'<w:tc><w:tcPr><w:tcW w:w="{w}" w:type="dxa"/>{fill}<w:vAlign w:val="center"/></w:tcPr>{"".join(paras)}</w:tc>'
        x+='<w:tr><w:trPr><w:cantSplit/><w:tblHeader/></w:trPr>'+''.join(cell(h,w,head=True) for h,w in zip(headers,widths))+'</w:tr>'
        for ri,r in enumerate(rows):
            last=(ri==len(rows)-1)
            x+='<w:tr><w:trPr><w:cantSplit/></w:trPr>'+''.join(cell(c,w,shade=('F5F7FA' if ri%2 else None),last=last) for c,w in zip(r,widths))+'</w:tr>'
        x+='</w:tbl>'
        s.body.append(x)
        if note: s.body.append(s.para(s.runs(note,sz=19,color=GREY,italic=True),'<w:spacing w:before="60" w:after="200" w:line="240" w:lineRule="auto"/><w:jc w:val="left"/>'))
        else: s.body.append(s.para('','<w:spacing w:before="0" w:after="120" w:line="120" w:lineRule="exact"/>'))
    def FIG(s,path,title,note,w_in=6.3,max_h_in=5.7,border=True):
        full=path if path.startswith('/') else CAPS+path
        crop=None
        b=os.path.basename(full); dn=os.path.basename(os.path.dirname(full))
        if dn=='03_terminal' and b.startswith('cmd_'): crop=(100,100,760,500)
        elif dn=='05_pacman_sereos_vbox': crop=(35,60,890,575)
        elif b=='explorador_archivos.png': crop=(45,75,920,585)
        elif b in ('monitor_sistema_foco.png','acerca_de.png','multiventana.png'): crop=(40,70,930,600)
        if crop:
            od=CAPS+'capturas/recortes_documento/'; os.makedirs(od,exist_ok=True)
            cf=od+dn+'__'+b
            Image.open(full).convert('RGB').crop((crop[0],crop[1],crop[0]+crop[2],crop[1]+crop[3])).save(cf)
            full=cf; note=note+' Recorte de la zona útil de la captura original de 1024x768, que se conserva completa en la carpeta de evidencias.'
        im=Image.open(full); W,H=im.size
        wi=w_in; hi=wi*H/W
        if hi>max_h_in: hi=max_h_in; wi=hi*W/H
        cx=int(wi*914400); cy=int(hi*914400)
        s.figs.append(title); n=len(s.figs); s.bm+=1; nm=f"_Fig{n}"
        idx=len(s.imgs)+1; ext=os.path.splitext(full)[1].lower()
        s.imgs.append((full,f"fig{idx:03d}{ext}")); rid=f"rId{200+idx}"
        cap=f'<w:bookmarkStart w:id="{s.bm}" w:name="{nm}"/><w:r><w:rPr><w:b/><w:color w:val="{NAVY}"/><w:sz w:val="22"/></w:rPr><w:t xml:space="preserve">Figura </w:t></w:r><w:r><w:rPr><w:b/><w:color w:val="{NAVY}"/><w:sz w:val="22"/></w:rPr><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:rPr><w:b/><w:color w:val="{NAVY}"/><w:sz w:val="22"/></w:rPr><w:instrText xml:space="preserve"> SEQ Figura \\* ARABIC </w:instrText></w:r><w:r><w:rPr><w:b/><w:color w:val="{NAVY}"/><w:sz w:val="22"/></w:rPr><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:rPr><w:b/><w:color w:val="{NAVY}"/><w:sz w:val="22"/></w:rPr><w:t>{n}</w:t></w:r><w:r><w:rPr><w:b/><w:color w:val="{NAVY}"/><w:sz w:val="22"/></w:rPr><w:fldChar w:fldCharType="end"/></w:r><w:r><w:rPr><w:b/><w:color w:val="{NAVY}"/><w:sz w:val="22"/></w:rPr><w:t xml:space="preserve">. </w:t></w:r>'+s.runs(title,sz=22,italic=True)+f'<w:bookmarkEnd w:id="{s.bm}"/>'
        s.body.append(s.para(cap,'<w:keepNext/><w:keepLines/><w:spacing w:before="200" w:after="80" w:line="252" w:lineRule="auto"/><w:jc w:val="left"/>','1097'))
        s.dpid+=1
        ln='<a:ln w="9525"><a:solidFill><a:srgbClr val="C3CAD5"/></a:solidFill></a:ln>' if border else ''
        alt=esc(title)
        draw=(f'<w:r><w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/><wp:effectExtent l="0" t="0" r="0" b="0"/><wp:docPr id="{s.dpid}" name="Imagen {s.dpid}" descr="{alt}"/><wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:nvPicPr><pic:cNvPr id="{s.dpid}" name="fig{idx}"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom>{ln}</pic:spPr></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r>')
        s.body.append(s.para(draw,'<w:keepNext/><w:spacing w:before="0" w:after="60" w:line="240" w:lineRule="auto"/><w:jc w:val="center"/>'))
        s.body.append(s.para(s.runs('Nota. ',sz=20,bold=True,color=GREY)+s.runs(note,sz=20,color=GREY),'<w:keepLines/><w:spacing w:before="0" w:after="240" w:line="252" w:lineRule="auto"/><w:jc w:val="both"/>'))
    def PB(s): s.body.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')

    # ---------- TOC ----------
    def _toc_entry(s,level,text,anchor,page,first_begin=None,style=None):
        st={1:'1100',2:'1101',3:'1102'}[level]
        ind={1:0,2:260,3:520}[level]
        pre=''
        if first_begin: pre=f'<w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve"> {first_begin} </w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r>'
        bold = '<w:b/>' if level==1 else ''
        entry=(f'<w:hyperlink w:anchor="{anchor}" w:history="1"><w:r><w:rPr>{bold}<w:lang w:val="es-CO"/></w:rPr><w:t xml:space="preserve">{esc(text)}</w:t></w:r><w:r><w:rPr>{bold}</w:rPr><w:tab/></w:r>'
               f'<w:r><w:rPr>{bold}</w:rPr><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:rPr>{bold}</w:rPr><w:instrText xml:space="preserve"> PAGEREF {anchor} \\h </w:instrText></w:r><w:r><w:rPr>{bold}</w:rPr><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:rPr>{bold}</w:rPr><w:t>{page}</w:t></w:r><w:r><w:rPr>{bold}</w:rPr><w:fldChar w:fldCharType="end"/></w:r></w:hyperlink>')
        sp='<w:spacing w:before="%d" w:after="0" w:line="252" w:lineRule="auto"/>'%(100 if level==1 else 20)
        return f'<w:p><w:pPr><w:pStyle w:val="{st}"/><w:tabs><w:tab w:val="right" w:leader="dot" w:pos="9350"/></w:tabs>{sp}<w:ind w:left="{ind}" w:right="0"/><w:jc w:val="left"/></w:pPr>{pre}{entry}</w:p>'
    def toc_xml(s,head_par):
        out=[head_par]
        for i,(lv,t,nm) in enumerate(s.heads):
            out.append(s._toc_entry(lv,t,nm,s.pages.get(nm,'0'),first_begin='TOC \\o &quot;1-3&quot; \\h \\z \\u' if i==0 else None))
        out.append('<w:p><w:pPr><w:spacing w:before="0" w:after="0"/></w:pPr><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>')
        return '<w:sdt><w:sdtPr><w:id w:val="2021202216"/><w:docPartObj><w:docPartGallery w:val="Table of Contents"/><w:docPartUnique/></w:docPartObj></w:sdtPr><w:sdtContent>'+''.join(out)+'</w:sdtContent></w:sdt>'
    def list_xml(s,title,items,prefix,label):
        h=f'<w:p><w:pPr><w:pStyle w:val="1111"/><w:pageBreakBefore/><w:spacing w:before="0" w:after="200"/><w:jc w:val="center"/></w:pPr><w:r><w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/><w:b/><w:color w:val="{NAVY}"/><w:sz w:val="30"/></w:rPr><w:t>{title}</w:t></w:r></w:p>'
        out=[h]
        for i,t in enumerate(items):
            n=i+1; anchor=f"{prefix}{n}"
            pre=''
            if i==0: pre=f'<w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve"> TOC \\h \\z \\c &quot;{label}&quot; </w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r>'
            txt=f"{label} {n}. {t}"
            entry=(f'<w:hyperlink w:anchor="{anchor}" w:history="1"><w:r><w:t xml:space="preserve">{esc(txt)}</w:t></w:r><w:r><w:tab/></w:r><w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve"> PAGEREF {anchor} \\h </w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>{s.pages.get(anchor,"0")}</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:hyperlink>')
            out.append(f'<w:p><w:pPr><w:pStyle w:val="1099"/><w:tabs><w:tab w:val="right" w:leader="dot" w:pos="9350"/></w:tabs><w:spacing w:before="40" w:after="40" w:line="252" w:lineRule="auto"/><w:ind w:left="0" w:right="0" w:hanging="0"/></w:pPr>{pre}{entry}</w:p>')
        out.append('<w:p><w:pPr><w:spacing w:before="0" w:after="0"/></w:pPr><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>')
        return ''.join(out)

    # ---------- ensamblado ----------
    def build(s,out_docx):
        if os.path.exists(WORK): shutil.rmtree(WORK)
        shutil.copytree(TPL,WORK)
        d=open(TPL+'/word/document.xml',encoding='utf8').read()
        root_end=d.index('<w:body>')+len('<w:body>')
        head=d[:root_end]
        i_sdt=d.index('<w:sdt>'); j_sdt=d.index('</w:sdt>')+len('</w:sdt>')
        cover=d[root_end:i_sdt]
        sdt=d[i_sdt:j_sdt]
        # parrafo "Tabla de contenido" original
        m=re.search(r'<w:sdtContent>(<w:p .*?</w:p>)',sdt,re.S)
        head_par=m.group(1)
        head_par=head_par.replace('<w:pStyle w:val="1111" />','<w:pStyle w:val="1111" /><w:spacing w:before="0" w:after="200"/><w:jc w:val="center"/>',1) if False else head_par
        # seccion de portada: incrustar sectPr en el ultimo parrafo de la portada
        k=cover.rindex('<w:p ')
        lastp=cover[k:]
        cover_sect=('<w:sectPr><w:footnotePr/><w:endnotePr/><w:type w:val="nextPage"/><w:pgSz w:w="12240" w:h="15840" w:orient="portrait"/><w:pgMar w:top="1820" w:right="1440" w:bottom="280" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/><w:cols w:num="1" w:space="720"/></w:sectPr>')
        lastp=lastp.replace('</w:pPr>',cover_sect+'</w:pPr>',1)
        cover=cover[:k]+lastp
        lof=s.list_xml('Lista de figuras',s.figs,'_Fig','Figura')
        lot=s.list_xml('Lista de tablas',s.tabs,'_Tab','Tabla')
        final_sect=('<w:sectPr><w:headerReference w:type="default" r:id="rId9"/><w:footerReference w:type="default" r:id="rId10"/><w:footnotePr/><w:endnotePr/><w:type w:val="nextPage"/><w:pgSz w:w="12240" w:h="15840" w:orient="portrait"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1300" w:left="1440" w:header="620" w:footer="560" w:gutter="0"/><w:cols w:num="1" w:space="720"/></w:sectPr>')
        doc=head+cover+s.toc_xml(head_par)+lof+lot+''.join(s.body)+final_sect+'</w:body></w:document>'
        open(WORK+'/word/document.xml','w',encoding='utf8').write(doc)
        # cabecera y pie
        ns='xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
        hdr=f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:hdr {ns}><w:p><w:pPr><w:pStyle w:val="1131"/><w:tabs><w:tab w:val="clear" w:pos="4680"/><w:tab w:val="clear" w:pos="9360"/><w:tab w:val="right" w:pos="9360"/></w:tabs><w:spacing w:after="0"/></w:pPr><w:r><w:rPr><w:color w:val="{GREY}"/><w:sz w:val="20"/></w:rPr><w:t>SereOS y PAC-MAN SereOS</w:t></w:r><w:r><w:rPr><w:sz w:val="20"/></w:rPr><w:tab/></w:r><w:r><w:rPr><w:sz w:val="22"/></w:rPr><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:rPr><w:sz w:val="22"/></w:rPr><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r><w:r><w:rPr><w:sz w:val="22"/></w:rPr><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:rPr><w:sz w:val="22"/></w:rPr><w:t>2</w:t></w:r><w:r><w:rPr><w:sz w:val="22"/></w:rPr><w:fldChar w:fldCharType="end"/></w:r></w:p></w:hdr>'
        ftr=f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:ftr {ns}><w:p><w:pPr><w:pStyle w:val="1132"/><w:pBdr><w:top w:val="single" w:sz="4" w:space="4" w:color="C3CAD5"/></w:pBdr><w:spacing w:before="0" w:after="0"/><w:jc w:val="center"/></w:pPr><w:r><w:rPr><w:color w:val="{GREY}"/><w:sz w:val="18"/></w:rPr><w:t xml:space="preserve">Proyecto final de Sistemas Operativos · Universidad Manuela Beltrán · Ingeniería de software</w:t></w:r></w:p></w:ftr>'
        open(WORK+'/word/header1.xml','w',encoding='utf8').write(hdr)
        open(WORK+'/word/footer1.xml','w',encoding='utf8').write(ftr)
        # imagenes
        os.makedirs(WORK+'/word/media',exist_ok=True)
        rels=open(WORK+'/word/_rels/document.xml.rels',encoding='utf8').read()
        add=''
        for k,(src,name) in enumerate(s.imgs,1):
            shutil.copy(src,WORK+'/word/media/'+name)
            add+=f'<Relationship Id="rId{200+k}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/{name}"/>'
        rels=rels.replace('</Relationships>',add+'</Relationships>')
        open(WORK+'/word/_rels/document.xml.rels','w',encoding='utf8').write(rels)
        # numeracion
        nx=open(WORK+'/word/numbering.xml',encoding='utf8').read()
        nums='<w:num w:numId="100"><w:abstractNumId w:val="10"/></w:num>'
        for q in range(len([1 for k in s.numids if k=='num'])):
            nums+=f'<w:num w:numId="{101+q}"><w:abstractNumId w:val="18"/><w:lvlOverride w:ilvl="0"><w:startOverride w:val="1"/></w:lvlOverride></w:num>'
        nx=nx.replace('</w:numbering>',nums+'</w:numbering>')
        open(WORK+'/word/numbering.xml','w',encoding='utf8').write(nx)
        # propiedades
        core=open(WORK+'/docProps/core.xml',encoding='utf8').read()
        open(WORK+'/docProps/core.xml','w',encoding='utf8').write(core)
        # settings: actualizar campos al abrir
        st=open(WORK+'/word/settings.xml',encoding='utf8').read()
        if 'w:updateFields' not in st:
            st=re.sub(r'(<w:settings[^>]*>)',r'\1<w:updateFields w:val="false"/>',st,1) if False else st
        open(WORK+'/word/settings.xml','w',encoding='utf8').write(st)
        # zip
        if os.path.exists(out_docx): os.remove(out_docx)
        with zipfile.ZipFile(out_docx,'w',zipfile.ZIP_DEFLATED) as z:
            # [Content_Types].xml primero
            z.write(WORK+'/[Content_Types].xml','[Content_Types].xml')
            for rt,_,fs in os.walk(WORK):
                for f in fs:
                    p=os.path.join(rt,f); a=os.path.relpath(p,WORK)
                    if a=='[Content_Types].xml': continue
                    z.write(p,a)
