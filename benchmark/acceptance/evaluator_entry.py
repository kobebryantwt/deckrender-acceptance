from .versioned import load
ev=load('render-release-contract','contract','2')

def evaluate(context):
    c=context['case'];norm=context['normalizedTargetOutput'];proc=norm.get('data',{})
    if not isinstance(proc,dict):proc={}
    assertions=[]
    for ch in c.get('evaluation',{}).get('checks',[]):
        if proc.get('blocked'):status,actual='blocked',proc['blocked']
        elif ch['id']=='outcome':status,actual=ev.outcome(proc,c['options'].get('expectedSupport'))
        elif ch['id'] in ['artifacts','integrity']:status,actual=ev.artifact_checks(proc,c.get('facts',{}))
        elif ch['id']=='fields':status,actual=ev.schema(proc)
        elif ch['id']=='commonSchema':status,actual=ev.common_schema(proc)
        else:status,actual='blocked','This multi-stage check requires release_acceptance.py orchestration; do not infer success from a single target invocation'
        assertions.append({**ch,'status':status,'actual':actual})
    return {'assertions':assertions,'metrics':{},'evidence':[]}
