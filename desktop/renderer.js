'use strict';
const $=id=>document.getElementById(id),api=window.handnavigate;
let state=null,editingId=null,filledSha=null,currentTab='setup',dirty=false,stepsDraft=[],rowDraft=null,pending=0;
const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const task=()=>state?.tasks.find(t=>t.id===state.selectedId);
const statusClass=status=>status==='VERIFIED'?'':status==='RUNNING'?'amber':['HALTED','NEEDS_REVIEW','AUTH_REQUIRED'].includes(status)?'red':'amber';
function message(text,error=false){$('notice').hidden=!text;$('notice').textContent=text||'';$('notice').classList.toggle('success',!error);syncBounds();}
async function call(name,arg){pending++;controls();try{const response=await api[name](arg);if(!response.ok)throw new Error(response.error);return response.value;}finally{pending--;controls();}}
function act(fn){return async event=>{event?.preventDefault();try{await fn(event);}catch(e){message(e.message,true);}};}
function chosenRow(){return Number($('run-row').value||0);}
function pagingForm(mode,limit,selector,existing){const kind=$(mode).value;return {kind,maxPages:Number($(limit).value),...(kind==='next'?{locator:$(selector).value.trim()?{kind:'css',value:$(selector).value.trim()}:existing?.locator||null}:{})};}
function formTask(){
  const t=structuredClone(task());if(!t)throw new Error('Choose a workflow first.');
  t.name=$('task-name').value.trim();t.type=$('task-type').value;t.startUrl=$('task-url').value.trim();
  const lines=$('task-values').value.split('\n').map(s=>s.trim()).filter(Boolean);if(!lines.length)throw new Error('Enter at least one topic or variable value.');
  t.rows=rowDraft||lines.map(topic=>({topic}));t.count=Number($('task-count-input').value);t.outputFolder=$('task-folder').value;t.newOnly=$('new-only').checked;
  t.pagination=pagingForm('page-mode','page-limit','next-selector',t.pagination);t.dedupeScope=$('dedupe-scope').value;t.skipSimilar=$('skip-similar').checked;
  if(t.target)t.target.pagination=pagingForm('gallery-mode','gallery-limit','gallery-next-selector',t.target.pagination);
  t.checks=[];if($('check-text').value.trim())t.checks.push({kind:'text',expected:$('check-text').value.trim()});if($('check-url').value.trim())t.checks.push({kind:'url',expected:$('check-url').value.trim()});
  // A new starting site is shown in Review before it can run.
  try{const origin=new URL(t.startUrl.replace(/\{\{\w+\}\}/g,'example')).origin;t.allowedOrigins=[...new Set([...t.allowedOrigins,origin])];}catch{}
  t.steps=stepsDraft;return t;
}
async function saveForm(){const value=await call('saveTask',{task:formTask()});dirty=false;rowDraft=null;editingId=null;await refresh();return value;}
async function refresh(){const value=await call('state');receive(value);}
function fill(t){
  if(!t)return;editingId=t.id;filledSha=t.sha;dirty=false;stepsDraft=structuredClone(t.steps);rowDraft=structuredClone(t.rows);
  $('task-name').value=t.name;$('task-type').value=t.type;$('task-url').value=t.startUrl;
  $('task-values').value=t.rows.map(r=>r.topic??Object.values(r)[0]??'').join('\n');$('task-count-input').value=t.count||20;$('task-folder').value=t.outputFolder||state.downloads;$('new-only').checked=t.newOnly!==false;
  $('dedupe-scope').value=t.dedupeScope||'workflow';$('skip-similar').checked=!!t.skipSimilar;
  for(const [mode,limit,selector,spec] of [['page-mode','page-limit','next-selector',t.pagination||{kind:'scroll',maxPages:50}],['gallery-mode','gallery-limit','gallery-next-selector',t.target?.pagination||{kind:'none',maxPages:20}]]){
    $(mode).value=spec.kind;$(limit).value=spec.maxPages;$(selector).value=spec.locator?.kind==='css'?spec.locator.value:'';$(selector).placeholder=spec.locator&&spec.locator.kind!=='css'?'Picked: '+(spec.locator.name||spec.locator.value):'e.g. a[rel=next]';
  }
  $('check-text').value=t.checks.find(c=>c.kind==='text')?.expected||'';$('check-url').value=t.checks.find(c=>c.kind==='url')?.expected||'';
  $('source-selector').value=t.sourceSelector||'img';$('allowed-origins').value=t.allowedOrigins.join('\n');$('image-origins').value=t.imageOrigins.join('\n');$('rows-json').value=JSON.stringify(t.rows,null,2);
  $('schedule-time').value=t.schedule?.time||'09:00';$('schedule-zone').value=t.schedule?.timezone||Intl.DateTimeFormat().resolvedOptions().timeZone||'Asia/Kolkata';
  $('review-ack').checked=false;renderSteps();renderReview(t);renderRows(t);renderSchedule(t);typeVisibility();
}
function typeVisibility(){const type=$('task-type').value;document.querySelectorAll('.image-settings').forEach(el=>el.hidden=type==='replay');$('pick-images').hidden=type==='replay';$('transfer-controls').hidden=type!=='transfer';$('image-verification').hidden=type==='replay';$('next-settings').hidden=$('page-mode').value!=='next';$('gallery-next-settings').hidden=$('gallery-mode').value!=='next';}
function renderRows(t){const before=$('run-row').value;$('run-row').innerHTML=t.rows.map((r,i)=>`<option value="${i}">${escape(Object.values(r).join(' · ').slice(0,45))}</option>`).join('');if(Number(before)<t.rows.length)$('run-row').value=before;}
function renderSteps(){
  $('steps-count').textContent=stepsDraft.length?'('+stepsDraft.length+')':'';
  $('steps-list').innerHTML=stepsDraft.length?stepsDraft.map((step,i)=>`<article class="step-card ${step.blocked?'blocked':''}"><div class="step-title"><strong>${i+1}. ${escape(step.op)} ${escape(step.label||'')}</strong><button data-remove-step="${i}" aria-label="Remove step ${i+1}">×</button></div>${step.blocked?`<p>${escape(step.blocked)}</p>`:''}${['fill','select','navigate','wait'].includes(step.op)?`<input data-step-value="${i}" aria-label="Step ${i+1} value" value="${escape(step.op==='wait'?step.amount:step.value)}">`:''}${step.op==='check'?`<label class="check"><input type="checkbox" data-step-checked="${i}" ${step.checked?'checked':''}> Checked</label>`:''}<div class="step-meta">${escape(step.locator?JSON.stringify(step.locator):step.op==='wait'?'Milliseconds':'')}</div></article>`).join(''):'<div class="empty">No recorded setup steps. A direct results page can download images without a demonstration.</div>';
}
function renderReview(t){$('review-summary').innerHTML=`<strong>${escape(t.type==='replay'?'Repeat taught actions':t.type==='transfer'?'Download → upload → verify':'Download verified images')}</strong>${escape(t.count||0)} image${t.count===1?'':'s'} · ${t.rows.length} value${t.rows.length===1?'':'s'}<br>${escape(t.startUrl)}<br>Websites: ${escape(t.allowedOrigins.join(' · '))}<br>Image hosts: ${escape(t.imageOrigins.join(' · ')||'Reviewed websites above')}<br>More results: ${escape(t.pagination?.kind||'scroll')} · limit ${escape(t.pagination?.maxPages||50)}<br>Duplicates: ${escape(t.dedupeScope==='library'?'all workflows':'this workflow')}${t.skipSimilar?' · similarity filtering':''}`;
  $('target-summary').textContent=t.target?`Upload: ${t.target.url} · Gallery: ${t.target.galleryUrl}`:'No upload form selected yet.';}
function renderSchedule(t){
  const count=t.rehearsals?.length||0,total=t.rows.length,active=t.schedule?.enabled;
  $('schedule-readiness').innerHTML=`<span>${count===total?'✓':'○'}</span><p>${count}/${total} value rows verified. ${count===total?'Ready for daily automation.':'Run each value once and inspect the result.'}${active?'<br>Next: '+escape(new Date(t.schedule.nextDue).toLocaleString()):''}</p>`;
  $('schedule-values').innerHTML=t.rows.map((r,i)=>`<div>${i+1}. ${escape(Object.values(r).join(' · '))} ${t.rehearsals?.includes(i)?'✓':''}</div>`).join('');
  $('schedule-enable').textContent=active?'Update daily time':'Turn on daily runs';$('schedule-pause').hidden=!active;
  $('workflow-id').value=t.id;const integration=state.integration||{};
  if(document.activeElement!==$('api-port'))$('api-port').value=integration.port||47831;
  $('api-status').textContent=integration.enabled?'Active: '+integration.endpoint:'The local API is off.';
  $('api-enable').textContent=integration.enabled?'Update API port':'Turn on local API';$('api-disable').hidden=!integration.enabled;$('api-copy').hidden=!integration.enabled;
  $('api-export').disabled=!integration.clientAvailable||pending>0;
}
function renderHistory(t){
  const runs=state.runs.filter(r=>r.taskId===t.id);
  $('history-list').innerHTML=runs.length?runs.map(r=>{
    const unresolved=r.items.filter(i=>['UPLOADING','NEEDS_REVIEW'].includes(i.state)).length;
    const review=r.status==='NEEDS_REVIEW'&&!r.acknowledged;
    return `<article class="history-card"><div class="history-title"><strong>${escape(Object.values(r.inputs).join(' · '))}</strong><span class="pill ${statusClass(r.status)}">${escape(r.status.replaceAll('_',' '))}</span></div>
      <p>${escape(new Date(r.startedAt).toLocaleString())} · ${escape(r.trigger)} · ${r.items.length} image${r.items.length===1?'':'s'}</p>
      <p>${r.pagesVisited||0} pages · ${r.duplicatesSkipped||0} duplicates skipped · ${r.items.filter(i=>i.reusedFrom).length} files reused</p>
      ${r.error?`<p>${escape(r.error)}</p>`:''}${r.reviewOutcome?`<p>${escape(r.reviewOutcome)}</p>`:''}
      ${r.folder?`<button class="button" data-run-folder="${r.id}">Open files ↗</button>`:''}
      ${review?`<p>${unresolved?'Recheck the uploaded originals first. If they are absent, explicitly confirm that before retrying.':'Inspect the site outcome before running again.'}</p>
        ${unresolved?`<button class="button" data-recheck-run="${r.id}">Recheck uploaded originals</button>`:''}
        <button class="button" data-ack-run="${r.id}" data-unresolved="${unresolved}">${unresolved?'Confirm missing uploads':'I checked this outcome'}</button>`:''}
      <details><summary>Result checks and run events</summary><pre>${escape(JSON.stringify({status:r.status,inputs:r.inputs,items:r.items,events:r.events},null,2))}</pre></details></article>`;
  }).join(''):'<div class="empty">Your verified results will appear here after the first run.</div>';
}
function receive(value){
  state=value;const t=task();
  $('workflow-list').innerHTML=state.tasks.filter(t=>!t.archived).map(t=>`<button class="workflow-item ${t.id===state.selectedId?'active':''}" data-task-id="${t.id}"><span class="item-top"><span class="workflow-icon">${t.type==='replay'?'↻':'▧'}</span><span><strong>${escape(t.name)}</strong><small>${t.schedule?.enabled?'Daily · '+escape(t.schedule.time):t.approvedSha?'Ready to run':'Draft workflow'}</small></span></span></button>`).join('');
  $('task-count').textContent=state.tasks.filter(t=>!t.archived).length;
  if(t){$('workflow-title').textContent=t.name;$('approval-status').textContent=state.busy?.taskId===t.id?'Running':t.schedule?.enabled?'Daily active':t.approvedSha?'Reviewed':'Draft';$('approval-status').classList.toggle('amber',!t.approvedSha);if(editingId!==t.id||!dirty&&filledSha!==t.sha)fill(t);renderHistory(t);renderSchedule(t);renderReview(t);}
  if(document.activeElement!==$('browser-address'))$('browser-address').value=state.browser.url==='about:blank'?'':state.browser.url;
  $('record').hidden=!!state.recording;$('stop-record').hidden=!state.recording;$('record-label').textContent=state.recording?`Recording · ${state.recording.events} steps`:'Ready to learn';
  $('record-help').textContent=state.recording?'Demonstrate in the browser, then stop teaching before choosing images or reviewing.':'Record searches, clicks, selections and form inputs. A direct results URL needs no recording.';
  const running=state.runs.find(r=>r.id===state.busy?.runId),latest=state.runs.find(r=>r.taskId===t?.id);
  $('run-state').textContent=running?'Working…':latest?.status==='VERIFIED'?'Last run verified':latest?latest.status.replaceAll('_',' '):'Ready when you are';
  $('run-detail').textContent=running?(running.events.at(-1)?.text||'Opening the website'):latest?.status==='VERIFIED'?`${latest.items.length} files · ${latest.duplicatesSkipped||0} duplicates skipped`:t?.approvedSha?'Uses reviewed steps · no AI calls':'Review before the first run';
  $('browser-status').textContent=state.picking?'Choose an image in the browser. Press Esc to cancel.':state.recording?'Recording your demonstration. Private fields are excluded.':state.busy?'Executing the reviewed workflow in this browser.':'Sign in here once. Runs use this same session.';
  if(state.error)message(state.error,true);controls();syncBounds();
}
function controls(){if(!state)return;const busy=!!state.busy,recording=!!state.recording;for(const id of ['new-workflow','save-task','open-site','record','choose-folder','choose-upload','pick-images','pick-gallery','pick-next','pick-gallery-next','save-steps','apply-advanced','browser-back','browser-forward','browser-reload','api-enable','api-disable'])$(id).disabled=pending>0||busy||(recording&&!['record'].includes(id));
  $('run-now').hidden=busy;$('stop-run').hidden=!busy;$('run-now').disabled=pending>0||recording||!!state.picking||!task()?.approvedSha||dirty;
  $('approve-run').disabled=pending>0||busy||recording||!$('review-ack').checked;$('schedule-enable').disabled=pending>0||busy||recording;$('stop-record').disabled=pending>0;
}
function syncBounds(){requestAnimationFrame(()=>{const r=$('browser-slot').getBoundingClientRect();api.setBrowserBounds({x:r.x,y:r.y,width:r.width,height:r.height});});}
async function tab(name){currentTab=name;document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('selected',b.dataset.tab===name));document.querySelectorAll('.tab-content').forEach(e=>e.hidden=e.id!=='tab-'+name);syncBounds();}
document.querySelectorAll('[data-tab]').forEach(b=>b.addEventListener('click',()=>tab(b.dataset.tab)));
for(const id of ['task-name','task-type','task-url','task-values','task-count-input','new-only','dedupe-scope','skip-similar','page-mode','page-limit','next-selector','gallery-mode','gallery-limit','gallery-next-selector','check-text','check-url'])$(id).addEventListener('input',()=>{dirty=true;if(id==='task-values')rowDraft=null;if(['task-type','page-mode','gallery-mode'].includes(id))typeVisibility();controls();});
$('review-ack').addEventListener('change',controls);
$('save-task').addEventListener('click',act(async()=>{await saveForm();message('Workflow saved. Open the site to sign in or teach the steps.');}));
$('open-site').addEventListener('click',act(async()=>{const t=await saveForm(),row=t.rows[chosenRow()]||t.rows[0];const url=t.startUrl.replace(/\{\{(\w+)\}\}/g,(_,key)=>encodeURIComponent(row[key]||''));await call('open',{url});}));
$('choose-folder').addEventListener('click',act(async()=>{const folder=await call('chooseFolder');if(folder){$('task-folder').value=folder;dirty=true;controls();}}));
$('open-folder').addEventListener('click',act(()=>call('showFolder',{id:task().id})));
$('record').addEventListener('click',act(async()=>{if(dirty)await saveForm();await call('record');message('Teaching started. Complete the browser steps, then click Stop teaching.');}));
$('stop-record').addEventListener('click',act(async()=>{await call('stopRecord');editingId=null;await refresh();await tab('review');message('Demonstration captured. Review the actions and bind changing inputs.');}));
$('pick-images').addEventListener('click',act(async()=>{if(dirty)await saveForm();await call('pick',{purpose:'source'});message('Click one image from the group to download.');}));
$('choose-upload').addEventListener('click',act(async()=>{if(dirty)await saveForm();await call('chooseUpload');editingId=null;await refresh();message('Upload form selected. Now open its saved-image gallery and choose that group.');}));
$('pick-gallery').addEventListener('click',act(()=>call('pick',{purpose:'gallery'})));
for(const [id,purpose] of [['pick-next','next'],['pick-gallery-next','galleryNext']])$(id).addEventListener('click',act(async()=>{if(dirty)await saveForm();await call('pick',{purpose});message('Click the Next page or Load more control in the browser.');}));
$('save-steps').addEventListener('click',act(async()=>{await saveForm();message('Step changes saved. Review the result checks before approving.');}));
$('add-wait').addEventListener('click',()=>{stepsDraft.push({op:'wait',amount:1000,label:'Wait for page'});dirty=true;renderSteps();controls();});
$('steps-list').addEventListener('input',event=>{const e=event.target;if(e.dataset.stepValue!==undefined){const s=stepsDraft[Number(e.dataset.stepValue)];if(s.op==='wait')s.amount=Number(e.value);else s.value=e.value;dirty=true;}if(e.dataset.stepChecked!==undefined){stepsDraft[Number(e.dataset.stepChecked)].checked=e.checked;dirty=true;}controls();});
$('steps-list').addEventListener('click',event=>{const b=event.target.closest('[data-remove-step]');if(b){stepsDraft.splice(Number(b.dataset.removeStep),1);dirty=true;renderSteps();controls();}});
$('apply-advanced').addEventListener('click',act(async()=>{const t=formTask();t.sourceSelector=$('source-selector').value.trim();t.allowedOrigins=$('allowed-origins').value.split('\n').map(s=>s.trim()).filter(Boolean);t.imageOrigins=$('image-origins').value.split('\n').map(s=>s.trim()).filter(Boolean);t.rows=JSON.parse($('rows-json').value);await call('saveTask',{task:t});editingId=null;await refresh();message('Advanced settings saved. Changes need review before running.');}));
$('approve-run').addEventListener('click',act(async()=>{const row=chosenRow(),t=await saveForm();await call('approve',{id:t.id,sha:t.sha});await call('run',{id:t.id,rowIndex:row});await tab('history');}));
$('run-now').addEventListener('click',act(()=>call('run',{id:task().id,rowIndex:chosenRow()})));
$('stop-run').addEventListener('click',act(()=>call('stop')));
$('schedule-enable').addEventListener('click',act(async()=>{await call('schedule',{id:task().id,enabled:true,time:$('schedule-time').value,timezone:$('schedule-zone').value.trim()});message('Daily automation is on. Keep the app open and this computer awake.');}));
$('schedule-pause').addEventListener('click',act(()=>call('schedule',{id:task().id,enabled:false,time:$('schedule-time').value,timezone:$('schedule-zone').value.trim()})));
$('api-enable').addEventListener('click',act(async()=>{await call('configureAPI',{enabled:true,port:Number($('api-port').value)});message('Local API enabled. Use the saved workflow ID and a new request ID for each intended run.');}));
$('api-disable').addEventListener('click',act(()=>call('configureAPI',{enabled:false})));
$('api-copy').addEventListener('click',act(async()=>{await call('copyAPIToken');message('API token copied. The PowerShell client reads it locally without copying.');}));
$('api-export').addEventListener('click',act(async()=>{const file=await call('exportAPIClient');if(file)message('Script client saved: '+file);}));
$('workflow-list').addEventListener('click',act(async event=>{const b=event.target.closest('[data-task-id]');if(b){if(dirty&&!confirm('Discard unsaved edits?'))return;await call('selectTask',{id:b.dataset.taskId});editingId=null;await refresh();}}));
$('history-list').addEventListener('click',act(async event=>{const b=event.target.closest('button');if(!b)return;if(b.dataset.runFolder)await call('showFolder',{runId:b.dataset.runFolder});if(b.dataset.recheckRun){const result=await call('recheckUploads',{runId:b.dataset.recheckRun});message(`${result.confirmed} original(s) confirmed; ${result.missing} still unverified.`,result.missing>0);}if(b.dataset.ackRun){const unresolved=Number(b.dataset.unresolved||0);const wording=unresolved?'I checked the destination gallery and confirmed the unresolved upload'+(unresolved===1?' is':'s are')+' absent. Allow a later run to send those images.':'I inspected the site outcome. A later run may repeat actions.';if(confirm(wording))await call('acknowledge',{runId:b.dataset.ackRun,confirmedAbsent:unresolved>0});}}));
$('address-form').addEventListener('submit',act(async()=>{let url=$('browser-address').value.trim();if(!/^https?:\/\//i.test(url))url='https://'+url;await call('open',{url});}));
for(const [id,name] of [['browser-back','back'],['browser-forward','forward'],['browser-reload','reload']])$(id).addEventListener('click',act(()=>call(name)));
async function newDialog(open){$('new-dialog').hidden=!open;await call('hideBrowser',{hidden:open});if(open)$('new-name').focus();}
$('new-workflow').addEventListener('click',act(()=>newDialog(true)));$('new-close').addEventListener('click',act(()=>newDialog(false)));
$('new-create').addEventListener('click',act(async()=>{const url=$('new-url').value.trim(),type=$('new-type').value;const t=await call('newTask',{name:$('new-name').value.trim()||'My workflow',type,startUrl:url,imageOrigins:[]});await newDialog(false);editingId=null;await refresh();await tab('setup');await call('open',{url:t.startUrl});}));
$('new-pinterest').addEventListener('click',act(async()=>{await call('newTask',{name:'Pinterest images'});await newDialog(false);editingId=null;await refresh();await tab('setup');await call('open',{url:'https://www.pinterest.com/'});}));
$('about').addEventListener('click',()=>message(`HandNavigate ${state.appVersion} · Local desktop runner. Teach supported browser actions and reuse them without AI. Websites with CAPTCHA, unsupported widgets or changed pages may require your attention.`));
new ResizeObserver(syncBounds).observe($('browser-slot'));window.addEventListener('resize',syncBounds);
api.onState(receive);refresh().catch(e=>message(e.message,true));
