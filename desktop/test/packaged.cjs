'use strict';
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const cp=require('node:child_process'),fs=require('node:fs'),net=require('node:net'),os=require('node:os'),path=require('node:path');
const {fixture}=require('./fixture.cjs');
const {draft}=require('../core.cjs');
const {imageInfo}=require('../engine.cjs');

const pause=ms=>new Promise(r=>setTimeout(r,ms));
async function freePort(){const server=net.createServer();await new Promise(r=>server.listen(0,'127.0.0.1',r));const port=server.address().port;await new Promise(r=>server.close(r));return port;}
async function main(){
  const executable=path.resolve(process.argv[2]||'dist/win-unpacked/HandNavigate.exe');
  assert.ok(fs.existsSync(executable),'Packaged Windows executable must exist');
  const site=await fixture(),port=await freePort();
  const temp=fs.mkdtempSync(path.join(os.tmpdir(),'handnavigate-packaged-'));
  const output=path.join(temp,'Downloads');fs.mkdirSync(output);
  const child=cp.spawn(executable,[`--remote-debugging-port=${port}`],{env:{...process.env,HANDNAVIGATE_TEST:'1',HANDNAVIGATE_USER_DATA:path.join(temp,'profile')},windowsHide:true,stdio:'ignore'});
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
    const task={...draft({startUrl:site.origin+'/images?count=3',outputFolder:output,imageOrigins:[]}),name:'Packaged smoke test',count:3,sourceSelector:'#gallery img'};
    const saved=await ui.evaluate(arg=>window.handnavigate.saveTask({task:arg}),task);assert.equal(saved.ok,true,JSON.stringify(saved));
    const approved=await ui.evaluate(arg=>window.handnavigate.approve(arg),{id:saved.value.id,sha:saved.value.sha});assert.equal(approved.ok,true,JSON.stringify(approved));
    const started=await ui.evaluate(id=>window.handnavigate.run({id,rowIndex:0}),saved.value.id);assert.equal(started.ok,true,JSON.stringify(started));
    let run;
    for(let i=0;i<300;i++){const state=await ui.evaluate(()=>window.handnavigate.state());run=state.value.runs.find(r=>r.taskId===saved.value.id);if(run&&run.status!=='RUNNING')break;await pause(200);}
    assert.equal(run?.status,'VERIFIED',JSON.stringify(run));assert.equal(run.items.length,3);
    for(const item of run.items){assert.ok(fs.existsSync(item.file));assert.equal((await imageInfo(fs.readFileSync(item.file))).sha256,item.sha256);}
    assert.equal(new Set(run.items.map(i=>i.sha256)).size,3);
    const result={passed:true,executable,files:run.items.length,sha256:run.items.map(i=>i.sha256),portablePath:path.resolve('dist/HandNavigate-0.5.0-Windows.exe')};
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
