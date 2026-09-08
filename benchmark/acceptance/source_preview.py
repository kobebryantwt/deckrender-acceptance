"""Independent source-to-page exports, isolated from the DeckRender target."""
import shutil,plistlib,zipfile
from .common import *
KEYNOTE_APP=Path('/Applications/Keynote.app')

def find_office(home):
    """Persist an observed tool path so desktop/server PATH differences do not erase GT."""
    configured=os.getenv('REN_SOFFICE')
    if configured:return configured if Path(configured).is_file() else None
    detected=shutil.which('soffice')
    config=Path(home)/'source-preview-tools.json'
    if detected:
        if Path(detected).is_file():atomic(config,{'soffice':detected})
        return detected
    saved=read(config,{}).get('soffice')
    for path in [saved,'/Applications/LibreOffice.app/Contents/MacOS/soffice']:
        if path and Path(path).is_file():return path
    return None

KEYNOTE='''on run argv
set sourceFile to POSIX file (item 1 of argv)
set targetFile to POSIX file (item 2 of argv)
tell application "Keynote"
  with timeout of 90 seconds
    set previewDocument to open sourceFile
    try
      set pageCount to count of slides of previewDocument
      export previewDocument to targetFile as PDF with properties {all stages:false, skipped slides:true}
      close previewDocument saving no
      return pageCount as text
    on error errorMessage number errorNumber
      try
        close previewDocument saving no
      end try
      error errorMessage number errorNumber
    end try
  end timeout
end tell
end run
'''

def export(source,home,_engine=None):
    """Cache by source + exporter identity/settings; never open the original in an editor."""
    path=Path(source['path']);fmt=source['format']
    if sha(path)!=source['sha256']:raise ValueError('源文件已变化，需要重新准备')
    if fmt=='pdf':return path,{'renderer':'PyMuPDF','method':'source PDF','sourceSha256':source['sha256']}
    # An explicit, hash-bound author PDF is preferable to a cross-application export.
    paired=read(REPO/'benchmark/config/paired-references.json',{}).get(source.get('id'))
    if paired:
        reference=inside(REPO,paired['path']);provenance=inside(REPO,paired['provenance'])
        if paired['sourceSha256']!=source['sha256'] or sha(reference)!=paired['sha256'] or sha(provenance)!=paired['provenanceSha256']:raise ValueError('Author reference or source changed; pairing needs review')
        return reference,{'renderer':'Author-supplied PDF / PyMuPDF','method':'publisher paired reference, selected original pages; candidate only','sourceSha256':source['sha256'],'referencePdfSha256':sha(reference),'provenance':read(provenance),'status':'draft'}

    if fmt in ['pptx','docx'] and not zipfile.is_zipfile(path):raise ValueError('加密或损坏的 Office 文件：需要密码或有效原件，不能生成完整页面')
    native=(fmt=='key' or _engine=='keynote') and KEYNOTE_APP.exists()
    if native:
        info=plistlib.loads((KEYNOTE_APP/'Contents/Info.plist').read_bytes())
        renderer={'name':'Keynote','version':info.get('CFBundleShortVersionString'),'settings':{'skippedSlides':True,'allBuildStages':False}}
    else:
        binary=find_office(home)
        if not binary:
            if fmt=='pptx' and KEYNOTE_APP.exists():return export(source,home,_engine='keynote')
            raise ValueError('独立 Office 预览工具不可用：需要 LibreOffice')
        version=process([binary,'--version'],timeout=15)
        if version['exitCode']!=0:raise ValueError('LibreOffice 无法启动')
        font_dirs=[str(p) for p in [Path('/System/Library/Fonts'),Path('/Library/Fonts')] if p.is_dir()]
        renderer={'name':'LibreOffice','version':version['stdout'].strip(),'settings':{'macroSecurity':3,'updateLinks':False,'exportHiddenSlides':True,'fontDirectories':font_dirs,'fontConfigurationVersion':1}}
    cache=Path(home)/'source-previews'/source['sha256']/digest(renderer)[:16]
    cached=read(cache/'export.json')
    if cached and (cache/'source.pdf').is_file() and sha(cache/'source.pdf')==cached.get('pdfSha256'):
        return cache/'source.pdf',cached
    cache.mkdir(parents=True,exist_ok=True)
    copied=cache/('source.'+fmt);shutil.copyfile(path,copied)
    if native:
        script=cache/'export.applescript';atomic(script,KEYNOTE)
        result=process(['osascript',str(script),str(copied.resolve()),str((cache/'source.pdf').resolve())],timeout=100)
    else:
        profile=cache/'profile';profile.mkdir(exist_ok=True)
        atomic(profile/'user/registrymodifications.xcu','''<?xml version="1.0" encoding="UTF-8"?><oor:items xmlns:oor="http://openoffice.org/2001/registry"><item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop></item><item oor:path="/org.openoffice.Office.Common/Load"><prop oor:name="UpdateLinks" oor:op="fuse"><value>false</value></prop></item></oor:items>''')
        filter_name='impress_pdf_Export' if fmt in ['pptx','ppt','key'] else 'writer_pdf_Export' if fmt in ['docx','pages'] else 'calc_pdf_Export'
        specification='pdf:'+filter_name+':'+json.dumps({'ExportHiddenSlides':{'type':'boolean','value':'true'}})
        environment=dict(os.environ)
        if font_dirs:
            config=cache/'fonts.conf'
            atomic(config,'<?xml version="1.0"?><fontconfig>'+''.join('<dir>'+html.escape(d)+'</dir>' for d in font_dirs)+'<cachedir>'+html.escape(str((Path(home)/'font-cache').resolve()))+'</cachedir></fontconfig>')
            environment['FONTCONFIG_FILE']=str(config.resolve())
        result=process([binary,'-env:UserInstallation='+profile.resolve().as_uri(),'--headless','--nologo','--nodefault','--norestore','--convert-to',specification,'--outdir',str(cache.resolve()),str(copied.resolve())],timeout=60,env=environment)
    atomic(cache/'process.json',result)
    pdf=cache/'source.pdf'
    if result['exitCode']!=0 or not pdf.is_file():
        if fmt=='pptx' and not native and KEYNOTE_APP.exists():return export(source,home,_engine='keynote')
        raise ValueError(renderer['name']+' 无法导出该文件：'+(result.get('stderr') or result.get('stdout') or '转换超时')[-900:])
    import fitz
    with fitz.open(pdf) as doc:
        if doc.needs_pass or len(doc)==0:raise ValueError('独立转换没有生成可读取的页面')
        pages=len(doc)
    if native and result.get('stdout','').strip().isdigit() and int(result['stdout'].strip())!=pages:raise ValueError('Keynote 导出页数与原演示文稿幻灯片数不一致')
    if sha(path)!=source['sha256']:raise ValueError('源文件在预览生成期间发生变化')
    provenance={'renderer':renderer,'sourceSha256':source['sha256'],'pdfSha256':sha(pdf),'pages':pages,'createdAt':now(),
                'status':'draft','method':'independent source export; not DeckRender output','caveats':['字体替换、动画静态化和分页可能受独立导出工具影响；仍需人工确认'],'processEvidence':str(cache/'process.json')}
    atomic(cache/'export.json',provenance)
    return pdf,provenance
