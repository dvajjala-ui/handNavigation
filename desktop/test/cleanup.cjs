'use strict';
const cp=require('node:child_process'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
async function closeApp(app){
  if(!app)return;const child=app.process();let timer;
  try{await Promise.race([(async()=>{await app.evaluate(()=>global.__handnavigateTest?.shutdown()).catch(()=>{});await app.close().catch(()=>{});})(),new Promise(resolve=>{timer=setTimeout(resolve,10000);})]);}finally{clearTimeout(timer);}
  if(child.exitCode===null&&child.signalCode===null){
    if(process.platform==='win32'){try{cp.execFileSync('taskkill',['/PID',String(child.pid),'/T','/F'],{stdio:'ignore',windowsHide:true});}catch{}}
    else child.kill('SIGKILL');
  }
}
function removeFixture(folder){const target=path.resolve(folder);if(!target.startsWith(path.resolve(os.tmpdir())+path.sep))throw new Error('Test cleanup must stay inside its temporary directory.');fs.rmSync(target,{recursive:true,force:true,maxRetries:10,retryDelay:500});}
module.exports={closeApp,removeFixture};
