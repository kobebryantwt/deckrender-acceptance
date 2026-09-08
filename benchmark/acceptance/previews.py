"""Independent page evidence. A preview is never an approved visual oracle."""
import shutil
from .common import *

def extract(path, directory, output_page=None):
    from PIL import Image
    import fitz
    path=Path(path); directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    rows=[]; origin=sha(path)
    def save(im, index, **mapping):
        dest=directory/f'{index:04d}.png';im.convert('RGB').save(dest)
        rows.append({'image':str(dest.resolve()),'imageSha256':sha(dest),'artifactSha256':origin,
                     'outputPage':output_page,'mapping':mapping,'size':list(im.size)})
    if path.suffix.lower()=='.pdf':
        with fitz.open(path) as doc:
            if doc.needs_pass:raise ValueError('Encrypted PDF requires independently authorized password')
            for i,page in enumerate(doc):
                pix=page.get_pixmap(matrix=fitz.Matrix(1.5,1.5),alpha=False)
                save(Image.frombytes('RGB',(pix.width,pix.height),pix.samples),i+1,pdfPage=i+1)
    elif path.suffix.lower() in {'.png','.jpg','.jpeg','.webp'}:
        with Image.open(path) as im:save(im,1,sourcePage=output_page)
    elif path.suffix.lower() in {'.mp4','.webm','.mov'}:
        probe=process(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(path)])
        if probe['exitCode']!=0:raise ValueError('Video metadata unavailable: '+probe.get('stderr',''))
        info=json.loads(probe['stdout']);duration=float(info['format']['duration'])
        if duration<=0 or not any(s.get('codec_type')=='video' for s in info['streams']):raise ValueError('No decodable video stream')
        # Fixed bounded temporal sample, explicitly not slide/page correspondence.
        for i,fraction in enumerate([.05,.25,.5,.75,.95],1):
            t=round(duration*fraction,6);dest=directory/f'{i:04d}.png'
            result=process(['ffmpeg','-v','error','-ss',str(t),'-i',str(path),'-frames:v','1','-y',str(dest)])
            if result['exitCode']!=0 or not dest.exists():raise ValueError('Video frame decode failed')
            with Image.open(dest) as im:size=list(im.size)
            rows.append({'image':str(dest.resolve()),'imageSha256':sha(dest),'artifactSha256':origin,'outputPage':output_page,'size':size,
                         'mapping':{'timestampSeconds':t,'durationSeconds':duration,'sourcePage':None,'coverage':'five temporal samples; slide mapping requires human evidence'}})
    else:raise ValueError('No independent preview adapter for '+path.suffix)
    return rows

def prepare(home):
    """Build candidates from PDFs or explicitly supplied source-bound references."""
    home=Path(home);corpus=read(home/'corpus.json');items=[]
    from . import purposes, maintenance
    cases=maintenance.load_suites(home)[1]
    old_pages={p['imageSha256']:p for item in read(home/'gt-manifest.json',{'items':[]})['items'] for p in item.get('pages',[])}
    for source in corpus['sources']:
        item={'sourceId':source['id'],'sourceSha256':source['sha256'],'name':source['inputName'],
              'format':source['format'],'public':source['public'],'license':source['license'],'status':'draft','pages':[],
              'provenance':{'method':'PyMuPDF source PDF rasterization','role':'GT candidate, human confirmation required'}}
        try:
            if sha(source['path'])!=source['sha256']:raise ValueError('Source content changed')
            from .source_preview import export as export_source
            refs=source.get('facts',{}).get('references',{})
            try:
                preview_pdf,provenance=export_source(source,home)
                item['provenance']=provenance
                original=extract(preview_pdf,home/'gt'/source['sha256']/'source'/sha(preview_pdf))
            except (ValueError,OSError) as error:
                if not refs:raise
                original=[];item['sourcePreviewUnavailable']=str(error)
            if refs:
                item['public']=source['public'] and all(r.get('public') for r in refs.values())
                for page,ref in sorted(refs.items(),key=lambda x:int(x[0])):
                    if ref.get('sourceSha256')!=source['sha256'] or not ref.get('provenance'):raise ValueError('Reference needs source binding and provenance')
                    if sha(ref['path'])!=ref['sha256']:raise ValueError('Reference changed')
                    rows=extract(ref['path'],home/'gt'/source['sha256']/str(page)/ref['sha256'],int(page))
                    for row in rows:
                        row['reviewStatus']=ref.get('status','draft');row['review']=ref.get('review')
                    item['pages']+=rows
                item['provenance']={'method':'supplied independent references','references':refs,'role':'candidate'}
                covered={p['mapping'].get('sourcePage') or p['mapping'].get('pdfPage') for p in item['pages']}
                item['pages'] += [p for p in original if p['mapping']['pdfPage'] not in covered]
            elif original:item['pages']=original
            else:raise ValueError('Independent reference not supplied; optional third-party export can prepare GT')
            for p in item['pages']:
                number=p['mapping'].get('sourcePage') or p['mapping'].get('pdfPage')
                base=next((r for r in original if r['mapping']['pdfPage']==number),None)
                if base:
                    if base['imageSha256']==p['imageSha256']:p['sourceSameAsCandidate']=True
                    else:p.update(sourceImage=base['image'],sourceImageSha256=base['imageSha256'])
            item['pages'].sort(key=lambda p:p['mapping'].get('sourcePage') or p['mapping'].get('pdfPage') or 0)
            expected=len(original) or source.get('facts',{}).get('pages')
            covered=sorted({p['mapping'].get('sourcePage') or p['mapping'].get('pdfPage') for p in item['pages']})
            item['coverage']={'sourcePages':expected,'candidatePages':covered,'missingSourcePages':[i for i in range(1,expected+1) if i not in covered] if expected else 'unknown'}
            item['coverage']['paginationAuthority']='independent source export; human confirmation required'
        except (ValueError,OSError) as e:item['status']='blocked';item['reason']=str(e)
        if item['pages'] and item['status']!='blocked' and all(p.get('reviewStatus')=='approved' for p in item['pages']):item['status']='approved'
        item['purpose']=purposes.for_source(source,cases)
        for page in item['pages']:
            previous=old_pages.get(page['imageSha256'],{})
            if previous.get('precheck'):page['precheck']=previous['precheck']
        items.append(item)
    from .curation import annotate,summary
    annotate(items)
    atomic(home/'curation-summary.json',summary(items))
    manifest={'version':3,'corpusSha256':sha(home/'corpus.json'),'createdAt':now(),'items':items,'approval':'No automatic answer approval'}
    atomic(home/'gt-manifest.json',manifest)
    from .workbench import write
    write(home/'gt.html',items,'参考图与审核',mode='gt',embed=False)
    from .coverage import write as write_coverage
    write_coverage(home,maintenance.project_inputs(maintenance.initialize(home),home))
    return {'page':str(home/'gt.html'),'sources':len(items),'previewPages':sum(len(x['pages']) for x in items),'blocked':sum(x['status']=='blocked' for x in items)}

def refresh_metadata(home):
    """Refresh purpose without rendering, trusting only unchanged source-bound previews."""
    from . import purposes, maintenance, workbench
    home=Path(home);manifest=read(home/'gt-manifest.json',{})
    if not manifest:return
    corpus=read(home/'corpus.json');existing={i['sourceId']:i for i in manifest['items']};items=[]
    cases=maintenance.load_suites(home)[1]
    for source in corpus['sources']:
        item=existing.get(source['id'])
        if not item or item['sourceSha256']!=source['sha256'] or sha(source['path'])!=source['sha256']:
            item={'sourceId':source['id'],'sourceSha256':source['sha256'],'name':source['inputName'],'format':source['format'],'pages':[],'status':'blocked','reason':'源版本变更或尚未生成独立候选，请重新准备预览'}
        for page in item.get('pages',[]):
            number=page['mapping'].get('sourcePage') or page['mapping'].get('pdfPage')
            reference=source.get('facts',{}).get('references',{}).get(str(number),{})
            if reference.get('sha256')==page['imageSha256'] and reference.get('sourceSha256')==source['sha256']:
                page['reviewStatus']=reference.get('status','draft');page['review']=reference.get('review')
            else:
                page['reviewStatus']='draft';page.pop('review',None)
        if item.get('pages') and item.get('status')!='blocked':item['status']='approved' if all(p.get('reviewStatus')=='approved' for p in item['pages']) else 'draft'
        item['purpose']=purposes.for_source(source,cases);items.append(item)
    from .curation import annotate,summary
    annotate(items)
    atomic(home/'curation-summary.json',summary(items))
    manifest.update(items=items,corpusSha256=sha(home/'corpus.json'),metadataUpdatedAt=now())
    atomic(home/'gt-manifest.json',manifest)
    workbench.write(home/'gt.html',items,'参考图与审核',mode='gt',embed=False)

def apply_draft(home,file):
    """Import explicitly reviewed candidates; business answers still require Casework approval."""
    home=Path(home);value=read(file);manifest=read(home/'gt-manifest.json');corpus=read(home/'corpus.json')
    if value.get('kind')!='visual-review-draft' or value.get('mode')!='gt' or not isinstance(value.get('actor'),str) or not value['actor'].strip() or not (value.get('reviews') or value.get('videoMappings')):raise ValueError('GT review export and explicit actor required')
    changed=0
    for row in value.get('reviews',[]):
        source=next((s for s in corpus['sources'] if s['sha256']==row.get('sourceSha256')),None)
        item=next((i for i in manifest['items'] if i['sourceSha256']==row.get('sourceSha256')),None)
        page=next((p for p in item['pages'] if p['imageSha256']==row.get('actualSha256') and (p['mapping']==row.get('page') or p['mapping'].get('sourcePage',p['mapping'].get('pdfPage'))==row.get('page',{}).get('sourcePage',row.get('page',{}).get('pdfPage')))),None) if item else None
        if not source or not page or sha(source['path'])!=source['sha256'] or sha(page['image'])!=page['imageSha256']:raise ValueError('Stale or unmapped GT review')
        rubric=row.get('rubric',{})
        if set(rubric)!=set(['文字','裁切','重叠','图表','层级','可读性']) or any(v not in ['符合','不适用'] for v in rubric.values()):raise ValueError('Only fully confirmed GT candidates can be imported; retain incomplete/rejected candidates as drafts')
        number=page['mapping'].get('sourcePage') or page['mapping'].get('pdfPage')
        if not number:raise ValueError('Explicit source page mapping required')
        source.setdefault('facts',{}).setdefault('references',{})[str(number)]={'path':page['image'],'sha256':page['imageSha256'],
            'sourceSha256':source['sha256'],'status':'approved','public':bool(source['public'] and item['public']),'provenance':item['provenance'],
            'review':{'actor':value['actor'],'importedAt':now(),'exportSha256':sha(file),'rubric':rubric,'note':row.get('note')}}
        changed+=1
    for source in corpus['sources']:
        item=next((i for i in manifest['items'] if i['sourceSha256']==source['sha256']),None)
        if not item or not item.get('pages'):continue
        count=item.get('coverage',{}).get('sourcePages')
        if type(count) is int and set(source.get('facts',{}).get('references',{}))==set(map(str,range(1,count+1))):
            refs=source['facts']['references']
            if all(r.get('status')=='approved' and r.get('review',{}).get('actor') for r in refs.values()):
                source['facts'].update(visualPageCount=count,pageCountReview={'actor':value['actor'],'sourceSha256':source['sha256'],'exportSha256':sha(file)})
    from .gt_contract import FRACTIONS
    for mapping in value.get('videoMappings',[]):
        source=next((s for s in corpus['sources'] if s['sha256']==mapping.get('sourceSha256')),None)
        if not source or sha(source['path'])!=source['sha256']:raise ValueError('Stale video source mapping')
        count=source.get('facts',{}).get('pages') or source.get('facts',{}).get('visualPageCount')
        frames=mapping.get('frames',[])
        if not mapping.get('evidence') or type(count) is not int or len(frames)!=5 or sorted(f.get('fraction',-1) for f in frames)!=FRACTIONS:raise ValueError('Complete video fractions, reviewed pagination and independent timing evidence required')
        if any(type(f.get('sourcePage')) is not int or not 1<=f['sourcePage']<=count for f in frames):raise ValueError('Invalid video source page')
        source.setdefault('facts',{})['videoReferenceFrames']=[{**f,'sourceSha256':source['sha256'],'review':{'actor':value['actor'],'exportSha256':sha(file),'evidence':mapping['evidence']}} for f in frames]
    atomic(home/'corpus-history'/(stamp()+'.json'),read(home/'corpus.json'));atomic(home/'corpus.json',corpus)
    atomic(home/'gt-review-history'/(stamp()+'.json'),value)
    from . import catalog,maintenance
    catalog.build(home);maintenance.refresh(home);refresh_metadata(home);maintenance.review_page(home)
    return {'confirmedReferencePages':changed,'answers':'Changed business answers remain draft; no quality run authorized'}

def attach(home,source_id,reference,provenance):
    """Optional reference import; independent exporters need not use target schema."""
    home=Path(home);corpus=read(home/'corpus.json');source=next((s for s in corpus['sources'] if s['id']==source_id),None)
    if not source or not provenance or not reference:raise ValueError('Source ID, independent reference file, and provenance are required')
    if sha(source['path'])!=source['sha256']:raise ValueError('Source changed')
    rows=extract(reference,home/'gt-imports'/source['sha256']/sha(reference),1)
    if any('timestampSeconds' in p['mapping'] for p in rows):raise ValueError('Video reference requires explicit source-page mapping')
    for i,p in enumerate(rows,1):
        source.setdefault('facts',{}).setdefault('references',{})[str(i)]={'path':p['image'],'sha256':p['imageSha256'],'sourceSha256':source['sha256'],
            'provenance':{'description':provenance,'referenceArtifactSha256':sha(reference),'method':'independent supplied export'},'status':'draft','public':False}
    atomic(home/'corpus-history'/(stamp()+'.json'),read(home/'corpus.json'));atomic(home/'corpus.json',corpus)
    from . import catalog,maintenance
    catalog.build(home);maintenance.refresh(home);maintenance.review_page(home)
    return prepare(home)
