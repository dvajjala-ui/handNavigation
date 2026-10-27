const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),{lock}=require('../lock.cjs');
test('a second service or login process cannot reuse the active browser/state directory',t=>{
  const folder=fs.mkdtempSync(path.join(os.tmpdir(),'handnavigate-lock-test-'));t.after(()=>fs.rmSync(folder,{recursive:true,force:true}));
  const release=lock(folder);assert.throws(()=>lock(folder),/already uses/);release();const again=lock(folder);again();assert.equal(fs.existsSync(path.join(folder,'worker.lock')),false);
});
