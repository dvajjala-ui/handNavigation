'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {CollectionManager}=require('../../desktop/collection-manager.cjs'),{fixture}=require('../../desktop/test/fixture.cjs'),{lock}=require('../lock.cjs');
test('desktop manager starts without a Node command, keeps credentials private, downloads and adopts an existing worker',async()=>{
  const folder=fs.mkdtempSync(path.join(os.tmpdir(),'hand-manager-')),site=await fixture(),old=process.env.HANDNAVIGATE_SOURCES_FILE;let manager,adopted;
  try{
    const sourceFile=path.join(folder,'sources.json');fs.writeFileSync(sourceFile,JSON.stringify([{id:'owned',searchUrl:site.origin+'/images?topic={{topic}}&count=2',selector:'#gallery img',allowedOrigins:[site.origin],imageOrigins:[],pagination:{kind:'none',maxPages:1}}]));process.env.HANDNAVIGATE_SOURCES_FILE=sourceFile;
    manager=new CollectionManager(folder,{downloads:path.join(folder,'Downloads'),headless:true});
    await manager.configure({folder:path.join(folder,'data'),dailyLimit:4,channel:process.platform==='win32'?'chrome':''});
    assert.equal((await manager.start()).running,true);const secret=JSON.parse(fs.readFileSync(path.join(folder,'data/service-key.json'))).token;
    assert.equal(JSON.stringify(await manager.status()).includes(secret),false);
    await assert.rejects(manager.configure({folder:path.join(folder,'other'),dailyLimit:4}),/Stop the worker/);
    const input={requestId:'desktop-manager-owned-001',topics:['cats'],sources:['owned'],limit:2,destination:'local'},created=await manager.collect(input);await manager.app.collections.pumpTask;
    const done=manager.app.collections.get(created.id);assert.equal(done.status,'VERIFIED_LOCAL');assert.equal(done.items.length,2);assert.ok(done.items.every(i=>i.file.startsWith(path.join(folder,'Downloads'))));
    adopted=new CollectionManager(folder,{headless:true});assert.equal((await adopted.status()).managed,false);assert.equal((await adopted.collect(input)).reused,true);await adopted.close();assert.equal((await manager.status()).running,true);
    await adopted.stop();for(let n=0;n<50&&(await manager.status()).running;n++)await new Promise(r=>setTimeout(r,20));assert.equal((await manager.status()).running,false);
    await manager.start();assert.equal(manager.app.collections.get(done.id).status,'VERIFIED_LOCAL');
  }finally{await adopted?.close();await manager?.close();await site.close();if(old===undefined)delete process.env.HANDNAVIGATE_SOURCES_FILE;else process.env.HANDNAVIGATE_SOURCES_FILE=old;if(path.resolve(folder).startsWith(path.resolve(os.tmpdir())+path.sep))fs.rmSync(folder,{recursive:true,force:true,maxRetries:10,retryDelay:200});}
});
test('a released profile lock cannot delete a newer lock owned by the same process',()=>{
  const folder=fs.mkdtempSync(path.join(os.tmpdir(),'hand-lock-'));
  try{const old=lock(folder);old();const current=lock(folder);old();assert.throws(()=>lock(folder),/already uses/);current();}
  finally{if(path.resolve(folder).startsWith(path.resolve(os.tmpdir())+path.sep))fs.rmSync(folder,{recursive:true,force:true});}
});
test('corrupt optional collection settings preserve their files and do not prevent the desktop app from starting',async()=>{
  const folder=fs.mkdtempSync(path.join(os.tmpdir(),'hand-manager-config-'));
  try{const file=path.join(folder,'collection-desktop.json');fs.writeFileSync(file,'broken settings');const manager=new CollectionManager(folder);const status=await manager.status();assert.equal(status.running,false);assert.match(status.error,/preserved/);assert.equal(fs.readFileSync(file,'utf8'),'broken settings');}
  finally{if(path.resolve(folder).startsWith(path.resolve(os.tmpdir())+path.sep))fs.rmSync(folder,{recursive:true,force:true});}
});
test('a damaged optional connection can be replaced by choosing a new folder without deleting the old files',async()=>{
  const folder=fs.mkdtempSync(path.join(os.tmpdir(),'hand-manager-repair-'));
  try{const manager=new CollectionManager(folder),oldFolder=manager.settings.folder;fs.mkdirSync(oldFolder,{recursive:true});const oldFile=path.join(oldFolder,'stickerdock.json');fs.writeFileSync(oldFile,'broken connection');await assert.rejects(manager.status());const repaired=await manager.configure({folder:path.join(folder,'recovered'),dailyLimit:20,channel:''});assert.equal(repaired.running,false);assert.equal(fs.readFileSync(oldFile,'utf8'),'broken connection');}
  finally{if(path.resolve(folder).startsWith(path.resolve(os.tmpdir())+path.sep))fs.rmSync(folder,{recursive:true,force:true});}
});
