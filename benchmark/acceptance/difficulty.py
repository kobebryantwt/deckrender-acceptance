"""Source-side observations, separate from visual truth and target output."""
import zipfile, collections, posixpath
from xml.etree import ElementTree as ET
from .common import *

AXES={'fonts':'多种显式字体或非 ASCII 文字','charts':'原生图表部件','special-elements':'公式、音视频、嵌入对象或页面切换','dense-page':'单页至少 50 个文本节点，或文档至少 20 张表（后者仅为候选）'}

def inspect(source):
    path=Path(source['path']);evidence=[];features=[];facts={}
    if sha(path)!=source['sha256']:raise ValueError('Source changed')
    try:
        if source['format']=='pdf':
            import fitz
            with fitz.open(path) as doc:
                if doc.needs_pass:raise ValueError('Encrypted PDF')
                facts['pages']=len(doc)
                for i,p in enumerate(doc):
                    fonts=sorted({f[3] for f in p.get_fonts()});words=p.get_text('words')
                    if len(fonts)>1:features.append('fonts');evidence.append({'axis':'fonts','location':f'page:{i+1}','fonts':fonts})
                    if len(words)>=300:features.append('dense-page');evidence.append({'axis':'dense-page','location':f'page:{i+1}','wordCount':len(words)})
        elif source['format'] in ['pptx','docx']:
            with zipfile.ZipFile(path) as z:
                names=z.namelist();slides=[];charts=set()
                if source['format']=='pptx':
                    relns='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
                    rels={e.attrib['Id']:e.attrib['Target'] for e in ET.fromstring(z.read('ppt/_rels/presentation.xml.rels'))}
                    presentation=ET.fromstring(z.read('ppt/presentation.xml'))
                    for e in presentation.iter():
                        if e.tag.rsplit('}',1)[-1]=='sldId':
                            target=rels[e.attrib[relns+'id']]
                            slides.append(posixpath.normpath(posixpath.join('ppt',target)).lstrip('/') if not target.startswith('/') else target.lstrip('/'))
                    facts['pages']=len(slides)
                    for slide in slides:
                        rel=posixpath.join(posixpath.dirname(slide),'_rels',posixpath.basename(slide)+'.rels')
                        if rel in names:
                            for e in ET.fromstring(z.read(rel)):
                                if e.attrib.get('Type','').endswith('/chart'):
                                    target=e.attrib['Target'];charts.add(posixpath.normpath(posixpath.join(posixpath.dirname(slide),target)).lstrip('/') if not target.startswith('/') else target.lstrip('/'))
                for n in names:
                    if not n.endswith('.xml'):continue
                    if (source['format']=='docx' or n in charts) and '/charts/chart' in n and re.search(r'chart\d+\.xml$',n):features.append('charts');evidence.append({'axis':'charts','location':n})
                    if n not in slides and n!='word/document.xml':continue
                    root=ET.fromstring(z.read(n));nodes=list(root.iter());texts=[e.text or '' for e in nodes if e.tag.rsplit('}',1)[-1]=='t']
                    fonts=sorted({v for e in nodes for k,v in e.attrib.items() if k.rsplit('}',1)[-1] in ['typeface','ascii','eastAsia']})
                    if len(fonts)>1 or any(not t.isascii() for t in texts):features.append('fonts');evidence.append({'axis':'fonts','location':n,'fonts':fonts,'nonAscii':any(not t.isascii() for t in texts)})
                    special=collections.Counter(e.tag.rsplit('}',1)[-1] for e in nodes if e.tag.rsplit('}',1)[-1] in ['oMath','videoFile','audioFile','oleObj','transition','timing'])
                    if special:features.append('special-elements');evidence.append({'axis':'special-elements','location':n,'counts':dict(special)})
                    tables=sum(e.tag.rsplit('}',1)[-1]=='tbl' for e in nodes)
                    if (n in slides and len(texts)>=50) or tables>=20:features.append('dense-page');evidence.append({'axis':'dense-page','location':n,'textNodes':len(texts),'tables':tables,'candidate':n=='word/document.xml'})
        else:return {'status':'uncharacterized','features':[],'evidence':[],'facts':{},'reason':'No independent structure scanner for this format'}
    except (ValueError,OSError,KeyError,zipfile.BadZipFile,ET.ParseError) as e:return {'status':'blocked','features':[],'facts':{},'evidence':[],'reason':str(e)}
    return {'status':'observed','features':sorted(set(features)),'facts':facts,'evidence':evidence,'sourceSha256':source['sha256'],'visualTruth':'draft; structural facts do not prove visual fidelity'}

def scan(home):
    home=Path(home);corpus=read(home/'corpus.json');atomic(home/'corpus-history'/(stamp()+'.json'),corpus)
    rows=[]
    for source in corpus['sources']:
        row=inspect(source);rows.append({'sourceId':source['id'],'name':source['inputName'],**row})
        source['difficulty']=row;source['features']=sorted(set(source.get('features',[])+row['features']))
        source.setdefault('facts',{}).update(row['facts']);source['facts']['difficultyEvidence']=row
    atomic(home/'corpus.json',corpus)
    coverage={axis:[r['sourceId'] for r in rows if axis in r['features']] for axis in AXES}
    result={'version':2,'definitions':AXES,'coverage':coverage,'gaps':[a for a,ids in coverage.items() if not ids],'sources':rows,
            'scope':'Source structure only; format-specific visual references and human review remain separate. Existing provenance/licensing unchanged.'}
    atomic(home/'difficulty.json',result);return result
