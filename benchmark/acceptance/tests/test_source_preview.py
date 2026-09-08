import sys,tempfile,unittest,json
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from acceptance import source_preview,workbench
from acceptance.common import REPO,sha,read

class SourcePreviewTests(unittest.TestCase):
    def source(self):
        p=REPO/'benchmark/fixtures/markers.pptx'
        return {'path':str(p),'sha256':sha(p),'format':'pptx'}
    def test_isolated_conversion_cache_and_tamper(self):
        import fitz
        calls=[]
        def execute(command,**kwargs):
            calls.append(command)
            if '--version' in command:return {'exitCode':0,'stdout':'LO test version','stderr':''}
            root=Path(command[command.index('--outdir')+1]);doc=fitz.open();doc.new_page();doc.save(root/'source.pdf');doc.close()
            return {'exitCode':0,'stdout':'converted','stderr':''}
        with tempfile.TemporaryDirectory() as d,patch('acceptance.source_preview.shutil.which',return_value='/test/soffice'),patch('acceptance.source_preview.process',side_effect=execute):
            source=self.source();before=sha(source['path']);pdf,provenance=source_preview.export(source,d)
            self.assertEqual(provenance['sourceSha256'],before);self.assertEqual(sha(source['path']),before)
            self.assertNotEqual(str(Path(calls[-1][-1]).resolve()),str(Path(source['path']).resolve()))
            source_preview.export(source,d)
            self.assertEqual(sum('--convert-to' in c for c in calls),1)
            pdf.write_bytes(b'changed');pdf.unlink();source_preview.export(source,d)
            self.assertEqual(sum('--convert-to' in c for c in calls),2)
    def test_encrypted_office_does_not_launch_converter(self):
        with tempfile.TemporaryDirectory() as d,patch('acceptance.source_preview.process') as execute:
            p=Path(d)/'encrypted.docx';p.write_bytes(b'not an OOXML archive')
            with self.assertRaisesRegex(ValueError,'加密或损坏'):source_preview.export({'path':str(p),'sha256':sha(p),'format':'docx'},d)
            execute.assert_not_called()
    def test_zero_exit_without_pdf_is_not_success(self):
        with tempfile.TemporaryDirectory() as d,patch('acceptance.source_preview.shutil.which',return_value='/test/soffice'),patch('acceptance.source_preview.process',return_value={'exitCode':0,'stdout':'cannot load source','stderr':''}):
            with self.assertRaises(ValueError):source_preview.export(self.source(),d)
    def test_external_images_are_hashed_and_portable(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=root/'page.png';Image.new('RGB',(5,5)).save(p)
            workbench.write(root/'gt.html',[{'pages':[{'image':str(p),'imageSha256':sha(p)}]}],'test',embed=False)
            self.assertTrue((root/'gt-assets'/(sha(p)+'.png')).exists())
            self.assertNotIn('data:image/png;base64,',(root/'gt.html').read_text())
    def test_preview_server_rejects_changed_image(self):
        import threading,urllib.request,urllib.error
        from acceptance.maintenance import Store
        from casework.server import make_server
        from PIL import Image
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=root/'page.png';Image.new('RGB',(5,5)).save(p)
            workbench.write(root/'gt.html',[{'pages':[{'image':str(p),'imageSha256':sha(p)}]}],'test',embed=False)
            server=make_server(None,0,extra_pages={'/':root/'gt.html'})
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                url='http://127.0.0.1:'+str(server.server_port)+'/gt-assets/'+sha(p)+'.png'
                with urllib.request.urlopen(url) as response:self.assertEqual(response.read(),p.read_bytes())
                (root/'gt-assets'/(sha(p)+'.png')).write_bytes(b'tampered')
                with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(url)
            finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':unittest.main()
