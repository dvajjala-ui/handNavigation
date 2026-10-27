'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const {fetchImage}=require('../engine.cjs');
const origin='https://owned.example',url=origin+'/image';
const read=(session,signal=new AbortController().signal,onRetry)=>fetchImage(session,url,[origin],signal,onRetry);

test('temporary HTTP image failures recover without changing the requested URL',async()=>{
  const requests=[],retries=[];
  const bytes=await read({fetch:async requested=>{requests.push(requested);return requests.length<3?new Response('busy',{status:503,headers:{'Retry-After':'0'}}):new Response('real bytes');}},undefined,retry=>retries.push(retry));
  assert.equal(bytes.toString(),'real bytes');assert.deepEqual(requests,[url,url,url]);assert.equal(retries.length,2);
});
test('image retry budget is bounded and access denial is not retried',async()=>{
  for(const status of [503,403]){
    let calls=0;await assert.rejects(read({fetch:async()=>{calls++;return new Response('unavailable',{status,headers:{'Retry-After':'0'}});}}),new RegExp('HTTP '+status));
    assert.equal(calls,status===503?3:1);
  }
});
test('a long server rate limit is respected without an early retry',async()=>{
  let calls=0;await assert.rejects(read({fetch:async()=>{calls++;return new Response('later',{status:429,headers:{'Retry-After':'60'}});}}),/HTTP 429/);assert.equal(calls,1);
});
test('stopping during retry backoff prevents the next request promptly',async()=>{
  const abort=new AbortController();let calls=0;
  const result=read({fetch:async()=>{calls++;return new Response('busy',{status:503,headers:{'Retry-After':'5'}});}},abort.signal,()=>setTimeout(()=>abort.abort(),20));
  const before=Date.now();await assert.rejects(result,/Run stopped/);assert.equal(calls,1);assert.ok(Date.now()-before<1000);
});
test('a reset while reading an image body can recover from a fresh GET',async()=>{
  let calls=0;
  const bytes=await read({fetch:async()=>{calls++;return calls===1?new Response(new ReadableStream({start(controller){controller.error(Object.assign(new Error('connection reset'),{code:'ECONNRESET'}));}})):new Response('complete');}});
  assert.equal(calls,2);assert.equal(bytes.toString(),'complete');
});
test('retry redirects are still checked against reviewed origins',async()=>{
  const requests=[];await assert.rejects(read({fetch:async requested=>{requests.push(requested);return requests.length===1?new Response('busy',{status:503,headers:{'Retry-After':'0'}}):new Response(null,{status:302,headers:{Location:'https://unreviewed.example/image'}});}}),/reviewed image websites/);
  assert.deepEqual(requests,[url,url]);
});
