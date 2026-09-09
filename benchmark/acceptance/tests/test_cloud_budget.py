import copy,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from acceptance.cloud_budget import Session
from acceptance import evaluation
from acceptance.common import atomic

class CloudBudget(unittest.TestCase):
    def case(self,cid='matrix',interface='cli',profile=None):
        o={'engine':'cloud','target':'image','interface':interface}
        if profile:o['credentialVariant']=profile
        return {'id':cid,'operation':'render','format':'pptx','source':{'sha256':'abc'},'facts':{'pages':3},'options':o}
    def success(self,home,case,out,**flags):
        atomic(Path(out)/'artifacts/page.png','synthetic')
        return {'exitCode':0,'stdout':'raw','stderr':'','payload':{'ok':True,'outputs':[{'file':str(Path(out)/'artifacts/page.png')}]},'artifactsDir':str(Path(out)/'artifacts')}
    def test_reuse_and_distinct_interfaces(self):
        c=self.case();q=self.case('quality');q['operation']='quality';sdk=self.case('sdk','sdk')
        s=Session([c,q,sdk],cloud_enabled=True)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            one=s.invoke(self.success,root,c,root/'one');two=s.invoke(self.success,root,q,root/'two')
            self.assertEqual(one['executionRef'],two['executionRef']);self.assertEqual(one['payload'],two['payload'])
            self.assertTrue((root/'two/artifacts/page.png').exists())
            three=s.invoke(self.success,root,sdk,root/'three')
            self.assertNotEqual(one['executionRef'],three['executionRef']);self.assertEqual(s.calls,2)
    def test_missing_and_null_parameters_do_not_share_calls(self):
        c=self.case();other=self.case('explicit-null');other['options']['pages']=None
        s=Session([c,other],cloud_enabled=True)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);s.invoke(self.success,root,c,root/'one');s.invoke(self.success,root,other,root/'two')
            self.assertEqual(s.calls,2)
    def test_malformed_payload_remains_available_to_schema_evaluator(self):
        c=self.case();s=Session([c],cloud_enabled=True)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            result=s.invoke(lambda *a,**kw:{'exitCode':0,'payload':[]},root,c,root/'one')
            self.assertEqual(result['payload'],[])
    def test_payment_circuit_preserves_second_account(self):
        c=self.case();second=self.case('second',profile='exhausted_quota')
        s=Session([c,second],cloud_enabled=True)
        def payment(*args,**kw):return {'exitCode':2,'payload':{'ok':False,'error':{'code':'auth_error','message':'402'}}}
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);s.invoke(payment,root,c,root/'one')
            self.assertIn('circuit',s.invoke(payment,root,c,root/'two')['blocked'])
            self.assertEqual(s.invoke(payment,root,second,root/'three')['exitCode'],2)
            self.assertEqual(s.calls,2)
    def test_debug_unknown_pages_and_limits(self):
        c=self.case()
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for s,reason in [(Session([c],mode='debug',cloud_enabled=True),'selection'),(Session([c],cloud_enabled=True,max_calls=0),'budget'),(Session([c],cloud_enabled=True,max_pages=2),'budget')]:
                self.assertIn(reason,s.invoke(self.success,root,c,root/'out')['blocked']);self.assertEqual(s.calls,0)
            c['facts']={};s=Session([c],cloud_enabled=True)
            self.assertIn('unknown',s.invoke(self.success,root,c,root/'unknown')['blocked'])
    def test_stability_repeats_not_cached_and_tampering_blocked(self):
        c=self.case();c['operation']='schema';s=Session([c],cloud_enabled=True)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            s.invoke(self.success,root,c,root/'one',invalid=True);s.invoke(self.success,root,c,root/'two',invalid=True)
            self.assertEqual(s.calls,2)
            c['operation']='render';s=Session([c],cloud_enabled=True)
            s.invoke(self.success,root,c,root/'cached')
            (root/'cached/artifacts/page.png').write_text('tampered')
            self.assertIn('changed',s.invoke(self.success,root,c,root/'reuse')['blocked'])
    def test_usage_error_uses_reviewed_error_contract(self):
        with tempfile.TemporaryDirectory() as d:
            proc={'exitCode':2,'payload':{'ok':False,'error':{'code':'usage_error'}},'artifactsDir':d}
            contract={'status':'declared','supported':False,'errorCodes':['usage_error']}
            self.assertEqual(evaluation.declared_outcome(proc,contract)[0],'passed')
            proc['payload']['error']['code']='unsupported_format'
            self.assertEqual(evaluation.declared_outcome(proc,contract)[0],'failed')

if __name__=='__main__':unittest.main()
