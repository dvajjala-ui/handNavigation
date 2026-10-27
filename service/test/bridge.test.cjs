'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {QueueBridge}=require('../bridge.cjs');
test('outbound bridge reuses durable jobs, reports only verified deliveries, and observes cancel',async()=>{
  const folder=fs.mkdtempSync(path.join(os.tmpdir(),'hand-bridge-'));
  try{
    let stopped=false,local={id:'12345678-1234-1234-1234-123456789012',status:'RUNNING',items:[{}, {delivery:{id:'stored'}}],sourceStatus:{reddit:{status:'COMPLETED'}}};
    const collections={folder,data:{jobs:[]},active:null,create:s=>{assert.equal(s.destination,'stickerdock');return {job:local,reused:false};},get:()=>local,stop:()=>{stopped=true;}};
    const calls=[],sink={call:async(endpoint,payload)=>{calls.push(payload);return payload.action==='claim'?{job:{id:local.id,topics:['cats'],sources:['reddit'],image_limit:2}}:{job:{cancel_requested:true}};}};
    const bridge=new QueueBridge(collections,sink);await bridge.tick();assert.ok(stopped);assert.equal(calls[1].report.saved,2);assert.equal(calls[1].report.delivered,1);assert.equal(calls[1].report.status,'RUNNING');
    local={...local,status:'PARTIAL'};await bridge.tick();assert.equal(bridge.pending,null);
    assert.equal(new QueueBridge(collections,sink).workerId,bridge.workerId);
  }finally{if(path.resolve(folder).startsWith(path.resolve(os.tmpdir())+path.sep))fs.rmSync(folder,{recursive:true,force:true});}
});
