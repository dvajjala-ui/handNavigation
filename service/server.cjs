'use strict';
const http=require('node:http'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {atomicWrite}=require('../desktop/core.cjs');
const {Collections}=require('./collections.cjs');
const {StickerDock}=require('./stickerdock.cjs');
const {lock}=require('./lock.cjs');
const {QueueBridge}=require('./bridge.cjs');
const registry=require('./registry.cjs');
function tokenEqual(actual,expected){const a=Buffer.from(actual||''),b=Buffer.from('Bearer '+expected);return a.length===b.length&&crypto.timingSafeEqual(a,b);}
async function body(req){let size=0,text='';for await(const part of req){size+=part.length;if(size>16000)throw new Error('Request exceeds 16 KB.');text+=part;}try{return JSON.parse(text);}catch{throw new Error('Send a JSON object.');}}
function createServer(options={}){
  const folder=path.resolve(options.folder||process.env.HANDNAVIGATE_DATA||path.join(__dirname,'..','runtime','service'));fs.mkdirSync(folder,{recursive:true});
  const file=path.join(folder,'service-key.json');
  let token=options.token||process.env.HANDNAVIGATE_API_TOKEN;
  if(!token){if(fs.existsSync(file))token=JSON.parse(fs.readFileSync(file,'utf8')).token;else{token=crypto.randomBytes(32).toString('hex');atomicWrite(file,{token});}}
  if(typeof token!=='string'||token.length<32)throw new Error('Use a service token with at least 32 characters.');
  const sink=options.sink||(process.env.STICKERDOCK_BASE_URL?new StickerDock(process.env.STICKERDOCK_BASE_URL):null);
  const configured=registry.load(folder,options.sources);
  const collections=new Collections(folder,{...options,sources:configured,sink,dailyLimit:options.dailyLimit||Number(process.env.HANDNAVIGATE_DAILY_LIMIT||20),
    browser:options.browser||{headless:process.env.HANDNAVIGATE_HEADLESS!=='0',channel:process.env.HANDNAVIGATE_BROWSER_CHANNEL||undefined,interactiveWaitMs:Number(process.env.HANDNAVIGATE_INTERACTIVE_WAIT_SECONDS||0)*1000},
    onError:error=>console.error('Collection error:',String(error.message).slice(0,200))});
  const send=(res,status,value)=>{res.writeHead(status,{'Content-Type':'application/json','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'});res.end(JSON.stringify(value));};
  const server=http.createServer(async(req,res)=>{
    if(req.headers.origin||req.headers['sec-fetch-site']==='cross-site')return send(res,403,{error:'Use a server-side client.'});
    if(!tokenEqual(req.headers.authorization,token))return send(res,401,{error:'Service authentication required.'});
    try{
      const url=new URL(req.url,'http://localhost');
      if(req.method==='GET'&&url.pathname==='/v1/health')return send(res,200,{ready:true,busy:!!collections.active,dailyUsed:collections.used(),dailyLimit:collections.options.dailyLimit,storageConfigured:!!sink});
      if(req.method==='GET'&&url.pathname==='/v1/collections')return send(res,200,{jobs:collections.data.jobs.slice(0,20).map(j=>({id:j.id,status:j.status,topics:j.topics,sources:j.sources,limit:j.limit,destination:j.destination,createdAt:j.createdAt,error:j.error,saved:j.items.length,delivered:j.items.filter(i=>i.delivery).length,sourceStatus:j.sourceStatus}))});
      if(req.method==='POST'&&url.pathname==='/v1/shutdown'){
        const input=await body(req);if(collections.active&&input.allowBusy!==true)return send(res,409,{error:'A collection is active. Stop it first or explicitly confirm stopping the worker.'});
        send(res,202,{stopping:true});setImmediate(()=>close().catch(error=>options.onError?.(error)));return;
      }
      if(req.method==='GET'&&url.pathname==='/v1/sources')return send(res,200,{sources:collections.sources.map(s=>({id:s.id,name:s.name||s.id,custom:s.id.startsWith('custom-'),revision:s.revision||null})),totalLimitAppliesAcrossAllTopicsAndSources:true});
      if(req.method==='POST'&&url.pathname==='/v1/collections'){
        const result=collections.create(await body(req));return send(res,result.reused?200:202,{...result.job,reused:result.reused});
      }
      const match=/^\/v1\/collections\/([0-9a-f-]{36})(?:\/(stop|resume))?$/.exec(url.pathname);
      if(match&&req.method==='GET'&&!match[2])return send(res,200,collections.get(match[1]));
      if(match&&req.method==='POST'&&match[2]){await body(req);if(match[2]==='stop'){collections.stop(match[1]);return send(res,200,collections.get(match[1]));}return send(res,202,collections.resume(match[1]));}
      send(res,404,{error:'Endpoint not found.'});
    }catch(error){send(res,409,{error:String(error.message).slice(0,500)});}
  });
  server.requestTimeout=30000;server.headersTimeout=10000;
  const bridge=options.cloudQueue&&sink?new QueueBridge(collections,sink,{onError:error=>{console.error('Cloud queue:',String(error.message).slice(0,200));options.onBridgeError?.(error);}}).start():null;
  let closing;
  function close(){if(!closing)closing=(async()=>{await collections.close();await bridge?.close();if(server.listening)await new Promise(resolve=>server.close(resolve));})();return closing;}
  queueMicrotask(()=>collections.pump().catch(error=>options.onError?.(error)));
  return {server,collections,token,folder,bridge,close};
}
if(require.main===module){
  const folder=path.resolve(process.env.HANDNAVIGATE_DATA||path.join(__dirname,'..','runtime','service')),release=lock(folder);
  process.once('exit',release);
  const configFile=process.env.HANDNAVIGATE_CONFIG||path.join(folder,'stickerdock.json');
  const config=fs.existsSync(configFile)?JSON.parse(fs.readFileSync(configFile,'utf8')):{};
  const sink=config.baseUrl?new StickerDock(config.baseUrl,config.token):undefined;
  const app=createServer({sink,cloudQueue:config.cloudQueue===true||process.env.HANDNAVIGATE_CLOUD_QUEUE==='1'}),host=process.env.HANDNAVIGATE_HOST||'127.0.0.1',port=Number(process.env.HANDNAVIGATE_PORT||47832);
  app.server.listen(port,host,()=>{const actualPort=app.server.address().port;atomicWrite(path.join(folder,'service-endpoint.json'),{port:actualPort,downloadFolder:path.join(folder,'downloads')});console.log(JSON.stringify({service:'HandNavigate',host,port:actualPort,profiles:path.join(app.folder,'profiles'),keyFile:path.join(app.folder,'service-key.json'),dailyLimit:app.collections.options.dailyLimit,storageConfigured:!!app.collections.options.sink}));});
  for(const signal of ['SIGINT','SIGTERM'])process.once(signal,()=>app.close().then(()=>process.exit(0)));
}
module.exports={createServer,tokenEqual};
