"""Declared routes are release evidence; source page counts never come from rendering."""
from .common import *
from . import releases

def retention_expectation(home):
    try:
        root,identity=releases.active(home)
        policy=read(REPO/'benchmark/config/release-contracts'/(identity['version']+'.json'),{}).get('retention')
        if not policy:raise ValueError('Retention capability needs a versioned public-contract review')
        evidence=[{'file':f,'sha256':sha(root/f)} for f in policy['evidenceFiles']]
        return {'status':'declared',**policy,'release':{k:identity[k] for k in ['tag','commit','version']},'evidence':evidence}
    except (ValueError,OSError,KeyError,TypeError) as e:return {'status':'unresolved','reason':str(e)}

def expectations(home,case):
    o=case['options'];engine=o['engine'];fmt=case['format'];target=o['target']
    try:
        root,identity=releases.active(home)
        catalog=Path(home)/'catalog'/identity['tag'];verify(catalog)
        record=read(catalog/(engine+'-formats.json'))
        if record.get('exitCode')!=0:raise ValueError('Declaration command failed')
        row=json.loads(record['stdout'])['matrix'][fmt][target]
        policy=read(REPO/'benchmark/config/release-contracts'/(identity['version']+'.json'))
        if not policy:raise ValueError('Release result semantics require review for this version')
        result={'status':'declared','release':{k:identity[k] for k in ['tag','commit','version']},
                'evidence':{'formatsSha256':sha(catalog/(engine+'-formats.json')),'resultPolicySha256':sha(REPO/'benchmark/config/release-contracts'/(identity['version']+'.json'))},
                'supported':row['supported'],'format':target}
        if row['supported']:
            passthrough=row.get('kind')=='passthrough'
            facts=case.get('facts',{});source_count=facts.get('pages')
            if source_count is None and facts.get('pageCountReview',{}).get('actor') and facts['pageCountReview'].get('sourceSha256')==case['source']['sha256']:source_count=facts.get('visualPageCount')
            result.update(engine=row['engine'],route=['passthrough'] if passthrough else row['tasks'],caveat=row.get('caveat'),
                outputCount=1 if target in policy['singleFileTargets'] else source_count,
                reportedPages=policy['passthroughReportedPages'] if passthrough else policy['cloudSingleFileReportedPages'] if engine=='cloud' and target in policy['singleFileTargets'] else source_count)
            if passthrough:result['handbookDifference']='发布声明为 passthrough；附件 local 标记要求由 R03 单独判定，不修改原始响应'
        else:result['errorCodes']=[policy['plannedCode'] if row.get('planned') else policy['unsupportedCode']]
        if o.get('variantId'):
            option_policy=policy.get('optionContract')
            if not option_policy:raise ValueError('Option semantics require release-specific review')
            result['optionEvidence']=[{'file':f,'sha256':sha(root/f)} for f in option_policy['evidenceFiles']]
            if o.get('expectedOptionError'):
                result.update(supported=False,errorCodes=[option_policy[o['expectedOptionError']]])
            else:
                if 'expectedSourcePages' in o:
                    result.update(selectedSourcePages=o['expectedSourcePages'],outputCount=len(o['expectedSourcePages']))
                if o.get('imageFormat'):result['imageEncoding']=o['imageFormat']
                # Additional WebP conversion route needs a separately reviewed task mapping.
                if o.get('imageFormat')=='webp':result['route']=result['route']+[option_policy['webpTask']]
        return result
    except (ValueError,OSError,KeyError,TypeError) as e:return {'status':'unresolved','reason':str(e)}
