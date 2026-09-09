import copy,json,sys,tempfile,unittest,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from acceptance import previews,quality,evaluation as ev,workbench,difficulty
from acceptance.common import sha,atomic,process,REPO

class VisualV2(unittest.TestCase):
    def test_report_page_selection_preserves_images_and_seal(self):
        from acceptance import reporting
        from acceptance.common import verify, read
        from test_workflow import Reports
        from unittest.mock import patch
        from PIL import Image
        for selection in ['1', '3,1', '1-3', None]:
            with self.subTest(selection=selection), tempfile.TemporaryDirectory() as d:
                root=Path(d);run=root/'run';cid='REN-R09-selection'
                image=run/'evidence'/cid/'previews'/'page.png'
                image.parent.mkdir(parents=True)
                Image.new('RGB',(30,20),'blue').save(image)
                options={'target':'image','engine':'local','interface':'cli','pages':selection}
                metrics=[{'image':str(image),'imageSha256':sha(image),'mapping':{'sourcePage':3}}]
                envelope=Reports().envelope()
                envelope['results']=[{'caseId':cid,'inputSha256':'synthetic','status':'review','options':options,
                    'assertions':[{'id':'visual','type':'quality','role':'observation','status':'review','featureId':'REN-R09',
                        'actual':{'options':options,'sourceFormat':'pdf','metrics':metrics}}]}]
                with patch.object(workbench,'write',wraps=workbench.write) as writer:
                    reporting.write_report(run,envelope,[])
                    item=writer.call_args.args[1][0]
                    self.assertEqual(item['pages'],metrics)
                    self.assertEqual(item['options'],options)
                    self.assertEqual(item['pageSelection'],selection)
                self.assertIn('data:image/png;base64,',(run/'visual.html').read_text())
                self.assertEqual(read(run/'run.json')['results'][0]['options'],options)
                verify(run)
                reporting.rebuild(run,root/'rebuilt')
                verify(root/'rebuilt')
                self.assertIn('data:image/png;base64,',(root/'rebuilt/visual.html').read_text())

    def test_pdf_every_page_and_binding(self):
        import fitz
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=root/'source.pdf';doc=fitz.open()
            for i in range(3):doc.new_page().insert_text((40,50),f'Page {i+1}')
            doc.save(p);doc.close()
            rows=previews.extract(p,root/'previews',1)
            self.assertEqual([r['mapping']['pdfPage'] for r in rows],[1,2,3])
            self.assertTrue(all(r['artifactSha256']==sha(p) for r in rows))
            c={'id':'test','source':{'sha256':sha(p)},'options':{'target':'pdf'},'facts':{}}
            out=quality.inspect({'payload':{'outputs':[{'page':1,'file':str(p)}]},'artifactsDir':d},c,root/'evidence')
            self.assertEqual(out['status'],'blocked');self.assertFalse(out['gtReadiness']['ready']);self.assertEqual(len(out['metrics']),3)
            workbench.write(root/'visual.html',[{'caseId':'test','sourceSha256':sha(p),'pages':rows}],'test')
            self.assertIn('data:image/png;base64,',(root/'visual.html').read_text())
            rows[0]['imageSha256']='forged'
            with self.assertRaises(ValueError):workbench.write(root/'bad.html',[{'pages':rows}],'test')
    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'ffmpeg required')
    def test_video_samples_are_not_page_numbers(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=root/'test.mp4'
            result=process(['ffmpeg','-v','error','-f','lavfi','-i','color=c=blue:s=64x64:d=2','-y',str(p)])
            self.assertEqual(result['exitCode'],0)
            rows=previews.extract(p,root/'frames',1)
            self.assertEqual(len(rows),5);self.assertTrue(all(r['mapping']['sourcePage'] is None for r in rows))
            self.assertEqual([r['mapping']['timestampSeconds'] for r in rows],sorted(r['mapping']['timestampSeconds'] for r in rows))
    def test_common_success_error_and_boolean_boundary(self):
        good={'exitCode':0,'payload':{'ok':True,'input':'source','format':'pdf','engine':'local','route':['pdf'],'pages':1,'durationMs':0,'outputs':[{'page':1,'file':'a.pdf'}],'caveat':None,'lifecycle':{}}}
        self.assertEqual(ev.common_schema(good)[0],'passed')
        bad=copy.deepcopy(good);bad['payload']['pages']=True;self.assertEqual(ev.common_schema(bad)[0],'failed')
        bad=copy.deepcopy(good);bad['payload'].pop('lifecycle');self.assertEqual(ev.common_schema(bad)[0],'failed')
        bad=copy.deepcopy(good);bad['payload']['outputs']*=2;self.assertEqual(ev.common_schema(bad)[0],'failed')
        self.assertEqual(ev.common_schema({'exitCode':2,'payload':{'ok':False,'error':{'code':'unsupported','message':'no'}}})[0],'passed')
        self.assertEqual(ev.common_schema({'exitCode':0,'payload':{'ok':False,'error':{'code':'unsupported','message':'no'}}})[0],'failed')
        self.assertEqual(ev.common_schema({'blocked':'cloud not configured'})[0],'blocked')
    def test_parity_does_not_compare_task_identity(self):
        a={'payload':{'ok':True,'lifecycle':{'task':'a'}}};b=copy.deepcopy(a);b['payload']['lifecycle']['task']='b'
        self.assertEqual(ev.parity(a,b)[0],'passed');b['payload']['engine']='cloud';self.assertEqual(ev.parity(a,b)[0],'failed')
    def test_all_render_cases_have_common_gate_and_matrix_mapping(self):
        for suite in ['deckrender-release','deckrender-quality']:
            cases=[json.loads(l) for l in (REPO/'benchmark/suites'/suite/'cases.jsonl').read_text().splitlines()]
            for c in cases:
                if c['operation'] in ['render','quality']:
                    self.assertTrue(any(x['id']=='commonSchema' and x['role']=='gate' for x in c['evaluation']['checks']))
                if c['operation']=='render' and c['options']['expectedSupport'] is True:self.assertTrue(c['qualityCaseId'])
    def test_unreviewed_gt_export_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);atomic(root/'gt-manifest.json',{'items':[]});atomic(root/'corpus.json',{'sources':[]});atomic(root/'review.json',{'kind':'visual-review-draft','mode':'gt','actor':'','reviews':[]})
            with self.assertRaises(ValueError):previews.apply_draft(root,root/'review.json')
    def test_source_structure_is_not_visual_truth(self):
        p=REPO/'benchmark/fixtures/markers.pptx'
        value=difficulty.inspect({'path':str(p),'sha256':sha(p),'format':'pptx'})
        self.assertEqual(value['facts']['pages'],3)
        self.assertIn('charts',value['features']);self.assertIn('draft',value['visualTruth'])
        self.assertTrue(all(e.get('location') for e in value['evidence']))
    def test_result_review_rejects_different_run(self):
        from acceptance import annotations,reporting
        from test_workflow import Reports
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);run=root/'run';reporting.write_report(run,Reports().envelope(),[])
            file=root/'draft.json';atomic(file,{'kind':'visual-review-draft','mode':'result','actor':'test only','runSha256':'wrong','reviews':[{}]})
            with self.assertRaisesRegex(ValueError,'different run'):annotations.apply_visual(run,file,root/'new')
    def test_complete_visual_review_and_missing_page(self):
        from acceptance import annotations,reporting
        from test_workflow import Reports
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);run=root/'run';cid='REN-R09-fake';folder=run/'evidence'/cid;folder.mkdir(parents=True)
            p=folder/'image.png';Image.new('RGB',(30,20),'blue').save(p)
            c={'id':cid,'source':{'sha256':'source-hash'},'options':{'target':'image'},'facts':{}}
            visual=quality.inspect({'payload':{'outputs':[{'page':1,'file':str(p)}]},'artifactsDir':str(folder)},c,folder)
            e=Reports().envelope();e['results']=[{'caseId':cid,'inputSha256':'source-hash','status':'review','assertions':[{'id':'visual','type':'quality','role':'observation','status':'review','actual':visual,'featureId':'REN-R09'}]}]
            reporting.write_report(run,e,[]);m=visual['metrics'][0]
            row={'caseId':cid,'sourceSha256':'source-hash','actualSha256':m['imageSha256'],'page':m['mapping'],'referenceSha256':None,
                 'rubric':{k:'符合' for k in ['文字','裁切','重叠','图表','层级','可读性']},'note':'Synthetic unit test, not product evidence'}
            value={'kind':'visual-review-draft','mode':'result','runSha256':sha(run/'run.json'),'actor':'unit-test-only','createdAt':'2026-09-08T00:00:00Z','reviews':[row]}
            file=root/'review.json';atomic(file,value)
            annotations.apply_visual(run,file,root/'reviewed')
            self.assertTrue((root/'reviewed/report.html').exists())
            value['reviews']=[row,row];atomic(file,value)
            with self.assertRaisesRegex(ValueError,'every recorded'):annotations.apply_visual(run,file,root/'invalid')

if __name__=='__main__':unittest.main()
