"""One source of review purpose and stable rule identity for both review surfaces."""
from .common import *
LABELS={'fonts':'字体与多语言','charts':'图表','special-elements':'公式/媒体/特殊元素','dense-page':'密集布局','page-order':'页数与页序'}
OPERATIONS={'release':'发布追溯','render':'格式矩阵与产物','privacy':'本地隐私边界','auto':'自动路由','schema':'错误码、接口一致性与边界','planned':'规划格式拒绝','retention':'保留期与删除证据','quality':'逐页渲染质量','deprecated':'公开能力范围','support':'支持与商业承诺','dependency':'本地依赖缺失'}

def policy():return read(REPO/'benchmark/config/case-selection.json')

def profile(source):
    p=policy()['profiles'].get(source['id'])
    if p:return p
    return {'role':'difficulty' if source.get('format') in ['pdf','pptx','ppt','key','docx'] else 'reference',
            'summary':source.get('description') or ('核对 '+source.get('inputName',source['id'])+' 的格式契约和已标注特征；用途需要人工确认。'),
            'focus':source.get('declaredFeatures',source.get('features',[]))}

def context(case):
    o=case['options'];parts=[case['format'].upper(),{'local':'本地','cloud':'云端','auto':'自动'}.get(o.get('engine')),
                            {'image':'图片','pdf':'PDF','video':'视频'}.get(o.get('target')),o.get('interface','').upper()]
    parts += [o.get('variantLabel')]
    return ' / '.join(p for p in parts if p)

def for_case(case,source):
    p=profile(source);op=case['operation']
    summary=OPERATIONS[op]+'：'+context(case)+'。'
    if source['id']=='handbook':summary+='核对冻结发布的公开资料与独立证据，不进行文档渲染。'
    else:summary+=p['summary']
    return {'summary':summary,'origin':'generated:case-selection-v3','focus':p.get('focus',[]),'role':p['role'],
            'checks':[{'label':ch['expected'],'ruleId':ch['ruleId'],'answerIds':[ch['questionId']]} for ch in case['evaluation']['checks']]}

def for_source(source,cases):
    p=profile(source);related=[c for c in cases if c['sourceId']==source['id']]
    checks={}
    for c in related:
        for ch in c['evaluation']['checks']:
            row=checks.setdefault(ch['ruleId'],{'ruleId':ch['ruleId'],'label':ch['expected'],'answerIds':[]})
            row['answerIds'].append(ch['questionId'])
    observed=source.get('difficulty',{})
    return {**p,'origin':'generated:case-selection-v3','caseIds':[c['id'] for c in related],'checks':list(checks.values()),
            'optionTests':[{'caseId':c['id'],'label':c['options']['variantLabel'],'interface':c['options']['interface'],'engine':c['options']['engine'],'sourcePages':c['options'].get('expectedSourcePages'),'qualityCaseId':c.get('qualityCaseId'),'operation':c['operation']} for c in related if c['operation']=='render' and c['options'].get('variantId')],
            'videoQualityRequired':any(c['operation']=='quality' and c['options'].get('target')=='video' for c in related),
            'routes':sorted({' / '.join(str(c['options'].get(k,'—')) for k in ['engine','target','interface']) for c in related if c['options'].get('engine')}),
            'observedFeatures':observed.get('features',[]) if observed.get('sourceSha256')==source['sha256'] else [],
            'independentPageCount':source.get('facts',{}).get('pages'),
            'featureEvidenceStatus':observed.get('status','uncharacterized'),
            'scopeNote':'仅作参考，不计入执行覆盖' if p['role']=='reference' else '已出题不代表已有 GT、已执行或通过'}
