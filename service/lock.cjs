'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
function lock(folder){
  fs.mkdirSync(folder,{recursive:true});const file=path.join(folder,'worker.lock');
  for(let attempt=0;attempt<2;attempt++){
    try{const fd=fs.openSync(file,'wx',0o600),nonce=crypto.randomUUID();try{fs.writeFileSync(fd,JSON.stringify({pid:process.pid,nonce}));}finally{fs.closeSync(fd);}let released=false;return ()=>{if(released)return;released=true;try{const owner=JSON.parse(fs.readFileSync(file,'utf8'));if(owner.pid===process.pid&&owner.nonce===nonce)fs.unlinkSync(file);}catch{}};}
    catch(error){
      if(error.code!=='EEXIST')throw error;
      let owner;try{owner=JSON.parse(fs.readFileSync(file,'utf8'));}catch{throw new Error('Worker lock is unreadable; preserve the profile and inspect its running process.');}
      if(!Number.isInteger(owner.pid)||owner.pid<=0)throw new Error('Invalid worker lock; inspect it before starting.');
      let alive=true;try{process.kill(owner.pid,0);}catch(e){if(e.code==='ESRCH')alive=false;else throw e;}
      if(alive)throw new Error('A HandNavigate worker already uses this data folder.');
      fs.unlinkSync(file);
    }
  }
  throw new Error('Could not obtain the HandNavigate worker lock.');
}
module.exports={lock};
