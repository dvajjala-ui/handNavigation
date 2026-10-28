'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const {createServer}=require('./server.cjs'),{imageInfo}=require('../desktop/engine.cjs'),{lock}=require('./lock.cjs');
async function main(){
  const folder=path.resolve('runtime/flickr-qualification'),release=lock(folder),app=createServer({folder,dailyLimit:20});
  await new Promise(resolve=>app.server.listen(0,'127.0.0.1',resolve));
  try{
    const endpoint='http://127.0.0.1:'+app.server.address().port,headers={Authorization:'Bearer '+app.token,'Content-Type':'application/json'};
    const input={requestId:'flickr-live-'+crypto.randomUUID(),topics:['cat','nature'],sources:['flickr'],limit:20,destination:'local'};
    const response=await fetch(endpoint+'/v1/collections',{method:'POST',headers,body:JSON.stringify(input)}),start=await response.json();assert.equal(response.status,202,JSON.stringify(start));
    let job;
    for(let n=0;n<1200;n++){job=await(await fetch(endpoint+'/v1/collections/'+start.id,{headers})).json();if(!['QUEUED','RUNNING','WAITING_FOR_LOGIN'].includes(job.status))break;await new Promise(resolve=>setTimeout(resolve,250));}
    for(const item of job.items)assert.equal((await imageInfo(fs.readFileSync(item.file))).sha256,item.sha256);
    const result={checkedAt:new Date().toISOString(),executor:'HandNavigate HTTP collection API -> Flickr public tag feed/oEmbed -> shared Runner',scope:'Actual public photo bytes, local verification only; no Supabase admission or generation',status:job.status,count:job.items.length,requested:20,sourceStatus:job.sourceStatus,error:job.error,items:job.items.map(i=>({platform:i.platform,source:i.postUrl,imageUrl:i.imageUrl,sha256:i.sha256,width:i.width,height:i.height})),aiCalls:0,apiKeys:0};
    fs.writeFileSync('service/evidence/flickr-local-20261029.json',JSON.stringify(result,null,2));console.log(JSON.stringify({...result,items:result.items.map(i=>({sha256:i.sha256,width:i.width,height:i.height}))}));
    assert.equal(job.status,'VERIFIED_LOCAL');assert.equal(job.items.length,20);
  }finally{await app.close();release();}
}
main().catch(error=>{console.error(error.message);process.exitCode=1;});
