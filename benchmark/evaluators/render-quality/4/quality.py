"""Visual review v2: image, every PDF page, and explicit temporal video samples."""
import platform
from acceptance.common import *
from acceptance.previews import extract
RUBRIC=['text','clipping','overlap','charts','hierarchy','legibility']

def inspect(proc,case,directory):
    from acceptance.gt_contract import readiness
    gt=readiness(case)
    root=Path(directory);root.mkdir(parents=True,exist_ok=True);rows=[];errors=[]
    for index,entry in enumerate((proc.get('payload') or {}).get('outputs',[])):
        try:
            path=Path(entry['file']).resolve()
            if not path.is_relative_to(Path(proc['artifactsDir']).resolve()):raise ValueError('Artifact outside output root')
            pages=extract(path,root/'previews'/str(index),entry.get('page'))
            from PIL import Image, ImageStat
            for page in pages:
                if 'pdfPage' in page['mapping']:
                    page['mapping']['sourcePage']=entry['page']+page['mapping']['pdfPage']-1 if type(entry.get('page')) is int else None
                page.update({'caseId':case['id'],'sourceSha256':case['source']['sha256'],'outputIndex':index,
                             'actualSha256':page['imageSha256'],'page':page['mapping'].get('sourcePage',entry.get('page'))})
                try:
                    with Image.open(page['image']) as im:
                        stat=ImageStat.Stat(im);is_blank=max(stat.stddev)<0.5
                        aspect=round(im.width/max(1,im.height),3);aspect_valid=0.5<=aspect<=2.5
                        res_valid=im.width>=400 and im.height>=300
                        page['precheck']={'status':'passed' if (not is_blank and aspect_valid and res_valid) else 'review','isUniform':is_blank,'aspectRatio':aspect,'size':list(im.size),'suggestedRubric':{k:'待审' for k in RUBRIC}}
                except Exception:page['precheck']={'status':'review','suggestedRubric':{k:'待审' for k in RUBRIC}}
                # Video ordinal is NOT a source page number. Requires independent mapping.
                source_page=page['page']
                if 'timestampSeconds' in page['mapping']:
                    fraction=page['mapping']['timestampSeconds']/page['mapping']['durationSeconds']
                    mapping=next((m for m in case.get('facts',{}).get('videoReferenceFrames',[]) if abs(m.get('fraction',-1)-fraction)<.0001),None)
                    source_page=mapping.get('sourcePage') if mapping else None
                    page['mapping']['sourcePage']=source_page
                    page['mapping']['referenceFraction']=mapping.get('fraction') if mapping else None
                selected=case.get('contract',{}).get('selectedSourcePages')
                if selected is not None and case['options']['target']=='image':
                    expected=selected[index] if index<len(selected) else None
                    page['mapping'].update(reportedSourcePage=source_page,expectedSourcePage=expected)
                    if source_page!=expected:errors.append({'outputIndex':index,'error':'Reported page differs from reviewed selection','expected':expected,'actual':source_page})
                    # Bind the comparison to reviewed intent; retain the target's reported page.
                    source_page=expected
                ref=case.get('facts',{}).get('references',{}).get(str(source_page))
                if ref:
                    if ref.get('sourceSha256')!=case['source']['sha256'] or not ref.get('provenance'):raise ValueError('Reference source binding/provenance missing')
                    if sha(ref['path'])!=ref['sha256']:raise ValueError('Reference changed')
                    dest=root/'previews'/f'reference-{index}-{source_page}.png'
                    with Image.open(ref['path']) as im:im.convert('RGB').save(dest)
                    page.update(referenceImage=str(dest.resolve()),referenceSha256=sha(dest),referenceProvenance=ref['provenance'],referenceStatus=ref.get('status','draft'))
                rows.append(page)
        except (ValueError,OSError,KeyError,TypeError) as e:errors.append({'outputIndex':index,'error':str(e)})
    template={'version':2,'sourceSha256':case['source']['sha256'],'caseId':case['id'],'options':case['options'],
              'pages':[{**p,'rubric':{k:None for k in RUBRIC},'conclusion':None} for p in rows],'actor':None,'reviewedAt':None}
    atomic(root/'visual-review-template.json',template)
    atomic(root/'visual-pages.json',{'caseId':case['id'],'sourceSha256':case['source']['sha256'],**case['options'],'pages':rows,'errors':errors,'status':'review' if rows and gt['ready'] and not errors else 'blocked'})
    return {'metrics':rows,'errors':errors,'options':case['options'],'sourceFormat':case.get('format'),'actualEngine':(proc.get('payload') or {}).get('engine'),'actualRoute':(proc.get('payload') or {}).get('route'),
            'environment':{'platform':platform.platform(),'rasterizer':'PyMuPDF / Pillow / ffmpeg','fonts':process(['fc-list',':','family'])},
            'rubric':RUBRIC,'reviewTemplate':str(root/'visual-review-template.json'),'status':'review' if rows and gt['ready'] and not errors else 'blocked',
            'gtReadiness':gt,'note':'All PDF pages; five temporal video samples, not all frames; no pixel release threshold; optional independent GT remains subject to human review'}
