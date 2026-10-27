'use strict';
// Starts the actual service and invokes its public API; no Codex browser/session is used.
const fs=require('node:fs'),path=require('node:path');
const {createServer}=require('./server.cjs');
const {lock}=require('./lock.cjs');
async function main(){
  const folder=path.resolve(process.env.HANDNAVIGATE_DATA||'runtime/service-live'),release=lock(folder);process.once('exit',release);
  const app=createServer({folder,dailyLimit:Number(process.env.HANDNAVIGATE_DAILY_LIMIT||20),
    browser:{headless:process.env.HANDNAVIGATE_HEADLESS==='1',...(process.platform==='win32'?{channel:'chrome'}:{}),interactiveWaitMs:180000},
    onAuth:info=>console.log('HUMAN_ACTION_REQUIRED '+JSON.stringify(info))});
  await new Promise(resolve=>app.server.listen(0,'127.0.0.1',resolve));
  const endpoint='http://127.0.0.1:'+app.server.address().port,headers={Authorization:'Bearer '+app.token,'Content-Type':'application/json'};
  try{
    const input={requestId:process.env.HANDNAVIGATE_REQUEST_ID||'live-'+new Date().toISOString().replace(/[^0-9]/g,''),topics:(process.env.HANDNAVIGATE_TOPICS||'funny cat reaction,cute dog reaction').split(','),sources:(process.env.HANDNAVIGATE_SOURCES||'reddit,pinterest').split(','),limit:Number(process.env.HANDNAVIGATE_COUNT||20),destination:process.env.HANDNAVIGATE_DESTINATION||'local'};
    const response=await fetch(endpoint+'/v1/collections',{method:'POST',headers,body:JSON.stringify(input)}),start=await response.json();if(!response.ok)throw new Error(start.error);
    console.log('COLLECTION '+JSON.stringify({id:start.id,requestId:input.requestId,folder}));
    let last='';
    while(true){
      const job=await (await fetch(endpoint+'/v1/collections/'+start.id,{headers})).json(),progress=job.status+' '+job.items.length+' '+(job.events.at(-1)?.text||'');
      if(progress!==last){console.log(progress);last=progress;}
      if(!['QUEUED','RUNNING','WAITING_FOR_LOGIN'].includes(job.status)){
        const evidence={checkedAt:new Date().toISOString(),executor:'HandNavigate service public API and ServiceBrowser, production Runner',request:input,id:job.id,status:job.status,count:job.items.length,sourceStatus:job.sourceStatus,error:job.error,
          items:job.items.map(i=>({platform:i.platform,topic:i.topic,source:i.source,postUrl:i.postUrl,imageUrl:i.imageUrl,sha256:i.sha256,width:i.width,height:i.height,file:i.file,delivery:i.delivery||null}))};
        fs.writeFileSync(path.join(folder,'live-result.json'),JSON.stringify(evidence,null,2));console.log(JSON.stringify(evidence,null,2));if(!['VERIFIED_LOCAL','VERIFIED_STORAGE'].includes(job.status))process.exitCode=1;break;
      }
      await new Promise(resolve=>setTimeout(resolve,1000));
    }
  }finally{await app.close();release();}
}
main().catch(error=>{console.error(error.message);process.exitCode=1;});
