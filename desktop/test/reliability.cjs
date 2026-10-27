'use strict';
const {_electron:electron}=require('playwright'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {fixture}=require('./fixture.cjs'),{draft}=require('../core.cjs'),{imageInfo}=require('../engine.cjs');
const {closeApp,removeFixture}=require('./cleanup.cjs');
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function until(fn,message,timeout=60000){const end=Date.now()+timeout;while(Date.now()<end){const result=await fn();if(result)return result;await pause(100);}throw new Error(message);}
async function main(){
  const site=await fixture(),folder=fs.mkdtempSync(path.join(os.tmpdir(),'handnavigate-reliability-')),output=path.join(folder,'Downloads'),results=[];fs.mkdirSync(output);
  let app;
  try{
    app=await electron.launch({args:[path.resolve('.')],env:{...process.env,HANDNAVIGATE_TEST:'1',HANDNAVIGATE_USER_DATA:path.join(folder,'profile')},timeout:60000});
    const ui=await app.firstWindow({timeout:60000});await ui.waitForSelector('#workflow-title');
    const call=async(name,arg)=>{const response=await ui.evaluate(async({name,arg})=>window.handnavigate[name](arg),{name,arg});assert.equal(response.ok,true,JSON.stringify(response));return response.value;};
    const state=()=>call('state'),base={...draft({startUrl:site.origin+'/images?count=1',outputFolder:output,imageOrigins:[]}),sourceSelector:'#gallery img',count:1,newOnly:false,pagination:{kind:'none',maxPages:1}};
    const create=async changes=>{const task=await call('saveTask',{task:{...base,...changes}});await call('approve',{id:task.id,sha:task.sha});return task;};
    const finished=runId=>until(async()=>{const s=await state(),r=s.runs.find(r=>r.id===runId);return !s.busy&&r?.status!=='RUNNING'?r:null;},'The real browser run did not finish');
    const execute=async task=>{const started=await call('run',{id:task.id,rowIndex:0});return finished(started.runId);};

    site.controls.failImageReads=2;
    const flaky=await create({name:'Recover temporary image reads',startUrl:site.origin+'/flaky'});let run=await execute(flaky);
    assert.equal(run.status,'VERIFIED',JSON.stringify(run));assert.equal(site.controls.readAttempts,3);assert.equal(run.imageRetries,2);
    assert.equal((await imageInfo(fs.readFileSync(run.items[0].file))).sha256,run.items[0].sha256);
    results.push({test:'two actual HTTP 503 image reads recover and save independently decoded bytes',passed:true});

    site.controls.readAttempts=0;site.controls.failImageReads=10;
    run=await execute(flaky);assert.equal(run.status,'HALTED',JSON.stringify(run));assert.equal(site.controls.readAttempts,3);assert.equal(run.items.length,0);
    results.push({test:'a persistent image failure stops after three reads without false success',passed:true});
    site.controls.failImageReads=0;

    const search=await create({name:'Wait for changed search results',startUrl:site.origin+'/async-search',rows:[{topic:'architecture'}],steps:[{op:'fill',locator:{kind:'css',value:'#topic'},value:'{{topic}}'},{op:'click',locator:{kind:'css',value:'#search'}}]});
    run=await execute(search);assert.equal(run.status,'VERIFIED',JSON.stringify(run));assert.equal(run.items[0].sha256,(await imageInfo(site.images[25])).sha256);
    results.push({test:'a taught asynchronous search waits for the new topic instead of downloading stale results',passed:true});

    site.controls.slowUploadMs=3200;
    const target={url:site.origin+'/target',fileInput:{kind:'css',value:'#upload'},submit:{kind:'css',value:'#send'},galleryUrl:site.origin+'/target',gallerySelector:'#gallery img'};
    const slow=await create({name:'Slow submitted uploads',type:'transfer',startUrl:site.origin+'/images?count=2',count:2,target});
    run=await execute(slow);assert.equal(run.status,'VERIFIED',JSON.stringify(run));assert.equal(site.writes,2);assert.equal(site.uploaded.length,2);assert.equal(site.controls.abortedUploads,0);assert.ok(run.items.every(i=>i.state==='CONFIRMED'));
    results.push({test:'two slow HTTP uploads finish before leaving the form, each submitted once and remotely verified',passed:true});
    run=await execute(slow);assert.equal(run.status,'VERIFIED',JSON.stringify(run));assert.equal(site.writes,2);
    results.push({test:'repeating a slow transfer reads existing originals without another upload',passed:true});

    const automatic=await create({name:'Slow automatic upload',type:'transfer',startUrl:site.origin+'/pages?page=2',target:{...target,url:site.origin+'/target?auto=1',submit:null}});
    run=await execute(automatic);assert.equal(run.status,'VERIFIED',JSON.stringify(run));assert.equal(site.writes,3);assert.equal(site.controls.abortedUploads,0);assert.equal(site.uploaded.length,3);
    results.push({test:'file-selection automatic upload also waits for the original HTTP write',passed:true});

    site.controls.slowUploadMs=8000;
    const interrupted=await create({name:'Stop an active upload',type:'transfer',startUrl:site.origin+'/pages?page=3',target});
    const started=await call('run',{id:interrupted.id,rowIndex:0});await until(()=>site.controls.uploadsInFlight,'Upload did not start');await call('stop');
    run=await finished(started.runId);assert.equal(run.status,'NEEDS_REVIEW',JSON.stringify(run));const writeCount=site.writes;
    const blocked=await ui.evaluate(id=>window.handnavigate.run({id,rowIndex:0}),interrupted.id);assert.equal(blocked.ok,false);assert.match(blocked.error,/Review/);assert.equal(site.writes,writeCount);
    results.push({test:'stopping an in-flight upload records uncertainty and blocks automatic resubmission',passed:true});

    site.controls.slowUploadMs=0;
    const background=await create({name:'Minimized browser controls',type:'replay',startUrl:site.origin+'/background-form',rows:[{topic:'architecture'}],checks:[{kind:'text',expected:'Ready: architecture · full · true'}],steps:[
      {op:'fill',locator:{kind:'css',value:'#topic'},value:'{{topic}}'},
      {op:'select',locator:{kind:'css',value:'#layout'},value:'full'},
      {op:'press',locator:{kind:'css',value:'#captions'},value:' '},
      {op:'check',locator:{kind:'css',value:'#captions'},checked:false},
      {op:'check',locator:{kind:'css',value:'#captions'},checked:true},
      {op:'click',locator:{kind:'css',value:'#prepare'}},
      {op:'press',locator:{kind:'css',value:'#topic'},value:'Enter'}
    ]});
    await app.evaluate(()=>global.__handnavigateTest.window.minimize());await until(()=>app.evaluate(()=>global.__handnavigateTest.window.isMinimized()),'Window did not minimize');
    run=await execute(background);
    const observed=await app.evaluate(async()=>global.__handnavigateTest.browser.wc.executeJavaScript('({topic:document.querySelector("#topic").value,layout:document.querySelector("#layout").value,checked:document.querySelector("#captions").checked,result:document.querySelector("#result").textContent,input:window.lastInputTrusted,key:window.lastKeyTrusted,click:window.lastClickTrusted})'));
    assert.equal(run.status,'VERIFIED',JSON.stringify({run,observed}));
    assert.deepEqual(await app.evaluate(async()=>global.__handnavigateTest.browser.wc.executeJavaScript('({input:window.lastInputTrusted,click:window.lastClickTrusted,key:window.lastKeyTrusted})')),{input:true,click:true,key:true});
    assert.equal(await app.evaluate(()=>global.__handnavigateTest.window.isMinimized()),true);
    results.push({test:'a minimized app replays trusted text, checkbox, click, Space and Enter input without taking focus',passed:true});
    const backgroundTransfer=await create({name:'Minimized browser upload',type:'transfer',startUrl:site.origin+'/pages?page=5',target});const writesBeforeBackground=site.writes;
    run=await execute(backgroundTransfer);assert.equal(run.status,'VERIFIED',JSON.stringify(run));assert.equal(site.writes,writesBeforeBackground+1);assert.equal(run.items[0].state,'CONFIRMED');assert.equal(await app.evaluate(()=>global.__handnavigateTest.window.isMinimized()),true);
    results.push({test:'a minimized app downloads and submits one real file, then confirms its persisted original',passed:true});
    await app.evaluate(()=>global.__handnavigateTest.window.restore());

    const daily=await create({name:'Daily deferred during sign-in'});run=await execute(daily);assert.equal(run.status,'VERIFIED');
    const due=await app.evaluate((_e,id)=>{const q=global.__handnavigateTest.queue;q.clock=()=>Date.parse('2026-10-27T00:00:00Z');q.enable(id,true,'09:00','Asia/Kolkata');return global.__handnavigateTest.store.get(id).schedule.nextDue;},daily.id);
    await call('open',{url:site.origin+'/images?count=1'});
    await app.evaluate(async(_e,url)=>global.__handnavigateTest.browser.wc.executeJavaScript('(()=>{window.open('+JSON.stringify(url)+');return true;})()',true),site.origin+'/login');
    const signInOpen=()=>app.evaluate(({BrowserWindow})=>BrowserWindow.getAllWindows().some(w=>{try{return !w.isDestroyed()&&!w.webContents.isDestroyed()&&w.webContents.getURL().includes('/login');}catch{return false;}}));
    await until(signInOpen,'Sign-in popup did not open');
    await app.evaluate((_e,due)=>{const at=Date.parse(due)+1000;global.__handnavigateTest.queue.clock=()=>at;},due);
    const deferred=await app.evaluate(async()=>global.__handnavigateTest.queue.tick());assert.deepEqual(deferred,[]);
    const pending=(await state()).tasks.find(t=>t.id===daily.id);assert.equal(pending.schedule.nextDue,due);assert.equal(pending.schedule.enabled,true);
    await app.evaluate(({BrowserWindow})=>{for(const window of BrowserWindow.getAllWindows())try{if(!window.isDestroyed()&&!window.webContents.isDestroyed()&&window.webContents.getURL().includes('/login'))window.close();}catch{}});
    await until(async()=>!await signInOpen(),'Popup did not close');
    await app.evaluate(async()=>global.__handnavigateTest.queue.tick());
    const resumed=await until(async()=>{const s=await state(),dailyRuns=s.runs.filter(r=>r.taskId===daily.id&&r.trigger==='daily');return !s.busy&&dailyRuns.length?dailyRuns:null;},'Deferred daily job did not finish');
    assert.equal(resumed.length,1);assert.equal(resumed[0].status,'VERIFIED',JSON.stringify(resumed));
    assert.deepEqual(await app.evaluate(async()=>global.__handnavigateTest.queue.tick()),[]);
    results.push({test:'a real sign-in popup defers a due daily job, then it runs once after the popup closes',passed:true});
    await app.evaluate(()=>{const a=global.__handnavigateTest;for(const task of a.store.data.tasks)if(task.schedule)task.schedule.enabled=false;a.queue.clock=()=>Date.now();a.store.flush();});

    fs.writeFileSync(path.resolve('desktop/evidence/reliability-results.json'),JSON.stringify({passed:results.length,failed:0,scope:'Real Electron browser, actual transient HTTP failures, asynchronous search, slow HTTP file uploads and sign-in popup',results},null,2));console.log(JSON.stringify(results,null,2));
  }finally{
    await closeApp(app);await site.close();removeFixture(folder);
  }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
