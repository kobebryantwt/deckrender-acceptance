"""Network namespaces with a privilege drop before any Python/Node target code."""
import os,platform,shutil,sys,tempfile
from .common import process,atomic,read,Path

PROBE="""import json,os,socket
print(json.dumps({'uid':os.geteuid(),'netns':os.readlink('/proc/self/ns/net'),'interfaces':[n for _,n in socket.if_nameindex()]}))
"""

def candidates():
    if platform.system()!='Linux':return []
    unshare=shutil.which('unshare');ip=shutil.which('ip')
    if not unshare or not ip:return []
    # Only loopback is enabled; no veth, host interface or external route is added.
    setup=[shutil.which('sh') or '/bin/sh','-c','"$1" link set lo up && shift && exec "$@"','namespace',ip]
    options=[('user-namespace',[unshare,'--user','--map-current-user','--net',*setup])]
    if os.getenv('REN_ALLOW_SUDO_NETNS')=='1' and os.geteuid()!=0 and shutil.which('sudo') and shutil.which('setpriv'):
        drop=[shutil.which('setpriv'),'--reuid',str(os.getuid()),'--regid',str(os.getgid()),'--clear-groups','--no-new-privs']
        options.append(('sudo-network-namespace',[shutil.which('sudo'),'-n',unshare,'--net',*setup,*drop]))
    return options

def probe():
    import json
    attempts=[]
    host=os.readlink('/proc/self/ns/net') if platform.system()=='Linux' else None
    for mode,prefix in candidates():
        result=process([*prefix,sys.executable,'-I','-c',PROBE],timeout=10)
        try:data=json.loads(result['stdout'])
        except (ValueError,TypeError):data={}
        valid=result['exitCode']==0 and data.get('uid')==os.getuid() and data.get('uid')!=0 and data.get('netns')!=host and data.get('interfaces')==['lo']
        attempts.append({'mode':mode,'process':result,'observed':data,'valid':valid})
        if valid:return {'exitCode':0,'mode':mode,'prefix':prefix,'attempts':attempts}
    return {'exitCode':None,'stderr':'No verified network namespace with ordinary user and loopback only','attempts':attempts}

def run(health,command,env,timeout=300,cwd=None):
    # sudo intentionally resets the environment. Restore the isolated HOME and sentinel
    # probes only AFTER dropping privileges. Never put environment values in argv/logs.
    with tempfile.TemporaryDirectory(prefix='ren-child-env-') as temp:
        path=Path(temp)/'environment.json';atomic(path,env);path.chmod(0o600)
        loader="import json,os,sys; e=json.load(open(sys.argv[1])); os.execvpe(sys.argv[2],sys.argv[2:],e)"
        return process([*health['prefix'],sys.executable,'-I','-c',loader,str(path),*command],timeout=timeout,cwd=cwd)
