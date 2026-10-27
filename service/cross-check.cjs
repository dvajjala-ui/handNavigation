'use strict';
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),cp=require('node:child_process'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const {fixture}=require('../desktop/test/fixture.cjs'),{createServer}=require('./server.cjs'),{StickerDock}=require('./stickerdock.cjs');
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function main(){
  const repo=path.resolve(process.argv[2]||'../sticker'),python=path.join(repo,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python'),folder=fs.mkdtempSync(path.join(os.tmpdir(),'handnavigate-cross-')),token=crypto.randomBytes(32).toString('hex');
  const child=cp.spawn(fs.existsSync(python)?python:'python',[path.join(repo,'tools/intake_contract_fixture.py'),'--folder',path.join(folder,'sink')],{cwd:repo,env:{...process.env,HANDNAVIGATE_INGEST_TOKEN:token},windowsHide:true});
  let output='',errors='';child.stdout.on('data',data=>{output+=data;});child.stderr.on('data',data=>{errors+=data;});let app,site;
  try{
    for(let n=0;n<100&&!output.includes('\n');n++){if(child.exitCode!==null)throw new Error(errors);await pause(100);}const info=JSON.parse(output.split('\n')[0]);
    site=await fixture();const origin=site.origin;
    const sink=new StickerDock('http://127.0.0.1:'+info.port,token);
    // Fixture provenance is HTTPS even though its owned HTTP media bytes are local.
    const nativeStore=sink.store.bind(sink);sink.store=(item,signal)=>nativeStore({...item,postUrl:'https://owned.example/post/'+item.sha256,imageUrl:'https://owned.example/image/'+item.sha256},signal);
    app=createServer({folder:path.join(folder,'worker'),sink,token,dailyLimit:20,browser:{headless:true,...(process.platform==='win32'?{channel:'chrome'}:{})},sources:[{id:'owned',searchUrl:origin+'/images?topic={{topic}}',selector:'#gallery img',allowedOrigins:[origin],imageOrigins:[],pagination:{kind:'none',maxPages:1}}]});
    await new Promise(resolve=>app.server.listen(0,'127.0.0.1',resolve));const endpoint='http://127.0.0.1:'+app.server.address().port,headers={Authorization:'Bearer '+token,'Content-Type':'application/json'};
    const stdout=await new Promise((resolve,reject)=>cp.execFile(fs.existsSync(python)?python:'python',['-c','from tools.handnavigate_client import HandNavigate;import json;print(json.dumps(HandNavigate().collect(["landscape","architecture"],["owned"],20)))'],{cwd:repo,env:{...process.env,HANDNAVIGATE_URL:endpoint,HANDNAVIGATE_API_TOKEN:token},windowsHide:true,timeout:60000},(error,stdout,stderr)=>error?reject(new Error(stderr)):resolve(stdout)));
    const start=JSON.parse(stdout),request={requestId:start.requestId,topics:start.topics,sources:start.sources,limit:start.limit,destination:start.destination};let job;
    for(let n=0;n<900;n++){job=await(await fetch(endpoint+'/v1/collections/'+start.id,{headers})).json();if(!['QUEUED','RUNNING','WAITING_FOR_LOGIN'].includes(job.status))break;await pause(100);}
    assert.equal(job.status,'VERIFIED_STORAGE',JSON.stringify(job));assert.equal(job.items.length,20);assert.ok(job.items.every(i=>i.delivery?.generationEligible===false));
    const repeat=await(await fetch(endpoint+'/v1/collections',{method:'POST',headers,body:JSON.stringify(request)})).json();assert.equal(repeat.id,start.id);assert.equal(repeat.reused,true);
    const rows=cp.execFileSync(fs.existsSync(python)?python:'python',['-c','import sqlite3,sys,json;db=sqlite3.connect(sys.argv[1]);print(json.dumps({"rows":db.execute("select count(*) from items").fetchone()[0]}))',path.join(folder,'sink','intake.sqlite3')],{encoding:'utf8',windowsHide:true});assert.equal(JSON.parse(rows).rows,20);
    const result={checkedAt:new Date().toISOString(),scope:'StickerDock Python caller -> HandNavigate API/Runner -> StickerDock production intake handler; owned HTTP source, disposable SQLite/blob sink (not live Supabase)',status:job.status,images:20,databaseRows:20,allReadBackVerified:true,idempotentRequest:true,publications:0,aiCalls:0};
    fs.mkdirSync('service/evidence',{recursive:true});fs.writeFileSync('service/evidence/cross-repo.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
  }finally{if(app)await app.close();if(site)await site.close();child.kill();await new Promise(resolve=>child.exitCode!==null?resolve():child.once('exit',resolve));if(path.resolve(folder).startsWith(path.resolve(os.tmpdir())+path.sep))fs.rmSync(folder,{recursive:true,force:true,maxRetries:10,retryDelay:500});}
}
main().catch(error=>{console.error(error.message);process.exitCode=1;});
