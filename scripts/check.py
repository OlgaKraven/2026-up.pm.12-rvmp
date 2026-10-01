"""Check one complete kit and prevent duplicate outputs from returning."""
import json
import re
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote
from pypdf import PdfReader
from build import ROOT, load_course, validate, source_fingerprint

class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]; self.ids=set()
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if 'id' in attrs: self.ids.add(attrs['id'])
        for key in ('href','src'):
            if key in attrs:self.links.append(attrs[key])

data=load_course(); validate(data)
site=ROOT/'site'
parsers={}
for file in site.glob('*.html'):
    p=Links(); p.feed(file.read_text(encoding='utf-8')); parsers[file.resolve()]=p
for file,p in parsers.items():
    for link in p.links:
        part=urlsplit(link)
        if part.scheme or part.netloc:
            assert link.startswith(('https://olgakraven.github.io/2026-up.pm.12-rvmp/downloads/','https://kenney.nl/','https://opengameart.org')),link
            continue
        target=(file.parent/unquote(part.path)).resolve() if part.path else file
        assert target.is_file(),link
        if part.fragment:assert part.fragment in parsers[target].ids,link
code_names={item['name'] for item in data['code_files']}
expected={'assignment.pdf','guide.pdf','CrystalRoute-UnityProject.zip','report-template.md'}|code_names
assert {p.name for p in (site/'downloads').iterdir()}==expected,'Unexpected duplicate output'
assert {p.name for p in (ROOT/'content').glob('*.json')}=={'course.json'},'Multiple content sources'
for item in data['code_files']:
    source=(ROOT/item['path']).read_text(encoding='utf-8')
    covered=[]
    for page in data['guide']:
        for block in page['blocks']:
            if block.get('kind')=='code' and block.get('code_file')==item['name']:
                start,end=block['code_lines']
                covered.extend(range(start,end))
    assert covered==list(range(len(source.splitlines()))),f'Incomplete or repeated code ranges: {item["name"]}'
    assert (site/'downloads'/item['name']).read_text(encoding='utf-8')==source
assert len(data['areas'])==30
variant_titles=[page['title'] for page in data['areas'] if page['title'].startswith('Вариант ')]
assert len(variant_titles)==30 and len(set(variant_titles))==30,'Expected 30 distinct variants'
assert (site/'downloads/CrystalRoute-UnityProject.zip').stat().st_size>1000
manifest=json.loads((site/'manifest.json').read_text(encoding='utf-8'))
assert manifest.get('source_sha256') == source_fingerprint(), 'Rebuild: deliverable inputs changed after verification'
import sys
if '--release' in sys.argv:
    validate(data, release=True)
    assert manifest.get('release') is True, 'Only the verified prepared release may be deployed'
for name,specs in [('assignment',data['assignment']+data['areas']),('guide',data['guide'])]:
    doc=PdfReader(site/f'downloads/{name}.pdf')
    assert len(doc.pages)==len(manifest[name])
    text=''.join(p.extract_text() for p in doc.pages)
    compact=re.sub(r'\s+','',text)
    for page in doc.pages:
        assert abs(float(page.mediabox.width)-841.89)<1 and abs(float(page.mediabox.height)-595.28)<1
    for spec in specs:
        for block in spec['blocks']:
            for line in block['text'].splitlines():
                if line.strip():assert re.sub(r'\s+','',line) in compact,line[:80]
for old in ['example.html','example-guide.html','example-result.html']:
    text=(site/old).read_text(encoding='utf-8')
    assert 'http-equiv="refresh"' in text and '<article' not in text
try:validate(data,release=True)
except ValueError:assert data['meta']['status']!='ready'
else:assert data['meta']['status']=='ready'
print('PASS: one source, two PDFs, complete code, offline links, PDF text, landscape layout, content-free redirects')

# Required report, self-contained variant materials and compliance of teaching prose.
report=(site/'downloads/report-template.md').read_text(encoding='utf-8')
assert 'Ссылка на репозиторий проекта' in report and 'Версия программы' in report
assert report.count('Вставьте скриншот')==10
assert '<h1 ' in report and '<h2 ' in report and "Times New Roman" in report
for area in data['areas']:
    links=[b for b in area['blocks'] if b['kind']=='link']
    assert {b['href'].rsplit('/',1)[-1] for b in links} >= {'guide.pdf','CrystalRoute-UnityProject.zip','report-template.md'}
for section in ('assignment','guide','areas'):
    for page in data[section]:
        assert not re.search(r'Шаг\s+\d+',page['title']+' '+page.get('kicker',''),re.I)
        assert page['title']!='Что сдавать'
for name in ('assignment','guide'):
    doc=PdfReader(site/f'downloads/{name}.pdf')
    assert any(a.get_object().get('/A',{}).get('/URI') for p in doc.pages for a in p.get('/Annots',[]))
assert 'Список предметных областей' in PdfReader(site/'downloads/assignment.pdf').pages[0].extract_text()
print('PASS: report, variant materials, clickable PDF links and audit compliance')
