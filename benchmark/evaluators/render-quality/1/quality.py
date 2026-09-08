import platform
from acceptance.common import *
RUBRIC=['text','clipping','overlap','charts','hierarchy','legibility']

def inspect(proc,case,directory):
    from PIL import Image, ImageChops, ImageStat
    root=Path(directory);metrics=[];p=proc.get('payload') or {}
    for entry in p.get('outputs',[]):
        path=Path(entry.get('file',''))
        if path.suffix.lower() not in ['.png','.jpg','.jpeg','.webp']:continue
        try:
            with Image.open(path) as im:
                im=im.convert('RGB');stat=ImageStat.Stat(im)
                row={'page':entry.get('page'),'actualSha256':sha(path),'size':list(im.size),'channelStddev':stat.stddev,'image':str(path),'uniformImageSignal':max(stat.stddev)<.5}
                ref=case.get('facts',{}).get('references',{}).get(str(entry.get('page')))
                if ref:
                    rp=Path(ref['path'])
                    if sha(rp)!=ref['sha256']:raise ValueError('Reference changed')
                    with Image.open(rp) as refim:
                        refim=refim.convert('RGB').resize(im.size)
                        diff=ImageChops.difference(refim,im);row['mae']=sum(ImageStat.Stat(diff).mean)/3
                        montage=Image.new('RGB',(im.width*3,im.height),'white');montage.paste(refim,(0,0));montage.paste(im,(im.width,0));montage.paste(diff,(im.width*2,0))
                        montage.thumbnail((2400,1200));dest=root/f'comparison-{entry["page"]}.png';montage.save(dest);row['comparison']=str(dest)
                metrics.append(row)
        except (ValueError,OSError) as e:metrics.append({'page':entry.get('page'),'error':str(e)})
    fonts=process(['fc-list',':','family'])
    env={'platform':platform.platform(),'resolutionRequest':1920,'fonts':fonts['stdout'].splitlines() if fonts['exitCode']==0 else None,'fontEvidenceStatus':'available' if fonts['exitCode']==0 else 'blocked','node':process(['node','--version'])['stdout'].strip()}
    template={'sourceSha256':case['source']['sha256'],'caseId':case['id'],'pages':[{'page':m.get('page'),'actualSha256':m.get('actualSha256'),'referenceEvidence':None,'rubric':{k:None for k in RUBRIC},'conclusion':None} for m in metrics],'actor':None,'reviewedAt':None}
    atomic(root/'visual-review-template.json',template)
    return {'metrics':metrics,'environment':env,'rubric':RUBRIC,'reviewTemplate':str(root/'visual-review-template.json'),'status':'review','note':'No calibrated visual pass/fail threshold; image metrics are observations, not fidelity verdicts'}
