"""Check prepared teaching artifacts; keep runtime acceptance separate."""
import argparse
import hashlib
from html.parser import HTMLParser
import json
import logging
from pathlib import Path
import re
from urllib.parse import unquote,urlsplit
import zipfile
from lxml import etree
import pdfplumber
from pypdf import PdfReader
from build import ROOT,load_course,validate,source_fingerprint,EXCLUDED

logging.getLogger('pdfminer').setLevel(logging.ERROR)

class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[];self.ids=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if 'id' in attrs:self.ids.append(attrs['id'])
        for key in ('href','src'):
            if key in attrs:self.links.append(attrs[key])

def compact(text):return re.sub(r'\s+','',text)

def check(site,release=False):
    data=load_course();validate(data,release)
    parsers={}
    for file in site.glob('*.html'):
        p=Links();p.feed(file.read_text(encoding='utf-8'));parsers[file.resolve()]=p
        assert len(p.ids)==len(set(p.ids)),('Duplicate anchors',file)
    for file,p in parsers.items():
        for link in p.links:
            part=urlsplit(link)
            if part.scheme or part.netloc:continue
            target=(file.parent/unquote(part.path)).resolve() if part.path else file
            assert target.is_file(),(file.name,link)
            if part.fragment:assert part.fragment in parsers[target].ids,link
    manifest=json.loads((site/'manifest.json').read_text(encoding='utf-8'))
    assert manifest['source_sha256']==source_fingerprint(),'Rebuild changed source'
    assert manifest['release'] is release
    if release:assert all(manifest.get('checks',{}).get(k) is True for k in ('unity','variants','visual','audit'))
    for name,sha in manifest['files'].items():assert hashlib.sha256((site/name).read_bytes()).hexdigest()==sha,name
    result={'release':release,'source_sha256':manifest['source_sha256'],'variants':30,'stand_archives':0,'pdf':{}}
    for filename,pages in [('assignment.pdf',data['assignment']+data['guide']),('guide.pdf',data['areas'])]:
        reader=PdfReader(site/'downloads'/filename)
        assert len(reader.pages)==manifest['pages'][filename]
        all_text='';fonts=set();overflows=[]
        with pdfplumber.open(site/'downloads'/filename) as pdf:
            for i,p in enumerate(pdf.pages,1):
                assert abs(p.width-595.276)<1 and abs(p.height-841.89)<1
                body=[c for c in p.chars if c['top']<795]
                for c in body:
                    if c.get('text','').strip() and (c['x0']<84 or c['x1']>539.6 or c['top']<55 or c['bottom']>787):overflows.append((i,c['text'],round(c['x0'],1),round(c['top'],1)))
                    fonts.add((c['fontname'].split('+')[-1],round(c['size'],1)))
                all_text+=(p.crop((0,0,p.width,795)).extract_text(x_tolerance=2) or '')
        assert not overflows,(filename,overflows[:12])
        normalized=compact(all_text)
        missing=[]
        for page in pages:
            for b in page['blocks']:
                if b['kind']=='image':continue
                for line in b['text'].splitlines():
                    if line.strip() and compact(line) not in normalized:missing.append(line[:100])
        assert not missing,(filename,'Lost text',missing[:5])
        assert any(size==10.5 for _,size in fonts),fonts
        assert any('Golos' in name for name,_ in fonts),fonts
        assert any(a.get_object().get('/A',{}).get('/URI') for p in reader.pages for a in p.get('/Annots',[]))
        result['pdf'][filename]={'pages':len(reader.pages),'fonts':sorted(fonts),'text_and_bounds':True}
    with zipfile.ZipFile(site/'downloads/CrystalRoute-UnityProject.zip') as z:
        for name in z.namelist():
            p=Path(name);assert not EXCLUDED.intersection(p.parts)
            assert z.read(name)==(ROOT/'unity-project'/Path(*p.parts[1:])).read_bytes(),name
    ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    master=ROOT/'forms/template/Отчет о выполнении.docx'
    report=site/'downloads/Отчет о выполнении.docx'
    with zipfile.ZipFile(master) as m,zipfile.ZipFile(report) as z:
        for name in m.namelist():
            if name not in {'word/document.xml','docProps/core.xml'}:assert z.read(name)==m.read(name),name
        doc=etree.fromstring(z.read('word/document.xml'))
    tags=doc.xpath('//w:sdtPr/w:tag/@w:val',namespaces=ns);assert len(tags)==len(set(tags))
    ids=doc.xpath('//w:sdtPr/w:id/@w:val',namespaces=ns);assert len(ids)==len(set(ids))
    captions=[]
    for p in doc.xpath('//w:p[w:r/w:instrText[contains(.,"SEQ Рисунок")]]',namespaces=ns):captions.append(''.join(p.xpath('.//w:t/text()',namespaces=ns)))
    wanted=[c for s in data['report']['sections'] for c in s['screenshots']]
    assert len(captions)==len(wanted)==14
    for i,(actual,label) in enumerate(zip(captions,wanted),1):assert actual==f'Рисунок {i} — '+label[:1].lower()+label[1:],actual
    report_text=''.join(doc.xpath('//w:t/text()',namespaces=ns))
    assert 'Университет "Синергия"' in report_text
    assert 'Содержание' not in report_text and 'Использованные источники' not in report_text
    assert 'Ссылка на репозиторий' in report_text
    for heading in data['report']['main_sections']:assert heading in report_text
    slots=doc.xpath('//w:tr[w:tc//w:sdtPr/w:tag[starts-with(@w:val,"pm12_figure_")]]',namespaces=ns)
    assert len(slots)==14
    for tr in slots:
        height=tr.find('w:trPr/w:trHeight',ns)
        assert int(height.get('{'+ns['w']+'}val'))>=3400
        assert height.get('{'+ns['w']+'}hRule')=='atLeast'
    result['report']={'common_master_preserved':True,'stages':5,'figure_slots':14,'unique_fields':True}
    result['unity_executed']=False
    (ROOT/'work/material-check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('PASS: 30 cards without stands, links, source ZIP, PDF text/fonts/bounds and common report; Unity not executed')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--release',action='store_true');args=parser.parse_args()
    check(ROOT/('site' if args.release else 'work/site'),args.release)
