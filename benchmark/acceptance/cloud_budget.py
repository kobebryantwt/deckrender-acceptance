"""Run-local cloud execution budget. Never persists credentials or reuses prior runs."""
import copy, shutil
from .common import *

def is_cloud(case):
    o=case['options']
    return o.get('engine')=='cloud' or o.get('engine')=='auto' and (case['format'] not in ['pptx','pdf'] or o.get('target')=='video')

def page_cost(case):
    facts=case.get('facts',{})
    count=facts.get('pages') or facts.get('visualPageCount')
    return count if type(count) is int and count>0 else None

def plan(cases):
    rows=[]
    for c in cases:
        if not is_cloud(c) or c.get('operation')=='retention':continue
        # Schema parity executes the main call, two repeated errors and counterpart calls.
        upper=6 if c['operation']=='schema' else 1
        rows.append({'caseId':c['id'],'maxCalls':upper,'sourcePagesPerCall':page_cost(c)})
    return {'cases':rows,'maxCalls':sum(r['maxCalls'] for r in rows),
            'maxSourcePages':sum(r['maxCalls']*(r['sourcePagesPerCall'] or 0) for r in rows),
            'unknownPageCases':[r['caseId'] for r in rows if r['sourcePagesPerCall'] is None],
            'unit':'source-page submissions; not provider credits or video frames'}

class Session:
    def __init__(self, cases, mode='formal', cloud_enabled=False, max_calls=None, max_pages=None, debug_cases=()):
        if mode not in ['formal','debug']:raise ValueError('Invalid execution mode')
        self.plan=plan(cases);self.mode=mode;self.enabled=cloud_enabled
        self.max_calls=self.plan['maxCalls'] if max_calls is None else min(max_calls,self.plan['maxCalls'])
        self.max_pages=self.plan['maxSourcePages'] if max_pages is None else min(max_pages,self.plan['maxSourcePages'])
        if self.max_calls<0 or self.max_pages<0:raise ValueError('Budget must be nonnegative')
        self.debug_cases=set(debug_cases);self.events=[];self.cache={};self.stopped=set();self.calls=0;self.pages=0
    def snapshot(self):
        return {'mode':self.mode,'enabled':self.enabled,'debugCases':sorted(self.debug_cases),'plan':self.plan,'limits':{'calls':self.max_calls,'sourcePages':self.max_pages},
                'actualCalls':self.calls,'submittedSourcePages':self.pages,'events':copy.deepcopy(self.events)}
    def invoke(self, invoke, home, case, output, **flags):
        if not is_cloud(case):return invoke(home,case,output,**flags)
        output=Path(output);output.mkdir(parents=True,exist_ok=True)
        o=case['options'];profile=o.get('credentialVariant','normal')
        reusable=case['operation'] in ['render','quality','auto','planned'] and not any(flags.values())
        key=digest({'source':case['source']['sha256'],'format':case['format'],
                    'options':{k:o[k] for k in ['engine','target','interface','pages','imageFormat','credentialVariant'] if k in o},'flags':flags})
        def blocked(reason):
            self.events.append({'caseId':case['id'],'status':'blocked','reason':reason,'profile':profile})
            result={'blocked':reason};atomic(output/'cloud-execution.json',result);return result
        if not self.enabled:return blocked('Cloud disabled for this execution mode')
        if self.mode=='debug' and case['id'] not in self.debug_cases:return blocked('Outside explicit debug cloud selection')
        if reusable and key in self.cache:
            old,proc,inventory=self.cache[key]
            if any(not (old/p).is_file() or sha(old/p)!=h for p,h in inventory.items()):return blocked('Cached execution evidence changed')
            for rel in inventory:
                dest=output/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(old/rel,dest)
            result=copy.deepcopy(proc)  # Original command, stdout/stderr and payload remain verbatim.
            self.events.append({'caseId':case['id'],'status':'reused','executionRef':proc['executionRef'],'profile':profile})
            atomic(output/'cloud-execution.json',{'status':'reused','executionRef':proc['executionRef']})
            return result
        if profile in self.stopped:return blocked('Cloud account circuit open after payment/authentication failure')
        cost=page_cost(case)
        if cost is None:return blocked('Cloud source page count unknown; cannot enforce page budget')
        if self.calls>=self.max_calls or self.pages+cost>self.max_pages:return blocked('Cloud execution budget exhausted')
        # Reserve before invoking; a crash or timeout must never refund a potentially billed call.
        self.calls+=1;self.pages+=cost;ref=f'cloud-{self.calls:04d}'
        result=invoke(home,case,output,**flags)
        result['executionRef']=ref
        event={'caseId':case['id'],'status':'invoked','executionRef':ref,'profile':profile,'sourcePages':cost}
        self.events.append(event)
        payload=result.get('payload')
        payload=payload if isinstance(payload,dict) else {}
        err=payload.get('error')
        err=err if isinstance(err,dict) else {}
        raw=str(err)+' '+result.get('stderr','')
        if profile=='normal' and (err.get('code')=='auth_error' or '402' in raw or 'out of balance' in raw.lower()):self.stopped.add(profile)
        atomic(output/'cloud-execution.json',event)
        if reusable and payload.get('ok') is True and result.get('exitCode')==0:
            inventory={str(p.relative_to(output)):sha(p) for p in output.rglob('*') if p.is_file()}
            self.cache[key]=(output,copy.deepcopy(result),inventory)
        return result
