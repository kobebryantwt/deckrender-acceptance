import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from acceptance import ci, execution, reporting, maintenance, cli, state, cleanup
from acceptance.common import atomic, digest, seal, read, sha, suite_root, locked


class Closure(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        cases=[];questions=[]
        for group,features in execution.GROUPS.items():
            cid='case-'+group
            checks=[{'id':n,'questionId':cid+'-'+n,'featureId':'REN-R%02d'%min(features),'role':'gate','expected':'ok'} for n in ['one','two']]
            cases.append({'id':cid,'source':{'uri':'/machine-a/source','sha256':cid},'covers':[checks[0]['featureId']],
                          'options':{},'facts':{},'operation':'render','evaluation':{'checks':checks}})
            questions.extend({'questionId':c['questionId']} for c in checks)
        self.data={'cases':cases,'questions':questions};self.manifest=execution.manifest(self.data)
        self.snapshot=self.root/'snapshot';atomic(self.snapshot/'SHA256SUMS.json',{'inputs':'dummy'})
    def tearDown(self):self.tmp.cleanup()
    def groups(self,mutate=None):
        for row in self.manifest['cases']:
            group=row['group'];folder=self.root/'incoming'/group
            (folder/'evidence'/row['id']).mkdir(parents=True)
            results=[{'caseId':row['id'],'inputSha256':row['sourceSha256'],'status':'passed',
                      'assertions':[{**c,'status':'passed'} for c in row['checks']]}]
            envelope={'group':group,'target':{'id':'fake'},'evaluator':{'id':'fake'},'qualityPolicyHash':'same',
                      'snapshotHash':sha(self.snapshot/'SHA256SUMS.json'),'executionManifest':self.manifest,
                      'executionContractHash':digest(self.manifest),'results':results,'suite':{'id':'fake'},'public':True}
            if mutate:mutate(envelope)
            atomic(folder/'run.json',envelope)
            atomic(folder/'questions.json',[q for q in self.data['questions'] if q['questionId'].startswith(row['id']+'-')]);seal(folder)
    def aggregate(self):
        with patch('acceptance.snapshot.load',return_value=self.data),patch.object(ci,'write_report') as write:
            result=ci.aggregate(self.root/'home',self.root/'incoming','test',self.snapshot)
            return result,write.call_args.args[1]
    def test_complete_groups_use_same_local_manifest(self):
        self.groups();result,e=self.aggregate()
        self.assertEqual(result['qualitySummary']['releaseDecision'],'PASS')
        self.assertEqual(e['executionContractHash'],digest(execution.manifest(self.data)))
    def test_debug_full_inventory_cannot_be_release_pass(self):
        self.groups(lambda e:e.update(executionMode='debug'))
        result,e=self.aggregate()
        self.assertEqual(result['qualitySummary']['scope'],'partial:debug')
        self.assertEqual(result['qualitySummary']['releaseDecision'],'INCOMPLETE')
    def test_mixed_modes_rejected(self):
        self.groups(lambda e:e.update(executionMode='debug' if e['group']=='cloud' else 'formal'))
        with self.assertRaisesRegex(ValueError,'Mixed execution modes'):self.aggregate()
    def test_missing_case_rejected(self):
        self.groups(lambda e:e['results'].clear() if e['group']=='local' else None)
        with self.assertRaisesRegex(ValueError,'cases'):self.aggregate()
    def test_missing_assertion_rejected(self):
        self.groups(lambda e:e['results'][0]['assertions'].pop())
        with self.assertRaisesRegex(ValueError,'assertions'):self.aggregate()
    def test_wrong_group_rejected(self):
        self.groups(lambda e:e['results'][0].update(caseId='wrong'))
        with self.assertRaisesRegex(ValueError,'cases'):self.aggregate()
    def test_mixed_snapshot_rejected(self):
        self.groups(lambda e:e.update(snapshotHash='another'))
        with self.assertRaisesRegex(ValueError,'snapshot'):self.aggregate()
    def test_changed_assertion_definition_rejected(self):
        self.groups(lambda e:e['results'][0]['assertions'][0].update(role='observation'))
        with self.assertRaisesRegex(ValueError,'definition'):self.aggregate()
    def test_duplicate_assertion_rejected(self):
        self.groups(lambda e:e['results'][0]['assertions'].append(e['results'][0]['assertions'][0]))
        with self.assertRaisesRegex(ValueError,'assertions'):self.aggregate()
    def test_portable_identity_retains_content_changes(self):
        a=copy.deepcopy(self.data);a['cases'][0]['facts']={'references':{'1':{'path':'/a/gt.png','sha256':'image'}}}
        b=copy.deepcopy(a);b['cases'][0]['source']['uri']='/other/input';b['cases'][0]['facts']['references']['1']['path']='/b/gt.png'
        self.assertEqual(execution.manifest(a),execution.manifest(b))
        b['cases'][0]['facts']['references']['1']['sha256']='changed'
        self.assertNotEqual(execution.manifest(a),execution.manifest(b))
    def public_run(self,batch,ident,body='report'):
        folder=self.root/batch/ident
        atomic(folder/'run.json',{'public':True,'runId':ident,'qualitySummary':{'releaseDecision':'PASS'}})
        atomic(folder/'report.html',body);seal(folder);return folder
    def test_history_index_survives_incremental_publish(self):
        self.public_run('first','old');reporting.publish(self.root/'first',self.root/'site')
        self.public_run('second','new');reporting.publish(self.root/'second',self.root/'site')
        text=(self.root/'site/index.html').read_text()
        self.assertIn('old/report.html',text);self.assertIn('new/report.html',text)
    def test_publish_conflict_keeps_original(self):
        self.public_run('first','same');reporting.publish(self.root/'first',self.root/'site')
        self.public_run('second','same','different')
        with self.assertRaisesRegex(ValueError,'conflict'):reporting.publish(self.root/'second',self.root/'site')
        self.assertEqual((self.root/'site/same/report.html').read_text(),'report')
    def test_home_suites_do_not_fall_back_to_shared_checkout(self):
        for name in ['a','b']:
            for sid in ['deckrender-release','deckrender-quality']:
                folder=suite_root(self.root/name)/sid
                atomic(folder/'suite.json',{'id':name});atomic(folder/'cases.jsonl','');atomic(folder/'questions.jsonl','')
        self.assertEqual(maintenance.load_suites(self.root/'a')[0][0]['id'],'a')
        self.assertEqual(maintenance.load_suites(self.root/'b')[0][0]['id'],'b')
    def test_prepare_changes_rebuild_but_noop_does_not(self):
        home=self.root/'home';home.mkdir();corpus={'sources':[]}
        def build(h):atomic(suite_root(h)/'deckrender-release/suite.json',{})
        with patch.object(cli.catalog,'import_sources',return_value=corpus),patch.object(cli.catalog,'build',side_effect=build) as b,patch.object(cli.maintenance,'refresh'),patch.object(cli.maintenance,'review_page',return_value={}):
            cli.prepare(home);cli.prepare(home);self.assertEqual(b.call_count,1)
            corpus['sources'].append({'sha256':'changed'});cli.prepare(home);self.assertEqual(b.call_count,2)
    def test_incomplete_retries_fail_is_not_pass(self):
        home=self.root/'home'
        with patch.object(state,'fingerprint',return_value='same'):
            state.check(home,{},self.data)
            envelope={'group':'all','runId':'fake','qualitySummary':{'scope':'complete','releaseDecision':'INCOMPLETE'}}
            state.record(home,envelope);self.assertTrue(state.check(home,{},self.data)['changed'])
            envelope['qualitySummary']['releaseDecision']='FAIL';state.record(home,envelope)
            self.assertFalse(state.check(home,{},self.data)['changed']);self.assertFalse((home/'last-passed.json').exists())
            self.assertTrue(state.check(home,{},self.data,force=True)['changed'])
    def test_cleanup_dry_run_and_protected_evidence(self):
        repo=self.root/'repo';cache=repo/'benchmark/acceptance/__pycache__';atomic(cache/'a.pyc','bytecode')
        protected=repo/'benchmark/artifacts/acceptance/gt/image.png';atomic(protected,'evidence')
        with patch.object(cleanup,'REPO',repo):
            self.assertEqual(len(cleanup.clean(self.root)['candidates']),1);self.assertTrue(cache.exists())
            cleanup.clean(self.root,True);self.assertFalse(cache.exists());self.assertTrue(protected.exists())
    def test_mutation_guard_rejects_overlapping_cli_writer(self):
        with locked(self.root):
            with self.assertRaises(ValueError):
                with locked(self.root):pass

if __name__=='__main__':unittest.main()
