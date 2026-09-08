"""Versioned common response contract; raw target fields are never synthesized."""
import math
from acceptance.versioned import load
_v1=load('render-release-contract','contract','1')
globals().update({k:v for k,v in vars(_v1).items() if not k.startswith('_')})

def schema(proc):
    status,errors=_v1.schema(proc)
    p=proc.get('payload')
    if not isinstance(p,dict):return status,errors
    if type(p.get('pages')) is not int:errors.append('pages must be an integer, not boolean')
    entries=p.get('outputs')
    if isinstance(entries,list):
        pages=[e.get('page') for e in entries if isinstance(e,dict)]
        if all(type(x) is int for x in pages) and (pages!=sorted(pages) or len(pages)!=len(set(pages))):errors.append('Duplicate/out-of-order output pages')
        if any(isinstance(e,dict) and not e.get('file') for e in entries):errors.append('Empty output file')
    return ('failed' if errors else 'passed'),errors

def common_schema(proc):
    if proc.get('blocked') or proc.get('launchError') or proc.get('timedOut'):return 'blocked','No target response available'
    p=proc.get('payload')
    if not isinstance(p,dict):return 'failed',['Missing JSON object']
    if p.get('ok') is False:
        err=p.get('error');valid=isinstance(err,dict) and isinstance(err.get('code'),str) and bool(err['code']) and isinstance(err.get('message'),str) and bool(err['message']) and proc.get('exitCode') not in [0,None] and not p.get('outputs')
        return ('passed' if valid else 'failed'),{'branch':'error','error':err,'exitCode':proc.get('exitCode')}
    status,errors=schema(proc)
    if p.get('ok') is not True or proc.get('exitCode')!=0:errors.append('Success requires ok=true and exitCode=0')
    if p.get('format') not in ['image','pdf','video']:errors.append('Invalid output format')
    if not isinstance(p.get('input'),str) or not p['input']:errors.append('Missing/invalid input')
    if type(p.get('durationMs')) not in [int,float] or not math.isfinite(p.get('durationMs',float('nan'))) or p['durationMs']<0:errors.append('Missing/invalid durationMs')
    for entry in p.get('outputs',[]) if isinstance(p.get('outputs'),list) else []:
        if not isinstance(entry,dict):continue
        for key in ['width','height','bytes']:
            if key in entry and (type(entry[key]) is not int or entry[key]<(0 if key=='bytes' else 1)):errors.append('Invalid output '+key)
    return ('failed' if errors else 'passed'),{'branch':'success','errors':errors}

def parity(first,second):
    for proc in [first,second]:
        if proc.get('blocked') or proc.get('launchError') or proc.get('timedOut'):return 'blocked','Parity requires both CLI and SDK responses'
    def project(proc):
        p=proc.get('payload') or {}
        return {**{k:p.get(k) for k in ['ok','engine','route','format','pages','caveat','lifecycle','uploaded']},
                'errorCode':machine_code(proc),'outputPages':[x.get('page') for x in p.get('outputs',[]) if isinstance(x,dict)]}
    a,b=project(first),project(second)
    # Lifecycle task identities/timestamps are per invocation; preserve shape, not values.
    def shape(value):
        if isinstance(value,dict):return {k:shape(v) for k,v in value.items()}
        if isinstance(value,list):return [shape(v) for v in value]
        return type(value).__name__
    a['lifecycle']=shape(a['lifecycle']);b['lifecycle']=shape(b['lifecycle'])
    return ('passed' if a==b else 'failed'),{'cliOrFirst':a,'sdkOrSecond':b}
