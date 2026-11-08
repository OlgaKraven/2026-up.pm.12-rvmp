"""Build three teaching pages and portrait PDFs from course.json.

Drafts go to work/site. Only --release with real current evidence replaces site.
"""
import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import math
import shutil
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]
BASE='https://olgakraven.github.io/2026-up.pm.12-rvmp/'
EXCLUDED={'Library','Temp','Logs','obj','UserSettings','Build','Builds'}
ESC=html.escape
TEXT_SUFFIXES={'.json','.py','.js','.cjs','.html','.css','.svg','.cs','.meta','.unity','.asset','.txt','.md','.yml','.yaml','.xml'}

def canonical_bytes(path):
    value=path.read_bytes()
    return value.replace(b'\r\n',b'\n') if path.suffix.lower() in TEXT_SUFFIXES else value

def load_course():
    data=json.loads((ROOT/'content/course.json').read_text(encoding='utf-8'))
    sources={item['name']:(ROOT/item['path']).read_text(encoding='utf-8') for item in data['code_files']}
    for page in data['guide']:
        for block in page['blocks']:
            if 'snippet_file' in block:
                actual=(ROOT/block['snippet_file']).read_text(encoding='utf-8').rstrip()
                if block.get('text')!=actual:raise ValueError('Update import-visible snippet: '+block['snippet_file'])
            if 'code_file' in block:
                lines=sources[block['code_file']].splitlines();start,end=block['code_lines']
                if not 0<=start<end<=len(lines):raise ValueError('Invalid code range: '+block['title'])
                block['text']='\n'.join(lines[start:end])
    data['_code_sources']=sources
    return data

def source_fingerprint(root=ROOT):
    paths=[root/'requirements.txt',root/'package.json']
    for folder in ('content','scripts','assets','tutorial','unity-project','forms/template'):
        paths.extend(p for p in (root/folder).rglob('*') if p.is_file()
                     and not EXCLUDED.union({'__pycache__'}).intersection(p.relative_to(root).parts))
    digest=hashlib.sha256()
    for p in sorted(paths):digest.update(p.relative_to(root).as_posix().encode()+b'\0'+canonical_bytes(p)+b'\0')
    return digest.hexdigest()

def validate(data,release=False):
    for key in ('meta','assignment','guide','areas','code_files','report'):
        if not data.get(key):raise ValueError('Missing '+key)
    for key in ('assignment','guide','areas'):
        for page in data[key]:
            if not page.get('title') or not page.get('blocks'):raise ValueError('Incomplete page')
            for b in page['blocks']:
                if not b.get('title') or not b.get('text'):raise ValueError('Empty '+b.get('title','block'))
    assert len(data['areas'])==30 and len({p['anchor'] for p in data['areas']})==30
    for item in data['code_files']:
        covered=[]
        for page in data['guide']:
            for b in page['blocks']:
                if b.get('code_file')==item['name']:covered.extend(range(*b['code_lines']))
        assert covered==list(range(len(data['_code_sources'][item['name']].splitlines()))),item['name']
    if release:
        if data['meta']['status']!='ready':raise ValueError('Not accepted for release')

def require_release_evidence():
    proof=json.loads((ROOT/'verification/release.json').read_text(encoding='utf-8'))
    if proof.get('source_sha256')!=source_fingerprint() or not all(proof.get('checks',{}).get(k) is True for k in ('unity','variants','visual','audit')):
        raise ValueError('Current real Unity, variant, visual and audit evidence required')

def relative_link(href,printing=False):
    return href if printing or not href.startswith(BASE) else href[len(BASE):]

def paragraphs(text):
    return ''.join('<p>'+ESC(s).replace('\n','<br>')+'</p>' for s in text.split('\n\n'))

def pieces(block):
    if block['kind']!='code':return [block]
    lines=block['text'].splitlines();result=[];start=0
    while start<len(lines):
        end=start;estimated=0;choices=[]
        while end<len(lines):
            height=max(1,math.ceil(len(lines[end])/65))
            if estimated+height>26 and end>start:break
            estimated+=height;end+=1
            if estimated>=18 and not lines[end-1].strip():choices.append(end)
        if end<len(lines):
            if choices:end=choices[-1]
        result.append({**block,'text':'\n'.join(lines[start:end]),'title':block['title']+(' · продолжение' if start else '')})
        start=end
    return result

def card(b,n,printing):
    if b['kind']=='image':
        src='assets/screenshots/'+Path(b['path']).name
        return f'<li class="figure-row"><figure><img src="{ESC(src)}" alt="{ESC(b.get("alt",b["text"]))}"><figcaption>{ESC(b["text"])}</figcaption></figure></li>'
    if b['kind']=='code':body='<pre>'+ESC(b['text'])+'</pre>'
    elif b['kind']=='link':
        href=relative_link(b['href'],printing)
        body=f'<p><a href="{ESC(href)}">{ESC(b.get("label",b["title"]))}</a></p>'+paragraphs(b['text'])
    elif b['kind']=='diagram':body=paragraphs(f'Состояние: {b.get("count",0)} из {b.get("target",5)}. '+b['text'])
    else:body=paragraphs(b['text'])
    return f'<li class="step"><span class="number">{n}</span><section class="card"><h3>{ESC(b["title"])}</h3>{body}</section></li>'

def chapter(p,index,printing=False):
    anchor=p.get('anchor',f'section-{index}');cards=[];n=0
    for b in p['blocks']:
        for part in pieces(b):
            n+=part['kind']!='image';cards.append(card(part,n,printing))
    return f'<article class="chapter" id="{ESC(anchor)}"><header class="doc-head"><div class="section-id">{ESC(p.get("kicker","ПМ.12"))}</div><h2>{ESC(p["title"])}</h2></header><ol class="steps">'+''.join(cards)+'</ol></article>'

def shell(title,body,active=None):
    links=[('index.html','Задание'),('lessons.html','Инструкция и образец'),('areas.html','Предметные области')]
    nav=''.join(f'<a href="{url}" '+('aria-current="page"' if url==active else '')+f'>{name}</a>' for url,name in links)
    return f'<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{ESC(title)}</title><link rel="icon" href="assets/favicon.svg"><link rel="stylesheet" href="assets/style.css"></head><body><a class="skip" href="#main">К содержанию</a><nav aria-label="Разделы практики">{nav}</nav><main id="main">{body}</main></body></html>'

def archive(out):
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted((ROOT/'unity-project').rglob('*')):
            rel=p.relative_to(ROOT/'unity-project')
            if not p.is_file() or EXCLUDED.intersection(rel.parts):continue
            if rel.parts[0] not in {'Assets','Packages','ProjectSettings'}:continue
            info=zipfile.ZipInfo(('CrystalRoute'/rel).as_posix(),(2026,11,4,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            z.writestr(info,canonical_bytes(p))

def build(data,out,release=False):
    out=out.resolve()
    if out not in {(ROOT/'site').resolve(),(ROOT/'work/site').resolve()}:raise ValueError('Unexpected output path')
    if out.exists():shutil.rmtree(out)
    (out/'downloads').mkdir(parents=True)
    shutil.copytree(ROOT/'assets',out/'assets');(out/'assets/screenshots').mkdir(exist_ok=True)
    for p in data['guide']:
        for b in p['blocks']:
            if b['kind']=='image':shutil.copyfile(ROOT/b['path'],out/'assets/screenshots'/Path(b['path']).name)
    archive(out/'downloads/CrystalRoute-UnityProject.zip')
    shutil.copyfile(ROOT/'forms/Отчет о выполнении.docx',out/'downloads/Отчет о выполнении.docx')
    for f in data['code_files']:shutil.copyfile(ROOT/f['path'],out/'downloads'/f['name'])
    def pages(items,printing=False):return ''.join(chapter(p,i,printing) for i,p in enumerate(items,1))
    downloads='<div class="actions"><a class="button" href="downloads/assignment.pdf">Задание и методические рекомендации · PDF</a><a class="button" href="downloads/guide.pdf">Список предметных областей · PDF</a></div>'
    selection=next(b for b in data['assignment'][0]['blocks'] if b['title']=='Первый шаг. Определите свой вариант')
    for name,title,items in [('index.html',data['meta']['title'],data['assignment']),('lessons.html','Инструкция и образец',data['guide']),('areas.html','Список предметных областей',data['areas'])]:
        start=''
        if name=='areas.html':
            index=''.join(f'<a href="#{ESC(p["anchor"])}">{i:02}</a>' for i,p in enumerate(items,1))
            start='<ol class="steps">'+card(selection,1,False)+'</ol><div class="variant-index" aria-label="Номера вариантов">'+index+'</div>'
        (out/name).write_text(shell(title,downloads+start+pages(items),name),encoding='utf-8')
    for name,title,items in [('print-method.html','Задание и методические рекомендации',data['assignment']+data['guide']),('print-areas.html','Список предметных областей',data['areas'])]:
        intro=f'<header class="hero"><div class="section-id">ПМ.12 / Прототип мобильной 2D-игры</div><h1>{title}</h1></header>'
        if name=='print-areas.html':
            conditions=next(b for b in data['assignment'][0]['blocks'] if b['title']=='Исходные данные и ресурсы')
            files=next(p for p in data['assignment'] if p.get('anchor')=='files')
            method_url=next(b['href'] for b in data['areas'][0]['blocks'] if b['kind']=='link')
            method_link={'kind':'link','title':'Скачать методические рекомендации (PDF)','text':'Задание, общий образец и разделы по игровым правилам.','href':method_url}
            links=[method_link]+[b for b in files['blocks'] if b.get('href','').endswith('.docx')]
            intro+='<ol class="steps">'+card(selection,1,True)+card(conditions,2,True)+''.join(card(b,i,True) for i,b in enumerate(links,3))+'</ol>'
        section='method' if name=='print-method.html' else 'areas'
        (out/name).write_text(shell(title,f'<div class="{section}">'+intro+pages(items,True)+'</div>'),encoding='utf-8')
    for old,new in [('example.html','index.html'),('example-guide.html','lessons.html'),('example-result.html','lessons.html')]:
        (out/old).write_text(f'<!doctype html><meta http-equiv="refresh" content="0;url={new}"><a href="{new}">Открыть материал</a>',encoding='utf-8')
    (out/'.nojekyll').touch()
    subprocess.run([os.environ.get('NODE_BIN','node'),str(ROOT/'scripts/export_pdf.cjs'),str(out)],check=True)
    from pypdf import PdfReader
    files={p.relative_to(out).as_posix():hashlib.sha256(canonical_bytes(p)).hexdigest() for p in sorted(out.rglob('*')) if p.is_file()}
    manifest={'release':release,'source_sha256':source_fingerprint(),'files':files,'pages':{name:len(PdfReader(out/'downloads'/name).pages) for name in ('assignment.pdf','guide.pdf')}}
    if release:manifest['checks']={k:True for k in ('unity','variants','visual','audit')}
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Built',out,manifest['pages'])

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--release',action='store_true');args=parser.parse_args()
    data=load_course();validate(data,args.release)
    if args.release:require_release_evidence()
    build(data,ROOT/('site' if args.release else 'work/site'),args.release)
