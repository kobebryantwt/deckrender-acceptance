import os,tempfile
from .common import *
from . import releases

def capture(home):
    root,identity=releases.active(home);pkg=releases.package_path(home)
    dest=Path(home)/'catalog'/identity['tag'];dest.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as d:
        env={k:v for k,v in os.environ.items() if not any(x in k.upper() for x in ['TOKEN','KEY','PASSWORD','SECRET'])}
        env.update({'HOME':d,'USERPROFILE':d,'XDG_CONFIG_HOME':d})
        for name,args in [('help',['--help']),('version',['--version']),('local-formats',['formats','--engine','local','--json']),('cloud-formats',['formats','--engine','cloud','--json'])]:
            atomic(dest/(name+'.json'),redact(process(['node',str(pkg/'dist/cli.js'),*args],env=env)))
    try:
        commit=releases.api(releases.API+'/commits/main')['sha']
        observation={'commit':commit,'observedAt':now(),'scope':'main only; never substitutes release-tag assertions'}
        for name in ['README.md','LICENSE']:
            data=releases.fetch('https://raw.githubusercontent.com/deckflow/deckrender/'+commit+'/'+name)
            atomic(dest/('main-'+name),data.decode());observation[name]=sha(dest/('main-'+name))
        atomic(dest/'main-observation.json',observation)
    except (ValueError,OSError) as e:atomic(dest/'main-observation.json',{'status':'blocked','reason':str(e)})
    seal(dest);return {'catalog':str(dest),'tag':identity['tag']}
