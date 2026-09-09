import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from acceptance import report_view

class ReportView(unittest.TestCase):
    def test_assertions_keep_native_values_statuses_and_approval(self):
        values=[{'licenseBodiesEqual':True}, {'uploaded':None}, 'Cloud execution disabled', False, 0]
        statuses=['passed','failed','blocked','review','passed']
        assertions=[{'id':str(i),'actual':v,'expected':False,'status':s,'reviewStatus':'approved','role':'gate','featureId':'REN-R01'} for i,(v,s) in enumerate(zip(values,statuses))]
        questions=[{'caseId':'REN-R01-test','assertionIds':[a['id']],'answer':'fallback must not replace false','reviewStatus':'approved','review':{'actor':'test','digest':'reviewed-digest'}} for a in assertions]
        with tempfile.TemporaryDirectory() as d:
            rows=report_view.build_model(Path(d),{'results':[{'caseId':'REN-R01-test','assertions':assertions}]},questions)['rows']
        self.assertEqual([r['actual'] for r in rows],values)
        self.assertEqual([r['status'] for r in rows],statuses)
        self.assertEqual([r['comparison'] for r in rows],['matched','different','blocked','review','matched'])
        for r in rows:
            self.assertNotIn('targetObservation',r)
            self.assertEqual(r['approval'],'approved')
            self.assertEqual(r['answer']['answerDigest'],'reviewed-digest')
            self.assertIs(r['expected'],False)
            self.assertEqual(len(r['protocol']['criteria']),1)

if __name__=='__main__':unittest.main()
