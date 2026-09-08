"""Freeze a published GitHub tag and independently verified npm tarball."""
import base64, hashlib, io, json, os, tarfile, urllib.request
from pathlib import Path
from .common import *

API='https://api.github.com/repos/deckflow/deckrender'

def fetch(url):
    headers={'User-Agent':'deckrender-acceptance','Accept':'*/*'}
    if url.startswith('https://api.github.com/') and os.getenv('GH_TOKEN'): headers['Authorization']='Bearer '+os.environ['GH_TOKEN']
    with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=60) as r: return r.read()
def api(url): return json.loads(fetch(url))

def discover(tag=None):
    release=api(API+('/releases/tags/'+safe_id(tag) if tag else '/releases/latest'))
    if release['draft'] or release['prerelease']: raise ValueError('A formal published release is required')
    commit=api(API+'/commits/'+release['tag_name'])['sha']
    return {'repository':'deckflow/deckrender','tag':release['tag_name'],'commit':commit,'publishedAt':release['published_at'],'releaseUrl':release['html_url'],'notes':release.get('body','')}

def extract(data, dest, strip=0):
    with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as tf:
        for member in tf.getmembers():
            parts=Path(member.name).parts[strip:]
            if not parts: continue
            if not member.isfile() and not member.isdir(): raise ValueError('Archive contains links or special files')
            p=inside(dest,str(Path(*parts)))
            if member.isdir():p.mkdir(parents=True,exist_ok=True)
            else:
                p.parent.mkdir(parents=True,exist_ok=True)
                with tf.extractfile(member) as src:p.write_bytes(src.read())

def prepare(home, tag=None):
    identity=discover(tag); tag=identity['tag']; root=Path(home)/'releases'/safe_id(tag)
    if root.exists():
        verify(root)
        lock=read(root/'release.json')
        if lock['commit']!=identity['commit']: raise ValueError('Published tag moved since freeze')
        atomic(Path(home)/'active-release.json',{'path':str(root.resolve())}); return lock
    stage=Path(home)/'staging'/stamp(); stage.mkdir(parents=True)
    source=fetch(API+'/tarball/'+identity['commit']); extract(source,stage/'source',1)
    pkg=read(stage/'source/package.json'); version=pkg['version']
    npm=api('https://registry.npmjs.org/@deckflow%2fdeckrender/'+version)
    raw=fetch(npm['dist']['tarball']); integrity=npm['dist'].get('integrity','')
    valid=False
    for value in integrity.split():
        algo,_,expected=value.partition('-')
        if algo in {'sha512','sha256'} and base64.b64encode(hashlib.new(algo,raw).digest()).decode()==expected:valid=True
    if not valid: raise ValueError('npm SRI missing or mismatched')
    (stage/'package.tgz').write_bytes(raw); extract(raw,stage/'package',1)
    atomic(stage/'npm-metadata.json',npm)
    runtime=stage/'runtime'; runtime.mkdir()
    atomic(runtime/'package.json',{'name':'deckrender-release-verification','version':'1.0.0','private':True,'dependencies':{'@deckflow/deckrender':'file:../package.tgz'}})
    install=process(['npm','install','--include=optional','--no-audit','--no-fund'],runtime,timeout=900)
    atomic(stage/'install.json',redact(install))
    if install['exitCode']!=0: raise ValueError(f'Frozen package installation blocked; inspect {stage}/install.json')
    lock={**identity,'version':version,'npmIntegrity':integrity,'npmTarballSha256':sha(stage/'package.tgz'),'sourceArchiveSha256':hashlib.sha256(source).hexdigest(),'packageLockSha256':sha(runtime/'package-lock.json'),'frozenAt':now()}
    # Node_modules are reproducible installation output, not part of the immutable release archive.
    atomic(stage/'release.json',lock)
    modules=runtime/'node_modules'; runtime_cache=Path(home)/'runtimes'/safe_id(tag)/'node_modules'
    runtime_cache.parent.mkdir(parents=True,exist_ok=True)
    modules.rename(runtime_cache);record_runtime(runtime_cache)
    seal(stage); root.parent.mkdir(parents=True,exist_ok=True); stage.rename(root)
    atomic(Path(home)/'active-release.json',{'path':str(root.resolve())}); return lock

def active(home):
    record=read(Path(home)/'active-release.json')
    if not record: raise ValueError('No frozen release; run prepare --online')
    root=Path(home)/'releases'/Path(record['path']).name; verify(root)
    return root,read(root/'release.json')

def package_path(home, minimal=False):
    root,identity=active(home)
    base=Path(home)/'runtimes'/identity['tag']
    if minimal:base=base/'cloud-only'
    p=base/'node_modules/@deckflow/deckrender'
    if not (p/'dist/cli.js').is_file(): raise ValueError('Frozen runtime missing; restore-runtime is required')
    # The executed package must match the unpacked registry artifact exactly.
    for f in (root/'package').rglob('*'):
        if f.is_file() and (not (p/f.relative_to(root/'package')).is_file() or sha(f)!=sha(p/f.relative_to(root/'package'))):
            raise ValueError('Installed package differs from frozen npm artifact')
    return p

def restore_runtime(home, minimal=False):
    root,identity=active(home); stage=Path(home)/'runtime-restore'/stamp(); stage.mkdir(parents=True)
    import shutil
    for name in ['package.json','package-lock.json']:shutil.copy2(root/'runtime'/name,stage/name)
    shutil.copy2(root/'package.tgz',stage.parent/'package.tgz')
    p=process(['npm','ci','--omit=optional' if minimal else '--include=optional','--no-audit','--no-fund'],stage,900)
    atomic(stage/'install.json',redact(p))
    if p['exitCode']!=0:raise ValueError('npm ci failed')
    base=Path(home)/'runtimes'/identity['tag']
    if minimal:base=base/'cloud-only'
    dest=base/'node_modules'; dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists():shutil.rmtree(dest)
    (stage/'node_modules').rename(dest);record_runtime(dest)
    return {'runtime':str(dest),'package':str(package_path(home,minimal))}

def record_runtime(modules):
    modules=Path(modules)
    inventory={str(p.relative_to(modules)):sha(p) for p in sorted(modules.rglob('*')) if p.is_file()}
    atomic(modules.parent/'runtime-inventory.json',inventory)
    return digest(inventory)

def verify_runtime(home,minimal=False):
    _,identity=active(home);base=Path(home)/'runtimes'/identity['tag']
    if minimal:base=base/'cloud-only'
    wanted=read(base/'runtime-inventory.json')
    if not wanted:raise ValueError('Runtime inventory missing; restore-runtime required')
    actual={str(p.relative_to(base/'node_modules')):sha(p) for p in sorted((base/'node_modules').rglob('*')) if p.is_file()}
    if actual!=wanted:raise ValueError('Frozen runtime dependencies changed; restore-runtime required')
    return digest(actual)
