'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {atomicWrite}=require('./core.cjs'),{createServer}=require('../service/server.cjs'),{StickerDock}=require('../service/stickerdock.cjs'),{lock}=require('../service/lock.cjs'),{sources}=require('../service/sources.cjs');
class CollectionManager{
  constructor(folder,options={}){
    this.options=options;this.file=path.join(folder,'collection-desktop.json');this.app=null;this.release=null;
    const legacy=(options.legacyFolders||[]).find(p=>fs.existsSync(path.join(p,'stickerdock.json')));
    const roots=[process.env.PROGRAMFILES,process.env['PROGRAMFILES(X86)'],process.env.LOCALAPPDATA].filter(Boolean);
    const channel=process.platform!=='win32'?'':roots.some(p=>fs.existsSync(path.join(p,'Google/Chrome/Application/chrome.exe')))?'chrome':roots.some(p=>fs.existsSync(path.join(p,'Microsoft/Edge/Application/msedge.exe')))?'msedge':'chrome';
    this.settings={folder:legacy||path.join(folder,'collection-worker'),dailyLimit:20,channel};
    if(fs.existsSync(this.file)){
      let recovered=false;
      for(const candidate of [this.file,this.file+'.bak'])try{const saved={...this.settings,...JSON.parse(fs.readFileSync(candidate,'utf8'))};this.validate(saved);this.settings=saved;recovered=true;if(candidate!==this.file)this.settingsWarning='Collection settings were recovered from their backup. Save the connection to confirm them.';break;}catch{}
      if(!recovered)this.settingsWarning='Collection settings could not be read. Their files were preserved; choose your existing worker folder in Connection settings.';
    }
    this.validate(this.settings);
  }
  validate(s){if(typeof s.folder!=='string'||!path.isAbsolute(s.folder)||s.folder===path.parse(s.folder).root||!Number.isInteger(s.dailyLimit)||s.dailyLimit<1||s.dailyLimit>10000||!['','chrome','msedge'].includes(s.channel))throw new Error('Invalid collection settings. Choose a data folder and a daily limit from 1 to 10000.');}
  config(){const file=path.join(this.settings.folder,'stickerdock.json');return fs.existsSync(file)?JSON.parse(fs.readFileSync(file,'utf8')):{};}
  endpoint(){const file=path.join(this.settings.folder,'service-endpoint.json');let port=47832;if(fs.existsSync(file))port=JSON.parse(fs.readFileSync(file,'utf8')).port;if(!Number.isInteger(port)||port<1||port>65535)throw new Error('Invalid saved worker endpoint.');return 'http://127.0.0.1:'+port;}
  async call(route,body){
    const file=path.join(this.settings.folder,'service-key.json');if(!fs.existsSync(file))throw new Error('Start the collection worker first.');
    const token=JSON.parse(fs.readFileSync(file,'utf8')).token;
    const response=await fetch(this.endpoint()+'/v1'+route,{method:body===undefined?'GET':'POST',redirect:'error',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},...(body===undefined?{}:{body:JSON.stringify(body)}),signal:AbortSignal.timeout(8000)});
    const result=await response.json();if(!response.ok)throw new Error(result.error||'Collection worker request failed.');return result;
  }
  async status(){
    const config=this.config();let health=null,jobs=[],registry=sources().map(s=>({id:s.id,name:s.name}));
    try{health=await this.call('/health');const remote=await this.call('/sources');registry=remote.sources;jobs=(await this.call('/collections')).jobs||[];}catch(error){this.lastError=health?error.message:null;}
    const endpointFile=path.join(this.settings.folder,'service-endpoint.json'),savedEndpoint=fs.existsSync(endpointFile)?JSON.parse(fs.readFileSync(endpointFile,'utf8')):{};
    const downloadFolder=typeof savedEndpoint.downloadFolder==='string'&&path.isAbsolute(savedEndpoint.downloadFolder)?savedEndpoint.downloadFolder:this.app?.collections.options.outputFolder||(health?path.join(this.settings.folder,'downloads'):path.join(this.options.downloads||this.settings.folder,'HandNavigate Collections'));
    return {...this.settings,baseUrl:config.baseUrl||'',tokenSet:!!config.token,cloudQueue:config.cloudQueue===true,managed:!!this.app?.server.listening,running:!!health?.ready,health,sources:registry,jobs,error:this.lastError||this.settingsWarning||null,downloadFolder};
  }
  async configure(input){
    let running=!!this.app?.server.listening;if(!running)try{running=(await this.call('/health')).ready===true;}catch{}
    if(running)throw new Error('Stop the worker before changing its connection or data folder.');
    const settings={folder:path.resolve(input.folder||this.settings.folder),dailyLimit:Number(input.dailyLimit),channel:input.channel||''};this.validate(settings);
    let previous={};if(settings.folder===this.settings.folder)try{previous=this.config();}catch{}
    const token=input.token||previous.token||'',baseUrl=String(input.baseUrl||'').trim(),cloudQueue=input.cloudQueue===true;
    if(baseUrl){if(token.length>256)throw new Error('Use the worker ingest credential, at most 256 characters.');new StickerDock(baseUrl,token);}else if(cloudQueue)throw new Error('Set the StickerDock site and ingest credential before enabling its queue.');
    fs.mkdirSync(settings.folder,{recursive:true});atomicWrite(path.join(settings.folder,'stickerdock.json'),{baseUrl,token:baseUrl?token:'',cloudQueue});
    this.settings=settings;atomicWrite(this.file,settings);this.lastError=null;this.settingsWarning=null;return this.status();
  }
  async start(){
    if(this.app?.server.listening)return this.status();
    if(this.app)await this.close();
    if((await this.status()).running)return this.status();
    this.release?.();this.release=lock(this.settings.folder);
    try{
      const config=this.config(),sink=config.baseUrl?new StickerDock(config.baseUrl,config.token):undefined;
      const configured=process.env.HANDNAVIGATE_SOURCES_FILE?JSON.parse(fs.readFileSync(process.env.HANDNAVIGATE_SOURCES_FILE,'utf8')):undefined;
      const keyFile=path.join(this.settings.folder,'service-key.json');let token;
      if(fs.existsSync(keyFile))token=JSON.parse(fs.readFileSync(keyFile,'utf8')).token;else{token=crypto.randomBytes(32).toString('hex');atomicWrite(keyFile,{token});}
      this.app=createServer({folder:this.settings.folder,token,sink,cloudQueue:config.cloudQueue===true,dailyLimit:this.settings.dailyLimit,sources:configured,
        outputFolder:path.join(this.options.downloads||this.settings.folder,'HandNavigate Collections'),
        browser:{headless:this.options.headless===true,channel:this.settings.channel||undefined,interactiveWaitMs:180000}});
      const app=this.app,release=this.release;app.server.once('close',()=>{release();if(this.app===app){this.app=null;this.release=null;}});
      await new Promise((resolve,reject)=>{this.app.server.once('error',reject);this.app.server.listen(0,'127.0.0.1',resolve);});
      atomicWrite(path.join(this.settings.folder,'service-endpoint.json'),{port:this.app.server.address().port,downloadFolder:this.app.collections.options.outputFolder});this.lastError=null;return this.status();
    }catch(error){await this.app?.close().catch(()=>{});this.app=null;this.release?.();this.release=null;throw error;}
  }
  async stop(allowBusy=false){
    const status=await this.status();if(!status.running){await this.close();return this.status();}
    if(status.health.busy&&!allowBusy)throw new Error('A collection is active. Stop that collection before stopping the worker.');
    if(this.app)await this.close();else await this.call('/shutdown',{allowBusy});
    return this.status();
  }
  async close(){if(this.app){const app=this.app,release=this.release;this.app=null;this.release=null;try{await app.close();}finally{release?.();}}}
  async collect(input){
    await this.start();return this.call('/collections',{requestId:input.requestId||crypto.randomUUID(),topics:input.topics,sources:input.sources,limit:input.limit,destination:input.destination||'local'});
  }
  async stopJob(id){if(!/^[0-9a-f-]{36}$/.test(id))throw new Error('Invalid collection ID.');await this.call('/collections/'+id+'/stop',{});return this.status();}
  async resumeJob(id){if(!/^[0-9a-f-]{36}$/.test(id))throw new Error('Invalid collection ID.');await this.start();await this.call('/collections/'+id+'/resume',{});return this.status();}
}
module.exports={CollectionManager};
