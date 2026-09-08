import copy, shutil
from .common import *
from .maintenance import sync
from .gt_contract import readiness

def export(home, output, allow_draft=False):
    output=Path(output)
    if output.exists():raise ValueError('Snapshot output already exists; preserve it and choose a new directory')
    data=sync(home);drafts=[q['questionId'] for q in data['questions'] if q['reviewStatus']!='approved']
    private=[c['id'] for c in data['cases'] if not c.get('public')]
    gt_gaps=[{'caseId':c['id'],**readiness(c)} for c in data['cases'] if c.get('operation')=='quality' and not readiness(c)['ready']]
    if (drafts or private or gt_gaps) and not allow_draft:raise ValueError(f'Snapshot not ready: {len(drafts)} draft questions, {len(private)} private cases, {len(gt_gaps)} incomplete visual GT cases')
    output.mkdir(parents=True)
    data=copy.deepcopy(data)
    for case in data['cases']:
        path=Path(case['source']['uri'])
        if not path.exists() or sha(path)!=case['source']['sha256']:raise ValueError('Source changed during snapshot export')
        if not case.get('public'):
            case['source']['uri']='[PRIVATE SOURCE OMITTED]';case.get('facts',{}).pop('references',None);continue
        rel='objects/'+case['source']['sha256']+path.suffix
        dest=output/rel;dest.parent.mkdir(exist_ok=True);shutil.copyfile(path,dest)
        case['source']['uri']=rel
        for ref in case.get('facts',{}).get('references',{}).values():
            if not allow_draft and ref.get('status')!='approved':raise ValueError('Formal snapshot requires reviewed GT references')
            if not ref.get('public') or ref.get('sourceSha256')!=case['source']['sha256']:raise ValueError('Private/unbound GT reference cannot enter a public snapshot')
            if sha(ref['path'])!=ref['sha256']:raise ValueError('GT reference changed')
            refrel='objects/'+ref['sha256']+Path(ref['path']).suffix
            shutil.copyfile(ref['path'],output/refrel);ref['path']=refrel
    data=redact(data)
    atomic(output/'inputs.json',data)
    atomic(output/'snapshot.json',{'schemaVersion':2,'createdAt':now(),'status':'draft' if drafts or private or gt_gaps else 'approved','inputSha256':sha(output/'inputs.json'),'draftCount':len(drafts),'privateCount':len(private),'gtGaps':gt_gaps,'policy':'strict-handbook-v2'})
    if not drafts and not private and not gt_gaps:atomic(output/'READY',{'snapshotSha256':sha(output/'snapshot.json'),'inputsSha256':sha(output/'inputs.json')})
    seal(output);return validate(output,require_ready=not allow_draft)

def validate(output, require_ready=True):
    output=Path(output);verify(output);meta=read(output/'snapshot.json');data=read(output/'inputs.json')
    if sha(output/'inputs.json')!=meta['inputSha256']:raise ValueError('Snapshot inputs changed')
    if require_ready:
        ready=read(output/'READY')
        if not ready or ready!={'snapshotSha256':sha(output/'snapshot.json'),'inputsSha256':sha(output/'inputs.json')}:raise ValueError('READY does not bind this snapshot')
        if meta['status']!='approved' or any(q['reviewStatus']!='approved' or not q.get('review') for q in data['questions']):raise ValueError('Draft or unaudited answers cannot be used in CI')
        if any(c.get('reviewStatus')!='approved' or not c.get('public') for c in data['cases']):raise ValueError('Unapproved/private case')
    for c in data['cases']:
        if require_ready and c.get('operation')=='quality' and not readiness(c,output)['ready']:raise ValueError('Incomplete reviewed visual GT')
        if not c.get('public') and not require_ready:continue
        p=inside(output,c['source']['uri'])
        if not p.is_file() or sha(p)!=c['source']['sha256']:raise ValueError('Snapshot object identity mismatch')
        for ref in c.get('facts',{}).get('references',{}).values():
            if require_ready and ref.get('status')!='approved':raise ValueError('Unreviewed GT reference')
            p=inside(output,ref['path'])
            if not ref.get('public') or ref.get('sourceSha256')!=c['source']['sha256'] or sha(p)!=ref['sha256']:raise ValueError('Snapshot GT reference identity mismatch')
    return {'ok':True,'status':meta['status'],'cases':len(data['cases'])}

def load(output):
    validate(output);data=read(Path(output)/'inputs.json')
    for c in data['cases']:
        c['source']['uri']=str(inside(output,c['source']['uri']))
        for ref in c.get('facts',{}).get('references',{}).values():ref['path']=str(inside(output,ref['path']))
    return data
