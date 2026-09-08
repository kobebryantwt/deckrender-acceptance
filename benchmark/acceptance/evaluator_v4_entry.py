from . import evaluation as ev

def evaluate(context):
    c=context['case'];norm=context['normalizedTargetOutput'];proc=norm.get('data',{})
    if not isinstance(proc,dict):proc={}
    assertions=[]
    from .gt_contract import readiness
    gt=readiness(c) if c.get('operation')=='quality' else {'ready':True}
    for ch in c.get('evaluation',{}).get('checks',[]):
        if not gt['ready']:status,actual='blocked',gt
        elif proc.get('blocked'):status,actual='blocked',proc['blocked']
        elif ch['id']=='outcome':status,actual=ev.declared_outcome(proc,c.get('contract'))
        elif ch['id'] in ['artifacts','integrity']:status,actual=ev.declared_artifacts(proc,c.get('facts',{}),c.get('contract'))
        elif ch['id']=='fields':status,actual=ev.schema(proc)
        elif ch['id']=='commonSchema':status,actual=ev.common_schema(proc)
        else:status,actual='blocked','This multi-stage check requires release_acceptance.py orchestration; do not infer success from a single target invocation'
        assertions.append({**ch,'status':status,'actual':actual})
    return {'assertions':assertions,'metrics':{},'evidence':[]}
