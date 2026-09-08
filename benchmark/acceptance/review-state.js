// Browser-local drafts are separate from server-confirmed references.
const storageKey='deckrender.visual-review.v1:__REVIEW_NAMESPACE__:'+mode+':'+String(__RUN_SHA__);
let storageError='', archivedDrafts=[], submitting=false, shownKey=null;
const submittedKeys=new Set();
function rowKey(row){const p=row.page||{};return JSON.stringify([mode==='gt'?null:row.caseId,row.sourceSha256,row.actualSha256,mode==='gt'?(p.sourcePage||p.pdfPage):p]);}
function rowFor(c,p){return {caseId:c.caseId,sourceSha256:c.sourceSha256,page:p.mapping,actualSha256:p.imageSha256,referenceSha256:p.referenceSha256||null};}
function currentRows(){return new Map(data.flatMap(c=>c.pages.map(p=>[rowKey(rowFor(c,p)),{c,p}])));}
function meaningful(r){return rubric.some(k=>r.rubric?.[k]&&r.rubric[k]!=='待审')||Boolean(r.note);}
function complete(r){return rubric.every(k=>['符合','不适用'].includes(r.rubric?.[k]));}
function pendingRows(){return Object.values(drafts).filter(meaningful);}
function notice(text){$('reviewMessage').textContent=text;}
function updateStatus(){
 const pending=pendingRows(),ready=pending.filter(complete).length;
 const approved=[...submittedKeys].filter(k=>!drafts[k]||!meaningful(drafts[k])).length;
 $('reviewStatus').textContent=`已提交 ${approved} 页 · 已标记未提交 ${ready} 页 · 待完善 ${pending.length-ready} 页`+(storageError?' · 本机保存失败': ' · 草稿已保存在此浏览器、此地址');
 $('submitReview').textContent=submitting?'正在提交…':`提交全部已完成审核（${ready} 页）`;
 $('submitReview').disabled=submitting||mode!=='gt';
}
function persist(){
 try{localStorage.setItem(storageKey,JSON.stringify({version:1,actor:$('actor').value,drafts:pendingRows(),videoMappings:Object.values(videoMappings),archivedDrafts}));storageError='';}
 catch(e){storageError='无法保存';notice('浏览器存储不可用，请立即导出备份；不要关闭页面。');}
 updateStatus();
}
function mergeRows(rows){
 const current=currentRows();let accepted=0,stale=0;
 for(const r of rows){
  if(!r||typeof r!=='object'||!r.rubric||!rubric.every(k=>['待审','符合','不符合','不适用'].includes(r.rubric[k]))) {archivedDrafts.push(r);stale++;continue;}
  const matched=current.get(rowKey(r));
  if(!matched){archivedDrafts.push(r);stale++;continue;}
  const {c,p}=matched;const value={...rowFor(c,p),rubric:r.rubric,note:typeof r.note==='string'?r.note:'',status:'draft'};
  if(meaningful(value)){drafts[rowKey(value)]=value;accepted++;}
 }
 return {accepted,stale};
}
function restore(){
 data.forEach(c=>c.pages.forEach(p=>{if(p.reviewStatus==='approved')submittedKeys.add(rowKey(rowFor(c,p)));}));
 try{
  const saved=JSON.parse(localStorage.getItem(storageKey)||'null');
  if(saved){$('actor').value=typeof saved.actor==='string'?saved.actor:'';archivedDrafts=Array.isArray(saved.archivedDrafts)?saved.archivedDrafts:[];const result=mergeRows(saved.drafts||[]);
   for(const v of saved.videoMappings||[])if(data.some(c=>c.sourceSha256===v.sourceSha256))videoMappings[v.sourceSha256]=v;
   notice(`已恢复 ${result.accepted} 页草稿`+(result.stale?`；${result.stale} 条源或参考已变化，已隔离，不会提交。`: '；可继续审核，最后统一提交。'));
  }
 }catch(e){storageError='读取失败';notice('旧草稿读取失败，请保留原导出备份；本页不会自动提交。');}
 updateStatus();
}
function exportPayload(onlyComplete=false){return {version:2,kind:'visual-review-draft',mode,runSha256:__RUN_SHA__,actor:$('actor').value.trim(),createdAt:new Date().toISOString(),videoMappings:Object.values(videoMappings).filter(m=>m.evidence||m.frames.some(f=>f.sourcePage)),reviews:pendingRows().filter(r=>!onlyComplete||complete(r)),...(!onlyComplete?{staleReviews:archivedDrafts}:{})};}
async function importBackup(file){
 const v=JSON.parse(await file.text());
 if(v.kind!=='visual-review-draft'||v.mode!==mode||!Array.isArray(v.reviews)||mode!=='gt'&&v.runSha256!==__RUN_SHA__)throw Error('文件类型或运行版本不匹配');
 save();const result=mergeRows(v.reviews);if(!$('actor').value&&typeof v.actor==='string')$('actor').value=v.actor;
 for(const m of v.videoMappings||[])if(data.some(c=>c.sourceSha256===m.sourceSha256))videoMappings[m.sourceSha256]=m;
 persist();show();notice(`已合并 ${result.accepted} 页草稿，${result.stale} 条不匹配记录已隔离；尚未提交。`);
}
async function submitAll(){
 save();saveVideoMapping();const payload=exportPayload(true);
 if(!payload.actor){notice('请先填写审核人，再统一提交。');$('actor').focus();return;}
 if(!payload.reviews.length&&!payload.videoMappings.length){notice('没有可提交的完整审核；不符合或待审项继续保留为草稿。');return;}
 submitting=true;updateStatus();
 try{
  const auth=await fetch('/api/projects');if(!auth.ok)throw Error('管理服务不可用；草稿仍保存在浏览器，可导出备份');
  const config=await auth.json();if(!config.canVisualReview)throw Error('当前页面不支持直接提交，请从本地管理服务打开');
  const res=await fetch('/api/visual-review',{method:'POST',headers:{'Content-Type':'application/json','X-Casework-Token':config.token},body:JSON.stringify(payload)});
  const result=await res.json();if(!res.ok)throw Error(result.error||'提交失败');
  for(const row of payload.reviews){const k=rowKey(row);submittedKeys.add(k);const match=currentRows().get(k);if(match){match.p.reviewStatus='approved';match.p.review={actor:payload.actor,rubric:row.rubric,note:row.note};}if(JSON.stringify(drafts[k])===JSON.stringify(row))delete drafts[k];}
  persist();show();notice(`已提交 ${result.confirmedReferencePages} 页图像 GT。Casework 的测试问题与预期答案仍需另行审核。`);
 }catch(e){notice('未完成提交：'+e.message+'。草稿已保留，请勿重复标记。');}
 finally{submitting=false;updateStatus();}
}
