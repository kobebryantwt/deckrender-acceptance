import argparse, os, sys
from .common import *
from . import catalog, releases, maintenance, target, snapshot, runner, reporting, cloud

def prepare(home,online=False,tag=None,source=None):
    home=Path(home);home.mkdir(parents=True,exist_ok=True)
    identity=releases.prepare(home,tag) if online else None
    if online:
        releases.restore_runtime(home,minimal=True)
        from .discovery import capture
        capture(home)
    corpus=catalog.import_sources(home,source)
    release_pointer=read(home/'active-release.json',{})
    frozen=read(Path(release_pointer['path'])/'release.json') if release_pointer.get('path') else None
    build_key=digest({'corpus':corpus,'release':frozen,
                      'code':{str(p.relative_to(REPO)):sha(p) for p in sorted((REPO/'benchmark/acceptance').glob('*.py'))},
                      'config':reporting.core.directory_sha256(REPO/'benchmark/config')})
    if read(home/'prepared.json',{}).get('key')!=build_key or not (suite_root(home)/'deckrender-release/suite.json').exists():
        catalog.build(home)
        maintenance.refresh(home)
        atomic(home/'prepared.json',{'key':build_key})
    review=maintenance.review_page(home)
    from .previews import refresh_metadata
    refresh_metadata(home)
    return {'release':identity,'sources':len(corpus['sources']),**review}

def check(home,tag=None):
    identity=releases.discover(tag);data=maintenance.sync(home)
    from .state import check as check_state
    return check_state(home,identity,data)

def main(argv=None):
    p=argparse.ArgumentParser(description='DeckRender independent release acceptance; generated answers stay draft')
    p.add_argument('--home',type=Path,default=DEFAULT_HOME)
    sub=p.add_subparsers(dest='command',required=True)
    s=sub.add_parser('prepare');s.add_argument('--online',action='store_true');s.add_argument('--tag');s.add_argument('--source',type=Path)
    s=sub.add_parser('clean');s.add_argument('--apply',action='store_true')
    sub.add_parser('doctor');sub.add_parser('restore-runtime')
    s=sub.add_parser('check');s.add_argument('--tag')
    s=sub.add_parser('run');s.add_argument('--group',choices=runner.GROUPS,default='all');s.add_argument('--snapshot',type=Path);s.add_argument('--run-id')
    s=sub.add_parser('manage');s.add_argument('--port',type=int,default=8768)
    s=sub.add_parser('review')
    s=sub.add_parser('gt');s.add_argument('action',choices=['prepare','apply','attach']);s.add_argument('--file',type=Path);s.add_argument('--source-id');s.add_argument('--provenance')
    sub.add_parser('difficulty')
    s=sub.add_parser('dataset');s.add_argument('--source',type=Path,required=True)
    s=sub.add_parser('snapshot');ss=s.add_subparsers(dest='action',required=True)
    e=ss.add_parser('export');e.add_argument('--output',type=Path,required=True);e.add_argument('--allow-draft',action='store_true')
    e=ss.add_parser('validate');e.add_argument('--snapshot',type=Path,required=True)
    s=sub.add_parser('compare');s.add_argument('--before',type=Path,required=True);s.add_argument('--after',type=Path,required=True);s.add_argument('--output',type=Path,required=True)
    s=sub.add_parser('report');s.add_argument('--run',type=Path,required=True);s.add_argument('--output',type=Path,required=True)
    s=sub.add_parser('apply-reviews');s.add_argument('--run',type=Path,required=True);s.add_argument('--file',type=Path,required=True);s.add_argument('--output',type=Path,required=True)
    s=sub.add_parser('apply-visual');s.add_argument('--run',type=Path,required=True);s.add_argument('--file',type=Path,required=True);s.add_argument('--output',type=Path,required=True)
    s=sub.add_parser('publish');s.add_argument('--output',type=Path,required=True)
    s=sub.add_parser('aggregate');s.add_argument('--inputs',type=Path,required=True);s.add_argument('--run-id',required=True);s.add_argument('--snapshot',type=Path,required=True)
    s=sub.add_parser('verdict');s.add_argument('--run',type=Path,required=True)
    s=sub.add_parser('cloud');ss=s.add_subparsers(dest='action',required=True)
    e=ss.add_parser('submit');e.add_argument('--snapshot',type=Path)
    e=ss.add_parser('collect');e.add_argument('--evidence',type=Path)
    a=p.parse_args(argv);home=a.home.resolve()
    try:
        if a.command=='doctor':out=target.doctor(home)
        elif a.command=='manage':maintenance.manage(home,a.port);return
        else:
            with locked(home):
                if a.command=='clean':
                    from .cleanup import clean
                    out=clean(home,a.apply)
                elif a.command=='prepare':out=prepare(home,a.online,a.tag,a.source)
                elif a.command=='restore-runtime':out={'full':releases.restore_runtime(home),'minimal':releases.restore_runtime(home,minimal=True)}
                elif a.command=='check':out=check(home,a.tag)
                elif a.command=='review':out=maintenance.review_page(home)
                elif a.command=='gt':
                    from .previews import prepare as prepare_gt,apply_draft,attach
                    if a.action=='apply' and not a.file:raise ValueError('gt apply requires --file')
                    out=prepare_gt(home) if a.action=='prepare' else attach(home,a.source_id,a.file,a.provenance) if a.action=='attach' else apply_draft(home,a.file)
                elif a.command=='difficulty':
                    from .difficulty import scan
                    result=scan(home);catalog.build(home);maintenance.refresh(home)
                    out={'coverage':{k:len(v) for k,v in result['coverage'].items()},'gaps':result['gaps'],**maintenance.review_page(home)}
                elif a.command=='dataset':
                    catalog.import_sources(home,a.source);catalog.build(home);maintenance.refresh(home);out=maintenance.review_page(home)
                    from .previews import prepare as prepare_gt
                    out['previews']=prepare_gt(home)
                elif a.command=='run':out=runner.execute(home,a.group,a.snapshot,a.run_id)
                elif a.command=='snapshot':out=snapshot.export(home,a.output,a.allow_draft) if a.action=='export' else snapshot.validate(a.snapshot)
                elif a.command=='compare':out=reporting.compare(a.before,a.after,a.output)
                elif a.command=='report':out=reporting.rebuild(a.run,a.output)
                elif a.command=='apply-reviews':
                    from .annotations import apply
                    out=apply(a.run,a.file,a.output)
                elif a.command=='apply-visual':
                    from .annotations import apply_visual
                    out=apply_visual(a.run,a.file,a.output)
                elif a.command=='publish':out=reporting.publish(home/'runs',a.output)
                elif a.command=='aggregate':
                    from .ci import aggregate
                    out=aggregate(home,a.inputs,a.run_id,a.snapshot)
                elif a.command=='verdict':
                    verify(a.run);e=read(a.run/'run.json');out=e['qualitySummary'];print(encoded(out))
                    from .state import record
                    record(home,e)
                    if e.get('group')!='all' or out.get('scope')!='complete' or out['releaseDecision']!='PASS':raise SystemExit(1)
                    return
                elif a.command=='cloud':
                    if a.action=='collect':out=cloud.collect(home,a.evidence)
                    else:
                        data=snapshot.load(a.snapshot) if a.snapshot else maintenance.sync(home)
                        out=[cloud.submit(home,c) for c in data['cases'] if c['operation']=='retention']
        print(encoded(redact(out)))
    except (ValueError,OSError,KeyError) as e:
        print(encoded({'status':'blocked','error':str(e)}));raise SystemExit(2)
