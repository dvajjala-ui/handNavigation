'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),http=require('node:http'),fs=require('node:fs'),os=require('node:os'),path=require('node:path'),sharp=require('sharp');
const {StickerDock}=require('../stickerdock.cjs'),{boundedText}=require('../http.cjs'),{Collections}=require('../collections.cjs');
test('intake retry is bounded and idempotent actions recover; a claim is never repeated',async t=>{
  let calls=0,mode='transient';
  const server=http.createServer(async(req,res)=>{for await(const _ of req){}calls++;const status=mode==='transient'&&calls>1?200:mode==='auth'?401:503;res.writeHead(status,{'Content-Type':'application/json',...(mode==='long'?{'Retry-After':'120'}:{})});res.end(JSON.stringify(status===200?{ok:true}:{error:'unavailable'}));});
  await new Promise(r=>server.listen(0,'127.0.0.1',r));t.after(()=>new Promise(r=>server.close(r)));
  const sink=new StickerDock('http://127.0.0.1:'+server.address().port,'a'.repeat(40),{retryDelayMs:1});
  assert.equal((await sink.call('ingest',{action:'store'})).ok,true);assert.equal(calls,2);
  for(const action of ['claim','report']){calls=0;await assert.rejects(sink.call('ingest',{action}),/503/);assert.equal(calls,1);}
  for(const next of ['auth','long','always']){mode=next;calls=0;await assert.rejects(sink.call('ingest',{action:'get'}));assert.equal(calls,next==='always'?3:1);}
});
test('HTTP response bounds stop oversized bodies and remote worker credentials require HTTPS',async()=>{
  await assert.rejects(boundedText(new Response('x'.repeat(11)),10),/byte limit/);
  await assert.rejects(boundedText(new Response('small',{headers:{'Content-Length':'1000'}}),10),/byte limit/);
  assert.throws(()=>new StickerDock('http://remote.example','a'.repeat(40)),/HTTPS/);
  assert.throws(()=>new StickerDock('https://safe.example/?token=secret','a'.repeat(40)),/origin/);
});

test('a fresh hosted worker rejects cloud duplicates without consuming its local daily budget',async()=>{
  const folder=fs.mkdtempSync(path.join(os.tmpdir(),'hand-cloud-history-'));let collector;
  try{
    const bytes=await sharp({create:{width:300,height:220,channels:3,background:'#94a6bc'}}).jpeg().toBuffer();
    const digest=require('node:crypto').createHash('sha256').update(bytes).digest('hex');let downloads=0;
    fs.writeFileSync(path.join(folder,'cloud-history.json'),JSON.stringify([{sha256:digest,source:'https://imgflip.com/memegenerator/12'}]));
    collector=new Collections(folder,{catalogFetch:async url=>{
      if(url==='https://api.imgflip.com/get_memes')return Response.json({success:true,data:{memes:[{id:'12',name:'Cat reaction',url:'https://i.imgflip.com/example.jpg'}]}});
      downloads++;return new Response(bytes);
    }});
    const {job}=collector.create({requestId:'cloud-duplicate-cat',topics:['cat'],sources:['imgflip'],limit:1,destination:'local'});
    await collector.pumpTask;assert.equal(collector.get(job.id).items.length,0);assert.equal(collector.used(),0);assert.equal(downloads,0);
  }finally{await collector?.close();if(path.resolve(folder).startsWith(path.resolve(os.tmpdir())+path.sep))fs.rmSync(folder,{recursive:true,force:true});}
});
test('Imgflip uses real Runner validation/dedup, rejects foreign media and finishes empty catalog results promptly',async()=>{
  const folder=fs.mkdtempSync(path.join(os.tmpdir(),'hand-catalog-'));let collector;
  try{
    const bytes=await sharp({create:{width:300,height:220,channels:3,background:'#8456bc'}}).jpeg().toBuffer(),calls=[];
    const transport=async url=>{calls.push(url);if(url==='https://api.imgflip.com/get_memes')return Response.json({success:true,data:{memes:[{id:'12',name:'Cat reaction',url:'https://i.imgflip.com/example.jpg'},{id:'13',name:'Cat unsafe',url:'https://unreviewed.invalid/cat.jpg'}]}});assert.equal(url,'https://i.imgflip.com/example.jpg');return new Response(bytes,{headers:{'Content-Type':'image/jpeg'}});};
    collector=new Collections(folder,{dailyLimit:4,catalogFetch:transport});
    const run=async(requestId,topic)=>{const {job}=collector.create({requestId,topics:[topic],sources:['imgflip'],limit:1,destination:'local'});await collector.pumpTask;return collector.get(job.id);};
    const first=await run('catalog-first-cat','cat');assert.equal(first.status,'VERIFIED_LOCAL');assert.equal(first.items[0].postUrl,'https://imgflip.com/memegenerator/12');assert.equal(first.items[0].platform,'imgflip');
    const second=await run('catalog-duplicate-cat','cat');assert.equal(second.items.length,0);assert.equal(calls.filter(x=>x==='https://i.imgflip.com/example.jpg').length,1);
    const started=Date.now(),empty=await run('catalog-empty-topic','unmatchedtopic');assert.equal(empty.items.length,0);assert.ok(Date.now()-started<3000);assert.equal(calls.some(x=>x.includes('unreviewed.invalid')),false);
  }finally{await collector?.close();if(path.resolve(folder).startsWith(path.resolve(os.tmpdir())+path.sep))fs.rmSync(folder,{recursive:true,force:true});}
});
