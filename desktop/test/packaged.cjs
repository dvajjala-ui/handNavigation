'use strict';
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const cp=require('node:child_process'),fs=require('node:fs'),net=require('node:net'),os=require('node:os'),path=require('node:path');
const {fixture}=require('./fixture.cjs');
const {draft,hash}=require('../core.cjs');
const {imageInfo}=require('../engine.cjs');

const pause=ms=>new Promise(r=>setTimeout(r,ms));
async function freePort(){const server=net.createServer();await new Promise(r=>server.listen(0,'127.0.0.1',r));const port=server.address().port;await new Promise(r=>server.close(r));return port;}
async function main(){
  const executable=path.resolve(process.argv[2]||'dist/HandNavigate-'+require('../../package.json').version+'-Windows.exe');
  assert.ok(fs.existsSync(executable),'Packaged Windows executable must exist');
  const site=await fixture(),port=await freePort();
  const temp=fs.mkdtempSync(path.join(os.tmpdir(),'handnavigate-packaged-'));
  const output=path.join(temp,'Downloads');fs.mkdirSync(output);
  const sourcesFile=path.join(temp,'sources.json');fs.writeFileSync(sourcesFile,JSON.stringify([{id:'owned',name:'Owned HTTP images',searchUrl:site.origin+'/images?topic={{topic}}&count=2',selector:'#gallery img',allowedOrigins:[site.origin],imageOrigins:[],pagination:{kind:'none',maxPages:1}}]));
  const child=cp.spawn(executable,[`--remote-debugging-port=${port}`],{env:{...process.env,HANDNAVIGATE_TEST:'1',HANDNAVIGATE_USER_DATA:path.join(temp,'profile'),HANDNAVIGATE_TEST_DOWNLOADS:output,HANDNAVIGATE_SOURCES_FILE:sourcesFile},windowsHide:true,stdio:'ignore'});
  let browser,primaryError;
  try{
    const endpoint=`http://127.0.0.1:${port}`;let ready=false;
    for(let i=0;i<300;i++){try{const response=await fetch(endpoint+'/json/version');if(response.ok){ready=true;break;}}catch{}await pause(200);}
    assert.ok(ready,'Packaged Electron debugger did not start');
    browser=await chromium.connectOverCDP(endpoint);
    const context=browser.contexts()[0];let ui;
    for(let i=0;i<150;i++){ui=context.pages().find(p=>p.url().endsWith('/index.html'));if(ui)break;await pause(200);}
    assert.ok(ui,'Packaged UI did not open');await ui.waitForSelector('#workflow-title');
    assert.match(await ui.title(),/HandNavigate/);
    assert.equal((await ui.evaluate(()=>window.handnavigate.state())).value.appVersion,require('../../package.json').version,'The packaged runtime must match the advertised app version');
    const task={...draft({startUrl:site.origin+'/images?count=3',outputFolder:output,imageOrigins:[]}),name:'Packaged smoke test',count:3,sourceSelector:'#gallery img',newOnly:false};
    const saved=await ui.evaluate(arg=>window.handnavigate.saveTask({task:arg}),task);assert.equal(saved.ok,true,JSON.stringify(saved));
    const approved=await ui.evaluate(arg=>window.handnavigate.approve(arg),{id:saved.value.id,sha:saved.value.sha});assert.equal(approved.ok,true,JSON.stringify(approved));
    const started=await ui.evaluate(id=>window.handnavigate.run({id,rowIndex:0}),saved.value.id);assert.equal(started.ok,true,JSON.stringify(started));
    let run;
    for(let i=0;i<300;i++){const state=await ui.evaluate(()=>window.handnavigate.state());run=state.value.runs.find(r=>r.taskId===saved.value.id);if(run&&run.status!=='RUNNING')break;await pause(200);}
    assert.equal(run?.status,'VERIFIED',JSON.stringify(run));assert.equal(run.items.length,3);
    for(const item of run.items){assert.ok(fs.existsSync(item.file));assert.equal((await imageInfo(fs.readFileSync(item.file))).sha256,item.sha256);}
    assert.equal(new Set(run.items.map(i=>i.sha256)).size,3);
    const apiPort=await freePort(),enabled=await ui.evaluate(port=>window.handnavigate.configureAPI({enabled:true,port}),apiPort);assert.equal(enabled.ok,true,JSON.stringify(enabled));
    const state=await ui.evaluate(()=>window.handnavigate.state());assert.equal(state.value.integration.clientAvailable,true);
    const settings=JSON.parse(fs.readFileSync(path.join(temp,'profile','integration.json'),'utf8')),headers={Authorization:'Bearer '+settings.token,'Content-Type':'application/json'},apiEndpoint='http://127.0.0.1:'+apiPort+'/v1';
    const request={workflowId:saved.value.id,rowIndex:0,requestId:'packaged-approved-once'},start=await (await fetch(apiEndpoint+'/runs',{method:'POST',headers,body:JSON.stringify(request)})).json();
    let apiRun;for(let i=0;i<300;i++){apiRun=await (await fetch(apiEndpoint+'/runs/'+start.id,{headers})).json();if(apiRun.status!=='RUNNING')break;await pause(200);}
    assert.equal(apiRun.status,'VERIFIED',JSON.stringify(apiRun));assert.equal(apiRun.items.length,3);
    const repeat=await (await fetch(apiEndpoint+'/runs',{method:'POST',headers,body:JSON.stringify(request)})).json();assert.equal(repeat.id,start.id);assert.equal(repeat.reused,true);
    site.controls.slowUploadMs=3200;
    const transfer={...task,id:undefined,name:'Packaged slow upload',type:'transfer',startUrl:site.origin+'/images?count=1',count:1,target:{url:site.origin+'/target',fileInput:{kind:'css',value:'#upload'},submit:{kind:'css',value:'#send'},galleryUrl:site.origin+'/target',gallerySelector:'#gallery img'}};
    const transferSaved=await ui.evaluate(task=>window.handnavigate.saveTask({task}),transfer);assert.equal(transferSaved.ok,true,JSON.stringify(transferSaved));
    assert.equal((await ui.evaluate(arg=>window.handnavigate.approve(arg),{id:transferSaved.value.id,sha:transferSaved.value.sha})).ok,true);
    const transferStart=await ui.evaluate(id=>window.handnavigate.run({id,rowIndex:0}),transferSaved.value.id);assert.equal(transferStart.ok,true,JSON.stringify(transferStart));
    let transferred;for(let i=0;i<300;i++){const state=await ui.evaluate(()=>window.handnavigate.state());transferred=state.value.runs.find(r=>r.id===transferStart.value.runId);if(!state.value.busy&&transferred?.status!=='RUNNING')break;await pause(200);}
    assert.equal(transferred?.status,'VERIFIED',JSON.stringify(transferred));assert.equal(site.writes,1);assert.equal(site.uploaded.length,1);assert.equal(site.controls.abortedUploads,0);assert.equal(transferred.items[0].state,'CONFIRMED');
    assert.equal((await imageInfo(site.uploaded[0])).sha256,transferred.items[0].sha256);
    const savedState=JSON.parse(fs.readFileSync(path.join(temp,'profile','workflows.json'),'utf8'));assert.equal(savedState.sha,hash(savedState.data));
    const savedTransfer=savedState.data.runs.find(r=>r.id===transferred.id);assert.equal(savedTransfer.status,'VERIFIED');assert.equal(savedTransfer.items[0].state,'CONFIRMED');
    assert.equal(JSON.parse(fs.readFileSync(path.join(transferred.folder,'manifest.json'),'utf8')).status,'VERIFIED');
    await ui.locator('#collections-open').click();await ui.locator('#collections-dialog').waitFor({state:'visible'});await ui.locator('#collections-start').click();await ui.locator('#collections-status').getByText(/Worker running/).waitFor();
    await ui.locator('#collections-run-form textarea').fill('nature');await ui.locator('#collections-run-form input[name=limit]').fill('2');await ui.getByRole('button',{name:'Collect images',exact:true}).click();await ui.locator('#collections-jobs').getByText(/Verified locally/).waitFor({timeout:60000});
    const collections=(await ui.evaluate(()=>window.handnavigate.collectionStatus())).value;assert.equal(collections.jobs[0].saved,2);assert.equal(collections.managed,true);
    const collectionJournal=JSON.parse(fs.readFileSync(path.join(collections.folder,'collections.json'))).data;for(const item of collectionJournal.jobs[0].items){assert.ok(item.file.startsWith(output));assert.equal((await imageInfo(fs.readFileSync(item.file))).sha256,item.sha256);}
    const collectionKey=JSON.parse(fs.readFileSync(path.join(collections.folder,'service-key.json'))).token;assert.equal(JSON.stringify(collections).includes(collectionKey),false);await ui.locator('#collections-stop').click();await ui.locator('#collections-close').click();
    const result={passed:true,executable,files:run.items.length,sha256:run.items.map(i=>i.sha256),apiVerified:true,idempotencyVerified:true,scriptClientBundled:true,slowUploadVerified:true,durableResultVerified:true,collectionWorkerBundled:true,collectionDownloadsVerified:2,collectionCredentialPrivate:true,portablePath:path.resolve('dist/HandNavigate-'+require('../../package.json').version+'-Windows.exe')};
    fs.mkdirSync(path.resolve('desktop/evidence'),{recursive:true});fs.writeFileSync(path.resolve('desktop/evidence/packaged-results.json'),JSON.stringify(result,null,2));
    console.log(JSON.stringify(result,null,2));
    await ui.evaluate(()=>window.close()).catch(()=>{});
  }catch(e){primaryError=e;throw e;}finally{
    if(browser)await browser.close().catch(()=>{});
    if(child.exitCode===null){try{cp.execFileSync('taskkill',['/PID',String(child.pid),'/T','/F'],{stdio:'ignore'});}catch{}}
    await site.close();
    const resolved=path.resolve(temp),root=path.resolve(os.tmpdir())+path.sep;
    if(resolved.startsWith(root))try{fs.rmSync(resolved,{recursive:true,force:true,maxRetries:10,retryDelay:500});}catch(e){if(!primaryError)throw e;console.error('Cleanup warning:',e.message);}
  }
}
main().catch(e=>{console.error(e);process.exitCode=1;});
