"""Reviewable handbook scenarios. Expected behavior never comes from target output."""
import copy, shutil
from .common import *

TITLES=['可追溯 MIT release','本地 PPTX/PDF','严格 local 边界','云端格式矩阵','Pages/Numbers 规划状态','auto 可审计','结构化结果契约','云端删除','质量基准','弃用范围','支持与商业边界']
POLICY={'version':'1','scoring':{'aggregation':'macro_feature','scale':100,'passThreshold':None,'reviewThreshold':None}}
CHECKS={
 'release': [('mit','发布 tag 与 npm 包均为 MIT；许可证正文一致'),('identity','tag、commit、包版本与发布说明一致')],
 'render':[('outcome','支持的路线成功，不可用组合明确拒绝且不伪造产物'),('artifacts','产物可解码；页序、数量与独立答案一致')],
 'privacy':[('network','整个进程树无外部网络连接尝试'),('credentials','无凭据文件读取或云凭据环境变量读取'),('local','结果明确标记 local；不发生云端回退')],
 'auto':[('selection','有本地候选时选择本地；无本地路线才选云端'),('warning','首次上传前产生云端警告'),('upload','结果提供实际上传状态')],
 'schema':[('error','错误提供稳定 machine code，CLI 退出码与发布文档一致'),('parity','CLI 与 SDK 公共结果语义一致，忽略调用独有路径与任务身份'),('boundary','不存在的输入明确失败，符合公共错误 Schema 且不产生渲染产物')],
 'planned':[('rejected','Pages/Numbers 返回明确 planned/unsupported/not_implemented，无虚假成功'),('declaration','发布文档与 formats 不宣称该输入当前可渲染')],
 'retention':[('configuration','公开接口允许指定保留期，默认 1 小时，支持 1 与 99 小时'),('deletion','到期后任务、输入、中间产物、输出全部删除，有服务端审计证据'),('training','不用于训练的公开政策和独立实施审计一致')],
 'quality':[('visual','逐页人工核对文字、裁切、重叠、图表、层级及可读性'),('integrity','记录有效图像、页序、字体、环境、分辨率与独立参考')],
 'deprecated':[('scope','HTML/URL/Markdown 不作为当前公共能力；v0.3.1 遗留能力有弃用和移除版本说明')],
 'support':[('channels','Issue、安全渠道与机密样例提交指引可用'),('promises','SLA、认证、地域、价格与企业条款有可核对依据')],
 'dependency':[('actionable','缺少本地依赖时返回稳定错误及可操作的修复提示；不联网安装或回退')],
}

def fixtures():
    """Explicit design yields independently inspectable facts, not product goldens."""
    import fitz
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.chart.data import CategoryChartData
    from pptx.enum.chart import XL_CHART_TYPE
    folder=REPO/'benchmark/fixtures'; folder.mkdir(exist_ok=True)
    pdf=folder/'markers.pdf'; ppt=folder/'markers.pptx'
    if not pdf.exists():
        d=fitz.open()
        for n in [1,2,3]:
            page=d.new_page(width=720,height=405)
            page.insert_text((36,60),f'REN PAGE {n}',fontsize=28)
            page.insert_text((36,100),'Independent source design / Helvetica',fontsize=16)
            page.draw_rect(fitz.Rect(36,140,150+n*80,220),color=(0,.3,.7),fill=(.1,.5,.8))
        d.save(pdf,no_new_id=True);d.close()
    if not ppt.exists():
        r=Presentation();r.slide_width=Inches(10);r.slide_height=Inches(5.625)
        for n in [1,2,3]:
            s=r.slides.add_slide(r.slide_layouts[6]); t=s.shapes.add_textbox(Inches(.5),Inches(.4),Inches(9),Inches(1)).text_frame
            t.text=f'REN PAGE {n}';t.paragraphs[0].font.size=Pt(28)
            if n==1:
                cd=CategoryChartData();cd.categories=['A','B','C'];cd.add_series('values',[1,2,3]);s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED,Inches(1),Inches(1.5),Inches(7),Inches(3),cd)
            elif n==2:
                tb=s.shapes.add_textbox(Inches(.5),Inches(1.5),Inches(9),Inches(3)).text_frame
                tb.text='Font coverage: Arial / Symbol\nSpecial: α β ± ≤ ≥\n中文字体替代检查';tb.paragraphs[0].font.name='Arial'
            else:
                table=s.shapes.add_table(12,6,Inches(.4),Inches(1.3),Inches(9.2),Inches(4)).table
                for i in range(12):
                    for j in range(6):table.cell(i,j).text=f'{i+1}:{j+1}'
        r.save(ppt)
    return [{'id':'markers-'+p.suffix[1:],'path':str(p),'sha256':sha(p),'format':p.suffix[1:],'inputName':p.name,'public':True,'license':'CC0-1.0','origin':'Repository-owned generator; catalog.py fixtures','facts':{'pages':3,'pageMarkers':['REN PAGE 1','REN PAGE 2','REN PAGE 3']},'features':['page-order','fonts','charts','special-elements','dense-page'] if p==ppt else ['page-order']} for p in [pdf,ppt]]

def import_sources(home, source=None):
    import csv
    old=read(Path(home)/'corpus.json',{'sources':[]})
    source=(Path(source) if source else REPO/'benchmark/corpus').resolve()
    previous={x['id']:x for x in old['sources']}
    # The scanned directory is authoritative; retired files remain in history, not the active corpus.
    records={x['id']:copy.deepcopy(x) for x in old['sources'] if not Path(x['path']).resolve().is_relative_to(source)}
    for item in fixtures():
        was=previous.get(item['id'])
        records[item['id']]=copy.deepcopy(was) if was and was['sha256']==item['sha256'] else item
    if source.exists():
        manifest=source/'manifest.tsv' if (source/'manifest.tsv').exists() else source/'来源清单.tsv'
        metadata={}
        if manifest.exists():
            with manifest.open(encoding='utf-8') as f:metadata={r['filename']:r for r in csv.DictReader(f,delimiter='\t') if r.get('filename')}
        seen=set()
        for p in sorted(source.rglob('*')):
            if p.suffix.lower() not in {'.pptx','.ppt','.pdf','.key','.docx','.pages','.numbers','.html'} or not p.is_file():continue
            ident=p.stem.replace(' ','_')[:32]
            if ident in seen:raise ValueError('Duplicate source ID: '+ident)
            seen.add(ident);meta=metadata.get(p.name,{});h=sha(p);was=previous.get(ident)
            same=bool(was and was['sha256']==h and was['format']==p.suffix[1:].lower())
            item=copy.deepcopy(was) if same else {'facts':{}}
            declared=[x.strip() for x in meta.get('difficulty_axes','').split(',') if x.strip()]
            item.update(id=ident,path=str(p),inputName=p.name,sha256=h,format=p.suffix[1:].lower(),
                public=was.get('public',False) if same else bool(meta),license=meta.get('license','requires-review'),
                origin=meta.get('origin',str(source)),description=meta.get('description',''),declaredFeatures=declared,
                features=sorted(set(declared+item.get('difficulty',{}).get('features',[]))))
            records[ident]=item
    value={'version':2,'sources':list(records.values())}
    if old!=value:atomic(Path(home)/'corpus-history'/(stamp()+'.json'),old)
    atomic(Path(home)/'corpus.json',value);return value

def describe_check(op,ch,src,opts,default_desc):
    if opts.get('credentialVariant') == 'exhausted_quota':
        if ch == 'outcome': return "精准拦截，JSON 返回 ok=false, exitCode!=0, error.code='auth_error' 并提示 402/Payment required 及充值余额"
        if ch == 'artifacts': return "未在输出目录生成任何伪造或残留文件 (noArtifacts=true)"
        if ch == 'commonSchema': return "符合标准错误 Schema：包含 code='auth_error', message, hint 及 requestId，无 outputs 产物"
    if op=='quality' and ch=='visual':
        from . import purposes
        return default_desc+'；重点：'+'、'.join(purposes.LABELS.get(f,f) for f in purposes.profile(src).get('focus',[]))
    if opts.get('variantLabel') and ch in ['outcome','artifacts','integrity','visual']:
        return opts['variantLabel']+'；'+default_desc+'；筛选输出按原始源页码匹配 GT，不按结果序号重编号'
    if ch in ['artifacts','integrity']:
        pages=src.get('facts',{}).get('pages')
        return '产物可解码、页序符合独立依据；物理源页数：'+(str(pages) if type(pages) is int else '未知，需独立核定')+'；文件数与 JSON pages 按冻结契约分别验证'
    return default_desc

def make_execution_snippets(source, options, operation):
    opts = options or {}
    inp = source.get('inputName') or Path(source.get('path', 'input.ext')).name
    engine = opts.get('engine', 'cloud')
    target = opts.get('target', 'image')
    interface = opts.get('interface', 'cli')
    if operation == 'release':
        cli = 'npm view @deckflow/deckrender@0.3.1 && git verify-tag v0.3.1'
        sdk = '// 校验发布包元数据与 package.json\nconst pkg = require("@deckflow/deckrender/package.json");'
    elif operation in ['deprecated', 'support']:
        cli = 'deckrender --help && grep -rn "HTML" node_modules/@deckflow/deckrender/docs/'
        sdk = '// 扫描公开导出类型与声明契约\nimport type * as Types from "@deckflow/deckrender";'
    elif operation == 'retention':
        hours = opts.get('retentionHours')
        cli = f'deckrender "{inp}" --engine cloud --retention-hours {hours or 1} -o ./out --json'
        sdk = f"import {{ render }} from '@deckflow/deckrender';\nconst result = await render({{\n  input: '{inp}',\n  engine: 'cloud',\n  retentionHours: {hours or 1}\n}});"
    elif operation == 'dependency':
        cli = f'deckrender "{inp}" --engine local -o ./out --json  # 缺失本地 Chromium/office2html 环境'
        sdk = f"import {{ render }} from '@deckflow/deckrender';\n// 缺少本地依赖时调用\nconst result = await render({{\n  input: '{inp}',\n  engine: 'local'\n}});"
    elif operation == 'schema':
        cli = f'deckrender "{inp}" --engine {engine} -o ./out --json'
        sdk = f"import {{ render }} from '@deckflow/deckrender';\nconst result = await render({{\n  input: '{inp}',\n  engine: '{engine}'\n}});"
    elif opts.get('credentialVariant') == 'exhausted_quota':
        cli = f'DECKRENDER_API_KEY="PKi92fmrbHzel1Bf41whfjxmUvF9eAGjapyfb2geCZKc198Pjcq5oj8VtbfYwHIC" deckrender "{inp}" --engine cloud --format image -o ./out --json'
        sdk = f"import {{ render }} from '@deckflow/deckrender';\n// 使用积分/额度不足的测试账号 Token 调用\nconst result = await render({{\n  input: '{inp}',\n  engine: 'cloud',\n  format: 'image',\n  apiKey: 'PKi92fmrbHzel1Bf41whfjxmUvF9eAGjapyfb2geCZKc198Pjcq5oj8VtbfYwHIC'\n}});"
    else:
        cli_parts = [f'deckrender "{inp}"', f'--engine {engine}', f'--format {target}', '-o ./out', '--json']
        if 'pages' in opts: cli_parts.append('--pages '+json.dumps(opts['pages']))
        if 'imageFormat' in opts: cli_parts.append('--image-format '+opts['imageFormat'])
        if opts.get('sourceFormat') and opts['sourceFormat'] != source.get('format'):
            cli_parts.append(f"--from {opts['sourceFormat']}")
        cli = ' '.join(cli_parts)
        if operation == 'privacy' or options.get('checkPrivacy'):
            cli = f'unshare -Urn strace -f -e trace=network,openat {cli}'
        sdk_opts = [f"  input: '{inp}',", f"  engine: '{engine}',", f"  format: '{target}',", "  out: './out',"]
        if 'pages' in opts: sdk_opts.append('  pages: '+json.dumps(opts['pages'])+',')
        if 'imageFormat' in opts: sdk_opts.append('  imageFormat: '+json.dumps(opts['imageFormat'])+',')
        sdk = "import { render } from '@deckflow/deckrender';\nconst result = await render({\n" + '\n'.join(sdk_opts) + "\n});"
    return {'cli': cli, 'sdk': sdk, 'interface': interface}

def build(home):
    from . import purposes
    sources=read(Path(home)/'corpus.json')['sources']; selected={}
    selection=purposes.policy();preferred=selection['matrixRepresentatives']
    by_id={x['id']:x for x in sources}
    for fmt,pid in preferred.items():
        if pid in by_id:selected[fmt]=by_id[pid]
    for x in sources:
        fmt=x['format']
        if fmt not in selected or (selected[fmt].get('difficulty',{}).get('status')=='blocked' and x.get('difficulty',{}).get('status')=='observed'):
            selected[fmt]=x
    handbook=REPO/'deckrender-github-release-acceptance.md'
    fallback={'id':'handbook','path':str(handbook),'sha256':sha(handbook),'format':'md','inputName':handbook.name,'public':True,'license':'user-supplied acceptance specification','facts':{}}
    cases=[];questions=[];matrix={}
    from . import releases,evaluation
    try:
        release_root,release_identity=releases.active(home)
        matrix=evaluation.declaration_matrix((release_root/'source/docs/formats.md').read_text())
    except (ValueError,OSError):release_identity=None
    from .contracts import expectations,retention_expectation
    def add(r,operation,source=None,**options):
        source=source or fallback
        if operation in ['render','quality'] and options.get('expectedSupport') is None:
            sec=options.get('engine','cloud')
            sfmt=options.get('sourceFormat',source['format'])
            options['expectedSupport']=matrix.get(f'{sec}:{sfmt}:{options.get("target")}')
        cid=f'REN-R{r:02d}-{operation}-'+digest([source['id'],options])[:12]
        definitions=[]
        check_list=CHECKS[operation]+(CHECKS['privacy'] if options.get('checkPrivacy') else [])
        common=[('commonSchema','每次 render 调用的成功或错误响应符合公共 Schema contract，不补造字段')] if operation in ['render','quality','auto','privacy','dependency','planned','schema'] else []
        for check,default_description in check_list+common:
            description=describe_check(operation,check,source,options,default_description)
            role='observation' if r==9 and check!='commonSchema' else 'gate';qid=cid+'-'+check
            rule_id=('response.commonSchema' if check=='commonSchema' else operation+'.'+check)+'.v3'
            definitions.append({'id':check,'ruleId':rule_id,'type':operation,'role':role,'severity':'critical' if check=='commonSchema' else 'minor' if r==9 else 'critical' if r in [2,3,4,7,8] else 'major','expected':description,'featureId':f'REN-R{r:02d}','questionId':qid})
            label=purposes.context({'format':source['format'],'options':options})
            questions.append({'questionId':qid,'ruleId':rule_id,'caseId':cid,'featureId':f'REN-R{r:02d}','question':f'{source["inputName"]} · {label}：{description}？','answer':description,'assertionIds':[check],'evidence':{'method':'用户验收手册与独立源事实','location':f'deckrender-github-release-acceptance.md#REN-R{r:02d}','sourceFacts':source.get('facts',{})},'uncertainty':'视觉/政策语义需人工；云审计需独立证据；未声明页数不可推断','reviewStatus':'draft'})
        covers=options.get('covers',[f'REN-R{r:02d}'])
        cases.append({'id':cid,'source':{'type':'local','uri':source['path'],'sha256':source['sha256']},'sourceId':source['id'],'format':source['format'],'public':source.get('public',False),'facts':source.get('facts',{}),'covers':covers,'operation':operation,'options':options,'evaluation':{'checks':definitions}})
        if operation in ['render','quality','planned']:
            cases[-1]['contract']=expectations(home,cases[-1])
            for ch in definitions:
                if ch['id'] in ['outcome','rejected','artifacts','integrity']:ch['contract']=copy.deepcopy(cases[-1]['contract'])
            for q in questions[-len(definitions):]:q['evidence']['releaseContract']=copy.deepcopy(cases[-1]['contract'])
        if operation=='retention':
            cases[-1]['retentionContract']=retention_expectation(home)
            for q in questions[-len(definitions):]:q['evidence']['retentionContract']=copy.deepcopy(cases[-1]['retentionContract'])
        snippet=make_execution_snippets(source,options,operation)
        cases[-1]['executionSnippet']=snippet
        for q in questions[-len(definitions):]:q['executionSnippet']=snippet
        cases[-1]['purpose']=purposes.for_case(cases[-1],source)
    add(1,'release')
    # Privacy has an independent CI owner; render/quality keep both public interfaces.
    for fmt in ['pptx','pdf']:
        for target in ['image','pdf']:
            for interface in ['cli','sdk']:
                add(2,'render',selected[fmt],engine='local',target=target,interface=interface,expectedSupport=True)
                add(3,'privacy',selected[fmt],engine='local',target=target,interface=interface)
        add(2,'dependency',selected[fmt],engine='local',target='image',interface='cli')
    for fmt in ['docx','key','ppt']:
        for interface in ['cli','sdk']:add(2,'render',selected.get(fmt),engine='local',target='image',interface=interface,sourceFormat=fmt,expectedSupport=False)
    for interface in ['cli','sdk']:add(2,'render',selected['pptx'],engine='local',target='video',interface=interface,sourceFormat='pptx',expectedSupport=False)
    for fmt in ['pptx','ppt','pdf','key','docx']:
        for target in ['image','pdf','video']:
            for interface in ['cli','sdk']:add(4,'render',selected.get(fmt),engine='cloud',target=target,interface=interface,sourceFormat=fmt,expectedSupport=None)
    for fmt in ['pages','numbers']:
        for target in ['image','pdf']:
            for interface in ['cli','sdk']:add(5,'planned',selected.get(fmt),engine='cloud',target=target,interface=interface,sourceFormat=fmt)
    for fmt in ['pptx','pdf','docx','key','ppt']:
        for interface in ['cli','sdk']:add(6,'auto',selected.get(fmt),engine='auto',target='image',interface=interface,sourceFormat=fmt)
    for interface in ['cli','sdk']:add(6,'auto',selected['pptx'],engine='auto',target='video',interface=interface,sourceFormat='pptx')
    # REN-R07: Parity between CLI and SDK (runs both CLI and SDK to ensure contract parity)
    for engine in ['local','cloud']:add(7,'schema',selected['pptx'],engine=engine,target='image',interface='cli')
    # Explicit option cases; representative fixtures keep boundary tests small.
    from .option_cases import variants
    for fmt,engine,variant in variants():
        source=by_id['markers-'+fmt] if fmt in ['pdf','pptx'] else selected[fmt]
        for interface in ['cli','sdk']:
            add(7,'render',source,engine=engine,target=variant.get('outputTarget','image'),interface=interface,**{k:v for k,v in variant.items() if k!='outputTarget'})
    # REN-R07 / REN-R11: 积分/额度不足时的错误拦截与提示（使用 Token 2 验证真实云端 402/auth_error 拦截）
    for interface in ['cli','sdk']:
        add(7,'render',selected['pptx'],engine='cloud',target='image',interface=interface,credentialVariant='exhausted_quota',expectedSupport=False,covers=['REN-R07','REN-R11'])
    # REN-R08: Cloud retention audit
    for hours in [1,None,99]:add(8,'retention',selected['pptx'],engine='cloud',target='image',interface='sdk',retentionHours=hours)
    # REN-R09: Quality (Visual Artifacts once per route on CLI)
    for c in list(cases):
        if c['operation']=='render' and c['options'].get('expectedSupport') is True:
            source=by_id.get(c['sourceId'],fallback)
            add(9,'quality',source,**copy.deepcopy(c['options']))
    for source in sources:
        if source['format'] not in ['pptx','pdf','ppt','key','docx'] or source['id'] in {s['id'] for s in selected.values()}:continue
        profile=purposes.profile(source)
        if profile['role']=='reference':continue
        routes=profile.get('routes') or {'cloud':'image'}
        for engine,target in routes.items():
            support=matrix.get(engine+':'+source['format']+':'+target)
            if support is False:continue
            add(9,'quality',source,engine=engine,target=target,interface='cli',sourceFormat=source['format'],expectedSupport=support)
    add(10,'deprecated');add(11,'support')
    def pairing(c):return (c['source']['sha256'],c['options'].get('engine'),c['options'].get('target'),c['options'].get('interface'),c['options'].get('pages'),c['options'].get('imageFormat'),c['options'].get('variantId'))
    quality_cases={pairing(c):c['id'] for c in cases if c['operation']=='quality'}
    for c in cases:
        if c['operation']=='render':c['qualityCaseId']=quality_cases.get(pairing(c))
    for sid,quality in [('deckrender-release',False),('deckrender-quality',True)]:
        subset=[c for c in cases if (c['operation']=='quality')==quality]; ids={c['id'] for c in subset}
        folder=suite_root(home)/sid
        existing=folder/'suite.json'
        if existing.exists():
            archive=Path(home)/'suite-history'/stamp()/sid;shutil.copytree(folder,archive)
        atomic(folder/'suite.json',{'id':sid,'displayName':'DeckRender '+('渲染质量证据' if quality else '发布验收'),'profile':'render','version':'5','selectionPolicy':'benchmark/config/case-selection.json','reviewStatus':'draft','evaluator':{'id':'render-quality' if quality else 'render-release-contract','version':'4'},'qualityPolicy':POLICY,'features':'features.json','cases':'cases.jsonl','questions':'questions.jsonl'})
        atomic(folder/'features.json',{'features':[{'id':f'REN-R{i+1:02d}','name':t} for i,t in enumerate(TITLES) if (i==8)==quality]})
        atomic(folder/'cases.jsonl',''.join(json.dumps(c,ensure_ascii=False)+'\n' for c in subset))
        atomic(folder/'questions.jsonl',''.join(json.dumps(q,ensure_ascii=False)+'\n' for q in questions if q['caseId'] in ids))
    return {'cases':cases,'questions':questions}
