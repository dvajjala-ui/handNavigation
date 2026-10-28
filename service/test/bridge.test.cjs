'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {QueueBridge}=require('../bridge.cjs');
test('outbound bridge reuses durable jobs, reports only verified deliveries, and observes cancel',async()=>{
  const folder=fs.mkdtempSync(path.join(os.tmpdir(),'hand-bridge-'));
  try{
    let stopped=false,local={id:'12345678-1234-1234-1234-123456789012',status:'RUNNING',items:[{}, {delivery:{id:'stored'}}],sourceStatus:{reddit:{status:'COMPLETED'}}};
    const collections={folder,sources:[{id:'imgflip',name:'Imgflip'}],data:{jobs:[]},active:null,create:s=>{assert.equal(s.destination,'stickerdock');return {job:local,reused:false};},get:()=>local,stop:()=>{stopped=true;}};
    const calls=[],sink={call:async(endpoint,payload)=>{calls.push(payload);return payload.action==='claim'?{job:{id:local.id,topics:['cats'],sources:['reddit'],image_limit:2}}:{job:{cancel_requested:true}};}};
    const bridge=new QueueBridge(collections,sink);await bridge.tick();assert.ok(stopped);assert.equal(calls[1].report.saved,2);assert.equal(calls[1].report.delivered,1);assert.equal(calls[1].report.status,'RUNNING');
    assert.deepEqual(calls[0].supported_sources,[{id:'imgflip',name:'Imgflip'}]);
    local={...local,status:'PARTIAL'};await bridge.tick();assert.equal(bridge.pending,null);
    assert.equal(new QueueBridge(collections,sink).workerId,bridge.workerId);
  }finally{if(path.resolve(folder).startsWith(path.resolve(os.tmpdir())+path.sep))fs.rmSync(folder,{recursive:true,force:true});}
});
test('an in-flight failed heartbeat cannot keep a browser running past its lease safety window',async()=>{
  const folder=fs.mkdtempSync(path.join(os.tmpdir(),'hand-bridge-'));
  let bridge;
  try{
    let stoppedAt=0;const started=Date.now(),collections={folder,data:{jobs:[]},get:()=>({id:'12345678-1234-1234-1234-123456789012',status:'RUNNING',items:[]}),stop:()=>{stoppedAt=Date.now();}};
    const sink={call:async()=>{await new Promise(r=>setTimeout(r,1800));throw new Error('StickerDock HTTP 503');}};
    bridge=new QueueBridge(collections,sink,{intervalMs:20});bridge.pending={cloud:{id:'12345678-1234-1234-1234-123456789012'},local:'12345678-1234-1234-1234-123456789012',lastConfirmed:started-91000};bridge.start();
    await new Promise(r=>setTimeout(r,1250));assert.ok(stoppedAt>0);assert.ok(stoppedAt-started<1700);assert.equal(bridge.pending,null);
  }finally{await bridge?.close();if(path.resolve(folder).startsWith(path.resolve(os.tmpdir())+path.sep))fs.rmSync(folder,{recursive:true,force:true});}
});

test('a claim resolving after shutdown cannot start an unleased browser run',async()=>{
  const folder=fs.mkdtempSync(path.join(os.tmpdir(),'hand-bridge-stop-'));
  try{
    let resolveClaim;const reports=[];
    const collections={folder,sources:[],data:{jobs:[]},active:null,create:()=>assert.fail('A stopped worker must not start a browser')};
    const sink={call:async(endpoint,payload)=>payload.action==='claim'?new Promise(resolve=>{resolveClaim=resolve;}):(reports.push(payload),{job:{}})};
    const bridge=new QueueBridge(collections,sink),tick=bridge.tick();
    await bridge.close();resolveClaim({job:{id:'12345678-1234-1234-1234-123456789012'}});await tick;
    assert.equal(bridge.pending,null);assert.equal(reports.length,1);assert.equal(reports[0].report.status,'FAILED');
  }finally{if(path.resolve(folder).startsWith(path.resolve(os.tmpdir())+path.sep))fs.rmSync(folder,{recursive:true,force:true});}
});
