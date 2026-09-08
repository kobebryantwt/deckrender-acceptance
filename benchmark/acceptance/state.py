"""Shared change detection: attempted, completed and passed are different states."""
import os, shutil
from .common import *
from .reporting import core
from .execution import manifest


def fingerprint(home, identity, data):
    parts = ['acceptance', 'evaluators', 'adapters', 'scripts', 'config']
    environment = {'cloudEnabled': os.getenv('REN_ALLOW_CLOUD') == '1',
                   'accountConfigured': any(os.getenv(k) for k in ['DECKRENDER_API_KEY','DECKFLOW_API_KEY','DECKHTML_API_KEY','DECKRENDER_TOKEN','DECKFLOW_TOKEN']),
                   'auditConfigured': bool(os.getenv('REN_AUDIT_COMMAND')),
                   'lifecycleConfigured': bool(os.getenv('REN_LIFECYCLE_COMMAND')),
                   'tools': {k: bool(shutil.which(k)) for k in ['strace', 'unshare', 'node', 'ffprobe', 'tesseract']}}
    return digest({'release': identity, 'execution': manifest(data),
                   'review': portable_reviews(data),
                   'code': {p: core.directory_sha256(REPO/'benchmark'/p) for p in parts},
                   'caseworkCode': core.directory_sha256(REPO/'casework/casework'),
                   'environment': environment,
                   'audit': core.directory_sha256(Path(home)/'cloud') if (Path(home)/'cloud').exists() else None})


def portable_reviews(data):
    return sorted((q['questionId'],q.get('reviewStatus'),digest(q.get('review'))) for q in data['questions'])


def check(home, identity, data, force=False):
    value=fingerprint(home,identity,data)
    prior=read(Path(home)/'last-attempted.json',{})
    # Incomplete runs remain retryable when external dependencies recover without code changes.
    changed=force or prior.get('fingerprint')!=value or prior.get('decision') not in {'PASS','FAIL'}
    result={'changed':changed,'fingerprint':value,'release':identity,'status':'CHANGE' if changed else 'NO_CHANGE',
            'previousDecision':prior.get('decision')}
    atomic(Path(home)/'last-check.json',result)
    return result


def record(home, envelope):
    check=read(Path(home)/'last-check.json')
    if not check or envelope.get('group')!='all' or envelope.get('qualitySummary',{}).get('scope')!='complete':return
    if check.get('release',{}).get('commit')!=envelope.get('target',{}).get('commit'):
        raise ValueError('Change-detection release differs from completed run')
    decision=envelope['qualitySummary']['releaseDecision']
    value={**check,'decision':decision,'runId':envelope['runId'],'recordedAt':now()}
    atomic(Path(home)/'last-attempted.json',value)
    if decision in {'PASS','FAIL'}:atomic(Path(home)/'last-completed.json',value)
    if decision=='PASS':atomic(Path(home)/'last-passed.json',value)
