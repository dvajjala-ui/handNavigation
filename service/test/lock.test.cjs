const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),{spawn}=require('node:child_process'),{once}=require('node:events'),{lock,waitForLock,STALE_MS}=require('../lock.cjs');
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function within(promise,ms,message){let timer;try{return await Promise.race([promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error(message)),ms);})]);}finally{clearTimeout(timer);}}
function removeFixture(folder){assert.ok(path.resolve(folder).startsWith(path.resolve(os.tmpdir())+path.sep));fs.rmSync(folder,{recursive:true,force:true});}
async function holder(folder){
  const child=spawn(process.execPath,['-e',"const release=require(process.argv[1]).lock(process.argv[2]);process.stdout.write('LOCKED\\n');process.on('message',()=>{release();process.exit(0)});setInterval(()=>{},1000)",require.resolve('../lock.cjs'),folder],{windowsHide:true,stdio:['ignore','pipe','pipe','ipc']});
  let errors='';child.stderr.on('data',part=>errors+=part);
  const ready=await within(Promise.race([once(child.stdout,'data').then(part=>part[0].toString().includes('LOCKED')),once(child,'exit').then(()=>{throw new Error('Lock holder exited: '+errors);})]),10000,'Lock holder did not start');
  assert.ok(ready);return child;
}
test('a second service cannot reuse the active directory and a waiting cron can be cancelled',async t=>{
  const folder=fs.mkdtempSync(path.join(os.tmpdir(),'handnavigate-lock-test-'));t.after(()=>removeFixture(folder));
  const release=lock(folder);assert.throws(()=>lock(folder),/already uses/);
  const controller=new AbortController(),waiting=waitForLock(folder,{signal:controller.signal});controller.abort();await assert.rejects(waiting,/abort/i);assert.throws(()=>lock(folder),/already uses/);
  release();const again=lock(folder);again();assert.equal(fs.existsSync(path.join(folder,'worker.lock')),false);
});

test('a separate worker heartbeats and a killed worker recovers after its lease expires without deleting saved data',async t=>{
  const folder=fs.mkdtempSync(path.join(os.tmpdir(),'hand-lease-crash-')),saved=path.join(folder,'saved-journal.json');fs.writeFileSync(saved,'preserve this journal');let child;
  t.after(async()=>{if(child?.exitCode===null&&child.signalCode===null){const ended=once(child,'exit');child.kill('SIGKILL');await ended;}removeFixture(folder);});
  child=await holder(folder);const file=path.join(folder,'worker.lock'),first=fs.statSync(file).mtimeMs;
  assert.ok(fs.statSync(file).isDirectory());assert.throws(()=>lock(folder),/already uses/);
  const deadline=Date.now()+15000;while(fs.statSync(file).mtimeMs===first&&Date.now()<deadline)await pause(100);
  assert.notEqual(fs.statSync(file).mtimeMs,first,'An actual child must renew its lease.');
  const ended=once(child,'exit');child.kill('SIGKILL');await ended;assert.equal(fs.readFileSync(saved,'utf8'),'preserve this journal');assert.throws(()=>lock(folder),/30 seconds/);
  const expires=fs.statSync(file).mtimeMs+STALE_MS,release=await waitForLock(folder);assert.ok(Date.now()>=expires,'A replacement must wait for the crashed lease to expire.');assert.equal(fs.readFileSync(saved,'utf8'),'preserve this journal');assert.throws(()=>lock(folder),/already uses/);release();assert.equal(fs.existsSync(file),false);
});

test('active legacy locks remain protected regardless of age; dead legacy locks are preserved during migration',async t=>{
  const folder=fs.mkdtempSync(path.join(os.tmpdir(),'hand-lease-legacy-'));t.after(()=>removeFixture(folder));
  const file=path.join(folder,'worker.lock'),live=JSON.stringify({pid:process.pid,nonce:'legacy-active'});fs.writeFileSync(file,live);fs.utimesSync(file,new Date(0),new Date(0));assert.throws(()=>lock(folder),/already uses/);assert.equal(fs.readFileSync(file,'utf8'),live);
  const process_=spawn(process.execPath,['-e','process.exit(0)'],{windowsHide:true});await once(process_,'exit');const dead=JSON.stringify({pid:process_.pid,nonce:'legacy-dead'});fs.writeFileSync(file,dead);
  const release=lock(folder),archives=fs.readdirSync(folder).filter(name=>name.startsWith('worker.lock.legacy-'));assert.equal(archives.length,1);assert.equal(fs.readFileSync(path.join(folder,archives[0]),'utf8'),dead);release();
  fs.writeFileSync(file,'incomplete old lock');assert.throws(()=>lock(folder),/unreadable/);assert.equal(fs.readFileSync(file,'utf8'),'incomplete old lock');
});

test('losing the lease stops its owner rather than continuing against another worker',async t=>{
  const folder=fs.mkdtempSync(path.join(os.tmpdir(),'hand-lease-lost-'));let child;
  t.after(async()=>{if(child?.exitCode===null&&child.signalCode===null){const ended=once(child,'exit');child.kill('SIGKILL');await ended;}removeFixture(folder);});
  child=await holder(folder);const ended=once(child,'exit'),file=path.join(folder,'worker.lock');fs.rmdirSync(file);
  const [code]=await within(ended,15000,'The owner continued after losing its lease');assert.equal(code,1);
  const release=lock(folder);release();
});

test('concurrent legacy migration cannot move or replace a newly acquired real worker lease',async t=>{
  const folder=fs.mkdtempSync(path.join(os.tmpdir(),'hand-lease-upgrade-')),file=path.join(folder,'worker.lock'),trigger=path.join(folder,'acquire'),ready=path.join(folder,'acquired');let child;
  t.after(async()=>{if(child?.exitCode===null&&child.signalCode===null){const ended=once(child,'exit');child.kill('SIGKILL');await ended;}removeFixture(folder);});
  const dead=spawn(process.execPath,['-e','process.exit(0)'],{windowsHide:true});await once(dead,'exit');fs.writeFileSync(file,JSON.stringify({pid:dead.pid,nonce:'old'}));
  child=spawn(process.execPath,['-e',"const fs=require('node:fs'),{lock}=require(process.argv[1]);const timer=setInterval(()=>{if(fs.existsSync(process.argv[3])){clearInterval(timer);lock(process.argv[2]);fs.writeFileSync(process.argv[4],'owned');setInterval(()=>{},1000);}},10);console.log('READY');",require.resolve('../lock.cjs'),folder,trigger,ready],{windowsHide:true,stdio:['ignore','pipe','pipe']});
  await within(once(child.stdout,'data'),30000,'Concurrent worker did not start');
  const read=fs.readFileSync,wait=new Int32Array(new SharedArrayBuffer(4));let triggered=false;
  try{
    fs.readFileSync=function(name,...args){
      const result=read.call(fs,name,...args);
      if(name===file&&!triggered){triggered=true;fs.unlinkSync(file);fs.writeFileSync(trigger,'acquire');const deadline=Date.now()+10000;while(!fs.existsSync(ready)){if(Date.now()>deadline)throw new Error('Concurrent worker did not acquire');Atomics.wait(wait,0,0,20);}}
      return result;
    };
    assert.throws(()=>lock(folder),/already uses/);
  }finally{fs.readFileSync=read;}
  assert.equal(triggered,true);assert.equal(fs.statSync(file).isDirectory(),true);assert.throws(()=>lock(folder),/already uses/);
});

test('HTTP shutdown releases the data folder even if the old CLI process remains alive',async t=>{
  const folder=fs.mkdtempSync(path.join(os.tmpdir(),'hand-lease-shutdown-')),hold=path.join(folder,'hold.cjs');fs.writeFileSync(hold,'setInterval(()=>{},1000);');let child;
  t.after(async()=>{if(child?.exitCode===null&&child.signalCode===null){const ended=once(child,'exit');child.kill('SIGKILL');await ended;}removeFixture(folder);});
  child=spawn(process.execPath,['--require',hold,require.resolve('../server.cjs')],{windowsHide:true,env:{...process.env,HANDNAVIGATE_DATA:folder,HANDNAVIGATE_CONFIG:path.join(folder,'none.json'),HANDNAVIGATE_PORT:'0',HANDNAVIGATE_CLOUD_QUEUE:'0',STICKERDOCK_BASE_URL:''},stdio:['ignore','pipe','pipe']});
  const [line]=await within(once(child.stdout,'data'),30000,'CLI did not listen'),endpoint=JSON.parse(line.toString()),token=JSON.parse(fs.readFileSync(path.join(folder,'service-key.json'),'utf8')).token;
  const response=await fetch('http://127.0.0.1:'+endpoint.port+'/v1/shutdown',{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:'{}'});assert.equal(response.status,202);await response.json();
  const end=Date.now()+5000;while(fs.existsSync(path.join(folder,'worker.lock'))&&Date.now()<end)await pause(50);
  assert.equal(child.exitCode,null,'The fixture process should still be alive.');const release=lock(folder);release();
});
