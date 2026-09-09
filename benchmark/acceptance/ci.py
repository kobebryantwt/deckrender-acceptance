import shutil
from .common import *
from .reporting import core, write_report

def aggregate(home,inputs,run_id,snapshot=None):
    runs=[]
    for p in Path(inputs).rglob('run.json'):
        if p.parent.parent.name=='raw':continue
        verify(p.parent);runs.append((p.parent,read(p)))
    expected={'release','local','privacy','cloud','quality'}
    if {e.get('group') for _,e in runs}!=expected or len(runs)!=len(expected):raise ValueError('Missing or duplicate CI group; cannot aggregate into a release verdict')
    from .snapshot import load
    from .execution import manifest, validate_group
    if snapshot is None:raise ValueError('Aggregation requires the reviewed source snapshot')
    expected_manifest=manifest(load(snapshot))
    snapshot_hash=sha(Path(snapshot)/'SHA256SUMS.json')
    for folder,envelope in runs:
        if envelope.get('snapshotHash')!=snapshot_hash or envelope.get('executionManifest')!=expected_manifest or envelope.get('executionContractHash')!=digest(expected_manifest):
            raise ValueError('CI groups do not bind the expected snapshot and execution manifest')
        validate_group(envelope,read(folder/'questions.json'),expected_manifest)
    baseline=runs[0][1]
    identity=lambda e:{k:v for k,v in e['target'].items() if k!='runtimeIntegrity'}
    if any(identity(e)!=identity(baseline) or e['evaluator']!=baseline['evaluator'] or e['qualityPolicyHash']!=baseline['qualityPolicyHash'] for _,e in runs):raise ValueError('CI groups have incompatible target/evaluator/policy')
    out=Path(home)/'runs'/safe_id(run_id)
    if out.exists():raise ValueError('Aggregate run exists')
    out.mkdir(parents=True);results=[];questions=[]
    for folder,e in runs:
        results.extend(e['results']);questions.extend(read(folder/'questions.json'))
        for sub in (folder/'evidence').iterdir():shutil.copytree(sub,out/'evidence'/sub.name)
    if len({r['caseId'] for r in results})!=len(results):raise ValueError('Duplicate CI cases')
    cases=[{'id':r['caseId'],'covers':[r['assertions'][0]['featureId']],'evaluation':{'checks':r['assertions']}} for r in results]
    summary=core.summarize_quality(results,cases,baseline['suite'],'command');g=summary['gate']
    summary.update(releaseDecision='FAIL' if g['failed'] else 'INCOMPLETE' if g['blocked'] else 'REVIEW' if g['review'] else 'PASS',decisionReason='strict_handbook_gates',scope='complete')
    envelope={**baseline,'runId':run_id,'createdAt':now(),'group':'all','results':results,'qualitySummary':summary,'counts':{s:sum(r['status']==s for r in results) for s in ['passed','failed','review','blocked']},'executionContractHash':digest(expected_manifest),'findings':core.build_findings(results,baseline['suite'],baseline['target'],run_id),'public':all(e.get('public') for _,e in runs)}
    modes={e.get('executionMode','formal') for _,e in runs}
    if len(modes)!=1:raise ValueError('Mixed execution modes')
    if len({e.get('executionPolicyHash') for _,e in runs})!=1:raise ValueError('Mixed execution budgets or cloud selection')
    envelope['executionMode']=modes.pop()
    sessions=[e['cloudExecution'] for _,e in runs if 'cloudExecution' in e]
    if sessions:envelope['cloudExecution']=max(sessions,key=lambda s:len(s['events']))
    if envelope['executionMode']=='debug':
        summary['scope']='partial:debug'
        summary['releaseDecision']='FAIL' if g['failed'] else 'INCOMPLETE'
        summary['decisionReason']='debug_run_not_release_signoff'
    write_report(out,envelope,questions);return {'runId':run_id,'report':str(out/'report.html'),'qualitySummary':summary}
