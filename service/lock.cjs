'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const lease=require('proper-lockfile');
const {setTimeout:pause}=require('node:timers/promises'),{performance}=require('node:perf_hooks');
const STALE_MS=30000,UPDATE_MS=10000;
function migrateLegacy(file){
  let stat;try{stat=fs.lstatSync(file);}catch(error){if(error.code==='ENOENT')return;throw error;}
  if(stat.isSymbolicLink())throw new Error('The worker lock is a link. Preserve the data folder and inspect it before starting.');
  if(stat.isDirectory())return;
  if(!stat.isFile())throw new Error('The worker lock has an unexpected type. Preserve it before starting.');
  let owner;try{owner=JSON.parse(fs.readFileSync(file,'utf8'));}catch{throw new Error('Worker lock is unreadable; preserve the profile and inspect its running process.');}
  if(!owner||!Number.isInteger(owner.pid)||owner.pid<=0)throw new Error('Invalid worker lock; inspect it before starting.');
  let alive=true;try{process.kill(owner.pid,0);}catch(error){if(error.code==='ESRCH')alive=false;else throw error;}
  if(alive)throw new Error('A HandNavigate worker already uses this data folder.');
  // Old workers did not heartbeat. Preserve a dead owner's diagnostic record,
  // but never infer that a still-running legacy worker is stale from its age.
  try{
    fs.copyFileSync(file,file+'.legacy-'+crypto.randomUUID(),fs.constants.COPYFILE_EXCL);
    // unlink refuses directories: a concurrent upgrader may already have
    // replaced the legacy file with its active lease. Never rename that lease.
    fs.unlinkSync(file);
  }catch(error){
    let current;try{current=fs.lstatSync(file);}catch(changed){if(changed.code==='ENOENT')return;throw changed;}
    if(current.isDirectory()&&!current.isSymbolicLink())return;
    throw error;
  }
}
function lock(folder,options={}){
  fs.mkdirSync(folder,{recursive:true});folder=fs.realpathSync(folder);const file=path.join(folder,'worker.lock');
  migrateLegacy(file);
  let release;
  try{release=lease.lockSync(folder,{lockfilePath:file,stale:STALE_MS,update:UPDATE_MS,retries:0,
    onCompromised:()=>{
      // Stop work when exclusivity is lost. The CLI exits; the desktop cancels
      // its worker. Durable collection/receipt journals reconcile on restart.
      const error=new Error('HandNavigate lost its data-folder lease. Saved files are preserved; stop other workers before restarting.');
      if(typeof options.onCompromised==='function'){options.onCompromised(error);return;}
      process.stderr.write(error.message+'\n');
      process.exit(1);
    }});
  }catch(error){if(error.code==='ELOCKED')throw Object.assign(new Error('A HandNavigate worker already uses this data folder, or its crashed lease is less than 30 seconds old.'),{code:'ELOCKED'});throw error;}
  let released=false;return ()=>{if(released)return;released=true;try{release();}catch(error){if(!['ERELEASED','ENOTACQUIRED'].includes(error.code))throw error;}};
}
async function waitForLock(folder,options={}){
  const deadline=performance.now()+STALE_MS+5000;
  for(;;){
    options.signal?.throwIfAborted();
    try{return lock(folder,options);}catch(error){if(error.code!=='ELOCKED'||performance.now()>=deadline)throw error;}
    await pause(250,undefined,{signal:options.signal});
  }
}
module.exports={lock,waitForLock,STALE_MS,UPDATE_MS};
