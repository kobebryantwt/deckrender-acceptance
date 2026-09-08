"""Visual GT readiness is distinct from text-answer approval and preview availability."""
from .common import *
FRACTIONS=[.05,.25,.5,.75,.95]

def readiness(case,base=None):
    facts=case.get('facts',{});count=facts.get('pages') or facts.get('visualPageCount');errors=[]
    if type(count) is not int or count<1:return {'ready':False,'errors':['Independent, reviewed source pagination unavailable']}
    if not facts.get('pages') and (not facts.get('pageCountReview',{}).get('actor') or facts.get('pageCountReview',{}).get('sourceSha256')!=case['source']['sha256']):errors.append('Visual pagination needs source-bound human review')
    refs=facts.get('references',{})
    if set(refs)!=set(map(str,range(1,count+1))):errors.append('GT must cover every source page exactly')
    for number,ref in refs.items():
        p=Path(ref.get('path',''));p=inside(base,p) if base and not p.is_absolute() else p
        if ref.get('status')!='approved' or not ref.get('review',{}).get('actor') or not ref.get('provenance'):errors.append('Unreviewed reference page '+number)
        if ref.get('sourceSha256')!=case['source']['sha256']:errors.append('Reference source identity mismatch '+number)
        if not p.is_file() or sha(p)!=ref.get('sha256'):errors.append('Reference missing or changed '+number)
        else:
            try:
                from PIL import Image
                with Image.open(p) as image:image.verify()
            except (OSError,ValueError):errors.append('Reference cannot be decoded '+number)
    if case.get('options',{}).get('target')=='video':
        frames=facts.get('videoReferenceFrames',[])
        if len(frames)!=5 or sorted(f.get('fraction',-1) for f in frames)!=FRACTIONS:errors.append('Five sampled video fractions need independent source-page mapping')
        for f in frames:
            if type(f.get('sourcePage')) is not int or not 1<=f['sourcePage']<=count or f.get('sourceSha256')!=case['source']['sha256'] or not f.get('review',{}).get('actor'):errors.append('Unreviewed video-to-source mapping')
    return {'ready':not errors,'sourcePages':count,'errors':errors}
