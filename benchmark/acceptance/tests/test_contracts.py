import copy, datetime as dt, io, json, os, sys, tarfile, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from acceptance.common import *
from acceptance import evaluation as ev, cloud, snapshot, reporting, releases
from acceptance.maintenance import Store, PROJECT, project_inputs

class Contracts(unittest.TestCase):
    def test_schema_missing_fields(self):
        status,errors=ev.schema({'payload':{'engine':'local','route':[],'outputs':[],'pages':1}})
        self.assertEqual(status,'failed');self.assertIn('Missing/invalid lifecycle',errors)
    def test_schema_complete(self):
        self.assertEqual(ev.schema({'payload':{'engine':'local','route':['capture'],'outputs':[{'page':1,'file':'page.png'}],'pages':1,'caveat':None,'lifecycle':{}}})[0],'passed')
    def test_schema_wrong_route(self):
        self.assertEqual(ev.schema({'payload':{'engine':'local','route':[1],'outputs':[],'pages':1,'caveat':None,'lifecycle':{}}})[0],'failed')
    def test_launch_blocked(self):self.assertEqual(ev.outcome({'launchError':True})[0],'blocked')
    def test_unknown_support_review(self):self.assertEqual(ev.outcome({},None)[0],'review')
    def test_false_success_fails(self):self.assertEqual(ev.outcome({'payload':{'ok':True},'exitCode':1})[0],'failed')
    def test_matrix_sections(self):
        m=ev.declaration_matrix('## Cloud\n| `.pptx` | ✅ | ✅ | ✅ |\n## Local\n| `.pptx` | ✅ | ✅ | — |')
        self.assertTrue(m['cloud:pptx:video']);self.assertFalse(m['local:pptx:video'])
    def test_privacy_monitor_missing(self):
        with tempfile.TemporaryDirectory() as d:self.assertEqual(ev.privacy_evidence({},d)['network'][0],'blocked')
    def test_privacy_violation(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d,'system.trace').write_text('1 connect(3, {sa_family=AF_INET, sin_addr=inet_addr("8.8.8.8")}, 16) = -1\n2 openat(1, "/tmp/.deckflow/credentials", O_RDONLY) = 5')
            result=ev.privacy_evidence({'payload':{'engine':'cloud'},'exitCode':0},d)
            self.assertEqual([result[k][0] for k in ['network','credentials','local']],['failed']*3)
    def test_env_credential_reads(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d,'system.trace').write_text('1 openat(1,"input.pdf",O_RDONLY)=1')
            Path(d,'credentials.jsonl').write_text('{"event":"env-read","key":"DECKRENDER_API_KEY"}\n')
            self.assertEqual(ev.privacy_evidence({},d)['credentials'][0],'failed')
    def test_artifact_decode_and_order(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.png';Image.new('RGB',(10,10)).save(p)
            proc={'artifactsDir':d,'payload':{'format':'image','pages':2,'outputs':[{'page':2,'file':str(p)},{'page':1,'file':str(p)}]}}
            self.assertEqual(ev.artifact_checks(proc,{'pages':2})[0],'failed')
    def test_corrupt_artifact(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.png';p.write_bytes(b'not an image')
            self.assertEqual(ev.artifact_checks({'artifactsDir':d,'payload':{'outputs':[{'page':1,'file':str(p)}]}},{})[0],'failed')
    def test_artifact_escape(self):
        self.assertEqual(ev.artifact_checks({'artifactsDir':'/tmp/expected','payload':{'outputs':[{'page':1,'file':'/etc/passwd'}]}},{})[0],'failed')
    def test_seal_tampering(self):
        with tempfile.TemporaryDirectory() as d:
            atomic(Path(d)/'a',{});seal(d);verify(d);atomic(Path(d)/'a',{'x':1})
            with self.assertRaises(ValueError):verify(d)
    def test_extra_file_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            atomic(Path(d)/'a',{});seal(d);atomic(Path(d)/'extra',{})
            with self.assertRaises(ValueError):verify(d)
    def test_path_escape_rejected(self):
        with self.assertRaises(ValueError):inside('/tmp/a','../b')
    def test_archive_traversal(self):
        b=io.BytesIO()
        with tarfile.open(fileobj=b,mode='w:gz') as tf:
            t=tarfile.TarInfo('../escape');t.size=1;tf.addfile(t,io.BytesIO(b'x'))
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):releases.extract(b.getvalue(),d)
    def test_redaction(self):
        with patch.dict(os.environ,{'TEST_API_KEY':'super-secret-123'}):
            r=redact({'token':'a','url':'https://a/b?signature=secret','stdout':'super-secret-123'})
        self.assertNotIn('super-secret',encoded(r));self.assertNotIn('signature=',encoded(r));self.assertEqual(r['token'],'[REDACTED]')
    def test_fail_not_masked_by_blocked(self):
        cases=[{'id':'c','evaluation':{'checks':[{'id':'a','role':'gate'},{'id':'b','role':'gate'}]}}]
        result=[{'caseId':'c','status':'failed','assertions':[{'id':'a','role':'gate','status':'failed'},{'id':'b','role':'gate','status':'blocked'}]}]
        q=reporting.core.summarize_quality(result,cases,{},'command')
        self.assertEqual(q['releaseDecision'],'FAIL');self.assertEqual(q['gate']['blocked'],1)
    def test_gate_review_not_pass(self):
        cases=[{'id':'c','evaluation':{'checks':[{'id':'a','role':'gate'}]}}]
        result=[{'caseId':'c','status':'review','assertions':[{'id':'a','role':'gate','status':'review'}]}]
        self.assertEqual(reporting.core.summarize_quality(result,cases,{},'command')['releaseDecision'],'REVIEW')

class Retention(unittest.TestCase):
    def setUp(self):
        self.start=dt.datetime(2026,1,1,tzinfo=dt.timezone.utc);self.end=self.start+dt.timedelta(hours=1)
        self.sub={'taskId':'task-1','sourceSha256':'abc','requestedHours':None,'effectiveHours':1,'createdAt':self.start.isoformat(),'expiresAt':self.end.isoformat(),'objects':[{'kind':k,'id':k+'-1'} for k in sorted(cloud.KINDS)]}
        self.e={'sourceSha256':'abc','submission':self.sub}
        self.audit={'taskId':'task-1','sourceSha256':'abc','authority':'independent audit','auditId':'log-1','checkedAt':(self.end+dt.timedelta(minutes=1)).isoformat(),'objects':[{**o,'state':'deleted','deletionLogId':o['id'],'deletedAt':self.end.isoformat()} for o in self.sub['objects']]}
        self.at=self.end+dt.timedelta(minutes=2)
    def test_submission_default(self):self.assertEqual(cloud.validate_submission(self.sub,None,'abc'),self.sub)
    def test_retention_changed_rejected(self):
        self.sub['effectiveHours']=99
        with self.assertRaises(ValueError):cloud.validate_submission(self.sub,None,'abc')
    def test_complete_deletion(self):self.assertEqual(cloud.evaluate_audit(self.e,self.audit,self.at)[0],'passed')
    def test_before_deadline(self):self.assertEqual(cloud.evaluate_audit(self.e,self.audit,self.start)[0],'blocked')
    def test_404_not_deletion(self):
        self.audit['objects'][0]['state']='404';self.assertEqual(cloud.evaluate_audit(self.e,self.audit,self.at)[0],'blocked')
    def test_missing_objects(self):
        self.audit['objects'].pop();self.assertEqual(cloud.evaluate_audit(self.e,self.audit,self.at)[0],'blocked')
    def test_retained_failed(self):
        self.audit['objects'][0]['state']='retained';self.assertEqual(cloud.evaluate_audit(self.e,self.audit,self.at)[0],'failed')
    def test_late_deleted_failed(self):
        self.audit['objects'][0]['deletedAt']=(self.end+dt.timedelta(seconds=1)).isoformat();self.assertEqual(cloud.evaluate_audit(self.e,self.audit,self.at)[0],'failed')
    def test_wrong_task(self):
        self.audit['taskId']='another';self.assertEqual(cloud.evaluate_audit(self.e,self.audit,self.at)[0],'blocked')
    def test_resume_does_not_resubmit(self):
        case={'id':'c','source':{'sha256':'x'},'options':{'retentionHours':1},'reviewStatus':'draft'}
        with tempfile.TemporaryDirectory() as d:
            a=cloud.submit(d,case)
            with patch('acceptance.cloud.provider',side_effect=AssertionError('Must not resubmit')):self.assertEqual(cloud.submit(d,case),a)

class Snapshots(unittest.TestCase):
    def data(self,folder,approved=False,public=True):
        p=Path(folder)/'source.pdf';p.write_bytes(b'source')
        return {'suites':[],'cases':[{'id':'c','source':{'uri':str(p),'sha256':sha(p)},'public':public,'reviewStatus':'approved' if approved else 'draft'}],'questions':[{'questionId':'q','reviewStatus':'approved' if approved else 'draft','review':{'actor':'test-fixture-only'}}]}
    def test_draft_has_no_ready(self):
        with tempfile.TemporaryDirectory() as d:
            with patch('acceptance.snapshot.sync',return_value=self.data(d)):
                dest=Path(d)/'out';snapshot.export(d,dest,True)
                self.assertFalse((dest/'READY').exists())
                with self.assertRaises(ValueError):snapshot.validate(dest)
    def test_approved_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            with patch('acceptance.snapshot.sync',return_value=self.data(d,True)):
                dest=Path(d)/'out';snapshot.export(d,dest);snapshot.validate(dest)
    def test_private_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with patch('acceptance.snapshot.sync',return_value=self.data(d,True,False)):
                with self.assertRaises(ValueError):snapshot.export(d,Path(d)/'out')
    def test_source_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            data=self.data(d,True);Path(data['cases'][0]['source']['uri']).write_bytes(b'changed')
            with patch('acceptance.snapshot.sync',return_value=data):
                with self.assertRaises(ValueError):snapshot.export(d,Path(d)/'out')

if __name__=='__main__':unittest.main()
