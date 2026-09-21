"""Check one complete kit and prevent duplicate outputs from returning."""
import json
import re
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote
from pypdf import PdfReader
from build import ROOT, load_course, validate

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
        assert not part.scheme and not part.netloc, link
        target=(file.parent/unquote(part.path)).resolve() if part.path else file
        assert target.is_file(),link
        if part.fragment:assert part.fragment in parsers[target].ids,link
code_names={item['name'] for item in data['code_files']}
expected={'assignment.pdf','guide.pdf','CrystalRoute-UnityProject.zip'}|code_names
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
assert len(data['areas'])==6
variant_titles=[b['title'] for page in data['areas'] for b in page['blocks'] if b['title'].startswith('Вариант ')]
assert len(variant_titles)==30 and len(set(variant_titles))==30,'Expected 30 distinct variants'
assert (site/'downloads/CrystalRoute-UnityProject.zip').stat().st_size>1000
manifest=json.loads((site/'manifest.json').read_text(encoding='utf-8'))
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
