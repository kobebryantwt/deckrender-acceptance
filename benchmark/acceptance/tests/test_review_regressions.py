"""Adversarial probes from the scope/GT audit; all targets and approvals are synthetic."""
import copy,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from acceptance import maintenance,runner,evaluation as ev,gt_contract,snapshot,quality,source_preview,catalog
from acceptance.common import *

class ReviewRegressions(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def quality_case(self):
        from PIL import Image
        source=self.root/'source.pdf';source.write_bytes(b'synthetic source identity only')
        image=self.root/'ref.png';Image.new('RGB',(500,400),'blue').save(image)
        ref={'path':str(image),'sha256':sha(image),'sourceSha256':sha(source),'status':'approved','public':True,'provenance':{'method':'synthetic test'},'review':{'actor':'unit-test'}}
        return {'id':'fake','source':{'uri':str(source),'sha256':sha(source)},'operation':'quality','format':'pdf','reviewStatus':'approved','public':True,'options':{'target':'image'},'facts':{'pages':1,'references':{'1':ref}},'evaluation':{'checks':[{'id':'visual'}]}}
    def response(self):return {'exitCode':0,'payload':{'ok':True,'engine':'local','format':'image','route':['local.pdfjs'],'caveat':None,'pages':1}}
    def contract(self):return {'status':'declared','supported':True,'engine':'local','format':'image','route':['local.pdfjs'],'caveat':None,'reportedPages':1}
    def test_contract_checks_values_not_only_shape(self):
        p=self.response();c=self.contract();self.assertEqual(ev.declared_outcome(p,c)[0],'passed')
        for field,value in [('route',['wrong']),('engine','cloud'),('format','pdf'),('caveat','hidden caveat'),('pages',2)]:
            bad=copy.deepcopy(p);bad['payload'][field]=value;self.assertEqual(ev.declared_outcome(bad,c)[0],'failed',field)
        self.assertEqual(ev.declared_outcome(p,{'status':'unresolved'})[0],'blocked')
    def test_planned_error_code_is_exact(self):
        p={'exitCode':2,'payload':{'ok':False,'error':{'code':'unsupported_format','message':'no'}},'artifactsDir':str(self.root/'empty')}
        c={'status':'declared','supported':False,'errorCodes':['not_implemented']}
        self.assertEqual(ev.declared_outcome(p,c)[0],'failed')
        p['payload']['error']['code']='not_implemented';self.assertEqual(ev.declared_outcome(p,c)[0],'passed')
    def test_pdf_page_count_not_file_count(self):
        import fitz
        path=self.root/'three.pdf';doc=fitz.open()
        for _ in range(3):doc.new_page()
        doc.save(path);doc.close()
        p={'payload':{'format':'pdf','engine':'passthrough','pages':1,'outputs':[{'page':1,'file':str(path)}]},'artifactsDir':str(self.root)}
        self.assertEqual(ev.declared_artifacts(p,{'pages':3},{'outputCount':1})[0],'passed')
        p['payload']['engine']='cloud'
        self.assertEqual(ev.declared_artifacts(p,{'pages':3},{'outputCount':1})[0],'passed')
        p['payload']['outputs'].append({'page':2,'file':str(path)})
        self.assertEqual(ev.declared_artifacts(p,{'pages':3},{'outputCount':1})[0],'failed')
    def test_no_filename_page_oracle(self):
        text=catalog.describe_check('render','artifacts',{'id':'planning-55','facts':{}},{},'default')
        self.assertIn('未知',text);self.assertNotIn('55',text)
    def test_privacy_group_and_evaluator_are_not_empty(self):
        cases=maintenance.load_suites()[1]
        privacy=[c for c in cases if int(c['covers'][0][-2:]) in runner.GROUPS['privacy']]
        self.assertEqual(len(privacy),8);self.assertEqual({c['options']['interface'] for c in privacy},{'cli','sdk'})
        proc={'exitCode':0,'payload':{}}
        with patch.object(runner.target,'invoke',return_value=proc),patch.object(runner.ev,'privacy_evidence',return_value={k:('failed','synthetic violation') for k in ['network','credentials','local']}) as check:
            results=runner.check_case(self.root,privacy[0],self.root,self.root,{})
        check.assert_called_once();self.assertTrue(all(results[k][0]=='failed' for k in ['network','credentials','local']))
        groups=[runner.GROUPS[k] for k in ['release','local','privacy','cloud','quality']]
        self.assertTrue(all(sum(int(c['covers'][0][-2:]) in g for g in groups)==1 for c in cases))
    def test_sdk_has_full_matrix_and_auto(self):
        cases=maintenance.load_suites()[1]
        for op in ['render','planned','auto']:
            project=lambda i:{(c['format'],c['options']['engine'],c['options']['target']) for c in cases if c['operation']==op and c['options']['interface']==i}
            self.assertEqual(project('cli'),project('sdk'));self.assertTrue(project('sdk'))
    def test_gt_requires_complete_reviewed_unchanged_pages(self):
        c=self.quality_case();self.assertTrue(gt_contract.readiness(c)['ready'])
        for mutate in [lambda x:x['facts'].update(pages=2),lambda x:x['facts']['references']['1'].update(status='draft'),lambda x:x['facts']['references']['1'].update(sourceSha256='wrong')]:
            bad=copy.deepcopy(c);mutate(bad);self.assertFalse(gt_contract.readiness(bad)['ready'])
        Path(c['facts']['references']['1']['path']).write_bytes(b'tampered');self.assertFalse(gt_contract.readiness(c)['ready'])
    def test_video_requires_reviewed_temporal_mapping(self):
        c=self.quality_case();c['options']['target']='video';self.assertFalse(gt_contract.readiness(c)['ready'])
        c['facts']['videoReferenceFrames']=[{'fraction':f,'sourcePage':1,'sourceSha256':c['source']['sha256'],'review':{'actor':'unit-test'}} for f in gt_contract.FRACTIONS]
        self.assertTrue(gt_contract.readiness(c)['ready'])
    def test_missing_gt_blocks_before_target_invocation(self):
        c=self.quality_case();c['facts']['references']={}
        with patch.object(runner.target,'invoke') as invoke:
            out=runner.check_case(self.root,c,self.root,self.root,{})
        invoke.assert_not_called();self.assertEqual(out['visual'][0],'blocked')
    def test_ready_requires_gt_even_if_text_approved(self):
        c=self.quality_case();data={'suites':[],'cases':[c],'questions':[{'reviewStatus':'approved','review':{'actor':'unit-test'}}]}
        with patch.object(snapshot,'sync',return_value=data):
            self.assertTrue(snapshot.export(self.root,self.root/'valid')['ok'])
            c['facts']['references']={}
            with self.assertRaisesRegex(ValueError,'visual GT'):snapshot.export(self.root,self.root/'invalid')
            snapshot.export(self.root,self.root/'draft',True)
            self.assertFalse((self.root/'draft/READY').exists())
    def test_retention_failure_not_hidden_by_audit_block(self):
        c={'id':'fake','operation':'retention','source':{'sha256':'fake'},'evaluation':{'checks':[]},'retentionContract':{'status':'declared','supported':False,'release':{'commit':'test'}}}
        out=runner.check_case(self.root,c,self.root,self.root,{'commit':'test'})
        self.assertEqual(out['configuration'][0],'failed');self.assertEqual(out['deletion'][0],'blocked')
        c['retentionContract']={'status':'unresolved'};self.assertEqual(runner.check_case(self.root,c,self.root,self.root,{})['configuration'][0],'blocked')
    def test_release_binding_cannot_be_reused(self):
        c=self.quality_case();c['contract']={'status':'declared','release':{'commit':'old'}}
        with patch.object(runner.target,'invoke') as invoke:out=runner.check_case(self.root,c,self.root,self.root,{'commit':'new'})
        invoke.assert_not_called();self.assertIn('another release',out['visual'][1])
    def test_saved_office_survives_server_path_change(self):
        binary=self.root/'soffice';binary.write_text('test placeholder')
        with patch.dict(os.environ,{},clear=True),patch('acceptance.source_preview.shutil.which',return_value=str(binary)):
            self.assertEqual(source_preview.find_office(self.root),str(binary))
        with patch.dict(os.environ,{},clear=True),patch('acceptance.source_preview.shutil.which',return_value=None):
            self.assertEqual(source_preview.find_office(self.root),str(binary))
    def test_keynote_fallback_keeps_original_unchanged(self):
        import fitz,plistlib
        app=self.root/'Keynote.app';(app/'Contents').mkdir(parents=True)
        (app/'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundleShortVersionString':'test'}))
        source=REPO/'benchmark/fixtures/markers.pptx';before=sha(source);calls=[]
        def execute(command,**kwargs):
            calls.append(command)
            if '--version' in command:return {'exitCode':0,'stdout':'LO-test','stderr':''}
            if command[0]=='osascript':
                doc=fitz.open();doc.new_page();doc.save(command[3]);doc.close()
                return {'exitCode':0,'stdout':'1','stderr':''}
            return {'exitCode':0,'stdout':'cannot load source','stderr':''}
        with patch.object(source_preview,'KEYNOTE_APP',app),patch.object(source_preview,'find_office',return_value='/test/soffice'),patch.object(source_preview,'process',side_effect=execute):
            pdf,meta=source_preview.export({'path':str(source),'sha256':before,'format':'pptx'},self.root)
        self.assertEqual(meta['renderer']['name'],'Keynote');self.assertTrue(pdf.is_file());self.assertEqual(sha(source),before)
        self.assertNotEqual(calls[-1][2],str(source))
    def test_video_mapping_import_is_source_bound_and_atomic(self):
        from acceptance import previews
        c=self.quality_case();src={'id':'fixture','path':c['source']['uri'],'sha256':c['source']['sha256'],'facts':c['facts']}
        atomic(self.root/'corpus.json',{'sources':[src]});atomic(self.root/'gt-manifest.json',{'items':[]})
        value={'kind':'visual-review-draft','mode':'gt','actor':'unit-test','reviews':[], 'videoMappings':[{'sourceSha256':src['sha256'],'evidence':'independent synthetic timeline','frames':[{'fraction':f,'sourcePage':1} for f in gt_contract.FRACTIONS]}]}
        file=self.root/'review.json';atomic(file,value)
        with patch.object(catalog,'build'),patch.object(maintenance,'refresh'),patch.object(maintenance,'review_page'),patch.object(previews,'refresh_metadata'):
            previews.apply_draft(self.root,file)
            self.assertEqual(len(read(self.root/'corpus.json')['sources'][0]['facts']['videoReferenceFrames']),5)
            before=sha(self.root/'corpus.json');value['videoMappings'][0]['frames'][0]['sourcePage']=2;atomic(file,value)
            with self.assertRaises(ValueError):previews.apply_draft(self.root,file)
            self.assertEqual(sha(self.root/'corpus.json'),before)

if __name__=='__main__':unittest.main()
