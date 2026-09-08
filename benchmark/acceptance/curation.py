"""A source/image-bound review queue, never an approval or a reduced test denominator."""
from .common import *

CONFIG=REPO/'benchmark/config/visual-curation.json'

def annotate(items,config=None):
    policy=config if config is not None else read(CONFIG,{'sources':{}})
    for item in items:
        spec=policy.get('sources',{}).get(item['sourceId'],{})
        current=spec.get('sourceSha256')==item['sourceSha256']
        item['curation']={'status':'candidate' if current else 'unselected','reason':spec.get('reason','尚未逐页筛选') if current else '无当前源版本的精选记录','scope':'精选仅决定审核顺序；不代替完整 GT、正式覆盖或人工批准'}
        for page in item.get('pages',[]):
            n=page.get('mapping',{}).get('sourcePage') or page.get('mapping',{}).get('pdfPage')
            selected=spec.get('pages',{}).get(str(n),{}) if current else {}
            valid=bool(selected and selected.get('imageSha256')==page['imageSha256'])
            page['curation']={**selected,'priority':bool(valid and selected.get('priority')),'status':'draft' if valid else 'stale' if selected else 'unselected'}
            if selected and not valid:page['curation']['note']='参考图变化，须重新筛选；旧页说明不适用于新图'
    return items

def summary(items):
    return {'sources':len(items),'prioritySources':sum(any(p.get('curation',{}).get('priority') for p in x.get('pages',[])) for x in items),
            'priorityPages':sum(p.get('curation',{}).get('priority',False) for x in items for p in x.get('pages',[])),
            'allPreviewPages':sum(len(x.get('pages',[])) for x in items),'approval':'draft; no automatic approval','scope':'Review priority only; full GT readiness unchanged'}
