"""Explicit human judgments bound to an immutable run and hashed evidence."""
import copy, shutil
from .common import *
from .reporting import core, write_report
from .quality import RUBRIC

REVIEWABLE={('quality','visual'),('support','channels'),('support','promises'),('deprecated','scope'),('auto','warning'),('retention','training')}

def apply_visual(run,file,output):
    """Convert a page-bound human export to the audited review protocol."""
    import tempfile
    run=Path(run);file=Path(file);verify(run);value=read(file);envelope=read(run/'run.json')
    if value.get('kind')!='visual-review-draft' or value.get('mode')!='result' or not value.get('actor') or not value.get('reviews'):raise ValueError('Result review export and explicit actor required')
    if value.get('runSha256')!=sha(run/'run.json'):raise ValueError('Visual review belongs to a different run')
    translated={'runSha256':sha(run/'run.json'),'actor':value['actor'],'reviewedAt':value.get('createdAt'),'reviews':[]}
    labels=dict(zip(['文字','裁切','重叠','图表','层级','可读性'],RUBRIC));states={'符合':'passed','不符合':'failed','不适用':'not_applicable'}
    groups={}
    for row in value['reviews']:groups.setdefault(row.get('caseId'),[]).append(row)
    for cid,rows in groups.items():
        result=next((r for r in envelope['results'] if r['caseId']==cid),None)
        assertion=next((a for a in result['assertions'] if a['id']=='visual'),None) if result else None
        metrics=assertion.get('actual',{}).get('metrics',[]) if assertion and isinstance(assertion.get('actual'),dict) else []
        if not metrics or len(rows)!=len(metrics):raise ValueError('Review must cover every recorded page/frame of the selected case')
        pending={(m['imageSha256'],digest(m['mapping'])):m for m in metrics};normalized=[]
        for row in rows:
            metric=pending.pop((row.get('actualSha256'),digest(row.get('page'))),None)
            if not metric or row.get('sourceSha256')!=result['inputSha256'] or row.get('referenceSha256')!=metric.get('referenceSha256'):raise ValueError('Stale, duplicate or incorrectly mapped page review')
            if set(row.get('rubric',{}))!=set(labels) or any(v not in states for v in row['rubric'].values()) or not row.get('note'):raise ValueError('Complete per-page rubric and evidence note required')
            normalized.append({labels[k]:states[v] for k,v in row['rubric'].items()})
        rubric={k:'failed' if any(r[k]=='failed' for r in normalized) else 'passed' if any(r[k]=='passed' for r in normalized) else 'not_applicable' for k in RUBRIC}
        translated['reviews'].append({'caseId':cid,'assertionId':'visual','status':'failed' if 'failed' in rubric.values() else 'passed','rubric':rubric,'pages':rows,
            'conclusion':'\n'.join(r['note'] for r in rows),'evidence':[{'path':str(file.resolve()),'sha256':sha(file)}]})
    with tempfile.TemporaryDirectory() as temp:
        p=Path(temp)/'review.json';atomic(p,translated);return apply(run,p,output)

def apply(run, file, output):
    run=Path(run);file=Path(file);output=Path(output);verify(run)
    if output.exists():raise ValueError('Reviewed report must have a new output directory')
    value=read(file);envelope=read(run/'run.json')
    if value.get('runSha256')!=sha(run/'run.json'):raise ValueError('Human review does not bind this run')
    if not value.get('actor') or not value.get('reviewedAt') or not value.get('reviews'):raise ValueError('Explicit actor, timestamp and reviews required')
    attachments=[]
    for row in value['reviews']:
        result=next((r for r in envelope['results'] if r['caseId']==row.get('caseId')),None)
        assertion=next((a for a in result['assertions'] if a['id']==row.get('assertionId')),None) if result else None
        if not assertion or (assertion['type'],assertion['id']) not in REVIEWABLE:raise ValueError('This deterministic assertion cannot be overridden by human review')
        if assertion['status']!='review' and not (assertion['type']=='retention' and assertion['id']=='training' and assertion['status']=='blocked'):raise ValueError('Review may not erase a confirmed failure or absent render')
        if row.get('status') not in ['passed','failed','review'] or not row.get('conclusion'):raise ValueError('Explicit judgment and conclusion required')
        if assertion['type']=='quality' and (set(row.get('rubric',{}))!=set(RUBRIC) or any(x not in ['passed','failed','not_applicable'] for x in row['rubric'].values())):raise ValueError('Complete visual rubric required')
        if assertion['type']=='quality' and isinstance(assertion.get('actual'),dict) and assertion['actual'].get('metrics'):
            metrics=assertion['actual']['metrics'];pages=row.get('pages',[])
            expected={(m['imageSha256'],digest(m['mapping']),m.get('referenceSha256')) for m in metrics}
            observed={(p.get('actualSha256'),digest(p.get('page')),p.get('referenceSha256')) for p in pages}
            if len(pages)!=len(metrics) or expected!=observed or any(p.get('sourceSha256')!=result['inputSha256'] for p in pages):raise ValueError('Complete source-bound page/frame reviews required')
            for p in pages:
                if set(p.get('rubric',{}))!=set(['文字','裁切','重叠','图表','层级','可读性']) or any(v not in ['符合','不符合','不适用'] for v in p['rubric'].values()) or not p.get('note'):raise ValueError('Complete per-page judgments required')
                if row['status']=='passed' and '不符合' in p['rubric'].values():raise ValueError('Failed page cannot yield pass')
        if not row.get('evidence'):raise ValueError('Independent review evidence required')
        for evidence in row['evidence']:
            p=Path(evidence['path'])
            if not p.is_absolute():p=file.parent/p
            if not p.is_file() or sha(p)!=evidence['sha256']:raise ValueError('Review evidence missing or changed')
            attachments.append((p,evidence['sha256']))
        if row['status']=='passed' and any(x=='failed' for x in row.get('rubric',{}).values()):raise ValueError('Failed rubric cannot yield pass')
        assertion.update(status=row['status'],humanReview={'actor':value['actor'],'reviewedAt':value['reviewedAt'],'conclusion':row['conclusion'],'rubric':row.get('rubric'),'evidence':[x['sha256'] for x in row['evidence']]})
        statuses=[a['status'] for a in result['assertions']];result['status']='failed' if 'failed' in statuses else 'review' if any(s in ['blocked','review'] for s in statuses) else 'passed'
    shutil.copytree(run,output)
    for p,h in attachments:shutil.copy2(p,output/'evidence'/('human-'+h+p.suffix))
    envelope['parentRunSha256']=value['runSha256'];envelope['runId']=safe_id(output.name);envelope['createdAt']=now();envelope['public']=False
    cases=[{'id':r['caseId'],'evaluation':{'checks':r['assertions']}} for r in envelope['results']]
    summary=core.summarize_quality(envelope['results'],cases,envelope['suite'],'command');g=summary['gate']
    summary['releaseDecision']='FAIL' if g['failed'] else 'INCOMPLETE' if g['blocked'] else 'REVIEW' if g['review'] else 'PASS'
    envelope['qualitySummary']=summary;envelope['findings']=core.build_findings(envelope['results'],envelope['suite'],envelope['target'],envelope['runId'])
    envelope['counts']={s:sum(r['status']==s for r in envelope['results']) for s in ['passed','failed','review','blocked']}
    atomic(output/'human-reviews.json',redact(value));write_report(output,envelope,read(output/'questions.json'))
    return {'report':str(output/'report.html'),'status':summary['releaseDecision'],'public':False}
