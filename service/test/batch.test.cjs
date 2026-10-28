'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const {runBatch,seconds}=require('../batch.cjs');

function fixture(){
  let time=0;const calls=[];
  const app={collections:{active:null,pumping:false,data:{jobs:[]}},
    bridge:{pending:null,close:async()=>{calls.push('stop-claims');}},
    close:async()=>{calls.push('close-browser');app.collections.active=null;}};
  return {app,calls,options:{maxRuntimeMs:100,idleMs:20,now:()=>time,wait:async ms=>{time+=Math.min(ms,10);}}};
}
test('an empty daily worker exits and releases all background resources',async()=>{
  const f=fixture(),result=await runBatch(f.app,f.options);
  assert.equal(result.ok,true);assert.equal(result.reason,'queue_empty');assert.deepEqual(f.calls,['stop-claims','close-browser']);
});
test('a cloud lease prevents idle exit and the runtime cap closes the browser',async()=>{
  const f=fixture();f.app.bridge.pending={local:'owned-job'};f.app.collections.active={job:{id:'owned-job'}};
  const result=await runBatch(f.app,f.options);
  assert.equal(result.reason,'runtime_limit');assert.equal(result.ok,false);assert.equal(f.app.collections.active,null);
  assert.deepEqual(f.calls,['stop-claims','close-browser']);
});
test('a completed partial job fails the batch while preserving its delivery count',async()=>{
  const f=fixture();let added=false;
  const wait=f.options.wait;f.options.wait=async ms=>{await wait(ms);if(!added){added=true;f.app.collections.data.jobs.push({id:'partial',status:'PARTIAL',finishedAt:'now',items:[{delivery:{id:'receipt'}},{}]});}};
  const result=await runBatch(f.app,f.options);
  assert.equal(result.ok,false);assert.deepEqual(result.jobs,[{id:'partial',status:'PARTIAL',saved:2,delivered:1}]);
});
test('a termination signal stops new claims before shutting down active work',async()=>{
  const f=fixture(),controller=new AbortController();controller.abort();
  const result=await runBatch(f.app,{...f.options,signal:controller.signal});
  assert.equal(result.reason,'interrupted');assert.equal(result.ok,false);assert.deepEqual(f.calls,['stop-claims','close-browser']);
});
test('shutdown reports the cancelled local result to its existing cloud lease',async()=>{
  const f=fixture(),reports=[];
  const local={id:'local',status:'RUNNING',items:[]};
  f.app.collections.active={job:local};f.app.collections.data.jobs.push(local);
  f.app.collections.get=()=>local;
  f.app.bridge.pending={local:'local',cloud:{id:'cloud'}};f.app.bridge.workerId='worker';
  f.app.bridge.report=job=>({status:job.status,saved:0,delivered:0});
  f.app.bridge.sink={call:async(endpoint,payload)=>{reports.push(payload);}};
  const close=f.app.close;f.app.close=async()=>{await close();local.status='CANCELLED';};
  const result=await runBatch(f.app,f.options);
  assert.equal(result.reason,'runtime_limit');assert.equal(reports[0].id,'cloud');assert.equal(reports[0].report.status,'CANCELLED');assert.equal(f.app.bridge.pending,null);
});
test('cron duration settings reject unbounded or malformed runtimes',()=>{
  assert.equal(seconds(undefined,1500,1800),1500000);
  for(const value of ['0','Infinity','1801','5.5','bad'])assert.throws(()=>seconds(value,1500,1800));
});
