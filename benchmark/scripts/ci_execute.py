"""One execution session across five independently reported acceptance groups."""
import os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from acceptance import runner,target,snapshot
from acceptance.cloud_budget import Session
from acceptance.common import DEFAULT_HOME,atomic,locked,safe_id

def main():
    source=Path('ci-input/current');data=snapshot.load(source)
    mode=os.getenv('REN_RUN_MODE','debug')
    selected=os.getenv('REN_DEBUG_CLOUD_CASES','').split()
    unknown=set(selected)-{c['id'] for c in data['cases']}
    if unknown:raise ValueError('Unknown debug case IDs: '+str(sorted(unknown)))
    limit=lambda name: int(os.environ[name]) if os.getenv(name) else None
    session=Session(data['cases'],mode,os.getenv('REN_ALLOW_CLOUD')=='1',limit('REN_MAX_CLOUD_CALLS'),limit('REN_MAX_SOURCE_PAGES'),selected)
    rid=safe_id(os.environ['GITHUB_RUN_ID'])
    with locked(DEFAULT_HOME):
        target.SESSION=session
        try:
            for group in ['release','local','privacy','cloud','quality']:
                print('Executing '+group,flush=True)
                runner.execute(DEFAULT_HOME,group,source,rid+'-'+group)
        finally:
            atomic(DEFAULT_HOME/'execution-budget.json',session.snapshot())
            target.SESSION=None
if __name__=='__main__':main()
