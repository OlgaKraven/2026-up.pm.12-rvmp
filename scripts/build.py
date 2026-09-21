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
from reportlab.platypus import Paragraph, Image as FlowImage, Table, TableStyle
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
            if 'code_file' in block:
                lines=sources[block['code_file']].splitlines()
                start,end=block['code_lines']
                block['text']='\n'.join(lines[start:end])
    data['_code_sources']=sources
    return data

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
    W, H = 841.89, 595.28  # A4 landscape, points
    margin, gap = 38, 28
    colw = (W - 2 * margin - gap) / 2
    c = canvas.Canvas(str(path), pagesize=(W, H))
    c.setTitle(f"{name} · {data['title']}")
    c.setAuthor(data["organization"])
    body = ParagraphStyle("body", fontName="Body", fontSize=13.5, leading=19, textColor=colors.HexColor("#30343b"), splitLongWords=True)
    head = ParagraphStyle("head", fontName="Bold", fontSize=14, leading=18, textColor=colors.HexColor("#1c1c1c"))
    code = ParagraphStyle("code", fontName="Mono", fontSize=9.2, leading=11.3, textColor=colors.HexColor("#22252a"), splitLongWords=True)
    def content(block):
        if block.get('kind') == 'image':
            item=FlowImage(str(ROOT/block['path']))
            item._restrictSize(colw, 205)
            caption=Paragraph(ESC(block['text']), body)
            return Table([[item],[caption]],colWidths=[colw],style=TableStyle([
                ('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),
                ('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(0,0),7),
            ]))
        if block.get('kind') == 'diagram': return diagram(block)
        raw = ESC(block['text']).replace('\n', '<br/>')
        if block.get('kind') == 'code': raw=raw.replace(' ', '&#160;')
        return Paragraph(raw, code if block.get('kind') == 'code' else body)
    for spec in pages:
        for block in spec["blocks"]:
            if block.get("kind") == "code":
                for line in block["text"].splitlines():
                    if pdfmetrics.stringWidth(line, "Mono", 9.2) > W - 2 * margin:
                        raise ValueError(f"Строка кода слишком длинная; разбейте выражение вручную: {spec['title']}: {line}")
    title_style = ParagraphStyle("title", fontName="Bold", fontSize=23, leading=28)
    page_no = 0
    records = []

    def frame(title, kicker, continuation=False):
        nonlocal page_no
        page_no += 1
        c.bookmarkPage(f"page-{page_no}")
        c.addOutlineEntry(title + (" · продолжение" if continuation else ""), f"page-{page_no}", level=0)
        c.setFillColor(colors.HexColor("#ed131c")); c.rect(margin, H - 35, 28, 5, fill=1, stroke=0)
        c.setFont("Bold", 8); c.setFillColor(colors.HexColor("#626975"))
        c.drawString(margin + 39, H - 36, kicker[:77])
        if data["status"] == "template":
            c.drawRightString(W - margin, H - 36, "ШАБЛОН · ДЛЯ ЗАПОЛНЕНИЯ")
        p = Paragraph(ESC(title + (" · продолжение" if continuation else "")), title_style)
        _, height = p.wrap(W - 2 * margin, 100)
        p.drawOn(c, margin, H - 54 - height)
        c.setStrokeColor(colors.HexColor("#dfe1e5")); c.line(margin, 37, W - margin, 37)
        c.setFont("Body", 8); c.setFillColor(colors.HexColor("#626975"))
        c.drawString(margin, 22, f"{name} · версия {data['version']}")
        c.drawRightString(W - margin, 22, f"{page_no:02}")
        records.append({"number": page_no, "title": title, "continuation": continuation})
        return H - 72 - height

    # The cover is a teaching page, not a portrait title sheet.
    top = frame(data["title"], "Учебно-методический комплект")
    c.setFillColor(colors.HexColor("#1c1c1c")); c.roundRect(margin, top - 162, W - 2 * margin, 148, 12, fill=1, stroke=0)
    cover_style = ParagraphStyle("cover", fontName="Bold", fontSize=29, leading=35, textColor=colors.white)
    p = Paragraph(ESC(name), cover_style); _, ph = p.wrap(W - 2 * margin - 48, 100); p.drawOn(c, margin + 24, top - 40 - ph)
    c.setFont("Body", 12); c.setFillColor(colors.HexColor("#e6e6e9")); c.drawString(margin + 24, top - 133, "Теория → образец → адаптация → проверка → результат")
    meta = [data["subtitle"], data["organization"], data["specialty"], f"{data['group']} · {data['module']}", f"Объём: {data['hours']} · Версия {data['version']}"]
    y = top - 186
    for text in meta:
        p = Paragraph(ESC(text), body); _, ph = p.wrap(W - 2 * margin, 100); p.drawOn(c, margin, y - ph); y -= ph + 9
    c.showPage()

    for spec in pages:
        ytop = frame(spec["title"], spec["kicker"])
        if any(block.get('kind') == 'code' for block in spec['blocks']):
            code_block=next(block for block in spec['blocks'] if block.get('kind')=='code')
            before=[]; after=[]; found=False
            for block in spec['blocks']:
                if block is code_block:
                    found=True
                elif found:
                    after.append(block)
                else:
                    before.append(block)
            fullw=W-2*margin
            y=ytop
            for block in before:
                title=Paragraph(ESC(block['title']),head)
                para=content(block)
                _,hh=title.wrap(fullw,100); _,bh=para.wrap(fullw,500)
                title.drawOn(c,margin,y-hh); y-=hh+5
                para.drawOn(c,margin,y-bh); y-=bh+12
            title=Paragraph(ESC(code_block['title']),head)
            para=content(code_block)
            _,hh=title.wrap(fullw,100); _,bh=para.wrap(fullw,1000)
            title.drawOn(c,margin,y-hh); y-=hh+5
            para.drawOn(c,margin,y-bh); y-=bh+14
            if after:
                note_gap=28
                note_w=(fullw-note_gap)/2
                max_height=0
                for index,block in enumerate(after[:2]):
                    x=margin+index*(note_w+note_gap)
                    title=Paragraph(ESC(block['title']),head)
                    para=content(block)
                    _,hh=title.wrap(note_w,100); _,bh=para.wrap(note_w,500)
                    title.drawOn(c,x,y-hh)
                    para.drawOn(c,x,y-hh-6-bh)
                    max_height=max(max_height,hh+6+bh)
                y-=max_height
            if y < 48:
                raise ValueError(f"Код и пояснения не помещаются на страницу: {spec['title']}")
            c.showPage()
            continue
        y, col = ytop, 0
        # Balance complete blocks between columns when the semantic page fits.
        heights = []
        for block in spec["blocks"]:
            raw = ESC(block["text"]).replace("\n", "<br/>")
            if block.get("kind") == "code": raw = raw.replace(" ", "&#160;")
            heights.append(Paragraph(ESC(block["title"]), head).wrap(colw, 2000)[1] + 7 + content(block).wrap(colw, 4000)[1] + 19)
        cut = min(range(1, len(heights)), key=lambda k: max(sum(heights[:k]), sum(heights[k:]))) if len(heights)>1 else -1
        balanced = cut > 0 and max(sum(heights[:cut]),sum(heights[cut:])) <= ytop - 54 + 19
        for block_index, block in enumerate(spec["blocks"]):
            if balanced and block_index == cut:
                col, y = 1, ytop
            kind = block.get("kind", "text")
            title = Paragraph(ESC(block["title"]), head)
            text = ESC(block["text"]).replace("\n", "<br/>")
            if kind == "code":
                text = text.replace(" ", "&#160;")
            para = content(block)
            _, hh = title.wrap(colw, 100)
            _, bh = para.wrap(colw, 2000)
            needed = hh + bh + 7 if hh + bh + 7 <= ytop - 54 else hh + 48 + 18
            if y - needed < 54:
                if col == 0:
                    col, y = 1, ytop
                else:
                    c.showPage(); ytop = frame(spec["title"], spec["kicker"], True); col, y = 0, ytop
            x = margin + col * (colw + gap)
            title.drawOn(c, x, y - hh); y -= hh + 7
            pending = [para]
            while pending:
                item = pending.pop(0)
                _, ih = item.wrap(colw, 2000)
                avail = y - 54
                if ih <= avail:
                    item.drawOn(c, x, y - ih); y -= ih + 19
                else:
                    parts = item.split(colw, avail)
                    if parts:
                        _, fh = parts[0].wrap(colw, avail)
                        parts[0].drawOn(c, x, y - fh)
                        pending = parts[1:] + pending
                    else:
                        pending.insert(0, item)
                    if col == 0:
                        col, y = 1, ytop
                    else:
                        c.showPage(); ytop = frame(spec["title"], spec["kicker"], True); col, y = 0, ytop
                    x = margin + col * (colw + gap)
                    label = Paragraph(ESC(block["title"] + " · продолжение"), head)
                    _, lh = label.wrap(colw, 100); label.drawOn(c, x, y - lh); y -= lh + 7
        c.showPage()
    c.save()
    return records

def block_html(block):
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

def page_html(page, i):
    anchor = page.get("anchor", f"page-{i}")
    return f'<article class="lesson" id="{anchor}"><p class="eyebrow">{ESC(page["kicker"])}</p><h2>{ESC(page["title"])}</h2><div class="blocks">' + "".join(block_html(b) for b in page["blocks"]) + '</div></article>'

def shell(data, active, title, lead, body):
    links = [("index.html", "Задание"), ("lessons.html", "Инструкция и образец"), ("areas.html", "Предметные области")]
    nav = "".join(f'<a {"aria-current=page" if url == active else ""} href="{url}">{label}</a>' for url, label in links)
    mark = '<span class="badge">Шаблон для заполнения</span>' if data["status"] == "template" else '<span class="badge">Заполненный пример</span>' if data['status']=='example' else '<span class="badge">Учебный комплект</span>'
    return f'''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Универсальный шаблон практик: страницы для вебинара и автономные учебные PDF."><title>{ESC(title)} · {ESC(data['title'])}</title><link rel="icon" href="assets/favicon.svg"><link rel="stylesheet" href="assets/style.css"></head><body><a class="skip" href="#main">Перейти к содержанию</a><header class="shell top"><a class="brand" href="index.html"><span class="emblem">ПР</span><span><strong>Практика / Методические материалы</strong><small>{ESC(data['subtitle'])}</small></span></a><span class="version">Версия {ESC(data['version'])}</span></header><div class="shell"><nav aria-label="Основная навигация">{nav}</nav><main id="main"><section class="hero"><p class="eyebrow">Учебный маршрут / 2026</p><h1>{ESC(title)}</h1><p>{ESC(lead)}</p>{mark}</section>{body}</main><footer><span>Материалы для обзора преподавателем</span><span>PDF A4 · альбомная ориентация · единый источник</span></footer></div></body></html>'''

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
        'assignment':pdf(OUT/'downloads/assignment.pdf',meta,assignment,'Задание студенту'),
        'guide':pdf(OUT/'downloads/guide.pdf',meta,data['guide'],'Пошаговая инструкция'),
    }
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
    def pages(items): return ''.join(page_html(p,i) for i,p in enumerate(items,1))
    def write(file,title,lead,body):
        (OUT/file).write_text(shell(meta,file,title,lead,body),encoding='utf-8')
    write('index.html',meta['title'],'Условия, этапы выполнения и сдача задания.',
          '<div class="downloads"><a class="button primary" href="downloads/assignment.pdf">Задание студенту · PDF</a></div>'+pages(data['assignment']))
    code_links=''.join(f'<a class="button" href="downloads/{ESC(item["name"])}">{ESC(item["name"])}</a>' for item in data['code_files'])
    write('lessons.html','Как выполнить задание','Теория, микро-шаги, снимки работающего прототипа и полный код. Выдаётся по решению преподавателя.',
          '<div class="downloads"><a class="button primary" href="downloads/guide.pdf">Инструкция · PDF</a><a class="button primary" href="downloads/CrystalRoute-UnityProject.zip">Unity-проект · ZIP</a>'+code_links+'</div>'+pages(data['guide']))
    write('areas.html','Предметные области','Индивидуальные условия задания. Номер варианта назначает преподаватель.',pages(data['areas']))
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
    build(data)
