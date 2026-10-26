"""Create honest recovered-content PDFs directly from the supplied VCE files."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'.tools/pdf-packages'))
import json
import re
import io
from xml.sax.saxutils import escape
from PIL import Image as PILImage
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,PageBreak,Image,Table,TableStyle,KeepTogether
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from vce_decode import decode_file
from vce_reader import Reader
from richview import parse_nested_documents
from pypdf import PdfReader

OUT=ROOT/'output/pdf'
OUT.mkdir(parents=True,exist_ok=True)
pdfmetrics.registerFont(TTFont('Noto',r'C:\Windows\Fonts\NotoSans-Regular.ttf'))
pdfmetrics.registerFont(TTFont('NotoBold',r'C:\Windows\Fonts\NotoSans-Bold.ttf'))
pdfmetrics.registerFontFamily('Noto',normal='Noto',bold='NotoBold',italic='Noto',boldItalic='NotoBold')
styles=getSampleStyleSheet()
for key in ('Normal','BodyText'):
    styles[key].fontName='Noto';styles[key].fontSize=10;styles[key].leading=15
styles.add(ParagraphStyle(name='TitleVCE',fontName='NotoBold',fontSize=27,leading=34,textColor=colors.HexColor('#132D43'),spaceAfter=18))
styles.add(ParagraphStyle(name='QuestionVCE',fontName='NotoBold',fontSize=18,leading=24,textColor=colors.HexColor('#132D43'),spaceAfter=12,keepWithNext=True))
styles.add(ParagraphStyle(name='SmallVCE',fontName='Noto',fontSize=8,leading=12,textColor=colors.HexColor('#536170'),spaceAfter=7))
styles.add(ParagraphStyle(name='LabelVCE',fontName='NotoBold',fontSize=10,leading=15,textColor=colors.HexColor('#176B81'),spaceBefore=11,spaceAfter=5,keepWithNext=True))

def clean(text):
    return str(text).replace('\u2011','-').replace('\u2013','-').replace('\u2014','-').replace('\x00','')

def p(text,style='BodyText'):
    return Paragraph(escape(clean(text)).replace('\n','<br/>'),styles[style])

def ranges(values):
    groups=[]
    for value in values:
        if groups and value==groups[-1][-1]+1:groups[-1].append(value)
        else:groups.append([value])
    return ', '.join(str(g[0]) if len(g)==1 else f'{g[0]}-{g[-1]}' for g in groups)

def graphic(path):
    # Normalize to PNG in memory for portable embedding, preserving aspect ratio.
    with PILImage.open(path) as source:
        source.load();source=source.convert('RGB')
        width,height=source.size
        stream=io.BytesIO();source.save(stream,format='PNG');stream.seek(0)
    scale=min(1,475/width,570/height)
    return Image(stream,width=width*scale,height=height*scale,hAlign='LEFT')

def documents(story,docs,base):
    if not isinstance(docs,list):
        story.append(p('This decoded binary field has an unsupported document layout.','SmallVCE'));return
    for doc in docs:
        text=doc.get('text','').replace('[Image]','').strip()
        if text:
            for paragraph in re.split(r'\n\s*\n',text):
                if paragraph.strip():story.append(p(paragraph));story.append(Spacer(1,7))
        for image in doc.get('images',[]):
            story.append(graphic(base/image['path']));story.append(Spacer(1,10))
        for link in doc.get('links',[]):story.append(p('Reference: '+link,'SmallVCE'))

def image_documents(record,base):
    raw=(base/record['image_data']['path']).read_bytes()
    return parse_nested_documents(raw)

def footer(title,partial):
    def draw(c,doc):
        c.saveState();w,h=A4
        c.setStrokeColor(colors.HexColor('#DCE3E8'));c.line(50,42,w-50,42)
        c.setFont('Noto',7);c.setFillColor(colors.HexColor('#536170'))
        label=title[:63]+' | '+('Partial recovery' if partial else 'Decoded source')
        c.drawString(50,29,label);c.drawRightString(w-50,29,str(doc.page));c.restoreState()
    return draw

def make(source):
    decoded=decode_file(source,ROOT/'decoded')
    manifest=Path(decoded['export']);base=manifest.parent
    exam=json.loads(manifest.read_text(encoding='utf-8'))
    count=len(exam['records']);available=sum(q['decoded'] for q in exam['records'])
    short=('Amazon-SAA-C03' if source.name.startswith('Amazon') else
           'CompTIA-SY0-701' if source.name.startswith('CompTIA') else
           'Databricks-Data-Engineer' if source.name.startswith('Databricks') else
           'Microsoft-AZ-104' if source.name.startswith('Microsoft') else source.stem)
    target=OUT/(short+'-recovered.pdf')
    title=exam['metadata']['title']
    story=[Spacer(1,30),p('VCE FILE RECOVERY','LabelVCE'),p(title,'TitleVCE')]
    status=f'{available} of {count} records decoded'
    story.append(p(status,'QuestionVCE'))
    story.append(p('Recovered text, choices, stored answers, and images are reproduced below. '
        'This PDF is a partial conversion when protected records are listed as unavailable. '
        'Missing question contents have not been reconstructed.'))
    story.extend([Spacer(1,18),p('Source','LabelVCE'),p(source.name,'SmallVCE'),
                  p('File format: '+str(exam['metadata']['format'])+' | Original numbering retained','SmallVCE')])
    rows=[[p('Source records','SmallVCE'),p(str(count))],
          [p('Structurally decoded','SmallVCE'),p(str(available))],
          [p('Protected / unavailable','SmallVCE'),p(str(count-available))]]
    table=Table(rows,colWidths=[280,180],hAlign='LEFT')
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#F1F5F8')),('VALIGN',(0,0),(-1,-1),'TOP'),
                              ('LEFTPADDING',(0,0),(-1,-1),12),('TOPPADDING',(0,0),(-1,-1),9),('BOTTOMPADDING',(0,0),(-1,-1),9)]))
    story.extend([Spacer(1,15),table,Spacer(1,18),p('Reading notes','LabelVCE'),
        p('Question wording is recovered source content. Stored answer keys are reproduced without independently verifying their correctness. '
          'Layout is reconstructed and may differ from the official player.','SmallVCE')])
    image_count=0
    for record in exam['records']:
        if not record['decoded']:continue
        story.append(PageBreak())
        story.append(p('Question '+str(record['index']+1),'QuestionVCE'))
        group=exam['groups'][record['group']]
        story.append(p(group['title'],'SmallVCE'))
        child=group['children'][record['child']]
        if child.get('kind')==1:
            story.append(p('Case-study context','LabelVCE'))
            if child.get('body_documents'):documents(story,child['body_documents'],base)
            else:story.append(p('The case-study context could not be recovered.','SmallVCE'))
        if record.get('type',0)&127 in (2,3,9):
            story.append(p('Image-based question','LabelVCE'))
            try:
                for doc in image_documents(record,base):
                    if doc.text:story.append(p(doc.text.replace('[Image]','')))
                story.append(graphic(base/record['image_aux_data']['path']));image_count+=1
                story.append(p('The source uses image-based answer regions. Its stored binary response is not translated into a guessed answer.','SmallVCE'))
            except (ValueError,KeyError,OSError) as error:
                story.append(p('The image interaction could not be rendered: '+str(error),'SmallVCE'))
        else:
            docs=record.get('prompt_documents',[])
            if isinstance(docs,list):
                choice_count=record.get('choice_count',0)
                for i,doc in enumerate(docs):
                    if i==0:label='Question'
                    elif i<=choice_count:label='Choice '+chr(64+i)
                    else:label='Explanation / additional source document'
                    if not doc.get('text','').strip() and not doc.get('images'):
                        if i<=choice_count:story.append(p(label+': [blank in source]','SmallVCE'))
                        continue
                    story.append(p(label,'LabelVCE'));documents(story,[doc],base)
                    image_count+=len(doc.get('images',[]))
            else:documents(story,docs,base)
            answer=record.get('stored_answer_text','').strip()
            story.append(p('Stored answer: '+(answer or '[blank or non-text response]'),'LabelVCE'))
        if 'extra_data' in record:
            try:
                raw=(base/record['extra_data']['path']).read_bytes()
                for doc in parse_nested_documents(raw):
                    story.append(p('Additional source content','LabelVCE'));story.append(p(doc.text))
            except ValueError:story.append(p('An additional binary field remains unrendered.','SmallVCE'))
    missing=[q['index']+1 for q in exam['records'] if not q['decoded']]
    if missing:
        story.extend([PageBreak(),p('Unavailable source records','QuestionVCE'),
            p(f'{len(missing)} protected or unsupported records could not be converted. The source numbering below identifies the gaps.'),Spacer(1,16)])
        for i,group in enumerate(exam['groups']):
            values=[q['index']+1 for q in exam['records'] if q['group']==i and not q['decoded']]
            if values:story.extend([p(group['title'],'LabelVCE'),p('Questions '+ranges(values))])
    doc=SimpleDocTemplate(str(target),pagesize=A4,rightMargin=50,leftMargin=50,topMargin=48,bottomMargin=57,
                          title=title+' - recovered VCE content',author='Offline VCE conversion')
    doc.build(story,onFirstPage=footer(short,bool(missing)),onLaterPages=footer(short,bool(missing)))
    pdf=PdfReader(target)
    extracted='\n'.join(page.extract_text() or '' for page in pdf.pages)
    for q in exam['records']:
        if q['decoded'] and 'Question '+str(q['index']+1) not in extracted:raise ValueError('Missing question heading in PDF')
    return dict(source=source.name,pdf=str(target),pages=len(pdf.pages),records=count,decoded_records=available,
                unavailable_records=len(missing),question_images=image_count,source_sha256=exam['source']['sha256'])

if __name__=='__main__':
    reports=[]
    for source in sorted((ROOT/'temp').glob('*.vce')):
        report=make(source);reports.append(report);print(json.dumps(report))
    (OUT/'conversion-report.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')
