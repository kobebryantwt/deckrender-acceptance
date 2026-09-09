import copy, importlib.util, shutil
from .common import *

spec=importlib.util.spec_from_file_location('benchmark_core',REPO/'benchmark/scripts/deck_benchmark.py')
core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)

def write_report(folder,envelope,questions):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    envelope=redact(envelope)
    atomic(folder/'run.json',envelope);atomic(folder/'questions.json',questions)
    for r in envelope['results']:atomic(folder/'raw'/f'{r["caseId"]}.json',r)
    core.build_reports(envelope,folder,questions)
    page=(folder/'report.html').read_text()
    labels=sorted({r['caseId'][:7] for r in envelope['results'] if re.match(r'REN-R\d\d',r['caseId'])})
    nav='<nav style="display:flex;gap:12px;flex-wrap:wrap">'+''.join(f'<a href="#{label}">{label}</a>' for label in labels)+'</nav>'
    page=page.replace('<h2>逐案例：标准答案与实际结果</h2>',nav+'<h2>逐案例：标准答案与实际结果</h2>')
    for i in range(1,12):
        label=f'REN-R{i:02d}'
        page=page.replace('<b>'+label, f'<b id="{label}">'+label,1)
    for r in envelope['results']:
        snip=r.get('executionSnippet')
        if not snip:continue
        cli=html.escape(snip.get('cli',''))
        sdk=html.escape(snip.get('sdk',''))
        code_block=(f'<div style="background:#0f172a;color:#f8fafc;padding:10px 14px;border-radius:6px;margin:10px 0;font-size:12px;border:1px solid #334155">'
                    f'<div style="color:#94a3b8;font-size:11px;font-weight:600;margin-bottom:4px">待测系统完整 CLI 命令：</div>'
                    f'<code style="color:#38bdf8;font-family:ui-monospace,monospace;white-space:pre-wrap;word-break:break-all">{cli}</code>'
                    f'<details style="margin-top:6px;color:#94a3b8"><summary>展开等价 Node SDK 调用代码</summary><pre style="margin:4px 0 0;color:#a5b4fc;font-family:ui-monospace,monospace;font-size:11px">{sdk}</pre></details>'
                    f'</div>')
        safe_raw_id=r['caseId'].replace(':','-')
        anchor=f'<a href="raw/{safe_raw_id}.json">查看原始运行证据</a></p>'
        if anchor in page:page=page.replace(anchor,anchor+code_block,1)
    evidence_links=[]
    for artifact in sorted((folder/'evidence').rglob('*')):
        if artifact.is_file() and artifact.suffix in {'.png','.jpg','.json','.txt','.trace','.jsonl'}:
            rel=str(artifact.relative_to(folder));evidence_links.append('<li><a href="'+html.escape(rel,quote=True)+'">'+html.escape(rel)+'</a></li>')
    page=page.replace('</main>', '<h2>证据文件索引</h2><ul>'+''.join(evidence_links)+'</ul></main>')
    page=page.replace('</main>', '<p>视觉观察项不代表人工批准；缺少证据不能推定成功。原始敏感日志仅保存在本机受限目录，报告提供脱敏证据。</p></main>')
    from .workbench import write
    items=[]
    for result in envelope['results']:
        assertion=next((a for a in result['assertions'] if a['id']=='visual'),None)
        if assertion is None:continue
        visual=assertion.get('actual') if isinstance(assertion.get('actual'),dict) else {'errors':assertion.get('actual'),'options':result.get('options',{}),'sourceFormat':result.get('format')}
        pages=copy.deepcopy(visual.get('metrics',[]))
        # Rebuild relocation: recorded previews live beneath this case's evidence directory.
        for row in pages:
            for key in ['image','referenceImage']:
                if not row.get(key):continue
                parts=Path(row[key]).parts
                if 'previews' in parts:
                    suffix=Path(*parts[parts.index('previews'):]);candidate=folder/'evidence'/result['caseId']/suffix
                    if candidate.exists():row[key]=str(candidate)
        options=copy.deepcopy(visual.get('options',{}))
        items.append({**options,'caseId':result['caseId'],'name':result['caseId'],'sourceSha256':result.get('inputSha256'),'status':result['status'],'pages':pages,'reason':visual.get('errors'),
                      'options':options,'pageSelection':options.get('pages'),'format':visual.get('sourceFormat'),'synthetic':envelope.get('target',{}).get('id')=='fake',
                      'provenance':{'actualEngine':visual.get('actualEngine'),'actualRoute':visual.get('actualRoute')}})
    write(folder/'visual.html',items,envelope.get('suite',{}).get('displayName','DeckRender')+' · 结果图像对照',run_sha=sha(folder/'run.json'))
    page=page.replace('</main>','<p><a href="visual.html">打开逐页图像对照与人工审核工作台</a></p></main>')
    page=page.replace('<main>','<main><p><a href="visual.html">进入图像对照工作台：独立参考 / 实际结果 / 逐页审核</a></p>',1)
    atomic(folder/'report.html',page);seal(folder)

def rebuild(folder, output):
    verify(folder);output=Path(output)
    if output.exists():raise ValueError('Rebuild must use a new directory')
    shutil.copytree(folder,output)
    write_report(output,read(output/'run.json'),read(output/'questions.json'))
    return {'report':str(output/'report.html')}

def compare(before,after,output):
    verify(before);verify(after);output=Path(output)
    if output.exists():raise ValueError('Comparison output must be new')
    b=read(Path(before)/'run.json');a=read(Path(after)/'run.json')
    reasons=[]
    for key in ['evaluator','qualityPolicyHash','executionContractHash']:
        if b.get(key)!=a.get(key):reasons.append(key+' differs')
    cohort=lambda e:sorted((r['caseId'],r.get('inputSha256')) for r in e['results'])
    if cohort(b)!=cohort(a):reasons.append('source cohort differs')
    old={(r['caseId'],x['id']):x['status'] for r in b['results'] for x in r['assertions']}
    new={(r['caseId'],x['id']):x['status'] for r in a['results'] for x in r['assertions']}
    changes=[{'caseId':k[0],'assertionId':k[1],'before':old.get(k),'after':new.get(k)} for k in sorted(old.keys()|new.keys()) if old.get(k)!=new.get(k)]
    data={'compatible':not reasons,'attributableToTarget':not reasons,'warnings':reasons,'changes':changes,'before':b['runId'],'after':a['runId']}
    atomic(output/'comparison.json',data)
    rows=''.join('<tr>'+''.join('<td>'+html.escape(str(x.get(k)))+'</td>' for k in ['caseId','assertionId','before','after'])+'</tr>' for x in changes)
    atomic(output/'comparison.html','<!doctype html><meta charset="utf-8"><h1>DeckRender 运行比较</h1><p>'+html.escape('可比较' if not reasons else '不可归因产品回归：'+', '.join(reasons))+'</p><table>'+rows+'</table>');seal(output);return data

def publish(runs,output):
    """Only explicitly public runs; never copy raw provider, task ledger or secret files."""
    output=Path(output);output.mkdir(parents=True,exist_ok=True);links=[]
    candidates=[]
    for folder in sorted(Path(runs).glob('*')):
        if not (folder/'run.json').exists():continue
        verify(folder);e=read(folder/'run.json')
        if not e.get('public'):continue
        dest=output/safe_id(e['runId'])
        if dest.exists():
            verify(dest)
            if read(dest/'SHA256SUMS.json')!=read(folder/'SHA256SUMS.json'):
                raise ValueError('Immutable published run ID conflict: '+e['runId'])
        candidates.append((folder,dest))
    for folder,dest in candidates:
        if not dest.exists():shutil.copytree(folder,dest)
    for dest in sorted(output.iterdir()):
        if not dest.is_dir() or not (dest/'run.json').exists():continue
        verify(dest);e=read(dest/'run.json')
        if not e.get('public'):raise ValueError('Private run found in public history')
        run_id=safe_id(e['runId'])
        if dest.name!=run_id:raise ValueError('Published folder identity differs')
        links.append(f'<li><a href="{run_id}/report.html">{html.escape(run_id)} · {e["qualitySummary"]["releaseDecision"]}</a></li>')
    atomic(output/'index.html','<!doctype html><meta charset="utf-8"><h1>DeckRender 发布验收历史</h1><ul>'+''.join(links)+'</ul>')
    return {'published':len(candidates),'history':len(links)}
