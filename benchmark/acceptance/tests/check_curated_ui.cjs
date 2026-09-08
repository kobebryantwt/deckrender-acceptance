// DOM simulation only; never submits real GT or creates product evidence.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync(process.argv[2],'utf8');
const data=html.match(/<script id="data" type="application\/json">([\s\S]*?)<\/script>/)[1];
const code=html.split('<script>')[1].split('</script>')[0],storage=new Map();
function boot({failStorage=false,failSubmit=false}={}){
 const els={};
 class Element {
  constructor(){this.style={};this.children=[];this.value='';this.textContent='';this.parentElement=this;}
  set id(v){this._id=v;els[v]=this;}
  replaceChildren(){this.children=[];}
  append(...x){this.children.push(...x);}
  add(x){this.children.push(x);}
  remove(){} focus(){} click(){this.onclick?.();}
 }
 els.data=Object.assign(new Element(),{textContent:data});els.scope=Object.assign(new Element(),{value:'curated'});els.zoom=Object.assign(new Element(),{value:'100'});
 const document={getElementById:id=>els[id]||(/^r[0-5]$/.test(id)?null:(els[id]=new Element())),createElement:()=>new Element(),createTextNode:t=>({textContent:t}),querySelector:id=>els[id]??=new Element(),querySelectorAll:()=>[],addEventListener(){}};
 const calls=[];
 const context={document,window:{addEventListener(){}},localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>{if(failStorage)throw Error('quota');storage.set(k,v);}},Option:class {constructor(text,value){this.text=text;this.value=value;}},console,URL,Blob,setTimeout,
  fetch:async(url,options)=>{calls.push({url,options});return {ok:!failSubmit,json:async()=>url==='/api/projects'?{canVisualReview:true,token:'synthetic'}:{confirmedReferencePages:JSON.parse(options.body).reviews.length}};}};
 vm.createContext(context);vm.runInContext(code,context);return {context,calls,els};
}
(async()=>{
 let {context}=boot();
 vm.runInContext(`
  if(data[ci].sourceId!=='docx_business_report'||pi!==1)throw Error('Default queue must select table page 2');
  $('quickPassCase').onclick();
  if(pendingRows().length!==1||(pendingRows()[0].page.pdfPage||pendingRows()[0].page.sourcePage)!==2)throw Error('Bulk review touched hidden page');
  const buttons=[...$('cases').children];
  for(const button of buttons){button.onclick();$('quickPassCase').onclick();}
  if(exportPayload().reviews.length!==8)throw Error('Cross-file marks lost');
  if(pendingRows().some(r=>!complete(r)))throw Error('Saved rubric overwritten during file switch');
  $('actor').value='synthetic-tester';persist();
 `,context);
 const original=JSON.parse(vm.runInContext('JSON.stringify(exportPayload())',context));
 context=boot().context;
 assert.equal(vm.runInContext('pendingRows().length',context),8,'refresh restores all eight pages');
 assert.equal(vm.runInContext("$('actor').value",context),'synthetic-tester');
 vm.runInContext(`
  ci=data.findIndex(c=>c.sourceId==='pptx_multilingual_fonts');pi=0;show();$('next').onclick();
  if(pi!==1)throw Error('Next selected page');$('next').onclick();if(pi!==1)throw Error('Must not visit hidden page 3');
  $('scope').value='render';listing();show();if($('pages').children.length!==3)throw Error('Full source pages unavailable');
  $('search').value='NO_MATCH_EXPECTED';listing();if(!document.querySelector('.workspace').hidden)throw Error('Stale case after empty search');
 `,context);
 const failed=boot({failSubmit:true});await vm.runInContext('submitAll()',failed.context);assert.equal(vm.runInContext('pendingRows().length',failed.context),8,'failed submit keeps drafts');
 const success=boot();await vm.runInContext('submitAll()',success.context);
 assert.equal(JSON.parse(success.calls[1].options.body).reviews.length,8,'one request includes all sources');
 assert.equal(vm.runInContext('pendingRows().length',success.context),0,'success clears submitted drafts');
 assert.equal(vm.runInContext('submittedKeys.size',success.context),8);
 storage.clear();context=boot().context;
 for(const rows of [original.reviews.slice(0,1),original.reviews.slice(1)]){
  context.file={text:async()=>JSON.stringify({...original,reviews:rows})};await vm.runInContext('importBackup(file)',context);
 }
 assert.equal(vm.runInContext('pendingRows().length',context),8,'multiple backups merge');
 context.bad={...original.reviews[0],actualSha256:'changed'};
 vm.runInContext('mergeRows([bad])',context);assert.equal(vm.runInContext('pendingRows().length',context),8);assert.equal(vm.runInContext('archivedDrafts.length',context),1);
 context=boot({failStorage:true}).context;vm.runInContext('persist()',context);assert.match(vm.runInContext("$('reviewStatus').textContent",context),/保存失败/);
 console.log('UI logic passed: cross-file eight-page batch, reload recovery, visible-only bulk, backup merge, stale isolation, failed/successful submit and storage failure.');
})().catch(e=>{console.error(e);process.exit(1);});
