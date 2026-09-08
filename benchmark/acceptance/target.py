import os, platform, shutil, tempfile
from .common import *
from .releases import package_path

CREDENTIAL_NAMES=['DECKRENDER_API_KEY','DECKFLOW_API_KEY','DECKHTML_API_KEY','DECKRENDER_TOKEN','DECKFLOW_TOKEN']

def doctor(home):
    commands={k:shutil.which(k) for k in ['python3','node','npm','strace','unshare','fc-list','ffprobe','tesseract','soffice']}
    from .source_preview import find_office
    commands['soffice']=find_office(home)
    chrome=next((shutil.which(k) for k in ['chromium','chromium-browser','google-chrome'] if shutil.which(k)),None)
    chrome=chrome or ( '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' if Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome').exists() else None )
    isolation=process(['unshare','-Urn','true']) if platform.system()=='Linux' and commands['unshare'] else {'exitCode':None,'stderr':'Linux unshare unavailable'}
    try:
        package=str(package_path(home));health=process(['node',str(Path(package)/'dist/cli.js'),'--version']);error=None if health['exitCode']==0 else health['stderr']
    except ValueError as e:package=None;error=str(e)
    return {'at':now(),'platform':platform.platform(),'tools':commands,'chrome':chrome,'isolation':isolation,'package':package,'packageError':error,'privacyReady':bool(commands['strace'] and isolation['exitCode']==0),'cloudEnabled':os.getenv('REN_ALLOW_CLOUD')=='1','auditConfigured':bool(os.getenv('REN_AUDIT_COMMAND'))}

def invoke(home, case, output, privacy=False, invalid=False, missing_dependency=False):
    output=Path(output);output.mkdir(parents=True,exist_ok=True); package=package_path(home,minimal=missing_dependency)
    options=case['options']; source=Path(case['source']['uri'])
    if not source.is_file() or sha(source)!=case['source']['sha256']:return {'blocked':'Source missing or changed'}
    if options.get('sourceFormat',case['format'])!=case['format']:return {'blocked':'No reviewed source for requested format'}
    cloud=options['engine']=='cloud' or options['engine']=='auto' and (case['format'] not in ['pptx','pdf'] or options.get('target')=='video')
    if cloud and os.getenv('REN_ALLOW_CLOUD')!='1':return {'blocked':'Cloud execution disabled; configure account and explicit usage authorization'}
    if cloud and not any(os.getenv(k) for k in CREDENTIAL_NAMES):return {'blocked':'Cloud test account not configured; guest mode is not an audit account'}
    if cloud and not case.get('public',False):return {'blocked':'Source is not approved for cloud upload'}
    env={k:v for k,v in os.environ.items() if not any(s in k.upper() for s in ['TOKEN','SECRET','PASSWORD','API_KEY'])}
    sandbox=output/'sandbox';sandbox.mkdir(exist_ok=True)
    # Per-child HOME is isolated; the parent environment is never reassigned.
    env.update({'HOME':str(sandbox.resolve()),'USERPROFILE':str(sandbox.resolve()),'XDG_CONFIG_HOME':str(sandbox/'config')})
    if cloud:
        for k in CREDENTIAL_NAMES:
            if os.getenv(k):env[k]=os.environ[k]
    if privacy:
        if not doctor(home)['privacyReady']:return {'blocked':'Independent Linux namespace/strace monitor unavailable'}
        for k in CREDENTIAL_NAMES:env[k]='REN_SENTINEL_NOT_A_REAL_KEY'
        for p in [sandbox/'.deckflow/credentials',sandbox/'.deckops/config.json']:atomic(p,{'token':'REN_SENTINEL_NOT_A_REAL_KEY'})
        env['REN_CREDENTIAL_LOG']=str((output/'credentials.jsonl').resolve())
        env['NODE_OPTIONS']='--require='+str(REPO/'benchmark/adapters/credential-probe.cjs')
        calibration=output/'calibration';calibration.mkdir(exist_ok=True)
        calibration_env={**env,'REN_CREDENTIAL_LOG':str((calibration/'credentials.jsonl').resolve())}
        sentinel=str((sandbox/'.deckflow/credentials').resolve())
        probe="require('fs').readFileSync("+json.dumps(sentinel)+");void process.env.DECKRENDER_API_KEY;const s=require('net').connect(9,'192.0.2.1');s.on('error',()=>{});setTimeout(()=>{s.destroy();process.exit(0)},150)"
        calibration_proc=process(['unshare','-Urn','strace','-f','-qq','-s','256','-e','trace=network,openat','-o',str((calibration/'system.trace').resolve()),'node','-e',probe],timeout=10,env=calibration_env)
        from .evaluation import privacy_evidence
        observed=privacy_evidence(calibration_proc,calibration)
        atomic(calibration/'calibration.json',{'process':calibration_proc,'observed':observed})
        if calibration_proc['exitCode']!=0 or observed['network'][0]!='failed' or observed['credentials'][0]!='failed' or not observed['credentials'][1]['files'] or not observed['credentials'][1]['environment']:return {'blocked':'Privacy monitor negative control failed; absence of events is not evidence'}

    inp=str(source.resolve()) if not invalid else str(output/'does-not-exist.pptx')
    out=str((output/'artifacts').resolve())
    render={'input':inp,'engine':options['engine'],'format':options['target'],'out':out,'width':1920}
    if case['format']=='key' or options['target']!='image':render.pop('width')
    if missing_dependency:render.update({'executablePath':'/missing/chromium','office2htmlPath':'/missing/office2html'})
    if 'pages' in options:render['pages']=options['pages']
    if 'imageFormat' in options:render['imageFormat']=options['imageFormat']
    if options['interface']=='sdk':
        spec=output/'request.json';atomic(spec,{'module':str(package/'dist/index.js'),'options':render})
        command=['node',str(REPO/'benchmark/adapters/sdk.mjs'),str(spec.resolve())]
    else:
        command=['node',str(package/'dist/cli.js'),inp,'--engine',options['engine'],'--format',options['target'],'--output',out,'--json']
        if 'width' in render:command+=['--width','1920']
        if 'pages' in render:command+=['--pages',render['pages']]
        if 'imageFormat' in render:command+=['--image-format',render['imageFormat']]
        # Dependency absence comes from the frozen --omit=optional installation, not invented CLI flags.
    if privacy:command=['unshare','-Urn','strace','-f','-qq','-s','256','-e','trace=network,openat','-o',str((output/'system.trace').resolve()),*command]
    result=process(command,REPO,timeout=300,env=env)
    atomic(output/'process.json',redact(result))
    try:result['payload']=json.loads(result['stdout'] if result['exitCode']==0 or options['interface']=='sdk' else result['stderr'])
    except (ValueError,TypeError):result['payload']=None
    result['artifactsDir']=out; result['evidenceDir']=str(output)
    return result
