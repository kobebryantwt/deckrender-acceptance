"""Core command adapter: records raw target output only, no quality rules."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from acceptance.common import DEFAULT_HOME
from acceptance.maintenance import load_suites
from acceptance.target import invoke
p=argparse.ArgumentParser();p.add_argument('--input');p.add_argument('--output');p.add_argument('--case');p.add_argument('--interface');a=p.parse_args()
_,cases,_=load_suites();case=next(c for c in cases if c['id']==a.case)
case['source']['uri']=a.input;case['options']['interface']=a.interface
print(json.dumps(invoke(DEFAULT_HOME,case,a.output),ensure_ascii=False))
