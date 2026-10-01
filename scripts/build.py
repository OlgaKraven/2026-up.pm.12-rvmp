"""Build an offline teacher site and two landscape student PDFs from one source."""
import argparse
import html
import json
import re
import shutil
import hashlib
import zipfile
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, Image as FlowImage, Table, TableStyle, SimpleDocTemplate, PageBreak, Spacer, KeepTogether, Preformatted
from reportlab.graphics.shapes import Drawing, Rect, Circle, String
from reportlab.graphics import renderSVG

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "site"
ESC = html.escape

def load_course():
    data=json.loads((ROOT/'content/course.json').read_text(encoding='utf-8'))
    sources={item['name']:(ROOT/item['path']).read_text(encoding='utf-8') for item in data['code_files']}
    for page in data['guide']:
        for block in page['blocks']:
            if 'snippet_file' in block:
                block['text']=(ROOT/block['snippet_file']).read_text(encoding='utf-8').rstrip()
            if 'code_file' in block:
                lines=sources[block['code_file']].splitlines()
                start,end=block['code_lines']
                block['text']='\n'.join(lines[start:end])
    # Publish every variant as an independent card; source grouping is only a compact
    # authoring convenience and is never shown to students.
    variants=[]
    for area in data['areas']:
        for block in area['blocks']:
            number=re.search(r'Вариант\s+(\d+)',block['title']).group(1)
            parts=[]
            for line in block['text'].splitlines():
                label, value=line.split(': ',1)
                parts.append({'title':label,'text':value,'kind':'text'})
            variants.append({
                'title':block['title'],
                'kicker':f'Индивидуальный вариант {number} / выполнить полностью',
                'anchor':f'variant-{number}',
                'blocks':[ *block.get('materials', []), *parts],
            })
    data['areas']=variants
    # A screenshot gets a separate page so that controls and labels remain readable.
    expanded=[]
    for page in data['guide']:
        images=[block for block in page['blocks'] if block.get('kind')=='image']
        trailing=[block for block in page['blocks'] if images and block['title']=='Регрессия']
        text_blocks=[block for block in page['blocks'] if block.get('kind')!='image' and block not in trailing]
        if text_blocks:
            expanded.append({**page,'blocks':text_blocks})
        for index,block in enumerate(images,1):
            block['wide']=True
            suffix=f' · изображение {index}' if len(images)>1 else ''
            expanded.append({
                'title':page['title']+suffix,
                'kicker':page['kicker']+' / крупный снимок',
                'blocks':[block, *(trailing if index==len(images) else [])],
            })
    data['guide']=expanded
    data['_code_sources']=sources
    return data

def source_fingerprint(root=ROOT):
    """Hash all deliverable inputs in stable path order, independent of OS fonts."""
    paths = [root/'content/course.json', root/'scripts/build.py', root/'scripts/check.py']
    for folder in ('assets', 'tutorial', 'unity-project'):
        paths.extend(p for p in (root/folder).rglob('*') if p.is_file()
                     and not {'Library','Temp','Logs','obj','UserSettings','Build'}.intersection(p.relative_to(root).parts))
    digest = hashlib.sha256()
    for path in sorted(set(paths)):
        digest.update(path.relative_to(root).as_posix().encode('utf-8') + b'\0')
        digest.update(path.read_bytes() + b'\0')
    return digest.hexdigest()


def validate(data, release=False):
    for key in ('meta','assignment','guide','areas','code_files'):
        if not data.get(key): raise ValueError(f'Нет обязательного раздела: {key}')
    for key in ('assignment','guide','areas'):
        for page in data[key]:
            if not page.get('title') or not page.get('blocks'): raise ValueError('Неполная страница')
            for block in page['blocks']:
                if not block.get('title') or not block.get('text'): raise ValueError('Неполный блок')
    if release and (data['meta']['status']!='ready' or 'ЗАПОЛНИТЬ' in json.dumps(data,ensure_ascii=False)):
        raise ValueError('Перед выдачей заполните реквизиты и установите meta.status=ready')

def fonts():
    candidates = [
        (Path("C:/Windows/Fonts"), "arial.ttf", "arialbd.ttf", "consola.ttf"),
        (Path("/usr/share/fonts/truetype/dejavu"), "DejaVuSans.ttf", "DejaVuSans-Bold.ttf", "DejaVuSansMono.ttf"),
        (Path("/System/Library/Fonts/Supplemental"), "Arial.ttf", "Arial Bold.ttf", "Courier New.ttf"),
    ]
    for root, regular, bold, mono in candidates:
        if all((root / x).exists() for x in (regular, bold, mono)):
            for name, file in [("Body", regular), ("Bold", bold), ("Mono", mono)]:
                pdfmetrics.registerFont(TTFont(name, str(root / file)))
            return
    raise RuntimeError("Нужны системные шрифты Arial/Consolas (Windows) или DejaVu (Linux)")

def diagram(block):
    d = Drawing(350, 174)
    d.add(Rect(0, 0, 350, 174, rx=10, ry=10, fillColor=colors.HexColor('#f4f4f6'), strokeColor=colors.HexColor('#dfe1e5')))
    count, target = block['count'], block['target']
    d.add(String(18, 145, f"Собрано: {count} из {target}", fontName='Bold', fontSize=17))
    for i in range(target):
        x=35+i*55
        d.add(Circle(x, 103, 18, fillColor=colors.HexColor('#ed131c') if i<count else colors.white, strokeColor=colors.HexColor('#777777')))
        d.add(String(x, 97, str(i+1), textAnchor='middle', fontName='Bold', fontSize=14, fillColor=colors.white if i<count else colors.HexColor('#333333')))
    d.add(String(18, 56, 'Цель достигнута' if count==target else 'Можно добавить предмет', fontName='Body', fontSize=13))
    d.add(String(18, 26, block['text'], fontName='Body', fontSize=11))
    return d

def pdf(path, data, pages, name):
    W, H = 841.89, 595.28
    width=W-76
    body=ParagraphStyle('body',fontName='Body',fontSize=12,leading=16,spaceAfter=8)
    head=ParagraphStyle('head',fontName='Bold',fontSize=14,leading=18,spaceBefore=7,spaceAfter=5,keepWithNext=True)
    title=ParagraphStyle('title',fontName='Bold',fontSize=23,leading=28,spaceAfter=14,keepWithNext=True)
    mono=ParagraphStyle('code',fontName='Mono',fontSize=9.2,leading=12,spaceAfter=12)
    compact_body=ParagraphStyle('compact-body',parent=body,leading=15,spaceAfter=5)
    compact_head=ParagraphStyle('compact-head',parent=head,spaceBefore=5,spaceAfter=4)
    records=[]; story=[]
    def heading(text): story.append(Paragraph(ESC(text),title))
    heading(name)
    for text in [data['title'],data['subtitle'],data['organization'],data['specialty'],data['module']]:
        story.append(Paragraph(ESC(text),body))
    story.append(Paragraph('Версия '+ESC(data['version']),body))
    for spec in pages:
        if name=='Список предметных областей' or len(story)<10 or any(b.get('kind')=='image' for b in spec['blocks']):
            story.append(PageBreak())
        else:
            story.append(Spacer(1,16))
        heading(spec['title'])
        compact=spec['title'].startswith(('Выборочный сбор /','Сбор по порядку /','Подбор и доставка /','Ограниченная вместимость /','Комплектование /','Ключи, переключатели и доступ /'))
        body_style=compact_body if compact else body
        head_style=compact_head if compact else head
        for block in spec['blocks']:
            kind=block.get('kind','text')
            if kind!='link': story.append(Paragraph(ESC(block['title']),head_style))
            if kind=='code':
                for line in block['text'].splitlines():
                    if pdfmetrics.stringWidth(line,'Mono',9.2)>width:
                        raise ValueError('Code line too long: '+line)
                story.append(Preformatted(block['text'],mono))
            elif kind=='image':
                im=FlowImage(str(ROOT/block['path']));im._restrictSize(width,320)
                story.append(KeepTogether([im,Spacer(1,8),Paragraph(ESC(block['text']),body_style)]))
            elif kind=='link':
                text='<link href="'+ESC(block['href'])+'" color="#125eab">'+ESC(block['title'])+'</link><br/>'+ESC(block['text'])
                story.append(Paragraph(text,body_style))
            else: story.append(Paragraph(ESC(block['text']).replace('\n','<br/>'),body_style))
    def frame(c,doc):
        c.setTitle(name+' · '+data['title']);c.setAuthor(data['organization'])
        c.setFillColor(colors.HexColor('#ed131c'));c.rect(38,H-27,28,4,fill=1,stroke=0)
        c.setFont('Body',8);c.setFillColor(colors.HexColor('#626975'))
        c.drawString(78,H-28,'ПМ.12 / Методические материалы / Версия '+data['version'])
        c.setStrokeColor(colors.HexColor('#dfe1e5'));c.line(38,32,W-38,32)
        c.drawString(38,18,'ПМ.12 / '+name);c.drawRightString(W-38,18,str(doc.page))
        records.append({'number':doc.page,'title':name})
    SimpleDocTemplate(str(path),pagesize=(W,H),leftMargin=38,rightMargin=38,
        topMargin=45,bottomMargin=45).build(story,onFirstPage=frame,onLaterPages=frame)
    return records


def report_template(data):
    family="font-family:'Times New Roman';color:#000;"
    para=family+'font-size:14pt;text-align:justify;line-height:1.5;text-indent:1.25cm;'
    h2=family+'font-size:14pt;text-align:justify;line-height:1.5;'
    result=['<div style="'+family+'">', '<h1 style="'+family+'font-size:16pt;text-align:center;line-height:1.5;text-transform:uppercase">ОТЧЁТ ПО УЧЕБНОЙ ПРАКТИКЕ ПМ.12</h1>']
    for label in ['ФИО','Группа','Номер варианта','Предметная область','Дата','Версия программы Unity','Ссылка на репозиторий проекта']:
        result.append('<p style="'+para+'">'+label+': ____________________</p>')
    number=0
    for section in data['report']['sections']:
        result.extend(['<h2 style="'+h2+'">'+ESC(section['title'])+'</h2>', '<p style="'+para+'">'+ESC(section['prompt'])+'</p>'])
        for caption in section['screenshots']:
            number+=1
            result.extend(['<div style="page-break-inside:avoid;break-inside:avoid">',
                '<table width="100%" border="1" cellspacing="0" cellpadding="0" style="border-collapse:collapse"><tr><td height="220" style="border:1px solid #000;height:220px;text-align:center;vertical-align:middle;'+family+'font-size:12pt">Вставьте скриншот</td></tr></table>',
                '<p style="'+family+'font-size:12pt;text-align:center;line-height:1">Рисунок '+str(number)+' — '+ESC(caption)+'</p></div>'])
    result.append('</div>');return '\n'.join(result)+'\n'

def block_html(block, site_url=""):
    block=dict(block)
    prefix=site_url.rstrip("/")+"/"
    if site_url and block.get("href", "").startswith(prefix): block["href"]=block["href"][len(prefix):]
    if block.get('kind')=='link':
        return '<section class="block"><h3><a href="'+ESC(block['href'])+'">'+ESC(block['title'])+'</a></h3><p>'+ESC(block['text'])+'</p></section>'

    if block.get('kind') == 'image':
        filename=Path(block['path']).name
        return f'<figure class="block screenshot"><h3>{ESC(block["title"])}</h3><img src="assets/screenshots/{ESC(filename)}" alt="{ESC(block.get("alt",block["title"]))}"><figcaption>{ESC(block["text"])}</figcaption></figure>'
    if block.get('kind') == 'diagram':
        suffix=hashlib.sha256(block['text'].encode('utf-8')).hexdigest()[:8]
        filename=f"state-{block['count']}-{block['target']}-{suffix}.svg"
        renderSVG.drawToFile(diagram(block), str(OUT / 'assets' / filename))
        svg=OUT/'assets'/filename
        svg.write_text(svg.read_text(encoding='utf-8').replace('font-family: Bold;', 'font-family: Arial, sans-serif; font-weight: bold;').replace('font-family: Body;', 'font-family: Arial, sans-serif;'),encoding='utf-8')
        return f'<figure class="block"><h3>{ESC(block["title"])}</h3><img style="width:100%;max-width:500px" src="assets/{filename}" alt="Собрано {block["count"]} из {block["target"]}. {ESC(block["text"])}"><figcaption>Схема состояния, не снимок интерфейса Unity.</figcaption></figure>'
    tag = "pre" if block.get("kind") == "code" else "p"
    content = ESC(block["text"])
    if tag != "pre": content = content.replace("\n", "<br>")
    return f'<section class="block {ESC(block.get("kind", "text"))}"><h3>{ESC(block["title"])}</h3><{tag}>{content}</{tag}></section>'

def page_html(page, i, site_url=""):
    anchor = page.get("anchor", f"page-{i}")
    return f'<article class="lesson" id="{anchor}"><p class="eyebrow">{ESC(page["kicker"])}</p><h2>{ESC(page["title"])}</h2><div class="blocks">' + "".join(block_html(b, site_url) for b in page["blocks"]) + '</div></article>'

def shell(data, active, title, lead, body):
    links = [("index.html", "Задание"), ("lessons.html", "Инструкция и образец"), ("areas.html", "Предметные области")]
    nav = "".join(f'<a {"aria-current=page" if url == active else ""} href="{url}">{label}</a>' for url, label in links)
    mark = '<span class="badge">Шаблон для заполнения</span>' if data["status"] == "template" else '<span class="badge">Заполненный пример</span>' if data['status']=='example' else '<span class="badge">Учебный комплект</span>'
    return f'''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Универсальный шаблон практик: страницы для вебинара и автономные учебные PDF."><title>{ESC(title)} · {ESC(data['title'])}</title><link rel="icon" href="assets/favicon.svg"><link rel="stylesheet" href="assets/style.css"></head><body><a class="skip" href="#main">Перейти к содержанию</a><header class="shell top"><a class="brand" href="index.html"><span class="emblem">ПР</span><span><strong>Практика / Методические материалы</strong><small>{ESC(data['subtitle'])}</small></span></a><span class="version">Версия {ESC(data['version'])}</span></header><div class="shell"><nav aria-label="Основная навигация">{nav}</nav><main id="main"><section class="hero"><p class="eyebrow">Учебный маршрут / 2026</p><h1>{ESC(title)}</h1><p>{ESC(lead)}</p>{mark}</section>{body}</main><footer><span>Материалы для самостоятельной работы и проверки</span><span>PDF A4 · альбомная ориентация · единый источник</span></footer></div></body></html>'''

def build(data):
    # Only this generated directory is replaced; never delete source directories.
    target=OUT.resolve()
    if target != ROOT.resolve()/'site' or target.parent != ROOT.resolve():
        raise ValueError('Unexpected output directory')
    if target.exists(): shutil.rmtree(target)
    (OUT/'assets').mkdir(parents=True)
    (OUT/'downloads').mkdir()
    (OUT/'assets'/'screenshots').mkdir()
    for name in ('style.css','favicon.svg'):
        shutil.copyfile(ROOT/'assets'/name,OUT/'assets'/name)
    for page in data['guide']:
        for item in page['blocks']:
            if item.get('kind')=='image':
                shutil.copyfile(ROOT/item['path'],OUT/'assets'/'screenshots'/Path(item['path']).name)
    fonts()
    meta=data['meta']
    assignment=data['assignment']+data['areas']
    manifest={
        'assignment':pdf(OUT/'downloads/assignment.pdf',meta,assignment,'Список предметных областей'),
        'guide':pdf(OUT/'downloads/guide.pdf',meta,data['guide'],'Пошаговая инструкция'),
    }
    (OUT/'downloads/report-template.md').write_text(report_template(data),encoding='utf-8')
    manifest['release']=data.get('_release',False)
    manifest['source_sha256']=source_fingerprint()
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    for item in data['code_files']:
        shutil.copyfile(ROOT/item['path'],OUT/'downloads'/item['name'])
    archive=OUT/'downloads'/'CrystalRoute-UnityProject.zip'
    excluded={'Library','Temp','Logs','obj','UserSettings','Build'}
    project=ROOT/'unity-project'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as package:
        for source in sorted(project.rglob('*')):
            relative=source.relative_to(project)
            if source.is_dir() or any(part in excluded for part in relative.parts):
                continue
            package.write(source,Path('CrystalRoute')/relative)
    def pages(items): return ''.join(page_html(p,i,meta.get("site_url", "")) for i,p in enumerate(items,1))
    def write(file,title,lead,body):
        (OUT/file).write_text(shell(meta,file,title,lead,body),encoding='utf-8')
    write('index.html',meta['title'],'Условия, этапы выполнения и сдача задания.',
          '<div class="downloads"><a class="button primary" href="downloads/assignment.pdf">Список предметных областей · PDF</a></div>'+pages(data['assignment']))
    code_links=''.join(f'<a class="button" href="downloads/{ESC(item["name"])}">Скачать исходник {ESC(item["name"])} для сверки кода</a>' for item in data['code_files'])
    write('lessons.html','Как выполнить задание','Объяснения, логические блоки кода, рабочие контрольные точки и снимки интерфейса. Движение → взаимодействия → индивидуальное правило → проверка и повтор.',
          '<div class="downloads"><a class="button primary" href="downloads/guide.pdf">Скачать методичку по созданию и проверке игры (PDF)</a><a class="button primary" href="downloads/CrystalRoute-UnityProject.zip">Скачать пример «Кристальный маршрут» для сверки (ZIP)</a><a class="button" href="downloads/report-template.md">Скачать общий шаблон отчёта</a>'+code_links+'</div>'+pages(data['guide']))
    write('areas.html','Список предметных областей','Индивидуальные условия задания. Номер варианта назначает преподаватель.',pages(data['areas']))
    # Compatibility addresses contain no educational content or duplicate files.
    for old,new in [('example.html','index.html'),('example-guide.html','lessons.html'),('example-result.html','lessons.html')]:
        (OUT/old).write_text(f'<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta http-equiv="refresh" content="0;url={new}"><title>Страница перенесена</title></head><body><a href="{new}">Открыть материал</a></body></html>',encoding='utf-8')
    (OUT/'.nojekyll').touch()
    print('Built: 3 sections, 2 PDFs, 1 source of content')

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--release',action='store_true')
    args=parser.parse_args()
    data=load_course()
    validate(data,args.release)
    if args.release:
        proof=json.loads((ROOT/'verification/release.json').read_text(encoding='utf-8'))
        actual=source_fingerprint()
        if proof.get('source_sha256')!=actual or not all(proof.get('checks',{}).get(k)==True for k in ['unity','variants','visual','audit']):
            raise ValueError('Current real verification and audit reconciliation required')
    data['_release']=args.release
    build(data)
