"""Conservative cache reclamation; evidence and history never enter the allowlist."""
import shutil
from .common import *


def clean(home, apply=False):
    # Only interpreter caches are unconditionally reproducible. Images, font caches,
    # runtime installations, snapshots and review histories are intentionally excluded.
    candidates=[]
    for root in [REPO/'benchmark/acceptance', REPO/'benchmark/scripts', REPO/'benchmark/evaluators', REPO/'casework']:
        for path in sorted(root.rglob('__pycache__')):
            if path.is_symlink() or any(p.is_symlink() for p in path.rglob('*')):continue
            files=[p for p in path.rglob('*') if p.is_file()]
            if any(p.suffix!='.pyc' for p in files):continue
            candidates.append({'path':str(path),'bytes':sum(p.stat().st_size for p in files),'reason':'Reproducible Python bytecode only'})
    for item in candidates:
        if apply:shutil.rmtree(item['path'])
    return {'mode':'apply' if apply else 'dry-run','bytes':sum(x['bytes'] for x in candidates),'candidates':candidates,
            'protected':['runs','releases','runtimes','cloud','casework/objects','suite-history','gt','gt-assets','source-previews','snapshots','browser feedback attachments']}
