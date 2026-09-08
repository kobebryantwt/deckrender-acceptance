import copy, sys
from .common import *
sys.path.insert(0,str(REPO/'casework'))
from casework.store import Store, answer_digest, binding
from casework.server import serve

PROJECT='deckrender-acceptance'

def load_suites(home=None):
    cases=[];questions=[];suites=[]
    for name in ['deckrender-release','deckrender-quality']:
        folder=suite_root(home)/name
        suites.append(read(folder/'suite.json'))
        cases.extend(json.loads(l) for l in (folder/'cases.jsonl').read_text().splitlines() if l.strip())
        questions.extend(json.loads(l) for l in (folder/'questions.jsonl').read_text().splitlines() if l.strip())
    return suites,cases,questions

def make_bundle(home):
    suites,cases,questions=load_suites(home); qmap={q['questionId']:q for q in questions};samples=[]
    sources={s['id']:s for s in read(Path(home)/'corpus.json')['sources']}
    for case in cases:
        src=sources.get(case['sourceId'],{});p=Path(case['source']['uri'])
        answers=[]
        for check in case['evaluation']['checks']:
            q=qmap[check['questionId']]
            answers.append({'id':q['questionId'],'kind':'contract','question':q['question'],'expected':q['answer'],'evidence':q['evidence'],'requirement':q['featureId'],'check':{'definition':check,'case':case},'options':[]})
        samples.append({'id':case['id'],'sourceId':case['sourceId'],'purpose':copy.deepcopy(case['purpose']),'executionSnippet':case.get('executionSnippet'),'title':case['id']+' '+p.name,'path':str(p),'sha256':case['source']['sha256'],'inputName':p.name,'format':case['format'],'private':not src.get('public',case['sourceId']=='handbook'),'license':src.get('license','acceptance specification'),'answers':answers})
    return {'schemaVersion':1,'project':{'id':PROJECT,'name':'DeckRender 发版验收：场景与标准答案','samples':samples,'sourceInventory':list(sources.values())}}

def initialize(home):
    store=Store(Path(home)/'casework')
    if any(p['id']==PROJECT for p in store.projects()):return store.get(PROJECT)
    return store.import_bundle(make_bundle(home))

def semantic_check(value):
    value=copy.deepcopy(value)
    if isinstance(value.get('case'),dict):value['case'].get('source',{}).pop('uri',None)
    return value

def project_inputs(project,home=None):
    suites,cases,questions=load_suites(home); cmap={c['id']:copy.deepcopy(c) for c in cases}; qmap={q['questionId']:copy.deepcopy(q) for q in questions}
    for q in qmap.values():q.update(reviewStatus='draft',review=None)
    samples={s['id']:s for s in project['samples']}
    for cid,c in cmap.items():
        s=samples.get(cid); c['reviewStatus']='draft';c['public']=False
        if not s or not s.get('active',True):continue
        c['public']=not s.get('private',True)
        for check in c['evaluation']['checks']:
            q=qmap[check['questionId']];a=next((a for a in s['answers'] if a['id']==q['questionId']),None)
            valid=bool(a and a.get('status')=='approved' and a.get('review',{}).get('digest')==answer_digest(a)==a.get('digest') and a.get('binding')==binding(s) and Path(s['path']).is_file() and sha(s['path'])==s['sha256'] and project.get('answerScopes',{}).get(a['id'],{}).get('mode')!='reference')
            # Execution definitions must be exactly the reviewed definitions, including source facts and routes.
            valid=valid and semantic_check(a.get('check',{}))==semantic_check({'definition':check,'case':next(x for x in cases if x['id']==cid)}) and a.get('expected')==q['answer']
            q['reviewStatus']='approved' if valid else 'draft'
            q['review']=a.get('review') if valid else None
        if all(qmap[ch['questionId']]['reviewStatus']=='approved' for ch in c['evaluation']['checks']):
            c['reviewStatus']='approved';c['source']['uri']=s['path']
    return {'suites':suites,'cases':list(cmap.values()),'questions':list(qmap.values()),'projectRevision':project['revision']}

def sync(home, project=None):
    if project is None:project=initialize(home)
    value=project_inputs(project,home)
    for suite in value['suites']:
        folder=suite_root(home)/suite['id']
        ids={json.loads(line)['id'] for line in (folder/'cases.jsonl').read_text().splitlines() if line.strip()}
        questions=[q for q in value['questions'] if q['caseId'] in ids]
        suite['reviewStatus']='approved' if questions and all(q['reviewStatus']=='approved' for q in questions) else 'draft'
        atomic(folder/'suite.json',suite)
        atomic(folder/'questions.jsonl',''.join(json.dumps(q,ensure_ascii=False)+'\n' for q in questions))
    atomic(Path(home)/'reviewed-inputs.json',value)
    from .coverage import write
    write(home,value)
    return value

def review_page(home):
    data=sync(home);rows=[]
    cases_map={c['id']:c for c in data['cases']}
    for q in data['questions']:
        c=cases_map.get(q['caseId'],{})
        purpose_sum=c.get('purpose',{}).get('summary','')
        snip=c.get('executionSnippet') or {}
        cli_code=f'<code>{html.escape(snip.get("cli",""))}</code>' if snip.get("cli") else ''
        sdk_code=f'<details><summary>SDK 代码</summary><pre>{html.escape(snip.get("sdk",""))}</pre></details>' if snip.get("sdk") else ''
        cmd_cell=f'{cli_code}<br>{sdk_code}' if sdk_code else cli_code
        rows.append('<tr>'+''.join('<td>'+(v if k=='cmd' else html.escape(str(v)))+'</td>' for k,v in [
            ('req',q['featureId']),('purpose',purpose_sum),('cmd',cmd_cell),('q',q['question']),('ans',q['answer']),('ev',q['evidence']),('chk',','.join(q['assertionIds'])),('unc',q['uncertainty']),('st',q['reviewStatus'])
        ])+'</tr>')
    page='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>DeckRender 答案审核包</title><style>body{font:14px/1.6 system-ui;margin:24px}td,th{border:1px solid #ccc;padding:8px 10px;vertical-align:top}table{border-collapse:collapse;width:100%}th{background:#eef5f5;position:sticky;top:0}a{color:#087f83}code{background:#f1f5f9;padding:2px 4px;border-radius:4px;word-break:break-all}pre{margin:4px 0;background:#f8fafc;padding:6px;border-radius:4px;font-size:12px;white-space:pre-wrap;word-break:break-all}</style><p><a href="gt.html">打开 GT 图像候选审核工作台</a> · <a href="/casework">打开 Casework 审核后台</a> · <a href="/coverage">范围与覆盖</a></p><h1>DeckRender 答案审核包</h1><p>所有用例均附带完整 CLI 执行命令与等价 SDK 调用代码，直接关联真实执行行为。修改规则或源内容后需重新核对。本页面不授予批准。</p><table><tr><th>要求</th><th>验证目的</th><th>待测 CLI 命令 / SDK 代码</th><th>问题</th><th>预期 JSON 契约 / 答案</th><th>证据</th><th>检查</th><th>不确定性</th><th>状态</th></tr>'+''.join(rows)+'</table></html>'
    page=page.replace('<h1>','<p><a href="gt.html">打开 GT 图像候选审核工作台</a></p><h1>',1)
    atomic(Path(home)/'review.html',page)
    atomic((REPO/'benchmark/REVIEW.md') if Path(home).resolve()==DEFAULT_HOME.resolve() else Path(home)/'REVIEW.md','# DeckRender 审核入口\n\n运行 `python3 benchmark/scripts/release_acceptance.py manage`，在本地 Casework 审核后点击“同步到验收”。\n\n生成问题见两个 suite 的 questions.jsonl；完整 HTML 审核表位于本地状态目录 review.html。新增答案均为 draft，不能签核。\n')
    return {'review':str(Path(home)/'review.html'),'questions':len(data['questions']),'approved':sum(q['reviewStatus']=='approved' for q in data['questions'])}

def manage(home,port):
    with locked(home):
        initialize(home)
        sync(home)
        _prepare_manage_previews(home)
    pages={'/':Path(home)/'gt.html','/gt':Path(home)/'gt.html'} if (Path(home)/'gt.html').exists() else None
    pages=pages or {}
    pages['/coverage']=Path(home)/'coverage.html';pages['/coverage.html']=Path(home)/'coverage.html'
    def apply_project(project):
        current=Store(Path(home)/'casework').get(PROJECT)
        if current['revision']!=project['revision']:raise ValueError('Project changed; refresh before syncing')
        return sync(home,current)
    def submit_visual(value):
        from .previews import apply_draft
        if not isinstance(value,dict) or value.get('mode')!='gt':raise ValueError('只接受 GT 图像审核')
        submission=digest(value);receipt=Path(home)/'gt-submissions'/(submission+'.receipt.json')
        if receipt.exists():return read(receipt)
        file=Path(home)/'gt-submissions'/(submission+'.json');atomic(file,value)
        result=apply_draft(home,file)
        result.update(submissionId=submission,status='submitted')
        atomic(receipt,result)
        return result
    serve(Path(home)/'casework',port,on_apply=apply_project,default_project=PROJECT,extra_pages=pages,mutation_guard=lambda:locked(home),on_visual_submit=submit_visual)

def refresh(home):
    """Adapter-owned atomic reconciliation; preserve only unchanged reviewed semantics."""
    import tempfile
    from casework.store import encoded as store_encoded, Conflict
    store=Store(Path(home)/'casework');old=initialize(home)
    with tempfile.TemporaryDirectory() as temp:
        new=Store(Path(temp)).import_bundle(make_bundle(home))
        old_samples={s['id']:s for s in old['samples']}
        for sample in new['samples']:
            previous=old_samples.get(sample['id']);sample.update(store.materialize(path=sample['path'],input_name=sample['inputName'],expected_hash=sample['sha256']))
            if previous and binding(previous)==binding(sample):
                old_answers={a['id']:a for a in previous['answers']}
                for index,a in enumerate(sample['answers']):
                    was=old_answers.get(a['id'])
                    if was and semantic_check(was.get('check',{}))==semantic_check(a.get('check',{})) and all(was.get(k)==a.get(k) for k in ['question','expected','evidence']):sample['answers'][index]=copy.deepcopy(was)
                sample['private']=previous['private'];sample['active']=previous['active']
                if previous.get('purpose') and not previous['purpose'].get('origin','').startswith('generated:') and previous['purpose'].get('binding')==binding(sample):sample['purpose']=copy.deepcopy(previous['purpose'])
        answer_ids={a['id'] for s in new['samples'] for a in s['answers']}
        for field in ['answerScopes','mappings']:new[field]={k:copy.deepcopy(v) for k,v in old.get(field,{}).items() if k in answer_ids}
        comparable=lambda p:{k:v for k,v in p.items() if k not in {'revision','updatedAt','createdAt'}}
        if comparable(new)==comparable(old):return sync(home,old)
        new['revision']=old['revision']+1
        with store.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            actual=c.execute('SELECT revision FROM projects WHERE id=?',(PROJECT,)).fetchone()[0]
            if actual!=old['revision']:raise Conflict('Review project changed during refresh')
            c.execute('UPDATE projects SET revision=?,data=? WHERE id=?',(new['revision'],store_encoded(new),PROJECT))
            c.execute('INSERT INTO history VALUES(?,?,?,?,?,?,?,?)',(PROJECT,new['revision'],now(),'dataset-refresh','scenario-refresh',PROJECT,'Preserve unchanged source/answer semantics; archive retired scenarios',store_encoded(new)))
    return sync(home,new)


def _prepare_manage_previews(home):
    manifest=read(Path(home)/'gt-manifest.json',{})
    if manifest.get('version')!=3 or manifest.get('corpusSha256')!=sha(Path(home)/'corpus.json'):
        from .previews import prepare
        prepare(home)
    from .previews import refresh_metadata
    refresh_metadata(home)
