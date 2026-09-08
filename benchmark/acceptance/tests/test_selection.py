import copy,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from acceptance import catalog,coverage,maintenance,purposes,target
from acceptance.common import atomic,read,sha

class Selection(unittest.TestCase):
    def inputs(self):
        _,cases,questions=maintenance.load_suites()
        return {'cases':cases,'questions':questions}
    def test_matrix_complete_no_duplicate_inflation(self):
        value=self.inputs();a=coverage.build({'sources':[]},value)
        self.assertEqual(len(a['matrix']),54)
        self.assertTrue(all(x['planned'] for x in a['matrix']))
        self.assertEqual(sum(x['qualityRequired'] for x in a['matrix']),30)
        self.assertTrue(all(x['qualityCaseIds'] for x in a['matrix'] if x['qualityRequired']))
        value['cases']*=2;b=coverage.build({'sources':[]},value)
        self.assertEqual(a['matrix'],b['matrix']);self.assertEqual(a['cases'],b['cases'])
    def test_missing_cell_is_visible(self):
        value=self.inputs();c=next(c for c in value['cases'] if c['operation']=='render')
        value['cases']=[x for x in value['cases'] if x['id']!=c['id']]
        self.assertEqual(sum(not x['planned'] for x in coverage.build({'sources':[]},value)['matrix']),1)
        declaration={':'.join([c['options']['engine'],c['format'],c['options']['target']]):True}
        rows=coverage.build({'sources':[]},value,declaration)['matrix']
        self.assertTrue(next(r for r in rows if not r['planned'])['qualityRequired'])
    def test_purposes_and_stable_common_rule(self):
        value=self.inputs();common=[]
        for c in value['cases']:
            self.assertTrue(c['purpose']['summary'])
            self.assertEqual({q for x in c['purpose']['checks'] for q in x['answerIds']},{x['questionId'] for x in c['evaluation']['checks']})
            common.extend(x['ruleId'] for x in c['evaluation']['checks'] if x['id']=='commonSchema')
            if c['operation']=='render':self.assertIn(c['options']['expectedSupport'],[True,False,None]);self.assertNotIsInstance(c['options']['expectedSupport'],str)
        self.assertEqual(set(common),{'response.commonSchema.v3'})
        self.assertEqual(sum(c['operation']=='schema' for c in value['cases']),2)
        self.assertEqual(sum(c['operation']=='quality' and not c['options'].get('variantId') for c in value['cases']),46)
    def test_declared_features_are_not_independent_evidence(self):
        src={'id':'pptx_math_formulas','sha256':'h','features':['special-elements']}
        value=coverage.build({'sources':[src]},self.inputs())
        rows=[r for r in value['difficulty'] if r['axis']=='special-elements']
        self.assertTrue(all(src['id'] in r['plannedSourceIds'] for r in rows))
        self.assertTrue(all(not r['independentlyObservedSourceIds'] for r in rows))
    def test_import_preserves_only_same_hash_facts_and_removes_retired(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);src=root/'sources';src.mkdir();f=src/'sample.pdf';f.write_bytes(b'a')
            (src/'manifest.tsv').write_text('filename\tlicense\torigin\tdifficulty_axes\tdescription\nsample.pdf\tCC0\tgenerated\tfonts\t测试用途\n')
            with patch('acceptance.catalog.fixtures',return_value=[]):
                v=catalog.import_sources(root,src);v['sources'][0]['facts']={'references':{'1':'preserved'}};atomic(root/'corpus.json',v)
                v=catalog.import_sources(root,src);self.assertEqual(v['sources'][0]['description'],'测试用途');self.assertTrue(v['sources'][0]['facts']['references'])
                f.write_bytes(b'b');v=catalog.import_sources(root,src);self.assertEqual(v['sources'][0]['facts'],{})
                f.unlink();self.assertEqual(catalog.import_sources(root,src)['sources'],[])
    def test_inactive_does_not_keep_stale_question_approval(self):
        try:
            from test_workflow import Approval
        except ImportError:
            from .test_workflow import Approval
        fixture=Approval();fixture.setUp()
        try:
            p=fixture.approved();p['samples'][0]['active']=False;fixture.q['reviewStatus']='approved'
            self.assertEqual(fixture.inputs(p)['questions'][0]['reviewStatus'],'draft')
        finally:fixture.tearDown()

if __name__=='__main__':unittest.main()
