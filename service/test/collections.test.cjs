'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),http=require('node:http');
const {createServer}=require('../server.cjs'),{fixture}=require('../../desktop/test/fixture.cjs'),{imageInfo}=require('../../desktop/engine.cjs');
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function wait(get,id){for(let n=0;n<900;n++){const job=await get(id);if(!['QUEUED','RUNNING','WAITING_FOR_LOGIN'].includes(job.status))return job;await pause(100);}throw new Error('Collection did not finish');}
test('real worker API collects 20 total across topics and sources, persists idempotency, dedup and a daily cap',async t=>{
  const site=await fixture(),folder=fs.mkdtempSync(path.join(os.tmpdir(),'handnavigate-service-test-'));
  const source=id=>({id,searchUrl:site.origin+'/images?topic={{topic}}',selector:'#gallery img',allowedOrigins:[site.origin],imageOrigins:[],pagination:{kind:'none',maxPages:1}});
  const options={folder,token:'test-secret-'.repeat(5),dailyLimit:24,sources:[source('one'),source('two')],browser:{headless:true,...(process.platform==='win32'?{channel:'chrome'}:{})}};
  let app=createServer(options);await new Promise(resolve=>app.server.listen(0,'127.0.0.1',resolve));
  let endpoint='http://127.0.0.1:'+app.server.address().port,headers={Authorization:'Bearer '+app.token,'Content-Type':'application/json'};
  const post=async body=>{const response=await fetch(endpoint+'/v1/collections',{method:'POST',headers,body:JSON.stringify(body)});return {status:response.status,body:await response.json()};};
  const get=async id=>(await fetch(endpoint+'/v1/collections/'+id,{headers})).json();
  t.after(async()=>{await app.close();await site.close();if(path.resolve(folder).startsWith(path.resolve(os.tmpdir())+path.sep))fs.rmSync(folder,{recursive:true,force:true,maxRetries:10,retryDelay:500});});
  assert.equal((await fetch(endpoint+'/v1/health')).status,401);assert.equal((await fetch(endpoint+'/v1/health',{headers:{...headers,Origin:'https://evil.example'}})).status,403);
  const spec={requestId:'two-platform-twenty-001',topics:['landscape','architecture'],sources:['one','two'],limit:20,destination:'local'};
  const start=await post(spec);assert.equal(start.status,202,JSON.stringify(start));const repeated=await post(spec);assert.equal(repeated.body.id,start.body.id);assert.equal(repeated.body.reused,true);
  let job=await wait(get,start.body.id);assert.equal(job.status,'VERIFIED_LOCAL',JSON.stringify(job));assert.equal(job.items.length,20);assert.equal(new Set(job.items.map(i=>i.sha256)).size,20);assert.equal(new Set(job.items.map(i=>i.topic)).size,2);assert.equal(new Set(job.items.map(i=>i.platform)).size,2);const firstHashes=new Set(job.items.map(i=>i.sha256));
  for(const item of job.items)assert.equal((await imageInfo(fs.readFileSync(item.file))).sha256,item.sha256);
  assert.equal((await post({...spec,limit:21})).status,409);
  const next=await post({...spec,requestId:'next-day-style-same-topics',limit:4});job=await wait(get,next.body.id);assert.equal(job.status,'VERIFIED_LOCAL',JSON.stringify(job));assert.equal(job.items.length,4);assert.equal(job.items.some(i=>firstHashes.has(i.sha256)),false);
  assert.equal((await post({...spec,requestId:'over-budget-request'})).status,409);
  await app.close();app=createServer(options);await new Promise(resolve=>app.server.listen(0,'127.0.0.1',resolve));endpoint='http://127.0.0.1:'+app.server.address().port;
  assert.equal((await post(spec)).body.id,start.body.id);assert.equal(app.collections.used(),24);
});
test('request contracts reject arbitrary sources and unsafe site recipes',()=>{
  const {sources,request}=require('../sources.cjs'),registry=sources();
  assert.throws(()=>request({requestId:'valid-request',topics:['cats'],sources:['https://unreviewed.example'],limit:20},registry),/configured source/);
  assert.throws(()=>request({requestId:'valid-request',topics:['cats'],sources:['reddit'],limit:1000},registry),/bound/);
  assert.throws(()=>sources([{...registry[0],searchUrl:'file:///{{topic}}'}]));
  assert.throws(()=>request({requestId:'valid-request',topics:['cats\nsecret'],sources:['reddit']},registry));
  assert.throws(()=>request({requestId:12345678,topics:['cats'],sources:['reddit']},registry));
});

test('delivery resumes saved sources after failure and a changed local file cannot become verified',async t=>{
  const {Collections}=require('../collections.cjs'),site=await fixture(),folder=fs.mkdtempSync(path.join(os.tmpdir(),'handnavigate-resume-test-'));let reject=true,calls=0;
  const collector=new Collections(folder,{dailyLimit:4,browser:{headless:true,...(process.platform==='win32'?{channel:'chrome'}:{})},sources:[{id:'owned',searchUrl:site.origin+'/images?topic={{topic}}&count=2',selector:'#gallery img',allowedOrigins:[site.origin],imageOrigins:[],pagination:{kind:'none',maxPages:1}}],sink:{store:async item=>{calls++;if(reject)throw new Error('Temporary storage outage');return {sha256:item.sha256,verifiedAt:new Date().toISOString()};}}});
  t.after(async()=>{await collector.close();await site.close();fs.rmSync(folder,{recursive:true,force:true,maxRetries:10,retryDelay:500});});
  const started=collector.create({requestId:'resume-after-delivery-failed',topics:['cats'],sources:['owned'],limit:2,destination:'stickerdock'});let job=await wait(id=>collector.get(id),started.job.id);
  assert.equal(job.status,'DELIVERY_FAILED',JSON.stringify(job));assert.equal(job.items.length,2);const reads=collector.runs.data.runs.length;
  reject=false;collector.resume(job.id);job=await wait(id=>collector.get(id),job.id);assert.equal(job.status,'VERIFIED_STORAGE',JSON.stringify(job));assert.equal(collector.runs.data.runs.length,reads);assert.equal(calls,3);
  const persisted=collector.data.jobs.find(j=>j.id===job.id);persisted.status='INTERRUPTED';fs.writeFileSync(persisted.items[0].file,'changed');collector.flush();
  collector.resume(job.id);job=await wait(id=>collector.get(id),job.id);assert.equal(job.status,'DELIVERY_FAILED');assert.equal(calls,3);assert.match(job.error,/valid bounded|changed/);
});
