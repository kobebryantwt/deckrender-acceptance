import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from acceptance import target,runner,report_view
from acceptance.common import atomic

class EvidenceRegressions(unittest.TestCase):
    def test_warning_records_and_result(self):
        result={'ok':False,'error':{'code':'auth_error','message':'Payment required (402)'}}
        self.assertEqual(target.parse_cli_result('{"warning":"cloud route"}\n'+json.dumps(result)),result)
        for text in ['noise\n'+json.dumps(result),json.dumps(result)+'\n'+json.dumps(result)]:
            with self.assertRaises(ValueError):target.parse_cli_result(text)
    def test_blocked_access_does_not_fail_dependent_checks(self):
        proc={'exitCode':2,'payload':{'ok':False,'error':{'code':'auth_error','message':'Payment required (402)'}}}
        for op,keys in [('render',['outcome','artifacts']),('auto',['selection','warning','upload']),('quality',['integrity','visual'])]:
            with self.subTest(op=op),tempfile.TemporaryDirectory() as d:
                root=Path(d);e=root/'evidence';e.mkdir()
                case={'id':'test','operation':op,'format':'pptx','options':{'engine':'cloud','target':'image','expectedSupport':True},'evaluation':{'checks':[]}}
                with patch.object(target,'invoke',return_value=proc),patch('acceptance.gt_contract.readiness',return_value={'ready':True}),patch.object(runner.ev,'declared_outcome',return_value=('blocked',proc['payload']['error'])):
                    out=runner.check_case(root,case,e,root,{})
                for key in keys:self.assertEqual(out[key][0],'blocked')
                self.assertEqual(out['commonSchema'][0],'passed')
    def test_evidence_directories_expand_to_real_files(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);atomic(root/'raw/case.json',{'assertions':[]});atomic(root/'evidence/case/target.json',{'payload':{'ok':True}})
            case={'caseId':'case','evidence':['evidence/case'],'assertions':[{'id':'test','status':'passed','actual':True}]}
            model=report_view.build_model(root,{'results':[case]},[])
            self.assertEqual(model['rows'][0]['evidence'],['raw/case.json','evidence/case/target.json'])
            self.assertEqual(model['evidence']['evidence/case/target.json']['payload'],{'ok':True})

if __name__=='__main__':unittest.main()
