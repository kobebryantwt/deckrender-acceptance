#!/usr/bin/env python3
"""Select existing slide records without redrawing; paired PDF stays an unapproved oracle."""
import json,hashlib,zipfile,xml.etree.ElementTree as ET,urllib.request
from pathlib import Path
import fitz
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 intake=ROOT/'benchmark/artifacts/acceptance/candidate-intake/zenodo-14623257'
 pptx=intake/'collab_git_v4.pptx';pdf=intake/'collab_git_v4.pdf';record_path=ROOT/'benchmark/references/paired-collaboration-upstream.json';record=json.loads(record_path.read_text())
 intake.mkdir(parents=True,exist_ok=True)
 for p in [pptx,pdf]:
  if not p.exists():
   url=next(f['links']['self'] for f in record['files'] if f['key']==p.name)
   with urllib.request.urlopen(url,timeout=60) as response:p.write_bytes(response.read())
 if sha(pptx)!='dff59cb7c3a2587f7af52772be60ed2ff614415e15e2030aa7674cd9b636e316' or sha(pdf)!='2d2a32bb0fada080f726c3f32f8ec842e26a5c74c6098dfba33b9f5ceab4ebc4':raise ValueError('Unverified upstream content')
 pages=[2,11,16];out=ROOT/'benchmark/corpus/pptx_paired_collaboration.pptx';ref=ROOT/'benchmark/references/paired-collaboration.pdf';ref.parent.mkdir(exist_ok=True)
 with zipfile.ZipFile(pptx) as src:
  root=ET.fromstring(src.read('ppt/presentation.xml'));ns={'p':'http://schemas.openxmlformats.org/presentationml/2006/main'};slides=root.find('p:sldIdLst',ns)
  assert len(slides)==86
  for i,slide in enumerate(list(slides),1):
   if i not in pages:slides.remove(slide)
  # Slide, relationship, master, font and media bytes are kept unchanged.
  # Unused parts remain so internal relationships cannot become dangling.
  with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED) as dst:
   for info in src.infolist():dst.writestr(info,ET.tostring(root,encoding='utf-8',xml_declaration=True) if info.filename=='ppt/presentation.xml' else src.read(info.filename))
 with fitz.open(pdf) as src:
  doc=fitz.open()
  for n in pages:doc.insert_pdf(src,from_page=n-1,to_page=n-1)
  doc.save(ref,no_new_id=True);doc.close()
 provenance={'version':1,'sourceId':'pptx_paired_collaboration','sourceSha256':sha(out),'referencePdfSha256':sha(ref),'originalPages':pages,'originalSlideCount':86,
   'originals':[{'filename':p.name,'sha256':sha(p),'url':next(f['links']['self'] for f in record['files'] if f['key']==p.name)} for p in [pptx,pdf]],
   'recordUrl':'https://zenodo.org/records/14623257','recordSha256':sha(record_path),'title':record['metadata']['title'],'creators':record['metadata']['creators'],'license':'CC-BY-4.0',
   'derivation':'presentation.xml slide list restricted to original pages 2,11,16; all other ZIP entries preserved byte-for-byte. PDF selects same original pages. Not redrawn; not DeckRender output.',
   'pairing':'Same publication and total page count; selected page headings match source XML. Human visual pairing review remains required.', 'reviewStatus':'draft'}
 (ref.parent/'paired-collaboration.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(provenance,ensure_ascii=False))
if __name__=='__main__':main()
