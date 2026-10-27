'use strict';
const {_electron:electron}=require('playwright'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),net=require('node:net'),cp=require('node:child_process');
const {fixture}=require('./fixture.cjs'),{draft}=require('../core.cjs'),{imageInfo}=require('../engine.cjs');
const {closeApp,removeFixture}=require('./cleanup.cjs');
const pause=ms=>new Promise(r=>setTimeout(r,ms));
async function freePort(){const s=net.createServer();await new Promise(r=>s.listen(0,'127.0.0.1',r));const p=s.address().port;await new Promise(r=>s.close(r));return p;}
async function finished(app,id,after){for(let n=0;n<600;n++){const s=await app.evaluate(()=>({active:!!global.__handnavigateTest.runner.active,runs:structuredClone(global.__handnavigateTest.store.data.runs)}));if(!s.active&&s.runs.length>after&&s.runs[0].taskId===id&&s.runs[0].status!=='RUNNING')return s.runs[0];await pause(150);}throw new Error('Run did not finish: '+id);}
async function main(){
  const site=await fixture(),folder=fs.mkdtempSync(path.join(os.tmpdir(),'handnavigate-workflows-')),output=path.join(folder,'Downloads'),profile=path.join(folder,'profile'),results=[];fs.mkdirSync(output);
  let app;const launch=()=>electron.launch({args:[path.resolve('.')],env:{...process.env,HANDNAVIGATE_TEST:'1',HANDNAVIGATE_USER_DATA:profile},timeout:60000});
  try{
    app=await launch();let ui=await app.firstWindow({timeout:60000});await ui.waitForSelector('#task-name');
    await ui.locator('#task-name').fill('Twenty images across pages');await ui.locator('#task-url').fill(site.origin+'/pages');await ui.locator('#save-task').click();
    let task=await app.evaluate((_e,folder)=>{const a=global.__handnavigateTest,t=a.store.get(a.store.data.tasks[0].id);t.outputFolder=folder;t.imageOrigins=[];a.store.save(t);a.flush();return t;},output);
    await ui.locator('#open-site').click();await ui.waitForFunction(()=>document.querySelector('#browser-address').value.includes('/pages'));
    await ui.locator('#pick-images').click();const website=app.context().pages().find(p=>p.url().includes('/pages'));await website.locator('#gallery img').first().click();
    await ui.locator('#page-mode').selectOption('next');await ui.locator('#page-limit').fill('10');await ui.locator('#pick-next').click();await website.getByRole('link',{name:'Next page',exact:true}).click();
    await ui.waitForFunction(()=>document.querySelector('#next-selector').placeholder.includes('Next page'));
    await ui.locator('[data-tab="review"]').click();await ui.locator('#review-ack').check();await ui.locator('#approve-run').click();
    let run=await finished(app,task.id,0);assert.equal(run.status,'VERIFIED',JSON.stringify(run));assert.equal(run.items.length,20);assert.equal(run.pagesVisited,4);
    const firstHashes=new Set(run.items.map(i=>i.sha256));results.push({test:'real image and Next-control pickers collect 20 images across four HTTP pages',passed:true});
    await ui.locator('#run-now').click();run=await finished(app,task.id,1);assert.equal(run.status,'VERIFIED',JSON.stringify(run));assert.equal(run.items.length,20);assert.equal(run.items.some(i=>firstHashes.has(i.sha256)),false);assert.ok(run.duplicatesSkipped>=20);results.push({test:'next daily-style run scans past old pages and saves 20 new images',passed:true});
    const create=async(d,approve=true)=>app.evaluate((_e,{d,approve})=>{const a=global.__handnavigateTest,t=a.store.save(d);if(approve)a.store.approve(t.id,t.sha);a.setSelected(t.id);return t;},{d,approve});
    const execute=async t=>{const before=await app.evaluate(()=>global.__handnavigateTest.store.data.runs.length);await app.evaluate((_e,id)=>{global.__handnavigateTest.runner.run(id,0);},t.id);return finished(app,t.id,before);};
    const base=draft({startUrl:site.origin+'/images?count=2',outputFolder:output,imageOrigins:[]});
    const named=await create({...base,name:'Named variable preservation',type:'replay',startUrl:site.origin+'/result',rows:[{subject:'gardens',tone:'brief'}],checks:[{kind:'text',expected:'Ready: {{subject}}'}]},false);
    await ui.locator('[data-tab="setup"]').click();await ui.locator('#task-name').fill('Named variable preservation edited');await ui.locator('#save-task').click();
    assert.deepEqual(await app.evaluate((_e,id)=>global.__handnavigateTest.store.get(id).rows,named.id),[{subject:'gardens',tone:'brief'}]);results.push({test:'saving ordinary UI edits preserves multiple named variable columns',passed:true});
    const apiTask=await create({...base,name:'API download',startUrl:site.origin+'/images?count=1',count:1,sourceSelector:'#gallery img',newOnly:false,pagination:{kind:'none',maxPages:1}});
    await ui.locator('[data-tab="schedule"]').click();await ui.locator('#api-port').fill(String(await freePort()));await ui.locator('#api-enable').click();
    await ui.waitForFunction(()=>document.querySelector('#api-status').textContent.startsWith('Active:'));
    const settings=JSON.parse(fs.readFileSync(path.join(profile,'integration.json'),'utf8')),endpoint='http://127.0.0.1:'+settings.port+'/v1',headers={Authorization:'Bearer '+settings.token,'Content-Type':'application/json'};
    const post=body=>fetch(endpoint+'/runs',{method:'POST',headers,body:JSON.stringify(body)});
    assert.equal((await fetch(endpoint+'/health')).status,401);assert.equal((await fetch(endpoint+'/health',{headers:{...headers,Origin:'https://untrusted.example'}})).status,403);
    const request={workflowId:apiTask.id,rowIndex:0,requestId:'owned-api-repeat-001'},beforeAPI=await app.evaluate(()=>global.__handnavigateTest.store.data.runs.length);
    const started=await (await post(request)).json(),repeated=await (await post(request)).json();assert.equal(started.id,repeated.id);assert.equal(repeated.reused,true);
    run=await finished(app,apiTask.id,beforeAPI);assert.equal(run.status,'VERIFIED',JSON.stringify(run));assert.equal(run.trigger,'api');assert.equal((await imageInfo(fs.readFileSync(run.items[0].file))).sha256,run.items[0].sha256);
    assert.equal((await app.evaluate(()=>global.__handnavigateTest.store.data.runs.length)),beforeAPI+1);
    assert.equal((await post({...request,rowIndex:1})).status,409);assert.equal((await post({...request,requestId:'owned-invalid-row',rowIndex:99})).status,409);
    const unapproved=await create({...base,name:'Unapproved API draft',count:1},false);assert.equal((await post({...request,requestId:'owned-unapproved',workflowId:unapproved.id})).status,409);
    results.push({test:'UI-enabled authenticated API runs real downloader once per request ID and rejects unapproved/invalid requests',passed:true});
    const partial=await create({...base,name:'Partial download history',count:3,sourceSelector:'#gallery img',pagination:{kind:'none',maxPages:1}});run=await execute(partial);assert.equal(run.status,'PARTIAL');assert.equal(run.items.length,2);run=await execute(partial);assert.equal(run.status,'PARTIAL');assert.equal(run.items.length,0);assert.equal(run.duplicatesSkipped,2);results.push({test:'partial downloads remain in duplicate history on the next run',passed:true});
    const library=await create({...base,name:'Library duplicate history',startUrl:site.origin+'/pages',count:1,dedupeScope:'library',sourceSelector:'#gallery img',pagination:{kind:'next',maxPages:10,locator:{kind:'css',value:'#next'}}});run=await execute(library);assert.equal(run.status,'VERIFIED',JSON.stringify(run));assert.ok(run.items[0].imageUrl.endsWith('/image/40'));results.push({test:'library scope skips images previously saved by other workflows',passed:true});
    const target={url:site.origin+'/target',fileInput:{kind:'css',value:'#upload'},submit:{kind:'css',value:'#send'},galleryUrl:site.origin+'/target?delay=1',gallerySelector:'#gallery img'};
    const transfer=await create({...base,name:'Resume partial transfer',type:'transfer',startUrl:site.origin+'/limited',count:3,sourceSelector:'#gallery img',target,pagination:{kind:'none',maxPages:1}});
    run=await execute(transfer);assert.equal(run.status,'PARTIAL');assert.equal(run.items.length,2);assert.equal(site.writes,0);site.controls.limit=3;
    run=await execute(transfer);assert.equal(run.status,'VERIFIED',JSON.stringify(run));assert.equal(run.items.filter(i=>i.reusedFrom).length,2);assert.equal(site.writes,3);assert.equal(site.uploaded.length,3);results.push({test:'partial transfer reuses two validated local files and uploads all three once to an asynchronous gallery',passed:true});
    const pagedTarget={...target,galleryUrl:site.origin+'/target?per=1',pagination:{kind:'next',maxPages:10,locator:{kind:'css',value:'#next'}}};
    const existing=await create({...transfer,id:undefined,name:'Verify paginated destination',newOnly:false,target:pagedTarget});run=await execute(existing);assert.equal(run.status,'VERIFIED',JSON.stringify(run));assert.equal(site.writes,3);results.push({test:'paginated destination verification finds existing originals without resending them',passed:true});
    const capped=await create({...existing,id:undefined,name:'Incomplete destination inventory',target:{...pagedTarget,pagination:{...pagedTarget.pagination,maxPages:1}}});run=await execute(capped);assert.equal(run.status,'NEEDS_REVIEW');assert.equal(site.writes,3);results.push({test:'destination page-limit exhaustion stops before any duplicate upload',passed:true});
    site.controls.fakeUpload=true;
    const late=await create({...base,name:'Delayed upload outcome',type:'transfer',startUrl:site.origin+'/pages?page=10',count:1,newOnly:false,sourceSelector:'#gallery img',target,pagination:{kind:'none',maxPages:1}});
    run=await execute(late);assert.equal(run.status,'NEEDS_REVIEW');const writesBeforeRecheck=site.writes;
    site.controls.fakeUpload=false;site.uploaded.push(fs.readFileSync(run.items[0].file));
    await ui.locator('[data-tab="history"]').click();await ui.locator(`[data-recheck-run="${run.id}"]`).click();
    let reviewed;
    for(let i=0;i<400;i++){
      const status=await ui.evaluate(async id=>{const state=(await window.handnavigate.state()).value;return {run:state.runs.find(r=>r.id===id),busy:state.busy,error:state.error};},run.id);
      if(!status.busy&&status.run?.reviewOutcome){reviewed=status.run;break;}
      if(!status.busy&&status.error)throw new Error('Recheck failed: '+status.error);
      await pause(150);
    }
    assert.equal(reviewed?.acknowledged,true,JSON.stringify(reviewed));assert.equal(reviewed.items[0].state,'CONFIRMED');assert.equal(site.writes,writesBeforeRecheck);
    assert.equal(JSON.parse(fs.readFileSync(path.join(profile,'workflows.json'),'utf8')).data.runs.find(r=>r.id===run.id).acknowledged,true);
    results.push({test:'a late persisted upload can be rechecked and resolved without resending it',passed:true});
    await closeApp(app);app=await launch();ui=await app.firstWindow({timeout:60000});await ui.waitForSelector('#workflow-title');
    for(let i=0;i<50;i++){try{if((await fetch(endpoint+'/health',{headers})).ok)break;}catch{}await pause(100);}
    const restored=await (await post(request)).json();assert.equal(restored.id,started.id);assert.equal(restored.reused,true);results.push({test:'API settings and request idempotency survive an app restart',passed:true});
    const outputJSON=await new Promise((resolve,reject)=>cp.execFile('powershell.exe',['-NoProfile','-File',path.resolve('Invoke-HandNavigate.ps1'),'-Action','run','-WorkflowId',apiTask.id,'-SettingsPath',path.join(profile,'integration.json'),'-RequestId','owned-powershell-001','-Wait'],{windowsHide:true,timeout:120000},(error,stdout,stderr)=>error?reject(new Error(stderr||error.message)):resolve(stdout)));
    assert.equal(JSON.parse(outputJSON).status,'VERIFIED');results.push({test:'the supplied PowerShell client invokes and waits for a real approved download',passed:true});
    fs.writeFileSync(path.resolve('desktop/evidence/workflow-results.json'),JSON.stringify({passed:results.length,failed:0,scope:'Real Electron browser with owned paginated HTTP sources and destinations, local HTTP API and PowerShell client',results},null,2));console.log(JSON.stringify(results,null,2));
  }finally{
    await closeApp(app);await site.close();removeFixture(folder);
  }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
