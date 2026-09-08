"""v3: evaluate source-bound structured expectations separately from JSON shape."""
from acceptance.versioned import load
_v2=load('render-release-contract','contract','2')
globals().update({k:v for k,v in vars(_v2).items() if not k.startswith('_')})

def declared_outcome(proc,contract):
    if not contract or contract.get('status')!='declared':return 'blocked',{'reason':'Frozen structured expectation unavailable','contract':contract}
    status,actual=outcome(proc,contract['supported'])
    if status!='passed':return status,actual
    p=proc.get('payload') or {};errors=[]
    if contract['supported']:
        for field in ['engine','format','route','caveat']:
            if p.get(field)!=contract.get(field):errors.append({'field':field,'expected':contract.get(field),'actual':p.get(field)})
        if type(contract.get('reportedPages')) is int and p.get('pages')!=contract['reportedPages']:errors.append({'field':'pages','expected':contract['reportedPages'],'actual':p.get('pages')})
    elif machine_code(proc) not in contract['errorCodes']:errors.append({'field':'error.code','expected':contract['errorCodes'],'actual':machine_code(proc)})
    return ('failed' if errors else 'passed'),{'errors':errors,'contract':contract,'response':actual}

def declared_artifacts(proc,facts,contract):
    if not facts.get('pages') and facts.get('visualPageCount') and facts.get('pageCountReview',{}).get('actor'):facts={**facts,'pages':facts['visualPageCount']}
    contract=contract or {}
    selected=contract.get('selectedSourcePages')
    if selected is not None:
        facts={**facts,'pages':len(selected)}
        if facts.get('pageMarkers'):facts['pageMarkers']=[facts['pageMarkers'][i-1] for i in selected]
    status,actual=artifact_checks(proc,facts)
    entries=(proc.get('payload') or {}).get('outputs',[])
    errors=[]
    if selected is not None and [e.get('page') for e in entries if isinstance(e,dict)]!=selected:
        errors.append('Output source-page identities differ from reviewed selection')
    if contract.get('imageEncoding'):
        from PIL import Image
        wanted={'png':'PNG','jpg':'JPEG','webp':'WEBP'}[contract['imageEncoding']]
        for entry in entries:
            try:
                path=Path(entry['file']).resolve()
                if not path.is_relative_to(Path(proc['artifactsDir']).resolve()):raise ValueError('Artifact outside output root')
                with Image.open(path) as image:
                    if image.format!=wanted:errors.append('Decoded encoding differs from '+wanted)
            except (ValueError,OSError,KeyError,TypeError) as e:errors.append(str(e))
    if errors:return 'failed',{'errors':errors,'artifacts':actual}

    n=(contract or {}).get('outputCount');entries=(proc.get('payload') or {}).get('outputs')
    if type(n) is int and isinstance(entries,list) and len(entries)!=n:
        return 'failed',{'expectedOutputFiles':n,'actualOutputFiles':len(entries),'artifacts':actual}
    return status,actual


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
    # JSON pages is checked by declared_outcome; this function checks physical source pages.
    if facts.get('pageMarkers') and p.get('format')!='video' and not marker_blocked:
        expected_markers=facts['pageMarkers']
        parsed=[re.search(r'REN\s+PAGE\s+(\d+)',text,re.I) for text in markers]
        if len(markers)!=len(expected_markers) or any(x is None for x in parsed):marker_uncertain=True
        elif [int(x.group(1)) for x in parsed]!=[int(re.search(r'\d+',x).group()) for x in expected_markers]:errors.append('Independent page content/order does not match source markers')
    return ('failed' if errors else 'blocked' if marker_blocked else 'review' if marker_uncertain or not facts.get('pages') or p.get('format')=='video' else 'passed'),{'errors':errors,'markerEvidence':markers,'markerUncertain':marker_uncertain,'oracleGaps':marker_blocked or ([] if facts.get('pages') else ['No independent page count/order oracle']),'pageOrder':pages,'decodedPages':decoded_pages,'pageCountOracle':facts.get('pages')}
