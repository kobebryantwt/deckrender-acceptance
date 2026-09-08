import copy,json,sys,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from acceptance import curation,source_preview,difficulty,gt_contract
from acceptance.common import REPO,sha

class CurationTests(unittest.TestCase):
    def setUp(self):
        self.item={'sourceId':'s','sourceSha256':'h','pages':[{'imageSha256':'im','mapping':{'pdfPage':1}},{'imageSha256':'im2','mapping':{'pdfPage':2}}]}
        self.policy={'sources':{'s':{'sourceSha256':'h','pages':{'2':{'imageSha256':'im2','priority':True,'purpose':'review'}}}}}
    def test_priority_is_not_approval_or_full_readiness(self):
        items=curation.annotate([self.item],self.policy)
        self.assertEqual(curation.summary(items)['priorityPages'],1)
        self.assertEqual(curation.summary(items)['allPreviewPages'],2)
        self.assertNotIn('reviewStatus',items[0]['pages'][1])
        self.assertFalse(gt_contract.readiness({'source':{'sha256':'h'},'facts':{'pages':2},'options':{'target':'image'}})['ready'])
    def test_source_or_image_changes_invalidate_priority(self):
        for field in ['source','image']:
            i=copy.deepcopy(self.item)
            if field=='source':i['sourceSha256']='new'
            else:i['pages'][1]['imageSha256']='new'
            self.assertEqual(curation.summary(curation.annotate([i],self.policy))['priorityPages'],0)
    def test_derived_slide_count_ignores_unlisted_parts(self):
        p=REPO/'benchmark/corpus/pptx_paired_collaboration.pptx'
        v=difficulty.inspect({'path':str(p),'sha256':sha(p),'format':'pptx'})
        self.assertEqual(v['facts']['pages'],3)
        with zipfile.ZipFile(p) as z:self.assertIn('ppt/slides/slide86.xml',z.namelist())
        locations={e['location'] for e in v['evidence']}
        self.assertTrue(all(not x.startswith('ppt/slides/') or x in {'ppt/slides/slide2.xml','ppt/slides/slide11.xml','ppt/slides/slide16.xml'} for x in locations))
    def test_author_reference_does_not_launch_converter(self):
        p=REPO/'benchmark/corpus/pptx_paired_collaboration.pptx'
        with tempfile.TemporaryDirectory() as d,patch('acceptance.source_preview.process') as run:
            ref,meta=source_preview.export({'id':'pptx_paired_collaboration','path':str(p),'sha256':sha(p),'format':'pptx'},d)
            self.assertEqual(meta['status'],'draft');self.assertTrue(ref.is_file());run.assert_not_called()
    def test_changed_pair_fails_closed(self):
        p=REPO/'benchmark/corpus/pptx_paired_collaboration.pptx'
        from acceptance.source_preview import read as original_read
        def altered(path,*args):
            value=original_read(path,*args)
            if Path(path).name=='paired-references.json':value['pptx_paired_collaboration']['sha256']='bad'
            return value
        with tempfile.TemporaryDirectory() as d,patch('acceptance.source_preview.read',side_effect=altered):
            with self.assertRaises(ValueError):source_preview.export({'id':'pptx_paired_collaboration','path':str(p),'sha256':sha(p),'format':'pptx'},d)

if __name__=='__main__':unittest.main()
