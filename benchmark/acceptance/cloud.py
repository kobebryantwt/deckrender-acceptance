"""Durable retention experiments; unavailable lifecycle authority stays blocked.
Provider commands are explicit JSON argv configuration, never shell interpolation.
They are not enabled by default and may only refer to an independently operated audit service.
"""
import datetime as dt, os, shlex
from .common import *

KINDS={'task','input','intermediate','output'}

def validate_submission(data, requested, source_sha):
    if data.get('sourceSha256')!=source_sha:raise ValueError('Submission source identity mismatch')
    if data.get('requestedHours')!=requested:raise ValueError('Provider changed requested retention')
    effective=1 if requested is None else requested
    if data.get('effectiveHours')!=effective:raise ValueError('Effective retention differs from handbook')
    if not data.get('taskId'):raise ValueError('No task identity')
    objects=data.get('objects',[])
    if {o.get('kind') for o in objects}!=KINDS or any(not o.get('id') for o in objects):raise ValueError('Task/input/intermediate/output inventory incomplete')
    if len({(o['kind'],o['id']) for o in objects})!=len(objects):raise ValueError('Duplicate lifecycle objects')
    created=dt.datetime.fromisoformat(data['createdAt']);expires=dt.datetime.fromisoformat(data['expiresAt'])
    if created.tzinfo is None or expires.tzinfo is None:raise ValueError('Lifecycle timestamps need timezone')
    if abs((expires-created).total_seconds()-effective*3600)>1:raise ValueError('Provider expiry does not match retention')
    return data

def provider(command_env, request, dest):
    command=json.loads(os.environ[command_env])
    if not isinstance(command,list) or not command or not all(isinstance(x,str) for x in command):raise ValueError('Provider command must be a JSON argv array')
    req=Path(dest)/'request.json';atomic(req,request)
    p=process([*command,str(req.resolve())],timeout=300)
    atomic(Path(dest)/'provider-process.json',redact(p))
    if p['exitCode']!=0:raise ValueError('Provider unavailable; see provider-process.json')
    return json.loads(p['stdout'])

def submit(home,case):
    from .releases import active
    try:
        _,release=active(home);target_identity={k:release[k] for k in ['tag','commit','npmTarballSha256']}
    except (ValueError,OSError):target_identity=None
    key=digest({'case':case,'source':case['source']['sha256'],'target':target_identity})[:24]
    folder=Path(home)/'cloud'/key;folder.mkdir(parents=True,exist_ok=True)
    existing=read(folder/'experiment.json')
    if existing and existing.get('status')!='blocked':return existing  # Never re-submit after an uncertain response.
    record={'id':key,'target':target_identity,'caseId':case['id'],'requestedHours':case['options']['retentionHours'],'sourceSha256':case['source']['sha256'],'status':'blocked','createdAt':existing['createdAt'] if existing else now()}
    if case.get('reviewStatus')!='approved':record['reason']='Scenario not approved'
    elif not target_identity:record['reason']='Frozen release identity unavailable'
    elif os.getenv('REN_ALLOW_CLOUD')!='1' or not case.get('public'):record['reason']='Cloud usage/source authorization missing'
    elif not os.getenv('REN_LIFECYCLE_COMMAND'):record['reason']='Released target retention submission API unavailable; configure verified lifecycle adapter only when API exists'
    elif not os.getenv('REN_AUDIT_COMMAND'):record['reason']='Independent audit provider unavailable'
    else:
        atomic(folder/'experiment.json',{**record,'status':'submission-uncertain','reason':'Intent persisted before external mutation; resume by idempotency key, never blindly resubmit'})
        try:
            data=provider('REN_LIFECYCLE_COMMAND',{'action':'submit','idempotencyKey':key,'input':case['source'],'requestedHours':record['requestedHours'],'target':target_identity},folder)
            validate_submission(data,record['requestedHours'],record['sourceSha256'])
            if data.get('target')!=target_identity:raise ValueError('Submission target release identity mismatch')
            record.update({'status':'pending','submission':data,'expiresAt':data['expiresAt']})
        except (ValueError,OSError) as e:record.update(status='submission-uncertain',reason=str(e))
    atomic(folder/'experiment.json',redact(record));return record

def evaluate_audit(experiment, audit, at=None):
    at=at or dt.datetime.now(dt.timezone.utc)
    submission=experiment['submission'];deadline=dt.datetime.fromisoformat(submission['expiresAt'])
    if at<deadline:return 'blocked','Retention interval not elapsed'
    if audit.get('taskId')!=submission['taskId'] or audit.get('sourceSha256')!=experiment['sourceSha256']:return 'blocked','Audit does not bind experiment identity'
    try:
        checked=dt.datetime.fromisoformat(audit['checkedAt'])
        if checked.tzinfo is None or checked<deadline or checked>at:return 'blocked','Invalid/early/future audit timestamp'
    except (ValueError,KeyError,TypeError):return 'blocked','Missing audit timestamp'
    if not audit.get('authority') or not audit.get('auditId'):return 'blocked','Independent service audit authority/ID missing'
    expected={(o['kind'],o['id']) for o in submission['objects']}
    rows=audit.get('objects',[])
    if {(o.get('kind'),o.get('id')) for o in rows}!=expected or len(rows)!=len(expected):return 'blocked','Incomplete object inventory'
    for row in rows:
        if row.get('state')=='retained':return 'failed',row
        if row.get('state')!='deleted' or not row.get('deletionLogId'):return 'blocked','A 404 or unavailable download is not deletion evidence'
        try:
            deleted=dt.datetime.fromisoformat(row['deletedAt'])
            if deleted.tzinfo is None or deleted>checked:return 'blocked','Invalid deletion timestamp'
            if deleted>deadline:return 'failed','Deletion happened after published expiry'
        except (ValueError,KeyError,TypeError):return 'blocked','Deletion timestamp missing'
    return 'passed',{'auditId':audit['auditId'],'authority':audit['authority'],'objects':len(rows)}

def collect(home, evidence=None):
    results=[]
    for path in sorted((Path(home)/'cloud').glob('*/experiment.json')):
        e=read(path)
        if e.get('status')=='submission-uncertain' and os.getenv('REN_LIFECYCLE_COMMAND'):
            folder=path.parent/'reconciliation'/stamp();folder.mkdir(parents=True)
            try:
                data=provider('REN_LIFECYCLE_COMMAND',{'action':'lookup','idempotencyKey':e['id']},folder)
                validate_submission(data,e['requestedHours'],e['sourceSha256'])
                if data.get('target')!=e.get('target'):raise ValueError('Lookup target identity mismatch')
                e.update(status='pending',submission=data,expiresAt=data['expiresAt']);atomic(path,redact(e))
            except (ValueError,OSError) as err:
                results.append({**e,'lookupError':str(err)});continue
        if e.get('status') not in ['pending','blocked-audit']:results.append(e);continue
        if dt.datetime.now(dt.timezone.utc)<dt.datetime.fromisoformat(e['expiresAt']):results.append(e);continue
        folder=path.parent/'audits'/stamp();folder.mkdir(parents=True)
        try:
            if evidence:
                audit=read(evidence)
                if audit.get('taskId')!=e['submission']['taskId']:continue
            elif os.getenv('REN_AUDIT_COMMAND'):audit=provider('REN_AUDIT_COMMAND',{'action':'collect','experiment':e},folder)
            else:raise ValueError('Independent audit provider missing')
            status,actual=evaluate_audit(e,audit);atomic(folder/'audit.json',redact(audit))
            e.update(status='blocked-audit' if status=='blocked' else status,actual=actual,lastCollectedAt=now(),auditEvidence=str(folder))
        except (ValueError,OSError) as err:e.update(status='blocked-audit',reason=str(err))
        atomic(path,e);results.append(e)
    return results
