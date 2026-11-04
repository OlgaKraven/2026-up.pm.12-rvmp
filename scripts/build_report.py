"""Adapt the retained common report master to PM.12 stages."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import zipfile
from docx import Document
from docx.oxml.ns import qn
from docx.shared import Mm
from docx.enum.table import WD_ROW_HEIGHT_RULE
import report_parts as parts

ROOT=Path(__file__).resolve().parents[1]
MASTER=ROOT/'forms/template/Отчет о выполнении.docx'
MASTER_SHA='5b91286458395ae589ded859021f287ce50cca1148cc5b29226b6fb1cb5373c4'

def text(e):return ''.join(t.text or '' for t in e.iter(qn('w:t')))

def label_rows(table,labels,tag):
    original=deepcopy(table.rows[1]._tr)
    while len(table.rows)<len(labels)+1:table._tbl.append(deepcopy(original))
    while len(table.rows)>len(labels)+1:table._tbl.remove(table.rows[-1]._tr)
    for i,label in enumerate(labels,1):
        for j,cell in enumerate(table.rows[i].cells):
            controls=cell._tc.xpath('.//w:sdt')
            for k,c in enumerate(controls):
                c.find('w:sdtPr/w:tag',c.nsmap).set(qn('w:val'),f'{tag}_{i}_{j}_{k}')
                ts=list(c.find(qn('w:sdtContent')).iter(qn('w:t')))
                ts[0].text=label if j==0 else '____________'
                for t in ts[1:]:t.text=''
            if j==0 and not controls:
                ts=cell._tc.xpath('.//w:t');ts[0].text=label
                for t in ts[1:]:t.text=''
    for row in table.rows:
        row.height=Mm(12);row.height_rule=WD_ROW_HEIGHT_RULE.AT_LEAST

def build():
    assert hashlib.sha256(MASTER.read_bytes()).hexdigest()==MASTER_SHA
    data=json.loads((ROOT/'content/course.json').read_text(encoding='utf-8'))
    out=ROOT/'forms/Отчет о выполнении.docx';shutil.copyfile(MASTER,out);doc=Document(out)
    for c in doc.element.xpath('.//w:sdt'):
        tag=c.find('w:sdtPr/w:tag',c.nsmap)
        if tag is not None and tag.get(qn('w:val'))=='practice_name':
            ts=list(c.find(qn('w:sdtContent')).iter(qn('w:t')))
            ts[0].text='Программирование мобильных игр (ПМ.12)'
            for t in ts[1:]:t.text=''
    label_rows(doc.tables[0],['Номер и предметная область варианта','Объекты, числа и начальные состояния','Правило, победа и поражение','Использованные исходные материалы'],'inputs')
    label_rows(doc.tables[1],['Операционная система','Unity Editor','Редактор C#','Microsoft Word'],'environment')
    label_rows(doc.tables[2],['Crystal и признаки предмета','Hazard и причина штрафа','Exit и место завершения','Счётчики и состояние правила'],'mapping')
    labels=['Начало и управление','Контакт без повторного зачёта','Индивидуальное правило','Раннее завершение','Победа и блокировка ввода','Поражение и блокировка ввода','Полный повтор','Контрольная копия и репозиторий']
    label_rows(doc.tables[-1],labels,'final')
    doc.tables[2]._tbl.getprevious().get_or_add_pPr().append(parts.el('pageBreakBefore'))
    table=doc.tables[-1];table.autofit=False
    for row in table.rows:
        row.height=Mm(10)
        for cell,w in zip(row.cells,[59,34,35,32]):cell.width=Mm(w)
    body=doc.element.body;children=list(body)
    start=next(i for i,e in enumerate(children) if text(e)=='Этап выполнения работы')
    end=next(i for i,e in enumerate(children) if text(e)=='Итоговая проверка и сдача')
    anchor=children[end]
    for e in children[start:end]:body.remove(e)
    parts.CONTROL_ID=10000;fig=0
    for index,stage in enumerate(data['report']['sections'],1):
        first=len(list(body))-1
        parts.heading(doc,stage['title'],level=2,new_page=index>1)
        doc.add_paragraph(stage['prompt'])
        for label,tag,lines in [('Исходные данные и ожидаемый результат','initial',2),('Выполненные действия','actions',3),('Фактический результат и проверка','actual',2),('Вывод по этапу и объяснение расхождений','conclusion',2)]:
            parts.response(doc,label,f's{index}_{tag}',lines)
        doc.add_page_break();p=doc.add_paragraph();p.add_run('Подтверждения этапа приведены на рис. ')
        for j,caption in enumerate(stage['screenshots']):
            if j:p.add_run(', ')
            parts.field(p,f'REF pm12_fig_{fig+j+1} \\h',str(fig+j+1))
        p.add_run('. Вставить собственные результаты, сохранив подписи.')
        for j,caption in enumerate(stage['screenshots']):
            if j and j%2==0:doc.add_page_break()
            fig+=1;parts.figure_slot(doc,caption,f'pm12_figure_{fig}',fig,f'pm12_fig_{fig}')
        generated=list(body)[first:-1]
        for e in generated:body.remove(e);anchor.addprevious(e)
    for cid,c in enumerate(doc.element.xpath('.//w:sdt'),30000):c.find('w:sdtPr/w:id',c.nsmap).set(qn('w:val'),str(cid))
    doc.core_properties.title='Отчет о выполнении';doc.core_properties.subject='ПМ.12'
    doc.core_properties.author=doc.core_properties.last_modified_by=''
    doc.core_properties.comments=doc.core_properties.keywords=''
    doc.save(out)
    with zipfile.ZipFile(out) as z:edited={n:z.read(n) for n in z.namelist()}
    with zipfile.ZipFile(MASTER) as z:original={n:z.read(n) for n in z.namelist()}
    allowed={'word/document.xml','docProps/core.xml'}
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for name,value in original.items():
            info=zipfile.ZipInfo(name,(2026,11,4,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,edited[name] if name in allowed else value)
    with zipfile.ZipFile(out) as z:
        for name,value in original.items():
            if name not in allowed:assert z.read(name)==value,name
    print('Copied common master; adapted',len(data['report']['sections']),'stages and',fig,'figure slots')

if __name__=='__main__':build()
