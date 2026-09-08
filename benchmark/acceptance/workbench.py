"""Offline visual workbench; explicit human drafts export, no implicit approval."""
import base64,shutil
from .common import *

def write(path,items,title,mode='result',run_sha=None,embed=True):
    import copy
    data=copy.deepcopy(items)
    for item in data:
        for page in item.get('pages',[]):
            for key in ['image','referenceImage','sourceImage']:
                if page.get(key):
                    p=Path(page[key]);expected=page.get({'image':'imageSha256','referenceImage':'referenceSha256','sourceImage':'sourceImageSha256'}[key])
                    if not expected or sha(p)!=expected:raise ValueError('Preview hash mismatch')
                    if embed:page[key]='data:image/png;base64,'+base64.b64encode(p.read_bytes()).decode()
                    else:
                        rel='gt-assets/'+expected+'.png';dest=Path(path).parent/rel;dest.parent.mkdir(exist_ok=True)
                        if not dest.exists() or sha(dest)!=expected:shutil.copyfile(p,dest)
                        page[key]=rel
    template=(Path(__file__).parent/'visual-workbench.html').read_text()
    template=template.replace('__REVIEW_STATE__',(Path(__file__).parent/'review-state.js').read_text()).replace('__REVIEW_NAMESPACE__',digest(str(Path(path).resolve().parent)))
    atomic(path,template.replace('__TITLE__',html.escape(title)).replace('__MODE__',mode).replace('__RUN_SHA__',json.dumps(run_sha)).replace('__DATA__',json.dumps(data,ensure_ascii=False).replace('<','\\u003c')))
