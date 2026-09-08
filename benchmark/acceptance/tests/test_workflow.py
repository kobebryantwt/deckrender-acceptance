import copy,json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from acceptance.common import *
from acceptance import target, reporting, annotations, maintenance, runner

class FakePackage(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.package=self.root/'pkg';(self.package/'dist').mkdir(parents=True)
        atomic(self.package/'package.json',{'type':'module'})
        (self.package/'dist/cli.js').write_text('process.stderr.write(JSON.stringify({ok:false,error:{code:"unsupported_format",message:"not supported"}}));process.exitCode=2;')
        (self.package/'dist/index.js').write_text('export async function render(options) {throw Object.assign(new Error("unsupported"),{code:"unsupported_format"});}')
        self.source=self.root/'input.pptx';self.source.write_bytes(b'synthetic-fixture-not-a-document')
        self.case={'id':'fake','source':{'uri':str(self.source),'sha256':sha(self.source)},'format':'pptx','options':{'engine':'local','target':'image','interface':'cli'}}
    def tearDown(self):self.tmp.cleanup()
    def test_cli_error_is_stderr_json(self):
        with patch('acceptance.target.package_path',return_value=self.package):p=target.invoke(self.root,self.case,self.root/'cli-out')
        self.assertEqual(p['payload']['error']['code'],'unsupported_format');self.assertEqual(p['exitCode'],2)
    def test_sdk_keeps_code(self):
        self.case['options']['interface']='sdk'
        with patch('acceptance.target.package_path',return_value=self.package):p=target.invoke(self.root,self.case,self.root/'sdk-out')
        self.assertEqual(p['payload']['error']['code'],'unsupported_format')
    def test_cloud_disabled_before_execution(self):
        self.case['options']['engine']='cloud'
        with patch('acceptance.target.package_path',return_value=self.package),patch.dict(os.environ,{'REN_ALLOW_CLOUD':''}):p=target.invoke(self.root,self.case,self.root/'cloud-out')
        self.assertIn('disabled',p['blocked'])
    def test_auto_video_requires_cloud_authorization(self):
        self.case['options'].update(engine='auto',target='video')
        with patch('acceptance.target.package_path',return_value=self.package),patch.dict(os.environ,{'REN_ALLOW_CLOUD':''}):p=target.invoke(self.root,self.case,self.root/'video-out')
        self.assertIn('disabled',p['blocked'])
    def test_source_hash_change_blocks(self):
        self.source.write_bytes(b'changed')
        with patch('acceptance.target.package_path',return_value=self.package):p=target.invoke(self.root,self.case,self.root/'changed-out')
        self.assertIn('changed',p['blocked'])
    def test_missing_dependency_does_not_invent_cli_flags(self):
        with patch('acceptance.target.package_path',return_value=self.package):p=target.invoke(self.root,self.case,self.root/'dep-out',missing_dependency=True)
        self.assertNotIn('--executable-path',p['command']);self.assertNotIn('--office2html-path',p['command'])

class Approval(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.source=self.root/'a.pdf';self.source.write_bytes(b'a')
        ch={'id':'a','type':'schema','role':'gate','expected':'x','questionId':'q'}
        self.case={'id':'c','source':{'uri':str(self.source),'sha256':sha(self.source)},'format':'pdf','options':{},'facts':{},'evaluation':{'checks':[ch]}}
        self.q={'questionId':'q','answer':'x','reviewStatus':'draft'}
        answer={'id':'q','question':'x?','expected':'x','evidence':{'method':'handbook'},'check':{'case':copy.deepcopy(self.case),'definition':ch},'options':[],'requirement':'REN-R07'}
        sample={'id':'c','path':str(self.source),'sha256':sha(self.source),'format':'pdf','inputName':'a.pdf','private':False,'answers':[answer]}
        self.store=maintenance.Store(self.root/'db');self.project=self.store.import_bundle({'schemaVersion':1,'project':{'id':'test','samples':[sample]}})
    def tearDown(self):self.tmp.cleanup()
    def approved(self):
        s=self.project['samples'][0];a=s['answers'][0]
        return self.store.act('test',{'action':'review_answer','sampleId':'c','answerId':'q','revision':self.project['revision'],'actor':'unit-test-only','status':'approved','answerDigest':a['digest'],'confirm':True})
    def inputs(self,p):
        with patch('acceptance.maintenance.load_suites',return_value=([],[self.case],[self.q])):return maintenance.project_inputs(p)
    def test_import_never_approves(self):self.assertEqual(self.inputs(self.project)['cases'][0]['reviewStatus'],'draft')
    def test_explicit_approval(self):self.assertEqual(self.inputs(self.approved())['cases'][0]['reviewStatus'],'approved')
    def test_forged_status_is_not_approval(self):
        self.project['samples'][0]['answers'][0]['status']='approved';self.assertEqual(self.inputs(self.project)['cases'][0]['reviewStatus'],'draft')
    def test_check_changed_stales_approval(self):
        p=self.approved();self.case['options']['engine']='cloud';self.assertEqual(self.inputs(p)['cases'][0]['reviewStatus'],'draft')
    def test_fact_changed_stales_approval(self):
        p=self.approved();self.case['facts']['pages']=99;self.assertEqual(self.inputs(p)['cases'][0]['reviewStatus'],'draft')
    def test_source_changed_stales_approval(self):
        p=self.approved();Path(p['samples'][0]['path']).chmod(0o600);Path(p['samples'][0]['path']).write_bytes(b'changed');self.assertEqual(self.inputs(p)['cases'][0]['reviewStatus'],'draft')

class Reports(unittest.TestCase):
    def envelope(self):
        checks=[{'id':'fields','type':'schema','role':'gate','status':'failed','expected':'lifecycle present','actual':'missing','featureId':'REN-R07'}, {'id':'visual','type':'quality','role':'observation','status':'review','expected':'human review','actual':'pending','featureId':'REN-R09'}]
        results=[{'caseId':'REN-R07-fake','status':'failed','source':{'sha256':'abc'},'inputSha256':'abc','command':['fake-only'],'assertions':checks}]
        suite={'id':'demo','displayName':'框架自测（模拟目标）','profile':'render','qualityPolicy':{}}
        q=reporting.core.summarize_quality(results,[{'id':'REN-R07-fake','evaluation':{'checks':checks}}],suite,'command')
        return {'runId':'demo','createdAt':now(),'suite':suite,'target':{'id':'fake','displayName':'Synthetic target; not DeckRender results'},'evaluator':{'id':'test','version':'1','codeSha256':'x'},'results':results,'findings':reporting.core.build_findings(results,suite,{'id':'fake'},'demo'),'qualitySummary':q,'qualityPolicyHash':'x','executionContractHash':'x','counts':{'failed':1,'review':0,'passed':0,'blocked':0},'public':False,'group':'all'}
    def test_report_rebuild_and_evidence_links(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'run';reporting.write_report(root,self.envelope(),[])
            self.assertTrue((root/'agent-report.json').exists());verify(root)
            reporting.rebuild(root,Path(d)/'new');verify(Path(d)/'new')
    def test_incompatible_comparison_does_not_attribute(self):
        with tempfile.TemporaryDirectory() as d:
            b=self.envelope();a=copy.deepcopy(b);a['evaluator']['codeSha256']='changed'
            reporting.write_report(Path(d)/'before',b,[]);reporting.write_report(Path(d)/'after',a,[])
            self.assertFalse(reporting.compare(Path(d)/'before',Path(d)/'after',Path(d)/'comparison')['attributableToTarget'])
    def test_human_cannot_override_deterministic_failure(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'run';reporting.write_report(root,self.envelope(),[])
            f=Path(d)/'review.json';atomic(f,{'runSha256':sha(root/'run.json'),'actor':'unit-test','reviewedAt':now(),'reviews':[{'caseId':'REN-R07-fake','assertionId':'fields','status':'passed'}]})
            with self.assertRaises(ValueError):annotations.apply(root,f,Path(d)/'new')
    def test_private_report_not_published(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'runs/run';reporting.write_report(root,self.envelope(),[])
            self.assertEqual(reporting.publish(Path(d)/'runs',Path(d)/'site')['published'],0)

if __name__=='__main__':unittest.main()
