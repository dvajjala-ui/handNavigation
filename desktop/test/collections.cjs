'use strict';
const {_electron:electron}=require('playwright'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict');
const {fixture}=require('./fixture.cjs'),{closeApp,removeFixture}=require('./cleanup.cjs'),{imageInfo}=require('../engine.cjs');
async function main(){
  const site=await fixture(),folder=fs.mkdtempSync(path.join(os.tmpdir(),'hand-collections-ui-')),file=path.join(folder,'sources.json'),downloads=path.join(folder,'Downloads');
  fs.writeFileSync(file,JSON.stringify([{id:'owned',name:'Owned image fixture',searchUrl:site.origin+'/images?topic={{topic}}&count=2',selector:'#gallery img',allowedOrigins:[site.origin],imageOrigins:[],pagination:{kind:'none',maxPages:1}}]));
  let app;
  try{
    app=await electron.launch({args:[path.resolve('.')],env:{...process.env,HANDNAVIGATE_TEST:'1',HANDNAVIGATE_USER_DATA:path.join(folder,'profile'),HANDNAVIGATE_TEST_DOWNLOADS:downloads,HANDNAVIGATE_SOURCES_FILE:file},timeout:60000});
    const ui=await app.firstWindow({timeout:60000}),errors=[];ui.on('pageerror',e=>errors.push(e.message));await ui.waitForSelector('#task-name');
    await ui.getByRole('button',{name:'Image collections',exact:false}).click();await ui.locator('#collections-dialog').waitFor({state:'visible'});
    assert.equal((await ui.evaluate(()=>window.handnavigate.state())).value.browser.hidden,true);
    await ui.locator('#collections-start').click();await ui.locator('#collections-status').getByText(/Worker running/).waitFor();
    await ui.locator('#collections-run-form textarea').fill('architecture');await ui.locator('#collections-run-form input[name=limit]').fill('2');await ui.getByRole('button',{name:'Collect images',exact:true}).click();
    await ui.locator('#collections-jobs').getByText(/Verified locally/).waitFor({timeout:30000});
    const snapshot=await ui.evaluate(()=>window.handnavigate.collectionStatus());assert.equal(snapshot.ok,true);assert.equal(snapshot.value.managed,true);assert.equal(snapshot.value.jobs[0].saved,2);
    const journal=JSON.parse(fs.readFileSync(path.join(snapshot.value.folder,'collections.json'))).data,job=journal.jobs[0];for(const item of job.items){assert.ok(item.file.startsWith(downloads));assert.equal((await imageInfo(fs.readFileSync(item.file))).sha256,item.sha256);}
    const key=JSON.parse(fs.readFileSync(path.join(snapshot.value.folder,'service-key.json'))).token;assert.equal(JSON.stringify(snapshot).includes(key),false);
    fs.mkdirSync('desktop/evidence',{recursive:true});await ui.screenshot({path:'desktop/evidence/collections.png'});
    await ui.locator('#collections-stop').click();await ui.locator('#collections-status').getByText('Worker stopped',{exact:true}).waitFor();await ui.locator('#collections-start').click();await ui.locator('#collections-status').getByText(/Worker running/).waitFor();assert.equal((await ui.evaluate(()=>window.handnavigate.collectionStatus())).value.jobs[0].status,'VERIFIED_LOCAL');
    await ui.locator('#collections-close').click();await ui.waitForFunction(async()=>!(await window.handnavigate.state()).value.browser.hidden);assert.deepEqual(errors,[]);
    const result={checkedAt:new Date().toISOString(),passed:true,checks:['desktop collection panel','managed worker start/stop/restart','two actual decoded owned-source downloads','Downloads destination','private API credential omitted from UI','durable history after restart','embedded browser restored after panel close'],pageErrors:errors};fs.writeFileSync('desktop/evidence/collection-results.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
  }finally{await closeApp(app);await site.close();removeFixture(folder);}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
