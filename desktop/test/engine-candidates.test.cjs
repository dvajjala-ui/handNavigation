const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const sharp=require('sharp');
const {Runner,imageInfo}=require('../engine.cjs');
const {Store,draft}=require('../core.cjs');

const picture=background=>sharp({create:{width:220,height:180,channels:3,background}}).png().toBuffer();

test('image collection skips invalid gallery candidates and saves the next real image',async t=>{
  const folder=fs.mkdtempSync(path.join(os.tmpdir(),'handnavigate-candidates-'));
  t.after(()=>fs.rmSync(folder,{recursive:true,force:true}));
  const valid=await picture('#c77d5d');
  const task={id:'task',sha:'reviewed',name:'Gallery',outputFolder:folder,count:1,sourceSelector:'img',newOnly:false};
  const run={id:'run-12345678',sha:'reviewed',startedAt:new Date().toISOString(),items:[]};
  const store={get:()=>task,known:()=>new Set(),flush:()=>{}};
  const runner=new Runner(store,{effectError:null,wc:{getURL:()=> 'https://example.test/gallery'}},()=>{});
  runner.active={task,run,abort:new AbortController(),deadline:Date.now()+30000};
  runner.candidates=async()=>[{sourceId:'picture-one',urls:['https://example.test/placeholder','https://example.test/photo']}];
  runner.fetch=async url=>url.endsWith('/photo')?valid:Buffer.from('<html>placeholder</html>');
  runner.event=()=>{};
  assert.equal(await runner.collect(task),true);
  assert.equal(run.items.length,1);
  assert.equal(run.items[0].imageUrl,'https://example.test/photo');
  assert.equal(fs.readFileSync(run.items[0].file).equals(valid),true);
});

test('receipt write failure still releases the browser and active runner',async t=>{
  const folder=fs.mkdtempSync(path.join(os.tmpdir(),'handnavigate-receipt-'));t.after(()=>fs.rmSync(folder,{recursive:true,force:true}));
  const blocked=path.join(folder,'not-a-directory');fs.writeFileSync(blocked,'occupied');
  const store=new Store(folder),task=store.save({...draft({startUrl:'https://owned.example',outputFolder:folder}),type:'replay',checks:[{kind:'text',expected:'Ready'}]});store.approve(task.id,task.sha);
  let released=false;const runner=new Runner(store,{beginRun:()=>{},endRun:()=>{released=true;},effectError:null},()=>{});
  runner.navigate=async()=>{};runner.checks=async()=>{runner.active.run.folder=blocked;};
  await assert.rejects(runner.run(task.id));assert.equal(runner.active,null);assert.equal(released,true);
});

test('destination inventory considers a linked original after invalid and resized images',async()=>{
  const thumb=await picture('#8ab8e8'),original=await picture('#183820');
  const expected=(await imageInfo(original)).sha256;
  const runner=new Runner({}, {wc:{getURL:()=> 'https://example.test/gallery'}},()=>{});
  runner.navigate=async()=>{};
  runner.candidates=async()=>[{sourceId:'gallery-one',urls:['https://example.test/thumb','https://example.test/detail','https://example.test/original']}];
  runner.fetch=async url=>url.endsWith('/thumb')?thumb:url.endsWith('/original')?original:Buffer.from('<html>detail page</html>');
  const found=await runner.inventory({galleryUrl:'https://example.test/gallery',gallerySelector:'img'},new Set([expected]));
  assert.equal(found.get(expected),'gallery-one');
  assert.equal(found.size,1);
});
