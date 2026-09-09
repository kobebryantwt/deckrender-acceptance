from __future__ import annotations
import contextlib, datetime as dt, hashlib, html, json, os, re, subprocess, tempfile, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT_HOME = REPO / 'benchmark/artifacts/acceptance'

def now(): return dt.datetime.now(dt.timezone.utc).isoformat()
def stamp(): return dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + os.urandom(3).hex()
def encoded(v): return json.dumps(v, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
def digest(v): return hashlib.sha256(encoded(v).encode()).hexdigest()
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p, default=None): return json.loads(Path(p).read_text()) if Path(p).exists() else default

def atomic(p, v):
    p=Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', dir=p.parent, delete=False, encoding='utf-8') as f:
        f.write(v if isinstance(v,str) else encoded(v)); tmp=f.name
    os.replace(tmp,p)

def safe_id(v):
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',v) or v in {'.','..'}: raise ValueError('Invalid identifier')
    return v

def inside(root, rel):
    p=(Path(root)/rel).resolve()
    if not p.is_relative_to(Path(root).resolve()): raise ValueError('Path escapes evidence root')
    return p

@contextlib.contextmanager
def locked(home):
    p=Path(home)/'.lock'; p.parent.mkdir(parents=True,exist_ok=True)
    try: fd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError: raise ValueError(f'Another operation holds {p}; inspect owner before removing stale lock')
    os.write(fd,str(os.getpid()).encode()); os.close(fd)
    try: yield
    finally: p.unlink(missing_ok=True)

def redact(v):
    if isinstance(v,dict):
        return {k: ('[REDACTED]' if re.search(r'(?i)(token|secret|password|api.?key|authorization|cookie)',k) else redact(x)) for k,x in v.items()}
    if isinstance(v,list): return [redact(x) for x in v]
    if not isinstance(v,str): return v
    v=re.sub(r'(https?://[^\s"<>?]+)\?[^\s"<>]*',r'\1?[REDACTED]',v)
    v=re.sub(r'(?i)((?:bearer|api[-_]?key|token|password|secret)\s*[:= ]\s*)[^\s,"}]+',r'\1[REDACTED]',v)
    for key,value in os.environ.items():
        if re.search(r'(?i)(token|secret|password|api.?key)',key) and len(value)>5: v=v.replace(value,'[REDACTED]')
    return v

def process(command, cwd=None, timeout=120, env=None):
    import signal
    start=time.monotonic()
    try:
        p=subprocess.Popen([str(x) for x in command],cwd=cwd,env=env,text=True,encoding='utf-8',errors='replace',stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=os.name=='posix')
        try:
            stdout,stderr=p.communicate(timeout=timeout)
            out={'exitCode':p.returncode,'stdout':stdout,'stderr':stderr}
        except subprocess.TimeoutExpired:
            if os.name=='posix':os.killpg(p.pid,signal.SIGKILL)
            else:p.kill()
            stdout,stderr=p.communicate()
            out={'exitCode':None,'stdout':stdout,'stderr':stderr,'timedOut':True}
    except OSError as e: out={'exitCode':None,'stdout':'','stderr':str(e),'launchError':True}
    return {**out,'durationMs':round((time.monotonic()-start)*1000),'command':[str(x) for x in command]}

def seal(folder):
    folder=Path(folder)
    hashes={str(p.relative_to(folder)):sha(p) for p in sorted(folder.rglob('*')) if p.is_file() and p.name!='SHA256SUMS.json'}
    atomic(folder/'SHA256SUMS.json',hashes); return hashes

def verify(folder):
    folder=Path(folder); manifest=read(folder/'SHA256SUMS.json')
    if not manifest: raise ValueError('Missing evidence seal')
    actual={str(p.relative_to(folder)) for p in folder.rglob('*') if p.is_file() and p.name!='SHA256SUMS.json'}
    if actual!=set(manifest):
        missing=sorted(set(manifest)-actual);extra=sorted(actual-set(manifest))
        raise ValueError(f'Evidence inventory changed in {folder.name}: missing={len(missing)} {missing[:5]}, extra={len(extra)} {extra[:5]}')
    for rel,want in manifest.items():
        p=inside(folder,rel)
        if p.is_symlink() or sha(p)!=want: raise ValueError(f'Evidence checksum mismatch: {rel}')
    return True


def suite_root(home=None):
    """Default checkout remains the Core suite export; alternate homes are isolated."""
    if home is None or Path(home).resolve() == DEFAULT_HOME.resolve():
        return REPO/'benchmark/suites'
    return Path(home)/'suites'
