const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),sharp=require('sharp');
const {Store,draft}=require('../core.cjs');
const {imageInfo,duplicateImage}=require('../engine.cjs');
test('duplicate history includes partial downloads and can span the library',t=>{
  const folder=fs.mkdtempSync(path.join(os.tmpdir(),'handnavigate-history-'));t.after(()=>fs.rmSync(folder,{recursive:true,force:true}));
  const store=new Store(folder),a=store.save(draft({startUrl:'https://owned.example',outputFolder:folder})),b=store.save(draft({startUrl:'https://owned.example/other',outputFolder:folder}));
  store.approve(a.id,a.sha);const run=store.begin(a.id,0);run.items.push({sha256:'a'.repeat(64),file:path.join(folder,'photo.png'),state:'DOWNLOADED'});store.finish(run,'PARTIAL');
  assert.equal(store.known(a.id).size,1);assert.equal(store.knownItems(b.id).length,0);assert.equal(store.knownItems(b.id,'library').length,1);
  assert.equal(new Store(folder).known(a.id).size,1);
});
test('pixel identity detects alternate encodings and optional similarity detects a resized photo',async()=>{
  const source=Buffer.from('<svg width="600" height="400"><defs><linearGradient id="g"><stop stop-color="#186f98"/><stop offset="1" stop-color="#ecab55"/></linearGradient></defs><rect width="600" height="400" fill="url(#g)"/><circle cx="180" cy="150" r="100" fill="#fff"/><path d="M0 350L250 90L420 330L600 60V400H0Z" fill="#274b38"/></svg>');
  const png=await sharp(source).png().toBuffer(),alternate=await sharp(png).png({compressionLevel:0}).toBuffer(),small=await sharp(png).resize(300,200).jpeg({quality:85}).toBuffer();
  const [a,b,c]=await Promise.all([imageInfo(png),imageInfo(alternate),imageInfo(small)]);
  assert.notEqual(a.sha256,b.sha256);assert.equal(duplicateImage(a,b),true);assert.equal(duplicateImage(a,c,true),true);
  const different=await imageInfo(await sharp({create:{width:300,height:200,channels:3,background:'#cc0055'}}).png().toBuffer());assert.equal(duplicateImage(a,different,true),false);
});
test('pagination and duplicate settings invalidate approval; incomplete Next drafts cannot run',t=>{
  const folder=fs.mkdtempSync(path.join(os.tmpdir(),'handnavigate-paging-'));t.after(()=>fs.rmSync(folder,{recursive:true,force:true}));const store=new Store(folder);
  let task=store.save(draft({startUrl:'https://owned.example',outputFolder:folder}));store.approve(task.id,task.sha);
  task=store.save({...task,pagination:{kind:'next',maxPages:10,locator:null}});assert.equal(task.approvedSha,null);assert.throws(()=>store.approve(task.id,task.sha));
  assert.throws(()=>store.save({...task,pagination:{kind:'next',maxPages:1000}}));
  task=store.save({...task,pagination:{kind:'next',maxPages:10,locator:{kind:'css',value:'a[rel=next]'}}});store.approve(task.id,task.sha);task=store.save({...task,dedupeScope:'library',skipSimilar:true});assert.equal(task.approvedSha,null);
});
