'use strict';
const {_electron:electron}=require('playwright'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict');
const {fixture}=require('./fixture.cjs'),{closeApp,removeFixture}=require('./cleanup.cjs'),{imageInfo}=require('../engine.cjs');
async function until(check,timeout=30000){const end=Date.now()+timeout;while(Date.now()<end){if(await check())return;await new Promise(resolve=>setTimeout(resolve,150));}throw new Error('The expected desktop result did not finish.');}
async function main(){
  const site=await fixture(),folder=fs.mkdtempSync(path.join(os.tmpdir(),'hand-collections-ui-')),file=path.join(folder,'sources.json'),downloads=path.join(folder,'Downloads');
  fs.writeFileSync(file,JSON.stringify([{id:'owned',name:'Owned image fixture',searchUrl:site.origin+'/images?topic={{topic}}&count=2',selector:'#gallery img',allowedOrigins:[site.origin],imageOrigins:[],pagination:{kind:'none',maxPages:1}}]));
  let app;
  try{
    app=await electron.launch({args:[path.resolve('.')],env:{...process.env,HANDNAVIGATE_TEST:'1',HANDNAVIGATE_USER_DATA:path.join(folder,'profile'),HANDNAVIGATE_TEST_DOWNLOADS:downloads,HANDNAVIGATE_SOURCES_FILE:file},timeout:60000});
    const ui=await app.firstWindow({timeout:60000}),errors=[];ui.on('pageerror',e=>errors.push(e.message));await ui.waitForSelector('#task-name');
    await ui.locator('#collections-open').click();await ui.locator('#collections-dialog').waitFor({state:'visible'});
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
    const taught=await ui.evaluate(async origin=>{const api=window.handnavigate;let result=await api.newTask({name:'Owned taught search',startUrl:origin+'/search-form'});if(!result.ok)throw new Error(result.error);let task={...result.value,count:1,sourceSelector:'#gallery img',pagination:{kind:'none',maxPages:1},rows:[{topic:'architecture'}],steps:[{op:'fill',locator:{kind:'css',value:'#topic'},value:'{{topic}}'},{op:'click',locator:{kind:'css',value:'button'}}],checks:[{kind:'text',expected:'Results: {{topic}}'}]};result=await api.saveTask({task});if(!result.ok)throw new Error(result.error);task=result.value;await api.approve({id:task.id,sha:task.sha});await api.run({id:task.id,rowIndex:0});return task;},site.origin);
    await until(async()=>{const s=(await ui.evaluate(()=>window.handnavigate.state())).value;return !s.busy&&s.runs.some(r=>r.taskId===taught.id&&r.status==='VERIFIED');});
    await ui.locator('[data-tab=review]').click();await ui.locator('#collection-import-source').click();await ui.locator('#notice').getByText(/available in Image collections/).waitFor();
    await ui.locator('#collections-open').click();const custom=ui.locator('#collections-sources').getByLabel('Owned taught search');await custom.waitFor();for(const item of await ui.locator('#collections-sources input').all())await item.uncheck();await custom.check();await ui.locator('#collections-run-form textarea').fill('gardens');await ui.locator('#collections-run-form input[name=limit]').fill('2');await ui.getByRole('button',{name:'Collect images',exact:true}).click();
    await until(async()=>{const s=(await ui.evaluate(()=>window.handnavigate.collectionStatus())).value;return s.jobs[0]?.topics[0]==='gardens'&&s.jobs[0].status==='VERIFIED_LOCAL';});
    const imported=(await ui.evaluate(()=>window.handnavigate.collectionStatus())).value;assert.equal(imported.jobs[0].saved,2,JSON.stringify(imported.jobs));assert.ok(imported.jobs[0].sources[0].startsWith('custom-'));
    await ui.getByRole('button',{name:'Remove source',exact:true}).click();await ui.locator('#collections-sources').getByLabel('Owned taught search').waitFor({state:'detached'});assert.equal((await ui.evaluate(()=>window.handnavigate.collectionStatus())).value.jobs.length,2);assert.deepEqual(errors,[]);
    const result={checkedAt:new Date().toISOString(),passed:true,checks:['desktop collection panel','managed worker start/stop/restart','two actual decoded owned-source downloads','Downloads destination','private API credential omitted from UI','durable history after restart','embedded browser restored after panel close','real verified taught search imported through Review','custom source downloads with preparation steps and result checks','remove source retains collection history'],pageErrors:errors};fs.writeFileSync('desktop/evidence/collection-results.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
  }finally{await closeApp(app);await site.close();removeFixture(folder);}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
