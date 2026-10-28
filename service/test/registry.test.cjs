'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {Store,draft}=require('../../desktop/core.cjs'),{Runner}=require('../../desktop/engine.cjs'),{ServiceBrowser}=require('../browser.cjs'),{Collections}=require('../collections.cjs'),registry=require('../registry.cjs'),{fixture}=require('../../desktop/test/fixture.cjs');
const browserOptions={headless:true,channel:process.platform==='win32'?'chrome':undefined};
async function qualify(folder,site,options){
  const store=new Store(path.join(folder,'teaching')),task=store.save({...draft({startUrl:site.origin+'/search-form',outputFolder:path.join(folder,'proof'),imageOrigins:[]}),name:'Owned topic search',sourceSelector:'#gallery img',count:1,rows:[{topic:'architecture'}],pagination:{kind:'none',maxPages:1},...options});
  assert.throws(()=>registry.compile(task,store.data.runs),/approved/);store.approve(task.id,task.sha);assert.throws(()=>registry.compile(task,store.data.runs),/verify/);
  const browser=await ServiceBrowser.open(path.join(folder,'teaching-profile'),browserOptions);
  try{const run=await new Runner(store,browser).run(task.id);assert.equal(run.status,'VERIFIED',JSON.stringify(run));return {store,task};}finally{await browser.close();}
}
function cleanup(folder){if(path.resolve(folder).startsWith(path.resolve(os.tmpdir())+path.sep))fs.rmSync(folder,{recursive:true,force:true,maxRetries:10,retryDelay:100});}
test('a real verified form-search workflow becomes a durable source with its taught preparation and result checks',async()=>{
  const folder=fs.mkdtempSync(path.join(os.tmpdir(),'hand-recipe-')),site=await fixture();let collections;
  try{
    const {store,task}=await qualify(folder,site,{steps:[{op:'fill',locator:{kind:'css',value:'#topic'},value:'{{topic}}'},{op:'click',locator:{kind:'css',value:'button'}}],checks:[{kind:'text',expected:'Results: {{topic}}'}]});
    const source=registry.compile(task,store.data.runs);registry.save(folder,source);assert.equal(registry.load(folder).length,5);assert.equal(registry.read(folder)[0].workflowSha,task.sha);
    collections=new Collections(path.join(folder,'collections'),{sources:[source],dailyLimit:20,browser:browserOptions});
    const spec={requestId:'verified-custom-form-search',topics:['gardens'],sources:[source.id],limit:2,destination:'local'},{job}=collections.create(spec);await collections.pumpTask;
    const done=collections.get(job.id);assert.equal(done.status,'VERIFIED_LOCAL',JSON.stringify(done));assert.equal(done.items.length,2);assert.ok(done.items.every(i=>i.imageUrl.includes('/image/')));assert.deepEqual(done.sourceRecipes[0].steps,task.steps);
    registry.remove(folder,source.id);assert.equal(registry.load(folder).length,4);collections.sources=registry.load(folder);assert.equal(collections.create(spec).reused,true);
    const damaged=JSON.parse(fs.readFileSync(path.join(folder,'source-recipes.json')));damaged.data.recipes.push(source);fs.writeFileSync(path.join(folder,'source-recipes.json'),JSON.stringify(damaged));assert.throws(()=>registry.read(folder),/integrity/);
  }finally{await collections?.close();await site.close();cleanup(folder);}
});
test('an incomplete collection resumes its frozen recipe after source removal and rejects an edited workflow without a new rehearsal',async()=>{
  const folder=fs.mkdtempSync(path.join(os.tmpdir(),'hand-recipe-resume-')),site=await fixture();let collections;
  try{
    const {store,task}=await qualify(folder,site,{startUrl:site.origin+'/limited?topic={{topic}}'}),source=registry.compile(task,store.data.runs);
    const edited=store.save({...task,sourceSelector:'img.other'});assert.throws(()=>registry.compile(edited,store.data.runs),/approved/);
    const collectionFolder=path.join(folder,'collections');collections=new Collections(collectionFolder,{sources:[source],dailyLimit:20,browser:browserOptions});
    const spec={requestId:'frozen-custom-source-retry',topics:['cats'],sources:[source.id],limit:3,destination:'local'},{job}=collections.create(spec);await collections.pumpTask;assert.equal(collections.get(job.id).status,'PARTIAL');await collections.close();
    site.controls.limit=3;collections=new Collections(collectionFolder,{sources:registry.load(folder),dailyLimit:20,browser:browserOptions});collections.resume(job.id);await collections.pumpTask;
    const done=collections.get(job.id);assert.equal(done.status,'VERIFIED_LOCAL',JSON.stringify(done));assert.equal(done.items.length,3);assert.equal(new Set(done.items.map(i=>i.sha256)).size,3);assert.equal(collections.create(spec).reused,true);
  }finally{await collections?.close();await site.close();cleanup(folder);}
});
