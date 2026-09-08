"""Synthetic evidence only: parameter forwarding, source identities, codec and GT mapping."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from acceptance import evaluation as ev,quality,target,maintenance,coverage
from acceptance.common import sha,read
from PIL import Image

class OptionContract(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def proc(self,order=(1,3),encoding='PNG'):
        entries=[]
        for n in order:
            p=self.root/f'{n}.png';Image.new('RGB',(500,400),'blue').save(p,format=encoding)
            entries.append({'page':n,'file':str(p)})
        return {'exitCode':0,'payload':{'ok':True,'format':'image','pages':3,'outputs':entries},'artifactsDir':str(self.root)}
    def test_subset_count_and_original_identity(self):
        p=self.proc();c={'outputCount':2,'selectedSourcePages':[1,3]}
        self.assertEqual(ev.declared_artifacts(p,{'pages':3},c)[0],'passed')
        for order in [(3,1),(1,2),(1,1),(1,2,3)]:
            self.assertEqual(ev.declared_artifacts(self.proc(order),{'pages':3},c)[0],'failed',order)
    def test_codec_checks_content_not_extension(self):
        c={'selectedSourcePages':[1],'outputCount':1,'imageEncoding':'jpg'}
        self.assertEqual(ev.declared_artifacts(self.proc((1,)),{'pages':3},c)[0],'failed')
        self.assertEqual(ev.declared_artifacts(self.proc((1,),'JPEG'),{'pages':3},c)[0],'passed')
    def test_corrupt_image_fails(self):
        p=self.proc((1,));Path(p['payload']['outputs'][0]['file']).write_bytes(b'bad')
        self.assertEqual(ev.declared_artifacts(p,{'pages':3},{'selectedSourcePages':[1]})[0],'failed')
    def test_cli_sdk_forward_exact_parameters(self):
        source=self.root/'input.pdf';source.write_bytes(b'synthetic')
        c={'source':{'uri':str(source),'sha256':sha(source)},'format':'pdf','options':{'engine':'local','target':'image','interface':'cli','pages':' ','imageFormat':'jpg'}}
        with patch('acceptance.target.package_path',return_value=self.root),patch('acceptance.target.process',return_value={'exitCode':0,'stdout':'{}','stderr':''}) as run:
            target.invoke(self.root,c,self.root/'cli');cmd=run.call_args.args[0]
            self.assertEqual(cmd[cmd.index('--pages')+1],' ');self.assertEqual(cmd[cmd.index('--image-format')+1],'jpg')
            c['options']['interface']='sdk';target.invoke(self.root,c,self.root/'sdk')
            opts=read(self.root/'sdk/request.json')['options'];self.assertEqual(opts['pages'],' ');self.assertEqual(opts['imageFormat'],'jpg')
    def test_gt_uses_reviewed_selection_not_renumbered_output(self):
        p=self.proc((1,2));refs={}
        for i in range(1,4):
            f=self.root/f'ref{i}.png';Image.new('RGB',(500,400),(i*60,0,0)).save(f)
            refs[str(i)]={'path':str(f),'sha256':sha(f),'sourceSha256':'source','provenance':{'method':'synthetic'},'status':'approved','review':{'actor':'test'}}
        c={'id':'synthetic','source':{'sha256':'source'},'options':{'target':'image'},'facts':{'pages':3,'references':refs},'contract':{'selectedSourcePages':[1,3]}}
        with patch('acceptance.quality.process',return_value={}):result=quality.inspect(p,c,self.root/'visual')
        page=result['metrics'][1];self.assertEqual(page['referenceSha256'],refs['3']['sha256'])
        self.assertEqual(page['mapping']['reportedSourcePage'],2);self.assertEqual(page['mapping']['expectedSourcePage'],3)
        self.assertTrue(result['errors'])
    def test_catalog_bindings_and_gt_purpose(self):
        _,cases,questions=maintenance.load_suites();byid={c['id']:c for c in cases}
        variants=[c for c in cases if c['operation']=='render' and c['options'].get('variantId')]
        self.assertTrue(variants)
        for c in variants:
            self.assertEqual(c['contract']['status'],'declared')
            self.assertEqual(c['contract']['supported'],c['options']['expectedSupport'])
            if c['options']['expectedSupport']:
                q=byid[c['qualityCaseId']];self.assertEqual(q['options'],c['options']);self.assertEqual(q['source'],c['source'])
            else:self.assertIsNone(c['qualityCaseId'])
        cv=coverage.build({'sources':[]},{'cases':cases,'questions':questions})
        self.assertEqual(len(cv['matrix']),54);self.assertEqual(len(cv['optionTests']),len(variants))
        self.assertTrue(all(q['reviewStatus'] in ['draft','approved'] for q in questions if byid[q['caseId']]['options'].get('variantId')))

if __name__=='__main__':unittest.main()
