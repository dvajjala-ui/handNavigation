'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const {createServer}=require('./server.cjs'),{imageInfo}=require('../desktop/engine.cjs'),{lock}=require('./lock.cjs');
async function main(){
  const folder=path.resolve('runtime/imgflip-qualification'),release=lock(folder),app=createServer({folder,dailyLimit:10});
  await new Promise(r=>app.server.listen(0,'127.0.0.1',r));
  try{
    const url='http://127.0.0.1:'+app.server.address().port,headers={Authorization:'Bearer '+app.token,'Content-Type':'application/json'};
    const input={requestId:'imgflip-live-'+crypto.randomUUID(),topics:['Distracted','Cat'],sources:['imgflip'],limit:2,destination:'local'};
    const start=await(await fetch(url+'/v1/collections',{method:'POST',headers,body:JSON.stringify(input)})).json();let job;
    for(let n=0;n<300;n++){job=await(await fetch(url+'/v1/collections/'+start.id,{headers})).json();if(!['QUEUED','RUNNING','WAITING_FOR_LOGIN'].includes(job.status))break;await new Promise(r=>setTimeout(r,100));}
    assert.equal(job.status,'VERIFIED_LOCAL',JSON.stringify(job));assert.equal(job.items.length,2);
    for(const item of job.items)assert.equal((await imageInfo(fs.readFileSync(item.file))).sha256,item.sha256);
    const result={checkedAt:new Date().toISOString(),executor:'HandNavigate HTTP collection API -> documented Imgflip catalog adapter -> shared Runner',scope:'Actual public catalog and image bytes; local storage, not Supabase',status:job.status,count:2,items:job.items.map(i=>({platform:i.platform,source:i.postUrl,imageUrl:i.imageUrl,sha256:i.sha256,width:i.width,height:i.height})),aiCalls:0,paidEndpoints:0};
    fs.writeFileSync('service/evidence/imgflip-local-20261028.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
  }finally{await app.close();release();}
}
main().catch(e=>{console.error(e.message);process.exitCode=1;});
