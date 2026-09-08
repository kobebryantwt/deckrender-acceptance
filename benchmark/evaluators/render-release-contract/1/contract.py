"""Focused render contracts. Observation and lack of authority never imply success."""
import re
from acceptance.common import *

def outcome(proc, expected=True):
    if proc.get('blocked'):return 'blocked',proc['blocked']
    if proc.get('launchError') or proc.get('timedOut'):return 'blocked','Target unavailable or timed out'
    p=proc.get('payload'); ok=isinstance(p,dict) and p.get('ok') is True and proc.get('exitCode')==0
    if expected is None:return 'review','Release support matrix has not been reviewed'
    if expected is True or expected=='supported':
        err=p.get('error',{}) if isinstance(p,dict) else {}
        if isinstance(err,dict) and err.get('code')=='auth_error':return 'blocked',err
        if isinstance(err,dict) and re.search(r'(missing|not found|not installed|unavailable).*(chromium|playwright|office2html)|(chromium|playwright|office2html).*(missing|not found|not installed|unavailable)',str(err),re.I):return 'blocked',err
        return ('passed' if ok else 'failed'),p or proc.get('stderr')
    # Negative expectation (planned or unsupported)
    if ok:
        reason=f'路线在发布文档中声明为 {expected}，但实际执行成功返回 ok:true；请核查文档是否未及时同步！'
        return 'failed',{'unexpectedSuccess':True,'expectedStatus':expected,'payload':p,'reason':reason}
    err=p.get('error',{}) if isinstance(p,dict) else {}
    code=err.get('code',p.get('code') if isinstance(p,dict) else None)
    no_outputs=not list(Path(proc.get('artifactsDir','/nonexistent')).glob('*'))
    code_str=str(code).lower() if code else ''
    if expected=='planned':
        valid=not ok and proc.get('exitCode') not in [0,None] and code_str in {'not_implemented','planned'} and no_outputs
        return ('passed' if valid else 'failed'),{'errorCode':code,'expectedStatus':'planned','payload':p,'noArtifacts':no_outputs,'hint':'规划中路线预期返回 not_implemented 机器错误码'}
    elif expected=='unsupported':
        valid=not ok and proc.get('exitCode') not in [0,None] and code_str in {'unsupported_format','unsupported'} and no_outputs
        return ('passed' if valid else 'failed'),{'errorCode':code,'expectedStatus':'unsupported','payload':p,'noArtifacts':no_outputs,'hint':'不支持路线预期返回 unsupported_format 机器错误码'}
    reject=not ok and proc.get('exitCode') not in [0,None] and code_str in {'unsupported_format','not_implemented','planned','unsupported'} and no_outputs
    return ('passed' if reject else 'failed'),{'errorCode':code,'payload':p,'noArtifacts':no_outputs}

def artifact_checks(proc, facts):
    import fitz
    from PIL import Image
    p=proc.get('payload') or {}; entries=p.get('outputs'); errors=[];pages=[]
    if not isinstance(entries,list) or not entries:return 'failed',{'errors':['Missing ordered outputs']}
    root=Path(proc['artifactsDir']).resolve()
    decoded_pages=0;markers=[];marker_blocked=[];marker_uncertain=False
    for entry in entries:
        if not isinstance(entry,dict):errors.append('Invalid output entry');continue
        page=entry.get('page');pages.append(page)
        try:
            path=Path(entry['file']).resolve()
            if not path.is_relative_to(root):raise ValueError('Artifact outside requested output root')
            if path.suffix.lower()=='.pdf':
                with fitz.open(path) as doc:
                    decoded_pages+=len(doc)
                    if facts.get('pageMarkers'):markers.extend(page.get_text() for page in doc)
            elif path.suffix.lower() in {'.png','.jpg','.jpeg','.webp'}:
                with Image.open(path) as img:img.verify()
                decoded_pages+=1
                if facts.get('pageMarkers'):
                    ocr=process(['tesseract',str(path),'stdout','--psm','11'],timeout=30)
                    if ocr['exitCode']==0:markers.append(ocr['stdout'])
                    else:marker_blocked.append('Independent OCR unavailable or failed')
            elif path.suffix.lower() in {'.mp4','.webm'}:
                result=process(['ffprobe','-v','error','-show_format','-of','json',str(path)])
                if result.get('launchError'):return 'blocked','ffprobe unavailable'
                if result['exitCode']:raise ValueError('Video decode failed')
            else:raise ValueError('Unexpected artifact extension')
        except (ValueError,OSError,KeyError,TypeError) as e:errors.append(str(e))
    if any(type(n)!=int or n<1 for n in pages) or pages!=sorted(pages,key=lambda x:x if type(x)==int else -1) or len(set(map(str,pages)))!=len(pages):errors.append('Invalid/duplicate/out-of-order pages')
    if facts.get('pages') and p.get('format')!='video' and decoded_pages!=facts['pages']:errors.append(f'Expected {facts["pages"]} pages, decoded {decoded_pages}')
    if p.get('engine')!='passthrough' and facts.get('pages') and p.get('pages')!=facts['pages']:errors.append('Reported page count mismatch')
    if facts.get('pageMarkers') and p.get('format')!='video' and not marker_blocked:
        expected_markers=facts['pageMarkers']
        parsed=[re.search(r'REN\s+PAGE\s+(\d+)',text,re.I) for text in markers]
        if len(markers)!=len(expected_markers) or any(x is None for x in parsed):marker_uncertain=True
        elif [int(x.group(1)) for x in parsed]!=[int(re.search(r'\d+',x).group()) for x in expected_markers]:errors.append('Independent page content/order does not match source markers')
    return ('failed' if errors else 'blocked' if marker_blocked else 'review' if marker_uncertain or not facts.get('pages') or p.get('format')=='video' else 'passed'),{'errors':errors,'markerEvidence':markers,'markerUncertain':marker_uncertain,'oracleGaps':marker_blocked or ([] if facts.get('pages') else ['No independent page count/order oracle']),'pageOrder':pages,'decodedPages':decoded_pages,'pageCountOracle':facts.get('pages')}

def schema(proc):
    p=proc.get('payload'); errors=[]
    if not isinstance(p,dict):return 'failed',['Missing JSON object']
    for key,typ in [('engine',str),('route',list),('outputs',list),('lifecycle',dict)]:
        if not isinstance(p.get(key),typ):errors.append('Missing/invalid '+key)
    if 'caveat' not in p:errors.append('Missing caveat (explicit null allowed for no known caveat)')
    elif p['caveat'] is not None and not isinstance(p['caveat'],str):errors.append('Invalid caveat')
    if not isinstance(p.get('pages'),int) or p.get('pages',-1)<1:errors.append('Invalid pages')
    if p.get('engine') not in {'local','cloud','passthrough'}:errors.append('Unknown actual engine')
    if isinstance(p.get('route'),list) and (not p['route'] or any(not isinstance(x,str) or not x for x in p['route'])):errors.append('Invalid route steps')
    if isinstance(p.get('outputs'),list) and (not p['outputs'] or any(not isinstance(x,dict) or type(x.get('page'))!=int or x['page']<1 or not isinstance(x.get('file'),str) for x in p['outputs'])):errors.append('Invalid ordered outputs')
    return ('failed' if errors else 'passed'),errors

def privacy_evidence(proc, directory):
    d=Path(directory);trace=d/'system.trace';envlog=d/'credentials.jsonl'
    if not trace.exists() or not trace.stat().st_size:return {k:('blocked','No independent process-tree trace') for k in ['network','credentials','local']}
    lines=trace.read_text(errors='replace').splitlines()
    external=[x for x in lines if re.search(r'(connect|sendto|sendmsg)\(',x) and ('AF_INET' in x) and not any(v in x for v in ['127.0.0.1','::1'])]
    creds=[x for x in lines if 'openat(' in x and any(s in x for s in ['.deckflow/credentials','.deckops/config.json'])]
    envreads=[line for line in envlog.read_text().splitlines() if '"env-read"' in line] if envlog.exists() else []
    p=proc.get('payload') or {}
    return {'network':('failed' if external else 'passed',external),'credentials':('failed' if creds or envreads else 'passed',{'files':creds,'environment':envreads,'scope':'Node property-read probe plus whole process-tree file trace; no claim about native direct environment reads'}),'local':('passed' if p.get('engine')=='local' and proc.get('exitCode')==0 else 'failed',p)}

def declaration_matrix(text):
    result={}; section='cloud'
    for line in text.splitlines():
        if line.startswith('##'):
            if re.search(r'local|community',line,re.I):section='local'
            elif re.search(r'cloud',line,re.I):section='cloud'
            else:section=None
        if not section or '|' not in line or line.startswith('| ---') or 'Input' in line:continue
        cells=[x.strip() for x in line.split('|')[1:-1]]
        if len(cells)!=4:continue
        formats=re.findall(r'`\.(pptx|ppt|pdf|key|docx|pages|numbers|html|htm|md|doc|xlsx)`',cells[0])
        for fmt in formats:
            for target,cell in zip(['image','pdf','video'],cells[1:]):
                if any(mark in cell for mark in ['✅','🕓','—','✗']):
                    result[f'{section}:{fmt}:{target}']='✅' in cell
    return result

def machine_code(proc):
    p=proc.get('payload') or {};err=p.get('error') or {}
    return err.get('code',p.get('code')) if isinstance(err,dict) else p.get('code')
