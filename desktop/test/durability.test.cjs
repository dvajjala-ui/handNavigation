'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {atomicWrite,Store,draft}=require('../core.cjs');
function fixture(t){const folder=fs.mkdtempSync(path.join(os.tmpdir(),'handnavigate-locks-'));t.after(()=>fs.rmSync(folder,{recursive:true,force:true}));return {folder,file:path.join(folder,'state.json')};}
function lock(t,method,matches,code,failures){
  const original=fs[method];let calls=0;
  fs[method]=(...args)=>{if(matches(args)){calls++;if(calls<=failures)throw Object.assign(new Error('injected '+code),{code});}return original(...args);};
  t.after(()=>{fs[method]=original;});return ()=>calls;
}
test('a verified upload journal survives a temporary replacement lock',t=>{
  const {folder}=fixture(t),store=new Store(folder),task=store.save(draft({startUrl:'https://owned.example',outputFolder:folder}));store.approve(task.id,task.sha);
  const run=store.begin(task.id,0);run.items.push({sha256:'a'.repeat(64),file:path.join(folder,'photo.png'),state:'CONFIRMED'});store.flush();
  const calls=lock(t,'renameSync',args=>args[1]===store.file,'EPERM',2);
  store.finish(run,'VERIFIED');assert.equal(calls(),3);
  const restored=new Store(folder);assert.equal(restored.data.runs[0].status,'VERIFIED');assert.equal(restored.data.runs[0].items[0].state,'CONFIRMED');assert.deepEqual(restored.get(task.id).rehearsals,[0]);
});
test('an antivirus lock on the temporary file can recover before writing',t=>{
  const {file}=fixture(t),calls=lock(t,'openSync',args=>args[0]===file+'.tmp','EACCES',2);
  atomicWrite(file,{saved:true});assert.equal(calls(),3);assert.deepEqual(JSON.parse(fs.readFileSync(file,'utf8')),{saved:true});
});
test('a backup sharing lock recovers while preserving the prior complete state',t=>{
  const {file}=fixture(t);atomicWrite(file,{revision:1});
  const calls=lock(t,'copyFileSync',args=>args[0]===file,'EBUSY',2);atomicWrite(file,{revision:2});assert.equal(calls(),3);
  assert.deepEqual(JSON.parse(fs.readFileSync(file,'utf8')),{revision:2});assert.deepEqual(JSON.parse(fs.readFileSync(file+'.bak','utf8')),{revision:1});
});
test('persistent sharing locks stop after a bounded number of attempts and preserve the primary',t=>{
  const {file}=fixture(t);atomicWrite(file,{revision:1});
  const calls=lock(t,'renameSync',args=>args[1]===file,'EPERM',Infinity);assert.throws(()=>atomicWrite(file,{revision:2}),/injected EPERM/);assert.equal(calls(),7);
  assert.deepEqual(JSON.parse(fs.readFileSync(file,'utf8')),{revision:1});assert.deepEqual(JSON.parse(fs.readFileSync(file+'.tmp','utf8')),{revision:2});
});
test('other filesystem failures stop immediately without replacing the primary',t=>{
  const {file}=fixture(t);atomicWrite(file,{revision:1});
  const calls=lock(t,'renameSync',args=>args[1]===file,'EIO',Infinity);assert.throws(()=>atomicWrite(file,{revision:2}),/injected EIO/);assert.equal(calls(),1);assert.deepEqual(JSON.parse(fs.readFileSync(file,'utf8')),{revision:1});
});
