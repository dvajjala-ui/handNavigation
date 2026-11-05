'use strict';
const $=id=>document.getElementById(id),token=document.querySelector('meta[name=agent-token]').content;
let initialized=false;
async function api(path,body){const response=await fetch('/api/'+path,{method:body===undefined?'GET':'POST',headers:{'X-Agent-Token':token,...(body===undefined?{}:{'Content-Type':'application/json'})},...(body===undefined?{}:{body:JSON.stringify(body)})});const value=await response.json();if(!response.ok)throw Error(value.error||'Request failed');return value;}
const lines=id=>$(id).value.split('\n').map(s=>s.trim()).filter(Boolean);
function button(text,action,parent){const b=document.createElement('button');b.textContent=text;b.onclick=()=>run(b,action);parent.append(b);}
async function run(control,action){control.disabled=true;try{await action();await refresh();}catch(e){$('message').textContent=e.message;}finally{control.disabled=false;}}
function row(parent,title,value){const article=document.createElement('article'),h=document.createElement('strong'),pre=document.createElement('pre');h.textContent=title;pre.textContent=JSON.stringify(value,null,2);article.append(h,pre);parent.append(article);return article;}
async function refresh(){const state=await api('state');$('status').textContent=state.busy?'Task running':'Runner ready';if(!initialized){const p=state.permissions;$('model').value=state.model;$('roots').value=(p.cleanup_roots||[]).join('\n');$('origins').value=(p.browser_origins||[]).join('\n');$('image-origins').value=(p.image_origins||[]).join('\n');$('uploads').checked=!!p.allow_upload;$('changes').checked=!!p.allow_browser_changes;$('likes').checked=!!p.allow_instagram_likes;initialized=true;}
 $('tasks').replaceChildren();for(const task of state.tasks){const card=row($('tasks'),task.plan.name,{id:task.id,kind:task.plan.kind,schedule:task.plan.schedule,enabled:!!task.enabled,next_due:task.next_due});button('Run now',()=>api('run',{id:task.id}),card);if(task.plan.schedule)button(task.enabled?'Pause daily':'Enable daily',()=>api('schedule',{id:task.id,enabled:!task.enabled}),card);}
 $('runs').replaceChildren();for(const result of state.runs){const card=row($('runs'),result.status+' · '+result.started,result.result);if(result.status==='NEEDS_REVIEW'){button('I inspected: completed',()=>api('reconcile',{id:result.id,decision:'completed'}),card);button('I inspected: effect absent',()=>api('reconcile',{id:result.id,decision:'absent'}),card);}}
}
$('save-setup').onclick=()=>run($('save-setup'),async()=>{await api('setup',{model:$('model').value,permissions:{cleanup_roots:lines('roots'),browser_origins:lines('origins'),image_origins:lines('image-origins'),allow_upload:$('uploads').checked,allow_browser_changes:$('changes').checked,allow_instagram_likes:$('likes').checked}});$('message').textContent='Setup saved. These permissions persist across restarts.';});
$('check-model').onclick=()=>run($('check-model'),async()=>{$('model-state').textContent=JSON.stringify(await api('model'),null,2);});
$('plan').onclick=()=>run($('plan'),async()=>{$('message').textContent='Local model is planning…';const result=await api('plan',{instruction:$('instruction').value});$('draft').value=JSON.stringify(result.plan,null,2);$('message').textContent=JSON.stringify(result.metrics)+'\n'+(result.plan.missing_information.join('\n')||'Review the plan, then save.');});
$('save-task').onclick=()=>run($('save-task'),async()=>{const result=await api('save',{plan:JSON.parse($('draft').value)});$('message').textContent='Task saved: '+result.id;});
$('stop').onclick=()=>run($('stop'),()=>api('stop',{}));
refresh().catch(e=>$('message').textContent=e.message);setInterval(()=>refresh().catch(e=>$('status').textContent=e.message),3000);
let libraryKey='',imageUrls=[];
async function loadLibrary(force=false){
 const source=$('library-source').value,topic=$('library-topic').value;
 let data;
 try{data=await api('collections?source='+encodeURIComponent(source)+'&topic='+encodeURIComponent(topic));}
 catch(e){$('library-summary').textContent='Library unavailable: '+e.message;return;}
 const selected=$('library-topic').value,jobSelected=$('collection-topic').value;
 $('library-topic').replaceChildren(new Option('All content',''));
 $('collection-topic').replaceChildren();
 for(const option of data.topics){$('library-topic').add(new Option(option.label,option.key));$('collection-topic').add(new Option(option.label+(option.pinterest_verified?'':' · unverified Pinterest source'),option.key));}
 $('library-topic').value=selected;$('collection-topic').value=jobSelected||'travel';
 $('library-summary').textContent=data.images.length+' shown · '+data.counts.map(x=>x.source+' / '+x.topic_key+': '+x.count).join(' · ');
 $('collection-jobs').replaceChildren();
 for(const job of data.jobs){
  const card=row($('collection-jobs'),job.name,{source:job.source,topic:job.random_topic?'Verified topic rotation':job.topic_key,count:job.image_count,time:job.daily_time,timezone:job.timezone,enabled:job.enabled,id:job.id});
  button('Run now',async()=>{await api('collection-run',{id:job.id});$('message').textContent='Collection started. Refresh the library to see its result.';},card);
  button(job.enabled?'Pause daily':'Enable daily',async()=>{await api('collection-schedule',{id:job.id,enabled:!job.enabled});await loadLibrary(true);},card);
 }
 $('collection-runs').replaceChildren();
 for(const entry of data.runs){row($('collection-runs'),entry.status+' · '+entry.started_at,{source:entry.source,topic:entry.topic_key,requested:entry.requested,downloaded:entry.downloaded,stored:entry.stored,error:entry.error});}
 const key=source+'|'+topic+'|'+data.images.map(x=>x.id).join(',');
 if(!force&&key===libraryKey)return;
 libraryKey=key;for(const old of imageUrls)URL.revokeObjectURL(old);imageUrls=[];$('gallery').replaceChildren();
 for(const item of data.images.slice(0,40)){
  const figure=document.createElement('figure'),img=document.createElement('img'),caption=document.createElement('figcaption'),link=document.createElement('a');
  img.alt=item.topic_key+' image from '+item.source;img.loading='lazy';
  link.href=item.source_page_url;link.target='_blank';link.rel='noopener noreferrer';link.textContent=item.source+' · '+item.topic_key;
  caption.append(link,document.createTextNode(' · '+item.width+'×'+item.height+' · '+item.rendition));
  figure.append(img,caption);$('gallery').append(figure);
  try{const response=await fetch('/api/collection-image/'+encodeURIComponent(item.id),{headers:{'X-Agent-Token':token}});
      if(!response.ok)throw Error('Image unavailable');const url=URL.createObjectURL(await response.blob());imageUrls.push(url);img.src=url;
  }catch(e){img.alt='Image failed verification';}
 }
}
$('refresh-library').onclick=()=>run($('refresh-library'),()=>loadLibrary(true));
$('library-source').onchange=()=>loadLibrary(true);
$('library-topic').onchange=()=>loadLibrary(true);
$('create-collection-job').onclick=()=>run($('create-collection-job'),async()=>{
 const body={name:$('collection-name').value,source:$('collection-source').value,
  topic_key:$('collection-topic').value,random_topic:$('collection-random').checked,
  image_count:Number($('collection-count').value),daily_time:$('collection-time').value,timezone:'Asia/Kolkata'};
 const result=await api('collection-jobs',body);$('message').textContent='Collection job saved, paused: '+result.id;await loadLibrary(true);
});
loadLibrary().catch(e=>$('library-summary').textContent=e.message);
setInterval(()=>loadLibrary().catch(()=>{}),30000);
