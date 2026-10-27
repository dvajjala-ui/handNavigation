const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {draft,Store,taskHash,validate,interpolate,siteUrl,DailyQueue,dueAt,occurrenceOn}=require('../core.cjs');
const {imageInfo}=require('../engine.cjs');
const sharp=require('sharp');
function fixture(t){const folder=fs.mkdtempSync(path.join(os.tmpdir(),'handnavigate-desktop-test-'));t.after(()=>fs.rmSync(folder,{recursive:true,force:true}));return {folder,store:new Store(folder)};}
function task(folder){return draft({startUrl:'https://owned.example/images?q={{topic}}',outputFolder:folder,imageOrigins:[]});}
test('variable interpolation is explicit and URL values cannot change origins',()=>{
  assert.equal(interpolate('Ready: {{topic}}',{topic:'gardens'}),'Ready: gardens');
  assert.equal(siteUrl('https://owned.example?q={{topic}}',{topic:'a&b'}),'https://owned.example/?q=a%26b');
  assert.throws(()=>interpolate('{{unknown}}',{}));
});
test('approval binds all execution fields and changes invalidate rehearsals',t=>{
  const {folder,store}=fixture(t);let saved=store.save(task(folder));store.approve(saved.id,saved.sha);
  const run=store.begin(saved.id,0);store.finish(run,'VERIFIED');assert.equal(store.get(saved.id).rehearsals.length,1);
  saved=store.save({...saved,count:10});assert.equal(saved.approvedSha,null);assert.deepEqual(saved.rehearsals,[]);
  assert.throws(()=>store.begin(saved.id,0));
});
test('changing a workflow title preserves exact executable approval',t=>{
  const {folder,store}=fixture(t);let saved=store.save(task(folder));store.approve(saved.id,saved.sha);
  saved=store.save({...saved,name:'Renamed'});assert.equal(saved.approvedSha,saved.sha);
});
test('replay drafts can be saved but require output checks before approval',t=>{
  const {folder,store}=fixture(t);const saved=store.save({...task(folder),type:'replay'});
  assert.throws(()=>store.approve(saved.id,saved.sha),/result check/);
});
test('invalid primitives, unknown actions and blocked recordings are rejected',()=>{
  const d=task(os.tmpdir());assert.throws(()=>validate({...d,count:true}));
  assert.throws(()=>validate({...d,steps:[{op:'script',value:'alert(1)'}]}));
  assert.throws(()=>validate({...d,steps:[{op:'fill',blocked:'private'}]}));
});
test('restarting preserves task state and marks interrupted remote work for review',t=>{
  const {folder,store}=fixture(t);const saved=store.save(task(folder));store.approve(saved.id,saved.sha);store.begin(saved.id,0);
  const reopened=new Store(folder);assert.equal(reopened.data.runs[0].status,'NEEDS_REVIEW');assert.equal(reopened.get(saved.id).approvedSha,saved.sha);
});
test('corrupt primary database restores its last integrity-checked backup',t=>{
  const {folder,store}=fixture(t);const saved=store.save(task(folder));store.approve(saved.id,saved.sha);fs.writeFileSync(store.file,'broken');
  const reopened=new Store(folder);assert.equal(reopened.data.tasks.length,1);assert.equal(reopened.data.runs[0].status,'NEEDS_REVIEW');
  assert.notEqual(fs.readFileSync(store.file+'.bak','utf8'),'broken');
  assert.equal(fs.readdirSync(folder).filter(name=>name.includes('.corrupt-')).length,1);
});
test('uncertain uploads need explicit absence confirmation before later retries',t=>{
  const {folder,store}=fixture(t);const saved=store.save({...task(folder),type:'transfer',target:{url:'https://owned.example/upload',galleryUrl:'https://owned.example/gallery',gallerySelector:'img',fileInput:{kind:'css',value:'input[type=file]'}}});
  store.approve(saved.id,saved.sha);const run=store.begin(saved.id,0);run.items.push({sha256:'a'.repeat(64),state:'UPLOADING'});store.finish(run,'NEEDS_REVIEW');
  assert.throws(()=>store.acknowledge(run.id),/explicitly confirm/);
  store.acknowledge(run.id,{confirmedAbsent:true});assert.equal(run.acknowledged,true);assert.equal(run.items[0].state,'RESOLVED_NOT_UPLOADED');
  assert.equal(new Store(folder).data.runs[0].items[0].state,'RESOLVED_NOT_UPLOADED');
});
test('schedule requires every row to have a verified rehearsal',t=>{
  const {folder,store}=fixture(t);const saved=store.save({...task(folder),rows:[{topic:'one'},{topic:'two'}]});store.approve(saved.id,saved.sha);
  const q=new DailyQueue(store,async()=>({status:'VERIFIED'}));assert.throws(()=>q.enable(saved.id,true,'09:00','Asia/Kolkata'));
  for(let i=0;i<2;i++){const r=store.begin(saved.id,i);store.finish(r,'VERIFIED');}
  q.enable(saved.id,true,'09:00','Asia/Kolkata');assert.equal(saved.schedule.enabled,true);
});
test('daily runs rotate variable rows and never replay the same occurrence',async t=>{
  const {folder,store}=fixture(t);const saved=store.save({...task(folder),rows:[{topic:'one'},{topic:'two'}]});store.approve(saved.id,saved.sha);saved.rehearsals=[0,1];
  let now=Date.parse('2026-10-26T03:00:00Z'),calls=[];const q=new DailyQueue(store,async(id,row)=>{calls.push(row);return {status:'VERIFIED'};},()=>now);
  q.enable(saved.id,true,'09:00','Asia/Kolkata');now=Date.parse('2026-10-26T03:30:00Z');await q.tick();await q.tick();assert.deepEqual(calls,[0]);
  now+=86400000;await q.tick();assert.deepEqual(calls,[0,1]);
});
test('missed days materialize only the latest occurrence',async t=>{
  const {folder,store}=fixture(t);const saved=store.save(task(folder));store.approve(saved.id,saved.sha);saved.rehearsals=[0];
  let now=Date.parse('2026-10-26T03:00:00Z'),calls=0;const q=new DailyQueue(store,async()=>{calls++;return {status:'VERIFIED'};},()=>now);
  q.enable(saved.id,true,'09:00','Asia/Kolkata');now+=7*86400000;await q.tick();assert.equal(calls,1);
});
test('non-verified daily outcomes pause the workflow',async t=>{
  const {folder,store}=fixture(t);const saved=store.save(task(folder));store.approve(saved.id,saved.sha);saved.rehearsals=[0];
  let now=Date.parse('2026-10-26T03:00:00Z');const q=new DailyQueue(store,async()=>({status:'PARTIAL'}),()=>now);
  q.enable(saved.id,true,'09:00','Asia/Kolkata');now+=3600000;await q.tick();assert.equal(saved.schedule.enabled,false);
});

test('a busy browser defers a due occurrence without consuming it or disabling the schedule',async t=>{
  const {folder,store}=fixture(t),saved=store.save(task(folder));store.approve(saved.id,saved.sha);saved.rehearsals=[0];
  let now=Date.parse('2026-10-26T03:00:00Z'),ready=false,calls=0;
  const queue=new DailyQueue(store,async()=>{calls++;return {status:'VERIFIED'};},()=>now,()=>ready);
  queue.enable(saved.id,true,'09:00','Asia/Kolkata');const due=saved.schedule.nextDue;now+=3600000;
  assert.deepEqual(await queue.tick(),[]);assert.equal(saved.schedule.nextDue,due);assert.equal(saved.schedule.enabled,true);assert.equal(Object.keys(store.data.occurrences).length,0);
  ready=true;await queue.tick();await queue.tick();assert.equal(calls,1);assert.equal(saved.schedule.enabled,true);
});

test('the queue checks browser availability again between due workflows',async t=>{
  const {folder,store}=fixture(t),tasks=[store.save(task(folder)),store.save({...task(folder),name:'Second'})];
  for(const saved of tasks){store.approve(saved.id,saved.sha);saved.rehearsals=[0];}
  let now=Date.parse('2026-10-26T03:00:00Z'),ready=true;const calls=[];
  const queue=new DailyQueue(store,async id=>{calls.push(id);ready=false;return {status:'VERIFIED'};},()=>now,()=>ready);
  for(const saved of tasks)queue.enable(saved.id,true,'09:00','Asia/Kolkata');now+=3600000;
  await queue.tick();assert.deepEqual(calls,[tasks[0].id]);assert.equal(tasks[1].schedule.enabled,true);
  ready=true;await queue.tick();assert.deepEqual(calls,tasks.map(t=>t.id));
});
test('DST nonexistent times skip and repeated times choose first occurrence',()=>{
  assert.equal(occurrenceOn({year:2026,month:3,day:8},{time:'02:30',timezone:'America/New_York'}),null);
  assert.equal(new Date(occurrenceOn({year:2026,month:11,day:1},{time:'01:30',timezone:'America/New_York'})).toISOString(),'2026-11-01T05:30:00.000Z');
  assert.equal(new Date(dueAt({time:'09:00',timezone:'Asia/Kolkata'},Date.parse('2026-10-26T03:30:00Z'))).toISOString(),'2026-10-27T03:30:00.000Z');
});
test('real JPEG PNG and WebP decoding checks content and rejects HTML',async()=>{
  for(const format of ['jpeg','png','webp']){const bytes=await sharp({create:{width:200,height:180,channels:3,background:'#44aa77'}}).toFormat(format).toBuffer();const meta=await imageInfo(bytes);assert.equal(meta.format,format);assert.equal(meta.width,200);assert.equal(meta.sha256.length,64);}
  await assert.rejects(imageInfo(Buffer.from('<html>Login required</html>')));
});
