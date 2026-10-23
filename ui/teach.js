(() => {
'use strict';
const $=id=>document.getElementById(id);
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const PREVIEW=window.__HANDNAVIGATE_TEACHING_PREVIEW||null;
const readOnly=Boolean(PREVIEW);
const csrf='__CSRF_TOKEN__';
const fieldNames={topic:'Topic',layout:'Layout',captions:'Include captions'};
let state={lessons:[],runs:[],active_id:null,error:null}, selected=null, recording=[], rows=[], plan=null;
let planRequestId=null, planConsumed=false, currentStage='record', pending=false;
let recipeSignature='', historySignature='', selectSignature='', toastTimer;
const practice=$('owned-workspace');
HandNavigatePractice.mount(practice);
const recorder=new HandNavigateTeachingRecorder(practice,snapshot=>{
 recording=snapshot.events;
 renderEvents();
 $('record-status').textContent=recorder.active?'Recording':'Recording stopped';
 $('record-status').className='recording-status'+(recorder.active?' active':'');
 updateButtons();
});
function newRequestId(){
 if(!globalThis.crypto || !crypto.getRandomValues)throw new Error('Secure request IDs are unavailable in this browser. Execution remains disabled.');
 const bytes=crypto.getRandomValues(new Uint8Array(16));bytes[6]=(bytes[6]&15)|64;bytes[8]=(bytes[8]&63)|128;
 const hex=Array.from(bytes,b=>b.toString(16).padStart(2,'0')).join('');
 return hex.slice(0,8)+'-'+hex.slice(8,12)+'-'+hex.slice(12,16)+'-'+hex.slice(16,20)+'-'+hex.slice(20);
}
function toast(message){$('toast').textContent=message;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,6000);}
async function api(path,body){
 if(readOnly)throw new Error('Read-only preview: no changes or execution are available.');
 const response=await fetch(path,body===undefined?{cache:'no-store'}:{method:'POST',headers:{'Content-Type':'application/json','X-HandNavigate-Token':csrf},body:JSON.stringify(body)});
 const result=await response.json();if(!response.ok)throw new Error(result.error||'Request failed');return result;
}
function action(id,fn){$(id).addEventListener('click',async()=>{if(pending||readOnly)return;pending=true;updateButtons();try{await fn();}catch(error){toast(error.message);}finally{pending=false;updateButtons();}});}
function stage(name){
 if(recorder.active && name!=='record'){recorder.stop();$('record-provenance').textContent='Browser events captured in the owned practice form. Capture alone does not prove a human performed them.';}
 currentStage=name;
 for(const node of document.querySelectorAll('[data-stage]')){const active=node.dataset.stage===name;node.classList.toggle('active',active);node.setAttribute('aria-selected',String(active));}
 for(const name of ['record','review','rehearse'])$('stage-'+name).hidden=name!==currentStage;
}
for(const button of document.querySelectorAll('[data-stage]'))button.addEventListener('click',()=>stage(button.dataset.stage));
function eventDescription(event){
 if(event.op==='blocked')return ['Blocked action',event.reason];
 if(event.op==='click')return ['Click Prepare preview','Owned form only'];
 return [(event.op==='fill'?'Fill ':event.op==='select'?'Select ':'Set ')+fieldNames[event.field],typeof event.value==='boolean'?(event.value?'Checked':'Unchecked'):event.value];
}
function renderEvents(){
 $('event-list').innerHTML=recording.length?recording.map((event,i)=>{const [title,value]=eventDescription(event);return '<div class="event"><span class="event-num">'+(i+1)+'</span><div><strong>'+esc(title)+'</strong><small>'+esc(value)+'</small></div></div>';}).join(''):'<div class="empty"><strong>Start with a demonstration</strong>Your inputs and clicks will appear here.<br>No screen-wide recording.</div>';
 renderBindings();
}
function renderBindings(){
 const existing={};for(const field of Object.keys(fieldNames)){if($('bind-mode-'+field))existing[field]={mode:$('bind-mode-'+field).value,name:$('bind-name-'+field).value};}
 const final={};for(const event of recording)if(event.field)final[event.field]=event.value;
 $('bindings').innerHTML=Object.keys(fieldNames).map(field=>'<div class="binding-grid"><div><strong>'+fieldNames[field]+'</strong><small>Example: '+esc(final[field]===undefined?'not recorded':JSON.stringify(final[field]))+'</small></div><select id="bind-mode-'+field+'" aria-label="'+fieldNames[field]+' binding"><option value="variable">Variable</option><option value="constant">Keep fixed</option></select><input id="bind-name-'+field+'" aria-label="'+fieldNames[field]+' variable name" value="'+field+'" maxlength="32"></div>').join('');
 for(const field of Object.keys(fieldNames)){
  if(existing[field]){$('bind-mode-'+field).value=existing[field].mode;$('bind-name-'+field).value=existing[field].name;}
  $('bind-name-'+field).disabled=readOnly||$('bind-mode-'+field).value==='constant';
  $('bind-mode-'+field).disabled=readOnly;
  $('bind-mode-'+field).addEventListener('change',()=>{$('bind-name-'+field).disabled=$('bind-mode-'+field).value==='constant';});
 }
}
function clearPlan(){plan=null;planRequestId=null;planConsumed=false;$('plan-consent').checked=false;renderPlan();updateButtons();}
function setLesson(lesson){
 const changed=selected?.sha256!==lesson?.sha256||selected?.id!==lesson?.id;
 selected=lesson;
 if(changed){rows=[];clearPlan();if(selected)rows=[defaultRow(1)];renderRows();}
 const signature=JSON.stringify(selected);
 if(signature!==recipeSignature){recipeSignature=signature;$('approval-consent').checked=false;renderRecipe();}
 if(selected)$('lesson-select').value=selected.id;
 updateButtons();
}
function parameterEntries(){
 const names=Object.keys(fieldNames).map(field=>selected.recipe.verification.expected[field].parameter).filter(Boolean);
 for(const name of Object.keys(selected.recipe.parameters))if(!names.includes(name))names.push(name);
 return names.map(name=>[name,selected.recipe.parameters[name]]);
}
function runTime(value){
 try{return new Intl.DateTimeFormat('en-IN',{timeZone:'Asia/Kolkata',dateStyle:'medium',timeStyle:'short'}).format(new Date(value))+' IST';}
 catch(_){return String(value);}
}
function defaultValues(index){
 const examples=[{topic:'architecture',layout:'detailed',captions:true},{topic:'city gardens',layout:'compact',captions:false},{topic:'quiet interiors',layout:'detailed',captions:true}];
 const input=examples[(index-1)%examples.length];const values={};
 for(const [field,source] of Object.entries(selected.recipe.verification.expected))if(source.parameter)values[source.parameter]=input[field];
 return values;
}
function defaultRow(index){return {row_id:'row-'+index,values:defaultValues(index)};}
function renderRecipe(){
 $('lesson-badge').textContent=selected?(selected.approved?'APPROVED':'REVIEW REQUIRED'):'NO DRAFT';
 $('lesson-badge').className='chip '+(selected?.approved?'green':'amber');
 if(!selected){$('recipe-summary').className='empty';$('recipe-summary').innerHTML='<strong>No compiled draft yet</strong>Record or load an example, then define its bindings.';$('recipe-json').textContent='No recipe';$('recipe-hash').textContent='';return;}
 const recipe=selected.recipe;$('recipe-summary').className='';
 $('recipe-summary').innerHTML='<strong>'+esc(recipe.name)+'</strong><p>'+recipe.steps.length+' actions per row &middot; '+Object.keys(recipe.parameters).length+' variables &middot; at most '+recipe.repeat.max_rows+' rows</p>'+recipe.steps.map((step,i)=>'<div class="event"><span class="event-num">'+(i+1)+'</span><div><strong>'+esc(step.op==='click'?'Click Prepare preview':step.op+' '+fieldNames[step.field])+'</strong><small>'+esc(step.value?(step.value.parameter?'{{'+step.value.parameter+'}}':JSON.stringify(step.value.literal)):'Then verify all three displayed values')+'</small></div></div>').join('')+'<div class="hint" style="margin-top:12px"><strong>Verified, not merely replayed.</strong><br>Every row must match all three expected output values. Stop on the first mismatch.</div>';
 $('recipe-json').textContent=JSON.stringify(recipe,null,2);$('recipe-hash').textContent='SHA-256 '+selected.sha256;
}
function renderRows(){
 if(!selected){$('row-editor').innerHTML='<div class="empty">Select or compile a lesson first.</div>';return;}
 $('row-editor').innerHTML=rows.map((row,index)=>'<div class="row-editor"><div class="row-top"><input aria-label="Row '+(index+1)+' identity" data-rowid="'+index+'" value="'+esc(row.row_id)+'" maxlength="64"><button class="small" data-remove-row="'+index+'" '+(rows.length===1?'disabled':'')+'>Remove</button></div><div class="row-variables">'+parameterEntries().map(([key,spec])=>spec.type==='boolean'?'<label class="check"><input type="checkbox" data-row="'+index+'" data-key="'+esc(key)+'" '+(row.values[key]?'checked':'')+'>'+esc(key)+'</label>':'<label class="form-field">'+esc(key)+(spec.type==='enum'?'<select data-row="'+index+'" data-key="'+esc(key)+'">'+spec.choices.map(value=>'<option '+(row.values[key]===value?'selected':'')+' value="'+esc(value)+'">'+esc(value)+'</option>').join('')+'</select>':'<input data-row="'+index+'" data-key="'+esc(key)+'" value="'+esc(row.values[key])+'" maxlength="80">')+'</label>').join('')+'</div></div>').join('');
 for(const input of $('row-editor').querySelectorAll('[data-row]')){
  input.disabled=readOnly;
  input.addEventListener('input',()=>{rows[Number(input.dataset.row)].values[input.dataset.key]=input.type==='checkbox'?input.checked:input.value;clearPlan();});
 }
 for(const input of $('row-editor').querySelectorAll('[data-rowid]')){input.disabled=readOnly;input.addEventListener('input',()=>{rows[Number(input.dataset.rowid)].row_id=input.value;clearPlan();});}
 for(const button of $('row-editor').querySelectorAll('[data-remove-row]')){button.disabled=readOnly||rows.length===1;button.addEventListener('click',()=>{rows.splice(Number(button.dataset.removeRow),1);clearPlan();renderRows();});}
}
function renderPlan(){
 $('plan-badge').textContent=plan?(planConsumed?'EXECUTION SUBMITTED':'REVIEW REQUIRED'):'PLAN REQUIRED';
 $('plan-badge').className='chip '+(planConsumed?'green':'amber');
 $('plan-json').textContent=plan?JSON.stringify(plan,null,2):'No reviewed plan';
 $('plan-summary').className=plan?'':'empty';
 $('plan-summary').innerHTML=plan?'<strong>'+plan.row_count+' rows &middot; '+plan.action_count+' actions &middot; '+plan.assertion_count+' checks</strong><p>No model calls. No external writes. Stop on first failed verification.</p>'+plan.rows.map(row=>'<div class="plan-item"><strong>'+esc(row.row_id)+'</strong><p>'+esc(row.expected.topic)+' &middot; '+esc(row.expected.layout)+' &middot; captions '+(row.expected.captions?'on':'off')+'</p></div>').join('')+'<div class="hash">Plan '+esc(plan.plan_sha256)+'</div>':'<strong>Review the actual inputs</strong>Preview the plan to see every expected result.';
}
function renderHistory(){
 const signature=JSON.stringify([state.runs,state.active_id,state.error]);if(signature===historySignature)return;historySignature=signature;
 const latest=state.runs.find(run=>run.report);
 $('metric-rows').textContent=latest?latest.report.verified_rows+' / '+latest.report.input_rows:'--';
 $('metric-models').textContent=latest?String(latest.report.model_calls):'--';
 $('history-count').textContent=state.runs.length+' RUN'+(state.runs.length===1?'':'S');
 $('run-history').innerHTML=state.runs.length?state.runs.slice(0,8).map(run=>{
  const report=run.report;
  return '<div class="receipt"><div class="receipt-top"><strong>'+esc(runTime(run.created_at))+'</strong><span class="chip '+(run.state==='VERIFIED'?'green':'amber')+'">'+esc(run.state)+'</span></div>'+(report?'<p>'+report.verified_rows+' / '+report.input_rows+' rows verified &middot; '+report.model_calls+' model calls</p>'+(report.error?'<p>'+esc(report.error.code+': '+report.error.message)+'</p>':'')+'<ul>'+report.rows.map(row=>'<li>'+esc(row.row_id)+': '+esc(row.observed.topic)+' <a '+(readOnly?'title="Artifact is included in the source package"':'href="/api/teaching/artifact?run='+encodeURIComponent(run.id)+'&row='+encodeURIComponent(row.row_id)+'" target="_blank" rel="noopener"')+'>verified receipt</a></li>').join('')+'</ul>':'<p>Awaiting evidence. A running state is not verified completion.</p>')+(run.state==='NEEDS_REVIEW'?'<div class="hint">Interrupted work is never retried automatically.</div><button class="small" data-ack="'+esc(run.id)+'" '+(readOnly?'disabled':'')+'>Acknowledge without retry</button>':'')+'</div>';
 }).join(''):'<div class="empty">Verified rows and halted runs will appear here.</div>';
 for(const button of $('run-history').querySelectorAll('[data-ack]'))button.addEventListener('click',async()=>{try{await api('/api/teaching/acknowledge',{run_id:button.dataset.ack,acknowledgement:'REVIEWED_WITHOUT_RETRY'});await refresh();}catch(e){toast(e.message);}});
 $('run-status').textContent=state.error|| (state.active_id?'Rehearsal is running. Stop is cooperative at step boundaries.':readOnly?'Recorded evidence only. No runner exists in this preview.':'No active rehearsal. The local studio must stay open.');
}
function updateButtons(){
 const disabled=readOnly||pending;
 $('record-start').disabled=disabled||recorder.active||!$('record-consent').checked;
 $('record-stop').disabled=disabled||!recorder.active;$('capture-inputs').disabled=disabled||!recorder.active;
 $('continue-review').disabled=disabled||!recording.length;$('load-demo').disabled=disabled||recorder.active;
 $('compile-lesson').disabled=disabled||recording.length<4||!$('verifier-consent').checked;
 $('approval-consent').disabled=disabled||!selected||selected.approved;
 $('approve-lesson').disabled=disabled||!selected||selected.approved||!$('approval-consent').checked;
 $('export-lesson').disabled=disabled||!selected;$('revoke-lesson').disabled=disabled||!selected?.approved||Boolean(state.active_id);
 $('to-rehearse').disabled=disabled||!selected;
 $('demo-rows').disabled=disabled||!selected;
 $('add-row').disabled=disabled||!selected||rows.length>=selected.recipe.repeat.max_rows;
 $('preview-plan').disabled=disabled||!selected||!rows.length;
 $('plan-consent').disabled=disabled||!plan||planConsumed;
 $('run-lesson').disabled=disabled||!selected?.approved||!plan||!planRequestId||planConsumed||!$('plan-consent').checked||Boolean(state.active_id)||Boolean(state.error);
 $('stop-lesson').disabled=disabled||!state.active_id;
 $('import-button').disabled=disabled;
}
async function refresh(){
 const data=readOnly?PREVIEW.state:await api('/api/teaching');state=data;
 const signature=JSON.stringify(state.lessons.map(l=>[l.id,l.sha256,l.approved]));
 if(signature!==selectSignature){selectSignature=signature;$('lesson-select').innerHTML='<option value="">Create a new lesson</option>'+state.lessons.map(lesson=>'<option value="'+esc(lesson.id)+'">'+esc(lesson.recipe.name)+(lesson.approved?' - approved':' - draft')+'</option>').join('');}
 if(selected){const updated=state.lessons.find(l=>l.id===selected.id);if(updated)setLesson(updated);}
 else if(state.lessons.length&&!recording.length)setLesson(state.lessons[0]);
 renderHistory();updateButtons();
}
for(const id of ['record-consent','verifier-consent','approval-consent','plan-consent'])$(id).addEventListener('change',updateButtons);
$('lesson-select').addEventListener('change',()=>setLesson(state.lessons.find(l=>l.id===$('lesson-select').value)||null));
action('record-start',()=>{setLesson(null);$('record-provenance').textContent='Recording only this owned form. Stop before leaving the practice workspace.';recorder.start();});
action('record-stop',()=>{recorder.stop();$('record-provenance').textContent='Browser events captured in the owned practice form; capture alone does not prove a human performed them.';});
action('capture-inputs',()=>{recorder.captureInputs();toast('Current values recorded explicitly. Now click Prepare preview.');});
action('continue-review',()=>stage('review'));
action('load-demo',()=>{recorder.stop();recording=[{op:'fill',field:'topic',value:'architecture'},{op:'select',field:'layout',value:'detailed'},{op:'check',field:'captions',value:true},{op:'click',control:'prepare'}];$('record-provenance').textContent='Synthetic sample trace, not recorded from your actions.';renderEvents();});
action('compile-lesson',async()=>{
 const bindings={};for(const field of Object.keys(fieldNames)){const mode=$('bind-mode-'+field).value;bindings[field]=mode==='constant'?{mode}:{mode,name:$('bind-name-'+field).value};}
 const result=await api('/api/teaching/compile',{events:recording,bindings,name:$('lesson-name').value,verification_contract:'inputs_match_preview_v1',max_rows:Number($('repeat-limit').value)});
 setLesson(result);await refresh();toast('Draft compiled. Inspect its exact actions before approving.');
});
action('approve-lesson',async()=>{setLesson(await api('/api/teaching/approve',{lesson_id:selected.id,reviewed_sha256:selected.sha256,acknowledgement:$('approval-consent').checked}));await refresh();toast('Exact recipe approved. Input plans still need review.');});
action('revoke-lesson',async()=>{setLesson(await api('/api/teaching/revoke',{lesson_id:selected.id}));clearPlan();await refresh();toast('Approval revoked. Nothing was retried.');});
action('export-lesson',()=>{const blob=new Blob([JSON.stringify(selected.recipe,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download='handnavigate-lesson.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);toast('Recipe exported without approval or credentials. Constants are included.');});
action('import-button',async()=>{const recipe=JSON.parse($('import-recipe').value);setLesson(await api('/api/teaching/import',{recipe}));await refresh();toast('Imported as an unapproved draft.');});
action('to-rehearse',()=>stage('rehearse'));
action('demo-rows',()=>{rows=[1,2,3].slice(0,selected.recipe.repeat.max_rows).map(defaultRow);clearPlan();renderRows();});
action('add-row',()=>{let index=rows.length+1;while(rows.some(row=>row.row_id==='row-'+index))index++;rows.push(defaultRow(index));clearPlan();renderRows();});
action('preview-plan',async()=>{
 const snapshot=JSON.stringify(rows), lessonId=selected.id;
 const result=await api('/api/teaching/plan',{lesson_id:lessonId,rows});
 if(selected?.id!==lessonId||JSON.stringify(rows)!==snapshot)throw new Error('Inputs changed during preview; request a new plan.');
 const requestId=newRequestId();plan=result;planConsumed=false;planRequestId=requestId;$('plan-consent').checked=false;renderPlan();
});
action('run-lesson',async()=>{
 const result=await api('/api/teaching/run',{lesson_id:selected.id,rows,reviewed_plan_sha256:plan.plan_sha256,request_id:planRequestId});
 planConsumed=true;$('plan-consent').checked=false;renderPlan();await refresh();toast(result.deduplicated?'This request was already accepted; no duplicate run was started.':'Rehearsal started. Inspect the verified rows in history.');
});
action('stop-lesson',async()=>{await api('/api/teaching/stop',{run_id:state.active_id});toast('Stop requested. Waiting for a safe step boundary.');});
renderBindings();renderPlan();renderRows();
if(readOnly){
 $('preview-notice').hidden=false;
 for(const id of ['brand-link','studio-link','schedules-link','connections-link'])$(id).removeAttribute('href');
 for(const node of document.querySelectorAll('input,textarea,select'))node.disabled=true;
 for(const node of practice.querySelectorAll('button'))node.disabled=true;
 $('lesson-select').disabled=false;
 if(PREVIEW.recording){recording=PREVIEW.recording;renderEvents();$('record-provenance').textContent='Recorded Chromium events driven by an automated test, not human teaching.';}
}
(async()=>{try{await refresh();if(readOnly){
 if(PREVIEW.lesson_id)setLesson(state.lessons.find(l=>l.id===PREVIEW.lesson_id)||selected);
 if(PREVIEW.rows){rows=PREVIEW.rows;renderRows();}if(PREVIEW.plan){plan=PREVIEW.plan;planConsumed=true;renderPlan();}
 stage(PREVIEW.stage||'rehearse');updateButtons();
 }else setInterval(()=>refresh().catch(e=>{$('run-status').textContent='Status unavailable: '+e.message;}),1600);
}catch(e){toast(e.message);}})();
})();
