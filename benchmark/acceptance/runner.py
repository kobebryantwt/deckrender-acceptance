import copy, os, re
from .common import *
from . import evaluation as ev, target, cloud, quality, releases
from .maintenance import sync
from .snapshot import load as load_snapshot
from .reporting import core, write_report

GROUPS={'release':{1,5,10,11},'local':{2,6,7},'privacy':{3},'cloud':{4,8},'quality':{9},'contracts':set(range(1,12))-{9},'all':set(range(1,12))}

def frozen_text(root):
    files=[root/'source/README.md',root/'source/SECURITY.md',*sorted((root/'source/docs').glob('*.md')),*sorted((root/'package/dist').glob('*.d.ts'))]
    return '\n'.join(f'FILE {p.relative_to(root)}\n'+p.read_text(errors='replace') for p in files if p.exists())

def check_case(home,case,directory,root,identity):
    op=case['operation'];checks=case['evaluation']['checks'];answers={};directory=Path(directory)
    for binding in [case.get('contract'),case.get('retentionContract')]:
        if binding and binding.get('status')=='declared' and binding.get('release',{}).get('commit')!=identity.get('commit'):
            return {ch['id']:('blocked','Reviewed expectation belongs to another release commit') for ch in checks}
    def result(key,status,actual):answers[key]=(status,actual)
    if op=='release':
        source=read(root/'source/package.json');pkg=read(root/'package/package.json')
        sl=(root/'source/LICENSE').read_text().replace('\r\n','\n');pl=(root/'package/LICENSE').read_text().replace('\r\n','\n')
        result('mit','passed' if source.get('license')==pkg.get('license')=='MIT' and sl==pl and sl.startswith('MIT License') else 'failed',{'tagLicense':source.get('license'),'npmLicense':pkg.get('license'),'licenseBodiesEqual':sl==pl})
        consistent=source['version']==pkg['version']==identity['version'] and identity['tag'].lstrip('v')==identity['version']
        result('identity','passed' if consistent and identity['notes'] else 'failed',identity)
    elif op in ['deprecated','support']:
        text=frozen_text(root);atomic(directory/'published-declarations.txt',text)
        if op=='deprecated':
            # Public source types and usage examples are stronger than a stray mention in deprecation text.
            readme=(root/'source/README.md').read_text()
            active=bool(re.search(r'deckrender\s+(?:[^\n]*\.html|https?://)|`\.md`\s*\|\s*✅',text))
            deprecated=bool(re.search(r'deprecat|弃用',text,re.I)) and bool(re.search(r'(remov\w*|移除)[^\n]*v?\d+\.\d+',text,re.I))
            result('scope','failed' if active and not deprecated else 'review',{'activeUsageEvidence':active,'deprecationAndRemovalVersion':deprecated,'evidence':'published-declarations.txt','note':'Human confirmation required if declarations are ambiguous'})
        else:
            security=(root/'source/SECURITY.md').exists()
            private=bool(re.search(r'confidential|sensitive|private report|机密|私密|敏感',text,re.I))
            result('channels','review' if security and private else 'failed',{'securityDocument':security,'confidentialGuidanceMention':private,'issueUrl':read(root/'source/package.json').get('bugs')})
            result('promises','review',{'evidence':'published-declarations.txt','rubric':'Verify each SLA, certification, region, price and enterprise promise against independently supplied terms; keyword presence is not proof'})
    elif op=='retention':
        from .contracts import retention_expectation
        contract=case.get('retentionContract') or retention_expectation(home)
        state=contract.get('supported') if contract.get('status')=='declared' else None
        result('configuration','failed' if state is False else 'review' if state is True else 'blocked',contract)
        experiments=[read(p) for p in (Path(home)/'cloud').glob('*/experiment.json')]
        e=next((x for x in experiments if x['caseId']==case['id'] and x['sourceSha256']==case['source']['sha256'] and x.get('target',{}).get('commit')==identity['commit']),None)
        result('deletion',e['status'] if e and e['status'] in ['passed','failed'] else 'blocked',e or {'productSupported':False,'reason':'上游服务未提供删除审计接口与试验数据；记录为 blocked'})
        result('training','blocked',{'productSupported':False,'reason':'需要独立的无训练政策与实施审计接口；记录为 blocked'})
    else:
        if op=='quality':
            from .gt_contract import readiness
            gt=readiness(case)
            if not gt['ready']:return {ch['id']:('blocked',{'reason':'Visual GT not ready; target not executed',**gt}) for ch in checks}
        privacy=op=='privacy' or op=='dependency' or op=='render' and case['options']['engine']=='local';proc=target.invoke(home,case,directory,privacy=privacy,missing_dependency=op=='dependency')
        # Raw target output is retained outside publishable reports with restrictive permissions.
        private=Path(home)/'private'/directory.parent.name/(case['id']+'.json');atomic(private,proc);private.chmod(0o600)
        atomic(directory/'target.json',redact(proc))
        if proc.get('blocked') or proc.get('timedOut') or proc.get('launchError'):
            return {ch['id']:('blocked',{'reason':proc.get('blocked') or proc.get('stderr'),'diagnostics':proc['diagnostics']} if proc.get('diagnostics') else proc.get('blocked') or proc.get('stderr')) for ch in checks}
        result('commonSchema',*ev.common_schema(proc))
        if op=='render':
            support=case['options'].get('expectedSupport')
            if case['options'].get('credentialVariant')=='exhausted_quota':
                status,actual=ev.outcome(proc,'exhausted_quota')
            else:
                status,actual=ev.declared_outcome(proc,case.get('contract')) if case.get('contract') else ev.outcome(proc,support)
            result('outcome',status,actual)
            if support is True and status=='passed':result('artifacts',*ev.declared_artifacts(proc,case.get('facts',{}),case.get('contract')))
            elif status=='blocked':result('artifacts','blocked',actual)
            elif support is False:result('artifacts',status,actual)
            else:result('artifacts','review' if support is None else 'failed','No successful render to inspect')
            if case['options'].get('checkPrivacy'):answers.update(ev.privacy_evidence(proc,directory))
        elif op=='privacy':answers.update(ev.privacy_evidence(proc,directory))
        elif op=='planned':
            status,actual=ev.declared_outcome(proc,case.get('contract'));code=str(ev.machine_code(proc)).lower()
            result('rejected','passed' if status=='passed' and any(x in code for x in ['unsupported','not_implemented','planned']) else 'failed',actual)
            matrix=ev.declaration_matrix((root/'source/docs/formats.md').read_text())
            advertised=any(value for key,value in matrix.items() if ':'+case['format']+':' in key)
            result('declaration','failed' if advertised else 'passed',{'advertisedRenderable':advertised})
        elif op=='schema':
            first=target.invoke(home,case,directory/'invalid-1',invalid=True);second=target.invoke(home,case,directory/'invalid-2',invalid=True)
            a=ev.machine_code(first);b=ev.machine_code(second)
            code_ok=bool(a and a==b and first['exitCode']==second['exitCode'] and first['exitCode'] not in [None,0])
            # Validate actual CLI exit code using the release's error table, not a guessed convention.
            docs=(root/'source/docs/errors.md').read_text() if (root/'source/docs/errors.md').exists() else ''
            rows=[line for line in docs.splitlines() if a and str(a).lower() in line.lower()]
            matches=any(str(first.get('exitCode')) in re.findall(r'\b\d+\b',line) for line in rows)
            result('error','failed' if not code_ok else 'passed' if case['options']['interface']=='sdk' or matches else 'review',{'firstCode':a,'secondCode':b,'exitCodes':[first.get('exitCode'),second.get('exitCode')],'documentedRows':rows})
            if any(p.get('blocked') or p.get('launchError') or p.get('timedOut') for p in [first,second]):result('error','blocked','Both repeated error responses are required to assess stability')
            boundary_status,boundary_actual=ev.common_schema(first)
            expected_codes=[m.group(1) for line in docs.splitlines() if 'missing input' in line.lower() for m in [re.search(r'`([a-z_]+)`',line)] if m]
            if boundary_status!='blocked':
                if (first.get('payload') or {}).get('ok') is not False or list(Path(first.get('artifactsDir',directory/'invalid-1'/'artifacts')).glob('*')) or expected_codes and a not in expected_codes:boundary_status='failed'
                elif not expected_codes and boundary_status=='passed':boundary_status='review'
            boundary_actual={'schema':boundary_actual,'documentedMissingInputCodes':expected_codes}
            result('boundary',boundary_status,boundary_actual)
            counterpart=copy.deepcopy(case);counterpart['options']['interface']='sdk' if case['options']['interface']=='cli' else 'cli'
            other=target.invoke(home,counterpart,directory/'counterpart')
            other_errors=[target.invoke(home,counterpart,directory/f'counterpart-invalid-{i}',invalid=True) for i in [1,2]]
            atomic(directory/'interface-comparison.json',redact({'first':proc,'second':other}))
            parity_status,parity_actual=ev.parity(proc,other)
            schema_status,schema_actual=ev.common_schema(other)
            statuses=[parity_status,schema_status]+[ev.common_schema(p)[0] for p in other_errors]
            codes=[ev.machine_code(p) for p in other_errors]
            if all(not p.get('blocked') and not p.get('launchError') and not p.get('timedOut') for p in other_errors):
                if not a or codes!=[a,a] or any((p.get('payload') or {}).get('ok') is not False or p.get('exitCode') in [0,None] or list(Path(p.get('artifactsDir',directory/f'counterpart-invalid-{i}'/'artifacts')).glob('*')) for i,p in enumerate(other_errors,1)):statuses.append('failed')
            else:statuses.append('blocked')
            result('parity',next((s for s in ['failed','blocked','review'] if s in statuses),'passed'),{'comparison':parity_actual,'counterpartSchema':schema_actual,'counterpartErrorCodes':codes,'expectedErrorCode':a})
        elif op=='dependency':
            err=ev.machine_code(proc);message=(proc.get('stdout','')+proc.get('stderr','')).lower()
            explicit=any(x in message for x in ['install','executable','binary','chromium','office2html'])
            result('actionable','passed' if err and proc['exitCode'] not in [0,None] and explicit and not (proc.get('payload') or {}).get('ok') else 'failed',proc.get('payload') or message)
        elif op=='auto':
            access_status,access_detail=ev.outcome(proc,True)
            if access_status=='blocked':
                for key in ['selection','warning','upload']:result(key,'blocked',access_detail)
                return answers
            p=proc.get('payload') or {};expected='local' if (case['format'] in ['pptx','pdf'] and case['options'].get('target')!='video') else 'cloud'
            result('selection','passed' if p.get('engine')==expected else 'failed',{'expectedEngine':expected,'actual':p})
            if expected=='local':result('warning','passed',{'cloudWarningRequired':False})
            elif case['options']['interface']=='sdk':
                events=[]
                for line in proc.get('stderr','').splitlines():
                    try:events.append(json.loads(line))
                    except ValueError:pass
                wi=next((i for i,e in enumerate(events) if e.get('kind')=='warning' and 'cloud' in e.get('message','').lower()),None)
                ui=next((i for i,e in enumerate(events) if e.get('kind')=='upload'),None)
                result('warning','passed' if wi is not None and ui is not None and wi<ui else 'failed',events)
            else:result('warning','review',{'stderr':proc.get('stderr'),'reason':'CLI warning observed; upload ordering requires timestamped transport trace, not stdout/stderr concatenation'})
            uploaded=p.get('uploaded',p.get('lifecycle',{}).get('uploaded') if isinstance(p.get('lifecycle'),dict) else None)
            result('upload','passed' if type(uploaded)==bool and uploaded==(expected=='cloud') else 'failed',{'uploaded':uploaded})
        elif op=='quality':
            status,actual=ev.declared_outcome(proc,case.get('contract'))
            if status!='passed':result('integrity',status,actual);result('visual','blocked' if status=='blocked' else 'review',actual if status=='blocked' else 'No usable render; no visual verdict')
            else:
                result('integrity',*ev.declared_artifacts(proc,case.get('facts',{}),case.get('contract')))
                visual=quality.inspect(proc,case,directory)
                result('visual',visual['status'],visual)
    return answers

def execute(home, group='all', snapshot=None, run_id=None, selected=None):
    conformance=core.core_conformance()
    if not conformance['ok']:raise ValueError('Core behavior check failed')
    data=load_snapshot(snapshot) if snapshot else sync(home)
    root,identity=releases.active(home)
    runtime_identity={'full':releases.verify_runtime(home)}
    try:runtime_identity['minimal']=releases.verify_runtime(home,minimal=True)
    except ValueError as err:runtime_identity['minimalBlocked']=str(err)
    cases=[c for c in data['cases'] if int(c['covers'][0][-2:]) in GROUPS[group]]
    if selected:
        unknown=set(selected)-{c['id'] for c in cases}
        if unknown:raise ValueError('Unknown selected cases: '+str(unknown))
        cases=[c for c in cases if c['id'] in selected]
    if not cases:raise ValueError('No cases selected; cannot create an empty PASS report')
    rid=safe_id(run_id or stamp());folder=Path(home)/'runs'/rid
    if folder.exists():raise ValueError('Run ID already exists')
    folder.mkdir(parents=True);atomic(folder/'core-check.json',conformance);atomic(folder/'doctor.json',target.doctor(home))
    results=[];qmap={q['questionId']:q for q in data['questions']}
    for case in cases:
        directory=folder/'evidence'/case['id'];directory.mkdir(parents=True)
        if case.get('reviewStatus')!='approved':answers={c['id']:('review','Draft answer: target was not executed') for c in case['evaluation']['checks']}
        else:
            try:answers=check_case(home,case,directory,root,identity)
            except (OSError,ValueError,KeyError,TypeError,ImportError) as e:answers={c['id']:('blocked',str(e)) for c in case['evaluation']['checks']}
        assertions=[{**ch,'status':answers.get(ch['id'],('blocked',None))[0],'actual':answers.get(ch['id'],('', 'Evaluator omitted assertion'))[1],'evidence':[str(directory.relative_to(folder))],'reviewStatus':qmap[ch['questionId']]['reviewStatus'],'finding':qmap[ch['questionId']]['reviewStatus']=='approved' and ch['role']!='observation'} for ch in case['evaluation']['checks']]
        statuses=[a['status'] for a in assertions]
        status='failed' if 'failed' in statuses else 'blocked' if all(s=='blocked' for s in statuses) else 'review' if any(s in ['blocked','review'] for s in statuses) else 'passed'
        record=read(directory/'target.json',{})
        results.append({'caseId':case['id'],'source':case['source'],'inputSha256':case['source']['sha256'],'options':case['options'],'format':case['format'],'qualityCaseId':case.get('qualityCaseId'),'command':record.get('command',['python3','benchmark/scripts/release_acceptance.py','run','--group',group]),'executionSnippet':case.get('executionSnippet'),'status':status,'assertions':assertions,'evidence':[str(directory.relative_to(folder))]})
    suite={'id':'deckrender-acceptance','displayName':'DeckRender 独立发布验收','profile':'render','version':'1','qualityPolicy':data['suites'][0]['qualityPolicy']}
    summary=core.summarize_quality(results,cases,suite,'command')
    g=summary['gate']
    summary.update(releaseDecision='FAIL' if g['failed'] else 'INCOMPLETE' if g['blocked'] else 'REVIEW' if g['review'] else 'PASS',decisionReason='strict_handbook_gates')
    # A group is explicitly a partial result, never a release sign-off.
    summary['scope']='complete' if group=='all' and not selected else 'partial:'+group
    from .execution import manifest
    execution_manifest=manifest(data)
    definitions_hash=digest(execution_manifest)
    evaluator={'id':'render-release-and-quality','version':'4','codeSha256':digest({part:core.directory_sha256(REPO/'benchmark'/part) for part in ['acceptance','evaluators','adapters']})}
    envelope={'contractVersion':'2','benchmarkCoreVersion':core.CORE_VERSION,'runId':rid,'createdAt':now(),'suite':suite,'target':{'id':'deckrender','displayName':'@deckflow/deckrender '+identity['version'],**identity,'runtimeIntegrity':runtime_identity},'evaluator':evaluator,'results':results,'findings':core.build_findings(results,suite,{'id':'deckrender'},rid),'qualitySummary':summary,'qualityPolicyHash':digest(suite['qualityPolicy']),'executionContractHash':definitions_hash,'executionManifest':execution_manifest,'snapshotHash':sha(Path(snapshot)/'SHA256SUMS.json') if snapshot else None,'counts':{s:sum(r['status']==s for r in results) for s in ['passed','failed','review','blocked']},'public':bool(snapshot),'group':group}
    if target.SESSION is not None:
        envelope['cloudExecution']=target.SESSION.snapshot()
        envelope['executionMode']=target.SESSION.mode
        session=envelope['cloudExecution']
        envelope['executionPolicyHash']=digest({k:session[k] for k in ['mode','enabled','debugCases','limits']})
        if target.SESSION.mode=='debug':summary['scope']='partial:debug'
    write_report(folder,envelope,[q for q in data['questions'] if q['caseId'] in {c['id'] for c in cases}]);return {'runId':rid,'report':str(folder/'report.html'),'qualitySummary':summary}
