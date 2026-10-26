'use strict';
const {_electron:electron}=require('playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {fixture}=require('./fixture.cjs');
const {imageInfo}=require('../engine.cjs');
const {draft}=require('../core.cjs');
async function finished(application,name,minimumRuns=1){
  const until=Date.now()+60000;
  while(Date.now()<until){const state=await application.evaluate(()=>({active:!!global.__handnavigateTest.runner.active,runs:JSON.parse(JSON.stringify(global.__handnavigateTest.store.data.runs))}));
    if(!state.active&&state.runs.length>=minimumRuns&&state.runs[0]?.taskName===name&&state.runs[0]?.status!=='RUNNING')return state.runs[0];
    await new Promise(r=>setTimeout(r,150));
  }
  throw new Error('Timed out waiting for '+name);
}
async function main(){
  const site=await fixture(),dir=fs.mkdtempSync(path.join(os.tmpdir(),'handnavigate-app-e2e-')),output=path.join(dir,'Downloads');fs.mkdirSync(output);
  const evidence=path.resolve('desktop/evidence');fs.mkdirSync(evidence,{recursive:true});
  let application;const results=[];
  try{
    application=await electron.launch({args:[path.resolve('.')],env:{...process.env,HANDNAVIGATE_TEST:'1',HANDNAVIGATE_USER_DATA:path.join(dir,'app')},timeout:60000});
    application.process().stderr.on('data',data=>{fs.appendFileSync(path.join(evidence,'electron-console.txt'),data);});
    const ui=await application.firstWindow();await ui.waitForSelector('#workflow-title');await ui.locator('#task-name').fill('Owned 20-image acceptance');
    console.log('App launched');
    await ui.locator('#task-url').fill(site.origin+'/images?topic={{topic}}');await ui.locator('#task-values').fill('landscape\narchitecture');
    await ui.locator('#save-task').click();
    await application.evaluate(({app},root)=>{const t=global.__handnavigateTest.store.data.tasks[0];t.outputFolder=root;t.sourceSelector='#gallery img';t.imageOrigins=[];global.__handnavigateTest.store.save(t);global.__handnavigateTest.flush();},output);
    // Reload the local editor to reflect the saved test folder, without changing its app API.
    await ui.reload();await ui.waitForSelector('#open-site');await ui.locator('#open-site').click();
    await ui.waitForFunction(()=>document.querySelector('#browser-address').value.includes('/images'));
    await ui.locator('[data-tab="review"]').click();await ui.locator('#review-ack').check();await ui.locator('#approve-run').click();
    await ui.waitForFunction(()=>document.querySelector('#run-state').textContent==='Last run verified',{timeout:60000});
    let runs=await application.evaluate(()=>global.__handnavigateTest.store.data.runs);assert.equal(runs[0].status,'VERIFIED');assert.equal(runs[0].items.length,20);
    for(const item of runs[0].items)assert.equal((await imageInfo(fs.readFileSync(item.file))).sha256,item.sha256);
    results.push({test:'real desktop UI source -> 20 independently validated files',passed:true,images:20});
    console.log('20 images verified');
    await ui.screenshot({path:path.join(evidence,'verified-download.png')});
    const appScreenshot=await application.evaluate(async()=> (await global.__handnavigateTest.window.capturePage()).toPNG().toString('base64'));
    fs.writeFileSync(path.join(evidence,'app-window.png'),Buffer.from(appScreenshot,'base64'));
    await ui.locator('[data-tab="setup"]').click();await ui.locator('#run-row').selectOption('1');await ui.locator('#run-now').click();
    await ui.waitForFunction(()=>document.querySelector('#run-state').textContent==='Last run verified'&&document.querySelector('#run-detail').textContent.includes('20 files'),{timeout:60000});
    await ui.waitForFunction(async()=>{const s=await window.handnavigate.state();return s.value.runs.filter(r=>r.status==='VERIFIED').length>=2;},{timeout:60000});
    runs=await application.evaluate(()=>global.__handnavigateTest.store.data.runs);assert.equal(runs[0].items.length,20);assert.equal(runs[0].inputs.topic,'architecture');
    assert.equal(new Set(runs.slice(0,2).flatMap(r=>r.items.map(i=>i.sha256))).size,40);
    results.push({test:'same approved workflow, second variable row, 20 distinct new files',passed:true});
    console.log('Second topic verified');
    await ui.locator('[data-tab="schedule"]').click();await ui.locator('#schedule-enable').click();
    let t=await application.evaluate(()=>global.__handnavigateTest.store.data.tasks[0]);assert.equal(t.schedule.enabled,true);results.push({test:'daily schedule enabled through UI after both rows verified',passed:true});
    await ui.locator('#schedule-pause').click();
    // Generic taught workflow: fill and click are demonstrated on a real HTTP page.
    const replayDraft={...draft({startUrl:site.origin+'/result',outputFolder:output,type:'replay',imageOrigins:[]}),name:'Taught form replay',checks:[{kind:'text',expected:'Ready: {{topic}}'}],rows:[{topic:'gardens'},{topic:'architecture'}]};
    await application.evaluate(async(_electron,arg)=>{const api=global.__handnavigateTest;const t=api.store.save(arg);api.setSelected(t.id);await api.browser.load(t.startUrl);return t;},replayDraft);
    await ui.locator('[data-tab="setup"]').click();await ui.locator('#record').click();
    const pages=application.context().pages();const website=pages.find(p=>p.url().includes('/result'));assert.ok(website,'embedded browser appears as a Playwright page');
    await website.getByLabel('Topic',{exact:true}).fill('gardens');await website.getByRole('button',{name:'Prepare preview',exact:true}).click();await ui.locator('#stop-record').click();
    await ui.locator('input[data-step-value]').first().fill('{{topic}}');await ui.locator('#save-steps').click();
    t=await application.evaluate(()=>global.__handnavigateTest.store.data.tasks.find(t=>t.name==='Taught form replay'));assert.ok(t.steps.some(s=>s.op==='fill'&&s.value==='{{topic}}'));assert.ok(t.steps.some(s=>s.op==='click'));
    await ui.locator('#review-ack').check();await ui.locator('#approve-run').click();
    const taughtResult=await finished(application,'Taught form replay',3);assert.equal(taughtResult.status,'VERIFIED',JSON.stringify(taughtResult));
    console.log('Taught replay verified');
    results.push({test:'actual teaching recorder -> parameter binding -> independent visible-result check',passed:true,steps:t.steps.length});
    await ui.screenshot({path:path.join(evidence,'taught-task.png')});
    // Shared app session: human-style ordinary navigation establishes an owned cookie.
    await application.evaluate(async(_e,url)=>{await global.__handnavigateTest.browser.load(url);},site.origin+'/login');
    await application.evaluate(async(_e,url)=>{await global.__handnavigateTest.browser.load(url);},site.origin+'/private');
    const privatePage=application.context().pages().find(p=>p.url().includes('/private'));await privatePage.getByText('Private gallery',{exact:true}).waitFor();
    results.push({test:'embedded browser reuses the same authenticated session',passed:true});
    // Actual desktop transfer path: browser upload and independent remote image reads.
    const transferDraft={...draft({name:'Desktop upload acceptance',startUrl:site.origin+'/images?count=2',outputFolder:output,imageOrigins:[]}),count:2,sourceSelector:'#gallery img',type:'transfer',newOnly:false,
      target:{url:site.origin+'/target',fileInput:{kind:'css',value:'#upload'},submit:{kind:'role',role:'button',name:'Upload image'},galleryUrl:site.origin+'/target',gallerySelector:'#gallery img'}};
    const transferId=await application.evaluate((_e,d)=>{const api=global.__handnavigateTest;const t=api.store.save(d);api.store.approve(t.id,t.sha);api.setSelected(t.id);api.runner.run(t.id,0);return t.id;},transferDraft);
    const transferred=await finished(application,'Desktop upload acceptance',4);assert.equal(transferred.status,'VERIFIED',JSON.stringify(transferred));assert.equal(site.uploaded.length,2);assert.ok(transferred.items.every(i=>i.state==='CONFIRMED'));
    results.push({test:'desktop engine downloads two images, uploads through real file input and verifies remote originals',passed:true});
    await application.evaluate((_e,id)=>{global.__handnavigateTest.runner.run(id,0);},transferId);
    const repeated=await finished(application,'Desktop upload acceptance',5);assert.equal(repeated.status,'VERIFIED',JSON.stringify(repeated));assert.equal(site.uploaded.length,2);
    results.push({test:'repeating transfer confirms remote copies without duplicate uploads',passed:true});
    // Exercise genuine failures through the same app engine, not a mocked completion path.
    const executeDraft=async d=>{const before=await application.evaluate(()=>global.__handnavigateTest.store.data.runs.length);const id=await application.evaluate((_e,task)=>{const api=global.__handnavigateTest,t=api.store.save(task);api.store.approve(t.id,t.sha);api.setSelected(t.id);api.runner.run(t.id,0);return t.id;},d);return {id,result:await finished(application,d.name,before+1)};};
    const base=draft({startUrl:site.origin+'/images?count=2',outputFolder:output,imageOrigins:[]});
    const partial=await executeDraft({...base,name:'Fewer than requested',count:3,sourceSelector:'#gallery img'});assert.equal(partial.result.status,'PARTIAL',JSON.stringify(partial.result));assert.equal(partial.result.items.length,2);results.push({test:'insufficient source images returns PARTIAL with real files preserved',passed:true});
    site.controls.corrupt=true;const corrupt=await executeDraft({...base,name:'Corrupt content',count:1,sourceSelector:'#gallery img'});assert.equal(corrupt.result.status,'HALTED');assert.equal(corrupt.result.items.length,0);site.controls.corrupt=false;results.push({test:'HTML pretending to be an image is rejected',passed:true});
    const denied=await executeDraft({...base,name:'Unreviewed image destination',startUrl:site.origin+'/images?count=1&external='+encodeURIComponent('https://unreviewed.invalid/image.png'),sourceSelector:'#gallery img',count:1,imageOrigins:[],allowedOrigins:[site.origin]});assert.equal(denied.result.status,'HALTED');assert.equal(denied.result.items.length,0);results.push({test:'image from an unreviewed origin is rejected before transfer',passed:true});
    site.controls.fakeUpload=true;
    const fake=await executeDraft({...transferDraft,name:'False upload confirmation',count:3,startUrl:site.origin+'/images?count=3'});assert.equal(fake.result.status,'NEEDS_REVIEW',JSON.stringify(fake.result));const writesBefore=site.writes;
    const retry=await application.evaluate(async(_e,id)=>{try{await global.__handnavigateTest.runner.run(id,0);return 'ran';}catch(e){return e.message;}},fake.id);assert.ok(retry.includes('Review'));assert.equal(site.writes,writesBefore);site.controls.fakeUpload=false;
    results.push({test:'fake upload success cannot pass; uncertain write is never blindly repeated',passed:true});
    await ui.locator('[data-tab="history"]').click();
    ui.once('dialog',dialog=>dialog.accept());await ui.locator(`[data-ack-run="${fake.result.id}"]`).click();
    const resolved=await application.evaluate((_e,id)=>global.__handnavigateTest.store.data.runs.find(r=>r.id===id),fake.result.id);
    assert.equal(resolved.items.find(i=>i.state==='RESOLVED_NOT_UPLOADED')?.sha256?.length,64);
    const beforeRecovery=await application.evaluate(()=>global.__handnavigateTest.store.data.runs.length);
    await application.evaluate((_e,id)=>{global.__handnavigateTest.runner.run(id,0);},fake.id);
    const recovered=await finished(application,'False upload confirmation',beforeRecovery+1);assert.equal(recovered.status,'VERIFIED',JSON.stringify(recovered));assert.equal(site.uploaded.length,3);assert.equal(site.writes,writesBefore+1);
    results.push({test:'explicitly resolved missing upload retries once and verifies the original without duplicates',passed:true});
    const replaySecond=await application.evaluate(async(_e,id)=>{await global.__handnavigateTest.runner.run(id,0);return global.__handnavigateTest.store.data.runs[0];},t.id);assert.equal(replaySecond.status,'VERIFIED',JSON.stringify(replaySecond));results.push({test:'recorded workflow replays with a different variable value',passed:true});
    const daily=await executeDraft({...base,name:'Actual daily worker',startUrl:site.origin+'/images?count=10',count:1,sourceSelector:'#gallery img'});assert.equal(daily.result.status,'VERIFIED');
    const dailyRun=await application.evaluate(async(_e,id)=>{const q=global.__handnavigateTest.queue;q.enable(id,true,'09:00','UTC');q.clock=()=>Date.now()+2*86400000;try{return await q.tick();}finally{q.clock=()=>Date.now();const t=global.__handnavigateTest.store.get(id);t.schedule.enabled=false;global.__handnavigateTest.store.flush();}},daily.id);
    assert.equal(dailyRun.length,1);assert.equal(dailyRun[0].status,'VERIFIED',JSON.stringify(dailyRun));assert.notEqual(dailyRun[0].items[0].sha256,daily.result.items[0].sha256);results.push({test:'daily queue executes the real embedded-browser downloader and selects a new image',passed:true});
    await application.evaluate(()=>global.__handnavigateTest.shutdown());await application.close();application=null;
    const reopened=await electron.launch({args:[path.resolve('.')],env:{...process.env,HANDNAVIGATE_TEST:'1',HANDNAVIGATE_USER_DATA:path.join(dir,'app')},timeout:60000});application=reopened;
    const restored=await reopened.firstWindow();await restored.waitForSelector('#workflow-title');
    const snapshot=await reopened.evaluate(()=>({tasks:global.__handnavigateTest.store.data.tasks.length,runs:global.__handnavigateTest.store.data.runs.length}));assert.ok(snapshot.tasks>=3);assert.ok(snapshot.runs>=5);results.push({test:'app restart restores workflows and verified run history',passed:true});
    await reopened.evaluate(async(_e,url)=>global.__handnavigateTest.browser.load(url),site.origin+'/private');
    const savedSession=reopened.context().pages().find(p=>p.url().includes('/private'));await savedSession.getByText('Private gallery',{exact:true}).waitFor();results.push({test:'same browser login survives app restart',passed:true});
    fs.writeFileSync(path.join(evidence,'e2e-results.json'),JSON.stringify({passed:results.length,failed:0,scope:'Real Electron UI and embedded browser, actual owned HTTP pages and image bytes',results},null,2));
    console.log(JSON.stringify(results,null,2));
    await reopened.evaluate(()=>global.__handnavigateTest.shutdown());await reopened.close();application=null;
  }catch(e){if(application){try{const page=await application.firstWindow();await page.screenshot({path:path.join(evidence,'failure.png')});console.error(await page.locator('#notice').textContent());}catch{}}throw e;}
  finally{if(application){await application.evaluate(()=>global.__handnavigateTest?.shutdown()).catch(()=>{});await application.close().catch(()=>{});}await site.close();fs.rmSync(dir,{recursive:true,force:true});}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
