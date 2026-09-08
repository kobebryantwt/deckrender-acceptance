"""CI environment values are data, never interpolated shell source."""
import argparse,os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from acceptance.common import *
from acceptance import releases,snapshot,reporting,cloud
p=argparse.ArgumentParser();p.add_argument('action',choices=['check','freeze','retention','record']);p.add_argument('--snapshot',type=Path,default=REPO/'ci-input/current');a=p.parse_args()
home=DEFAULT_HOME
with locked(home):
 if a.action=='check':
    snapshot.validate(a.snapshot)
    identity=releases.discover(os.getenv('RELEASE_TAG') or None)
    from acceptance.state import check
    result=check(home,identity,snapshot.load(a.snapshot),os.getenv('FORCE_RUN')=='true')
    changed=result['changed']
    if os.getenv('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write('changed='+str(changed).lower()+'\n')
    print('CHANGE' if changed else 'NO_CHANGE')
 elif a.action=='record':
    from acceptance.state import record
    for path in (home/'runs').glob('*/run.json'):
        verify(path.parent);record(home,read(path))
 elif a.action=='freeze':print(encoded(releases.prepare(home,os.getenv('RELEASE_TAG') or None)))
 elif os.getenv('RETENTION_ACTION')=='submit':
    data=snapshot.load(a.snapshot)
    print(encoded([cloud.submit(home,c) for c in data['cases'] if c['operation']=='retention']))
 else:print(encoded(cloud.collect(home)))
