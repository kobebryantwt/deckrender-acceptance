"""Review coverage with fixed matrix denominators; never infer execution from drafts."""
from .common import *
from . import purposes

def expected_cells():
    cells=set()
    for engine,formats,targets in [('local',['pptx','pdf'],['image','pdf']),('cloud',['pptx','ppt','pdf','key','docx'],['image','pdf','video']),('local',['ppt','key','docx'],['image']),('local',['pptx'],['video']),('cloud',['pages','numbers'],['image','pdf'])]:
        cells.update((engine,f,t,i) for f in formats for t in targets for i in ['cli','sdk'])
    return sorted(cells)

def build(corpus, inputs, declarations=None):
    cases=inputs['cases'];questions=inputs['questions'];sources=corpus['sources']
    def key(c):return (c['options'].get('engine'),c['format'],c['options'].get('target'),c['options'].get('interface'))
    matrix=[]
    for cell in expected_cells():
        cc=[c for c in cases if c['operation'] in ['render','planned'] and key(c)==cell and not c['options'].get('variantId')]
        declared=(declarations or {}).get(':'.join(cell[:3]))
        positive=declared is True if declarations is not None else any(c['options'].get('expectedSupport') is True for c in cc)
        qq=[q for q in cases if q['operation']=='quality' and key(q)==cell and not q['options'].get('variantId') and any(q['source']['sha256']==c['source']['sha256'] for c in cc)]
        matrix.append({'cell':list(cell),'caseIds':sorted({c['id'] for c in cc}),'planned':bool(cc),'expectation':'成功' if positive else '明确拒绝' if cc and all(c['operation']=='planned' or c['options'].get('expectedSupport') is False for c in cc) else '待冻结确认',
            'approved':any(c.get('reviewStatus')=='approved' for c in cc),'qualityCaseIds':sorted({c['id'] for c in qq}),'qualityRequired':positive,
            'qualityApproved':any(c.get('reviewStatus')=='approved' for c in qq),'execution':'未在此审核统计中评估；以绑定版本的 run.json 为准'})
    difficulty=[]
    for axis in ['fonts','charts','special-elements','dense-page']:
        for engine in ['local','cloud']:
            planned={c['sourceId'] for c in cases if c['operation']=='quality' and c['options'].get('engine')==engine and axis in c.get('purpose',{}).get('focus',[])}
            observed={s['id'] for s in sources if s.get('difficulty',{}).get('sourceSha256')==s['sha256'] and axis in s.get('difficulty',{}).get('features',[])}
            difficulty.append({'axis':axis,'engine':engine,'plannedSourceIds':sorted(planned),'independentlyObservedSourceIds':sorted(planned&observed)})
    req=[]
    for n in range(1,12):
        rid=f'REN-R{n:02d}';cc=[c for c in cases if rid in c['covers']];qq=[q for q in questions if q['featureId']==rid]
        req.append({'requirement':rid,'cases':len({c['id'] for c in cc}),'rules':len({ch.get('ruleId',ch['id']) for c in cc for ch in c['evaluation']['checks']}),'assertions':len(qq),'approvedAssertions':sum(q.get('reviewStatus')=='approved' for q in qq)})
    return {'version':1,'generatedAt':now(),'projectRevision':inputs.get('projectRevision'),'sources':len(sources),'executionSources':len({c['sourceId'] for c in cases if c['sourceId']!='handbook'}),'cases':len({c['id'] for c in cases}),'assertions':len(questions),'ruleFamilies':len({ch.get('ruleId',ch['id']) for c in cases for ch in c['evaluation']['checks']}),'matrix':matrix,'optionTests':[{'caseId':c['id'],'label':c['options']['variantLabel'],'engine':c['options']['engine'],'interface':c['options']['interface'],'qualityCaseId':c.get('qualityCaseId'),'approved':c.get('reviewStatus')=='approved'} for c in cases if c['operation']=='render' and c['options'].get('variantId')],'difficulty':difficulty,'requirements':req,'limits':purposes.policy()['limits'],
        'meaning':'出题覆盖只表示有对应问题；独立结构证据不等于渲染真值。审核与产品执行结果分开，不能用题数推导产品通过率。'}

def write(home,inputs):
    from . import releases,evaluation
    declarations={};identity=None
    try:
        root,identity=releases.active(home)
        declarations=evaluation.declaration_matrix((root/'source/docs/formats.md').read_text())
    except (ValueError,OSError):pass
    corpus=read(Path(home)/'corpus.json',{'sources':[]})
    data=build(corpus,inputs,declarations)
    data['releaseDeclaration']=identity
    from .gt_contract import readiness
    data['qualityReadiness']=[{'caseId':c['id'],**readiness(c)} for c in inputs['cases'] if c['operation']=='quality']
    previews={i['sourceId']:i for i in read(Path(home)/'gt-manifest.json',{'items':[]})['items']}
    data['sourceReadiness']=[]
    for source in corpus['sources']:
        p=previews.get(source['id'],{});valid=p.get('sourceSha256')==source['sha256'];pages=p.get('pages',[]) if valid else []
        data['sourceReadiness'].append({'sourceId':source['id'],'role':purposes.profile(source)['role'],'previewPages':len(pages),'approvedPages':sum(x.get('reviewStatus')=='approved' for x in pages),'reason':p.get('reason','') if valid else '尚无当前源版本的独立候选'})
    from .curation import annotate,summary
    data['curation']=summary(annotate(list(previews.values())))
    atomic(Path(home)/'coverage.json',data)
    esc=lambda x:html.escape(str(x))
    def table(headers,rows):return '<table><tr>'+''.join('<th>'+esc(h)+'</th>' for h in headers)+'</tr>'+''.join('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in row)+'</tr>' for row in rows)+'</table>'
    m=data['matrix'];p=sum(x['planned'] for x in m);q=[x for x in m if x['qualityRequired']]
    page='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><link rel="icon" href="data:,"><title>范围与覆盖</title><style>body{font:15px/1.6 system-ui;margin:32px;color:#18323b}td,th{padding:8px;border:1px solid #ccd}table{border-collapse:collapse;width:100%}th{background:#eef5f5}a{color:#087f83}</style><p><a href="/">GT 图像审核</a> · <a href="/casework">契约答案审核</a></p><h1>范围与覆盖</h1>'
    page+=f'<p>{data["sources"]} 份文件 · {data["executionSources"]} 份用于执行 · {data["cases"]} 个案例 · {data["ruleFamilies"]} 类规则 · {data["assertions"]} 条绑定断言</p><p>'+esc(data['meaning'])+'</p>'
    page+=f'<p>矩阵出题 {p}/{len(m)}；矩阵答案已审核 {sum(x["approved"] for x in m)}/{len(m)}；已确认成功格的质量出题 {sum(bool(x["qualityCaseIds"]) for x in q)}/{len(q)}。这里不统计执行通过率。</p>'
    page+=f'<p>逐页 GT 已就绪的质量案例：{sum(x["ready"] for x in data["qualityReadiness"])}/{len(data["qualityReadiness"])}。生成预览不会批准 GT；正式 READY 要求全部必需的逐页参考与视频映射完成审核。</p>'
    page+=f'<p>优先视觉审核队列：{data["curation"]["prioritySources"]} 份文件 / {data["curation"]["priorityPages"]} 页；全部候选 {data["curation"]["allPreviewPages"]} 页。精选不减少正式 GT 分母，也不构成批准。</p>'
    if identity is None:page+='<p>缺少冻结发布声明：成功组合的分母尚未确定，不能将 0/0 视为覆盖完成。</p>'
    page+='<h2>格式 × 路线 × 输出 × 接口</h2>'+table(['组合','预期','已出题','答案已审核','质量题'],[(' / '.join(x['cell']),x['expectation'],'是' if x['planned'] else '缺失','是' if x['approved'] else '否',len(x['qualityCaseIds']) if x['qualityRequired'] else '无需成功渲染质量题') for x in m])
    page+='<h2>页面筛选与图片编码专项（不计入基础矩阵分母）</h2>'+table(['案例','测试点','路线','接口','质量映射','答案已审核'],[list(x.values()) for x in data['optionTests']])
    page+='<h2>困难特征：出题与独立结构依据</h2>'+table(['特征','路线','候选样本','已由源结构证实的样本'],[(x['axis'],x['engine'],', '.join(x['plannedSourceIds']) or '缺失',', '.join(x['independentlyObservedSourceIds']) or '尚未证实') for x in data['difficulty']])
    page+='<h2>R01—R11</h2>'+table(['要求','案例','规则种类','断言','已审核断言'],[list(x.values()) for x in data['requirements']])
    page+='<h2>独立 GT 就绪情况</h2><p>预览页数不等于已审核 GT 页数；拒绝测试和参考文件不要求成功渲染。</p>'+table(['文件','用途类别','独立候选页','已审核页','缺少的条件'],[list(x.values()) for x in data['sourceReadiness']])
    page+='<details><summary>质量案例尚缺的 GT 条件</summary>'+table(['案例','缺少条件'],[(x['caseId'],'；'.join(x['errors'])) for x in data['qualityReadiness'] if not x['ready']])+'</details>'
    page+='<h2>范围限制</h2><ul>'+''.join('<li>'+esc(x)+'</li>' for x in data['limits'])+'</ul><p>生成时间：'+esc(data['generatedAt'])+'；同步答案后更新。执行、失败与阻塞请查看对应运行报告。</p></html>'
    atomic(Path(home)/'coverage.html',page);return data
