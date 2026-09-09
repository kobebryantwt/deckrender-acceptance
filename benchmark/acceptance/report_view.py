"""Interactive, presentation-layer report generator matching deckprobe-acceptance mode."""
from __future__ import annotations
import copy, html, json, os, re, shutil
from pathlib import Path
from urllib.parse import urlparse
from .common import REPO, atomic, digest, now, read, sha

ASSETS = Path(__file__).parent / 'presentation'

def report_template():
    template = (ASSETS / 'templates/report.template.html').read_text(encoding='utf-8')
    if '<!-- TEMPLATE_ONLY_BEGIN -->' in template:
        before, rest = template.split('<!-- TEMPLATE_ONLY_BEGIN -->', 1)
        _, after = rest.split('<!-- TEMPLATE_ONLY_END -->', 1)
        return before + after
    return template

def build_model(folder, envelope, questions):
    folder = Path(folder)
    qmap = {(q['caseId'], aid): q for q in questions for aid in q.get('assertionIds', [])}
    home = folder.parent.parent
    corpus_file = home / 'corpus.json' if (home / 'corpus.json').is_file() else REPO / 'benchmark/artifacts/acceptance/corpus.json'
    sources_list = read(corpus_file, {}).get('sources', [])
    sources = {s['id']: s for s in sources_list}
    sources_by_sha = {s['sha256']: s for s in sources_list}
    
    evidence = {}
    def evidence_files(result):
        names = [f"raw/{result['caseId']}.json"]
        for rel in result.get('evidence', []):
            path = folder / rel
            if not path.resolve().is_relative_to(folder.resolve()):
                continue
            if path.is_dir():
                names.extend(str(p.relative_to(folder)) for p in sorted(path.rglob('*')) if p.is_file() and p.suffix in {'.json','.txt','.trace','.jsonl'})
            elif path.is_file():
                names.append(rel)
        for name in names:
            path = folder / name
            if path.is_file() and path.stat().st_size <= 262144:
                try:
                    text = path.read_text(encoding='utf-8')
                    evidence[name] = json.loads(text) if path.suffix == '.json' else text
                except (ValueError, UnicodeError):
                    pass
        return list(dict.fromkeys(names))
    rows = []
    for r in envelope.get('results', []):
        cid = r['caseId']
        opts = r.get('options', {})
        source_meta = sources.get(r.get('sourceId')) or sources_by_sha.get(r.get('inputSha256'), {})
        source_id = source_meta.get('id') or r.get('sourceId') or ''
        source_ids = [source_id] if source_id else []
        archived = evidence_files(r)
        snip = r.get('executionSnippet') or {}
        cmd = snip.get('cli') or (' '.join(r.get('command', [])) if isinstance(r.get('command'), list) else str(r.get('command', '')))
        sdk = snip.get('sdk', '')
        
        for a in r.get('assertions', []):
            aid = a['id']
            q = qmap.get((cid, aid), {})
            status = a.get('status', 'review')
            req = a.get('featureId') or (cid[:7] if re.match(r'REN-R\d\d', cid) else 'REN-R04')
            title = q.get('question') or f"{cid} · {aid}"
            expected = a['expected'] if 'expected' in a else q.get('answer')
            actual = a.get('actual')
            
            if status == 'passed': kind = 'matched'
            elif status == 'failed': kind = 'different'
            elif status == 'blocked': kind = 'blocked'
            else: kind = 'review'
            
            method_text = [
                f"输入格式：{r.get('format','').upper()} ({source_meta.get('inputName', cid)})",
                f"执行引擎：{opts.get('engine', 'default')}",
                f"目标格式：{opts.get('target', 'default')}",
                f"接入接口：{opts.get('interface', 'cli').upper()}"
            ]
            if cmd: method_text.append(f"完整 CLI 命令：{cmd}")
            if sdk: method_text.append(f"等价 SDK 代码：\n{sdk}")
            
            criteria_text = [f"预期契约：{expected}"]
            if aid == 'commonSchema':
                criteria_text.append('按本项冻结的公共 Schema 检查成功 / 错误分支；逐项缺口见实际结果。')
            if aid in {'artifacts', 'integrity'}:
                criteria_text.append('检查产物可解码性、格式、页数及页序；不等于视觉质量已审核。')
            approval = a.get('reviewStatus', q.get('reviewStatus', 'draft'))
            review = q.get('review') or {}
            
            protocol = {
                'kind': '发版契约门禁' if a.get('role') == 'gate' else '视觉/质量观察项',
                'method': method_text,
                'criteriaLabel': '通过判定条件与验收依据',
                'criteria': criteria_text,
                'basis': [[f'deckrender-github-release-acceptance.md#{req}', f'{req} 验收手册标准规范']]
            }
            
            row = {
                'id': f"{cid}:{aid}",
                'checkId': aid,
                'caseId': cid,
                'requirement': req,
                'title': title,
                'status': status,
                'kind': kind,
                'comparison': kind,
                'approval': approval,
                'role': a.get('role'),
                'scope': 'full',
                'expected': expected,
                'actual': actual,
                'command': cmd,
                'sdkCode': sdk,
                'durationMs': r.get('durationMs', 0),
                'evidence': archived,
                'protocol': protocol,
                'answer': {'question': title, 'expected': expected, 'status': approval, 'review': review, 'answerDigest': review.get('digest'), 'evidence': q.get('evidence', {'method': '独立事实与发布规范', 'location': '发版手册标准'})},
                'sourceIds': source_ids,
                'observationKind': 'render-assertion'
            }
            rows.append(row)
            
    summary = envelope.get('qualitySummary', {})
    
    model = {
        'version': 1,
        'executionMode': envelope.get('executionMode','formal'),
        'cloudExecution': envelope.get('cloudExecution'),
        'runId': envelope.get('runId', 'latest'),
        'targetVersion': envelope.get('target', {}).get('version', '0.3.1'),
        'target': envelope.get('target', {}),
        'createdAt': envelope.get('createdAt', now()),
        'quality': summary,
        'counts': {status: sum(r['status'] == status for r in rows) for status in ['passed','failed','review','blocked']},
        'caseCounts': envelope.get('counts', {}),
        'context': {'corpusBound': True, 'answersBound': True, 'protocolBound': True},
        'rows': rows,
        'sources': list(sources.values()),
        'evidence': evidence
    }
    return model

def render(folder, envelope, questions):
    folder = Path(folder)
    model = build_model(folder, envelope, questions)
    payload = json.dumps(model, ensure_ascii=False, separators=(',', ':')).replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')
    template = report_template()
    css = (ASSETS / 'report.css').read_text(encoding='utf-8')
    js = (ASSETS / 'report.mjs').read_text(encoding='utf-8')
    page = template.replace('/*REPORT_CSS*/', css).replace('/*REPORT_JS*/', js).replace('REPORT_DATA_JSON', payload)
    budget=envelope.get('cloudExecution')
    if budget:
        mode='正式周检 / 完整检查清单' if envelope.get('executionMode')=='formal' else '调试 / 部分验收，不可用于完整放行'
        usage=f"云端调用尝试 {budget['actualCalls']} / {budget['limits']['calls']}；源页提交 {budget['submittedSourcePages']} / {budget['limits']['sourcePages']}（非积分）；复用 {sum(e['status']=='reused' for e in budget['events'])} 次"
        banner='<section style="padding:16px;background:#fff4da"><strong>'+html.escape(mode)+'</strong><p>'+html.escape(usage)+'</p><details><summary>预算计划与调用身份映射</summary><pre>'+html.escape(json.dumps(budget,ensure_ascii=False,indent=2))+'</pre></details></section>'
        page=page.replace('<main>', '<main>'+banner,1)
    return page
