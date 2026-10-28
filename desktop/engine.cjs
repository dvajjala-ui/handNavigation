'use strict';
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const sharp=require('sharp');
const {TaskError,hash,clone,webUrl,interpolate,siteUrl,atomicWrite}=require('./core.cjs');
const {script}=require('./dom.cjs');
const delay=(ms,signal)=>new Promise((resolve,reject)=>{
  if(signal?.aborted)return reject(new TaskError('Run stopped.','CANCELLED'));
  const stop=()=>{clearTimeout(timer);signal.removeEventListener('abort',stop);reject(new TaskError('Run stopped.','CANCELLED'));};
  const timer=setTimeout(()=>{signal?.removeEventListener('abort',stop);resolve();},ms);
  signal?.addEventListener('abort',stop,{once:true});
});
const MAX_BYTES=25*1024*1024, MAX_PIXELS=40000000;

async function imageInfo(bytes) {
  if(!Buffer.isBuffer(bytes)||!bytes.length||bytes.length>MAX_BYTES)throw new TaskError('An image is empty or exceeds the 25 MB limit.');
  let meta;
  try {
    meta=await sharp(bytes,{failOn:'warning',limitInputPixels:MAX_PIXELS,animated:true}).metadata();
    if(!['jpeg','png','webp'].includes(meta.format)||meta.pages>1||!meta.width||!meta.height||meta.width*meta.height>MAX_PIXELS)throw new Error('format');
    await sharp(bytes,{failOn:'warning',limitInputPixels:MAX_PIXELS}).stats();
  }catch{throw new TaskError('The downloaded content is not a valid bounded JPEG, PNG, or WebP image.');}
  const pixels=await sharp(bytes).rotate().resize(9,8,{fit:'fill'}).flatten({background:'#ffffff'}).removeAlpha().toColourspace('srgb').raw().toBuffer();
  const gray=[],color=[0,0,0];for(let i=0;i<pixels.length;i+=3){gray.push((pixels[i]*299+pixels[i+1]*587+pixels[i+2]*114)/1000);for(let c=0;c<3;c++)color[c]+=pixels[i+c]/72;}
  const mean=gray.reduce((a,b)=>a+b,0)/72,contrast=Math.sqrt(gray.reduce((a,b)=>a+(b-mean)**2,0)/72);
  let bits=0n;for(let y=0;y<8;y++)for(let x=0;x<8;x++)bits=(bits<<1n)|(gray[y*9+x]>gray[y*9+x+1]?1n:0n);
  const normalized=await sharp(bytes).rotate().resize(32,32,{fit:'fill'}).flatten({background:'#ffffff'}).removeAlpha().toColourspace('srgb').raw().toBuffer();
  return {sha256:crypto.createHash('sha256').update(bytes).digest('hex'),pixelSha256:crypto.createHash('sha256').update(normalized).digest('hex'),visualHash:bits.toString(16).padStart(16,'0'),color:color.map(Math.round),contrast,
    bytes:bytes.length,width:meta.width,height:meta.height,
    format:meta.format,extension:{jpeg:'.jpg',png:'.png',webp:'.webp'}[meta.format],mime:'image/'+meta.format};
}
function duplicateImage(a,b,similar=false) {
  if(a.sha256===b.sha256||a.pixelSha256&&a.pixelSha256===b.pixelSha256)return true;
  if(!similar||!a.visualHash||!b.visualHash||a.contrast<8||b.contrast<8||!a.color||!b.color)return false;
  if(Math.abs(a.width/a.height-b.width/b.height)>0.1||Math.max(...a.color.map((v,i)=>Math.abs(v-b.color[i])))>16)return false;
  let value=BigInt('0x'+a.visualHash)^BigInt('0x'+b.visualHash),distance=0;while(value){distance++;value&=value-1n;}
  return distance<=4;
}
const RETRY_HTTP=new Set([408,429,500,502,503,504]);
function transientNetwork(error){return /ECONNRESET|ECONNREFUSED|ETIMEDOUT|EAI_AGAIN|UND_ERR_SOCKET|UND_ERR_CONNECT_TIMEOUT|net::ERR_(CONNECTION_RESET|CONNECTION_CLOSED|CONNECTION_ABORTED|CONNECTION_REFUSED|TIMED_OUT|NETWORK_CHANGED|EMPTY_RESPONSE|HTTP2_PROTOCOL_ERROR)/.test([error?.code,error?.cause?.code,error?.message].join(' '));}
async function fetchImage(browserSession,url,origins,signal,onRetry=()=>{}) {
  for(let attempt=0;attempt<3;attempt++){
    try{return await readImage(browserSession,url,origins,signal);}
    catch(error){
      if(signal.aborted)throw new TaskError('Run stopped.','CANCELLED');
      if(attempt===2||!(error.transient||transientNetwork(error)))throw error;
      const wait=error.retryAfterMs??500*2**attempt;
      // Long rate limits need a later run, rather than retrying before the server allows it.
      if(wait>5000)throw error;
      onRetry({attempt:attempt+1,wait,status:error.code||'NETWORK'});
      await delay(wait,signal);
    }
  }
}
async function readImage(browserSession,url,origins,signal) {
  let current=url;
  for(let hop=0;hop<6;hop++) {
    if(signal.aborted)throw new TaskError('Run stopped.','CANCELLED');
    const u=webUrl(current);if(!origins.includes(u.origin))throw new TaskError(`This image comes from ${u.origin}. Add it to the reviewed image websites first.`);
    const response=await browserSession.fetch(u.href,{redirect:'manual',signal,credentials:'include',headers:{Accept:'image/*'}});
    if([301,302,303,307,308].includes(response.status)) {
      const loc=response.headers.get('location');await response.body?.cancel();
      if(!loc)throw new TaskError('The image redirect had no destination.');
      const next=webUrl(new URL(loc,u).href);if(u.protocol==='https:'&&next.protocol!=='https:')throw new TaskError('The image tried to redirect from HTTPS to HTTP.');
      current=next.href;continue;
    }
    if(!response.ok){
      const retryAfter=response.headers.get('retry-after');await response.body?.cancel();
      const error=new TaskError(`Image request returned HTTP ${response.status}.`,'HTTP_'+response.status);
      error.transient=RETRY_HTTP.has(response.status);
      if(retryAfter!==null){const value=/^\d+(?:\.\d+)?$/.test(retryAfter)?Number(retryAfter)*1000:Date.parse(retryAfter)-Date.now();if(Number.isFinite(value))error.retryAfterMs=Math.max(0,value);}
      throw error;
    }
    const declared=response.headers.get('content-length');
    if(declared&&(!/^\d+$/.test(declared)||Number(declared)>MAX_BYTES)){await response.body?.cancel();throw new TaskError('The image exceeds the 25 MB transfer limit.');}
    const chunks=[];let size=0;
    try {
      for await(const chunk of response.body) {
        if(signal.aborted)throw new TaskError('Run stopped.','CANCELLED');
        size+=chunk.byteLength;if(size>MAX_BYTES)throw new TaskError('The image exceeds the 25 MB transfer limit.');
        chunks.push(Buffer.from(chunk));
      }
    }catch(e){try{await response.body?.cancel();}catch{}throw e;}
    return Buffer.concat(chunks);
  }
  throw new TaskError('The image redirected too many times.');
}

class Runner {
  constructor(store,browser,notify=()=>{}){this.store=store;this.browser=browser;this.notify=notify;this.active=null;}
  async input(method,params){
    // Chromium input targets this page even when the desktop window is minimized.
    this.check();const debugger_=this.browser.wc.debugger;
    if(!debugger_.isAttached())debugger_.attach('1.3');
    return debugger_.sendCommand(method,params);
  }
  check() {
    if(!this.active||this.active.abort.signal.aborted)throw new TaskError('Run stopped.','CANCELLED');
    if(Date.now()>this.active.deadline)throw new TaskError('This run reached its time limit.','NEEDS_REVIEW');
    if(this.store.get(this.active.task.id).sha!==this.active.run.sha)throw new TaskError('The workflow changed while running.');
    if(this.browser.effectError)throw new TaskError(this.browser.effectError,'NEEDS_REVIEW');
  }
  event(text){this.check();this.active.run.events.push({at:new Date().toISOString(),text});if(this.active.run.events.length>300)this.active.run.events.shift();this.store.flush();this.notify();}
  async until(fn,message,timeout=10000) {
    const end=Math.min(this.active.deadline,Date.now()+timeout);let last;
    while(Date.now()<end){this.check();try{const result=await fn();if(result)return result;}catch(e){last=e;}await delay(150);}
    this.check();throw new TaskError(last?.message||message);
  }
  async navigate(url) {
    this.check();const u=webUrl(url);if(!this.active.task.allowedOrigins.includes(u.origin))throw new TaskError('This navigation leaves the reviewed websites.');
    await this.browser.load(u.href);this.check();
    await this.until(async()=>this.browser.wc.executeJavaScript('document.readyState!=="loading"'), 'The website did not load.');
    if(this.browser.settle)await this.browser.settle();this.check();
  }
  async step(step,row,index) {
    this.check();const wc=this.browser.wc;
    this.event(`Step ${index+1}: ${step.op}${step.label?' '+step.label:''}`);
    if(step.op==='navigate'){await this.navigate(siteUrl(step.value,row));return;}
    if(step.op==='wait'){await delay(step.amount);this.check();return;}
    const info=await this.until(()=>wc.executeJavaScript(script('findTarget',{locator:step.locator})), 'The taught control did not appear.');
    this.check();
    if(step.op==='select') {
      this.active.effectStarted=true;
      await wc.executeJavaScript(script('selectTarget',{...info,locator:step.locator,value:interpolate(step.value,row)}),true);
    } else {
      await wc.executeJavaScript(script('focusTarget',{...info,locator:step.locator}),true);this.check();
      if(step.op==='fill') {
        this.active.effectStarted=true;
        await Promise.race([this.input('Input.insertText',{text:interpolate(step.value,row)}),delay(8000).then(()=>{throw new TaskError('The browser did not accept text input. Open the app browser and try again.');})]);
      } else if(step.op==='press') {
        this.active.effectStarted=true;
        const key={key:step.value,code:step.value===' '?'Space':step.value,windowsVirtualKeyCode:{Enter:13,Tab:9,Escape:27,ArrowDown:40,ArrowUp:38,ArrowLeft:37,ArrowRight:39,' ':32}[step.value]};
        const text=step.value==='Enter'?'\r':step.value===' '?' ':null;
        await this.input('Input.dispatchKeyEvent',{...key,type:text?'keyDown':'rawKeyDown',...(text?{text,unmodifiedText:text}:{})});
        await this.input('Input.dispatchKeyEvent',{...key,type:'keyUp'});
      } else if(step.op==='click'||step.op==='check'&&info.checked!==step.checked) {
        const fresh=await wc.executeJavaScript(script('findTarget',{locator:step.locator}));
        if(fresh.fingerprint!==info.fingerprint||fresh.url!==info.url)throw new TaskError('The control changed before the click.');
        this.check();this.active.effectStarted=true;
        const pointer={x:fresh.x,y:fresh.y,button:'left',clickCount:1};
        await this.input('Input.dispatchMouseEvent',{...pointer,type:'mousePressed',buttons:1});
        await this.input('Input.dispatchMouseEvent',{...pointer,type:'mouseReleased',buttons:0});
      }
    }
    await delay(250);this.check();
  }
  async checks(task,row) {
    for(const check of task.checks) {
      const expected=check.kind==='url'?siteUrl(check.expected,row):interpolate(check.expected,row);
      await this.until(()=>this.browser.wc.executeJavaScript(script('verifyCheck',{kind:check.kind,expected})), 'The visible result check did not pass.',15000);
      this.event(`Verified ${check.kind==='url'?'final URL':'visible result'}: ${expected.slice(0,100)}`);
    }
  }
  async fetch(url) {
    this.check();const controller=new AbortController();const parent=this.active.abort.signal;
    const abort=()=>controller.abort();parent.addEventListener('abort',abort,{once:true});
    const timer=setTimeout(abort,30000);
    try {const data=await fetchImage(this.browser.session,url,[...new Set([...this.active.task.allowedOrigins,...this.active.task.imageOrigins])],controller.signal,retry=>{this.active.run.imageRetries=(this.active.run.imageRetries||0)+1;this.event(`Retrying an image read (${retry.status}), attempt ${retry.attempt+1}/3`);});this.check();return data;}
    catch(error){if(controller.signal.aborted&&!parent.aborted)throw new TaskError('The image request timed out after 30 seconds.');throw error;}
    finally{clearTimeout(timer);parent.removeEventListener('abort',abort);}
  }
  async candidates(selector) {
    const result=await this.browser.wc.executeJavaScript(script('imageCandidates',{selector}));
    if(result.authRequired)throw new TaskError('Sign in inside the app browser first, then run again. Your login is kept in this browser.','AUTH_REQUIRED');
    return result.items;
  }
  async advance(spec,selector,items) {
    if(spec.kind==='none')return false;
    const signature=JSON.stringify(items.map(i=>[i.sourceId,i.urls])),beforeUrl=this.browser.wc.getURL();
    if(spec.kind==='next'){
      const next=await this.browser.wc.executeJavaScript(script('nextControl',{locator:spec.locator}));
      if(!next.available)return false;
      if(next.href){await this.navigate(next.href);return true;}
      await this.step({op:'click',locator:spec.locator,label:'Next results page'},this.active.run.inputs,0);
    }else await this.browser.wc.executeJavaScript(script('scrollPage'));
    const end=Math.min(this.active.deadline,Date.now()+(spec.kind==='next'?10000:4000));
    while(Date.now()<end){this.check();await delay(250);try{const next=await this.candidates(selector);if(this.browser.wc.getURL()!==beforeUrl||JSON.stringify(next.map(i=>[i.sourceId,i.urls]))!==signature){if(this.browser.settle)await this.browser.settle();return true;}}catch(e){if(this.browser.effectError||e.code==='AUTH_REQUIRED')throw e;}}
    if(spec.kind==='next')throw new TaskError('The Next control did not produce a new results page. Teach or select the changed control again.');
    return false;
  }
  async collect(task) {
    const run=this.active.run,seen=new Set(),pageKeys=new Set(),saved=[];
    if(this.browser.settle)await this.browser.settle();this.check();
    const pending=task.type==='transfer'&&task.newOnly?this.store.pendingItems(task,run.rowIndex):[];
    const pendingHashes=new Set(pending.map(i=>i.sha256));
    const history=task.newOnly?(this.store.knownItems?this.store.knownItems(task.id,task.dedupeScope||'workflow').filter(i=>!pendingHashes.has(i.sha256)):[...this.store.known(task.id)].map(sha256=>({sha256}))):[];
    const knownSources=new Set(history.map(i=>i.source).filter(Boolean)),paging=task.pagination||{kind:'scroll',maxPages:50};
    const safeName=task.name.replace(/[^a-zA-Z0-9_-]+/g,'-').slice(0,70)||'images';
    const folder=path.join(task.outputFolder,safeName,new Date(run.startedAt).toISOString().slice(0,10)+'-'+run.id.slice(0,8));
    fs.mkdirSync(folder,{recursive:true});run.folder=folder;this.store.flush();
    run.duplicatesSkipped=0;run.pagesVisited=0;
    const save=(data,meta,item,extra={})=>{
      const file=String(run.items.length+1).padStart(2,'0')+'-'+meta.sha256.slice(0,16)+meta.extension,filePath=path.join(folder,file);
      fs.writeFileSync(filePath+'.part',data,{flag:'wx'});fs.renameSync(filePath+'.part',filePath);
      run.items.push({...meta,file:filePath,source:item.sourceId,imageUrl:item.imageUrl,postUrl:item.postUrl||null,state:'DOWNLOADED',...extra});saved.push(meta);
      this.event(`Downloaded and validated ${run.items.length}/${task.count}`);atomicWrite(path.join(folder,'manifest.json'),{runId:run.id,status:'RUNNING',items:run.items});
    };
    for(const item of pending){
      if(run.items.length>=task.count)break;this.check();if(saved.some(i=>duplicateImage(item,i,false))||!fs.existsSync(item.file))continue;
      const data=fs.readFileSync(item.file),meta=await imageInfo(data);if(meta.sha256!==item.sha256)throw new TaskError('A pending image changed on disk. Review its earlier download before continuing.');
      save(data,meta,{sourceId:item.source,imageUrl:item.imageUrl,postUrl:item.postUrl},{reusedFrom:item.file});
    }
    let validCandidates=0,invalidCandidates=0;
    for(let page=0;page<paging.maxPages&&run.items.length<task.count;page++) {
      this.check();let items=await this.candidates(task.sourceSelector);
      if(page===0&&!items.length&&!this.browser.catalogExhausted)items=await this.until(async()=>{const value=await this.candidates(task.sourceSelector);return value.length?value:false;}, 'The selected image group did not appear.',15000);
      const key=this.browser.wc.getURL()+'|'+JSON.stringify(items.map(i=>i.sourceId));if(pageKeys.has(key))break;pageKeys.add(key);run.pagesVisited++;
      for(const item of items) {
        this.check();if(run.items.length>=task.count)break;
        if(item.gated||!item.sourceId||seen.has(item.sourceId))continue;seen.add(item.sourceId);
        if(seen.size>1000)break;
        if(task.newOnly&&knownSources.has(item.sourceId)){run.duplicatesSkipped++;continue;}
        let data,chosen,meta;
        for(const url of item.urls) {
          try {
            const candidate=await this.fetch(url);
            const inspected=await imageInfo(candidate);
            validCandidates++;
            if(inspected.width<128||inspected.height<128)continue;
            data=candidate;meta=inspected;chosen=url;break;
          }catch(e){if(e.code==='HTTP_404'||e instanceof TaskError&&/not a valid bounded JPEG, PNG, or WebP image/.test(e.message)){invalidCandidates++;continue;}throw e;}
        }
        if(!data)continue;
        this.check();
        if([...history,...saved].some(old=>duplicateImage(meta,old,!!task.skipSimilar))){run.duplicatesSkipped++;continue;}
        save(data,meta,{...item,imageUrl:chosen});
      }
      if(run.items.length>=task.count||seen.size>1000)break;
      if(page+1<paging.maxPages&&!await this.advance(paging,task.sourceSelector,items))break;
    }
    if(run.items.length===0&&validCandidates===0&&invalidCandidates>0)throw new TaskError('No valid JPEG, PNG, or WebP images were found in the chosen image group.');
    return run.items.length===task.count;
  }
  async inventory(target,expectedHashes) {
    await this.navigate(target.galleryUrl);await delay(500);
    const result=new Map(),sources=new Set(),pages=new Set(),paging=target.pagination||{kind:'none',maxPages:1};let candidates=0;
    for(let page=0;page<paging.maxPages;page++){
      const items=await this.candidates(target.gallerySelector),key=this.browser.wc.getURL()+'|'+JSON.stringify(items.map(i=>i.sourceId));
      if(pages.has(key))break;pages.add(key);
      for(const item of items) {
      if(sources.has(item.sourceId))continue;sources.add(item.sourceId);
      if(++candidates>500)throw new TaskError('The destination gallery exceeded its 500-image verification limit. Choose a smaller complete gallery.','NEEDS_REVIEW');
      const ownHashes=new Set();
      for(const url of item.urls) {
        let meta;
        try {meta=await imageInfo(await this.fetch(url));}
        catch(e){if(e.code==='HTTP_404'||e instanceof TaskError&&/not a valid bounded JPEG, PNG, or WebP image/.test(e.message))continue;throw e;}
        if(!expectedHashes.has(meta.sha256))continue;
        if(ownHashes.has(meta.sha256))continue;
        if(result.has(meta.sha256))throw new TaskError('Duplicate image bytes already exist in this gallery. Review the destination.','NEEDS_REVIEW');
        ownHashes.add(meta.sha256);
        result.set(meta.sha256,item.sourceId);
      }
      }
      if(!await this.advance(paging,target.gallerySelector,items))break;
      if(page+1===paging.maxPages)throw new TaskError('The destination has more pages than the reviewed verification limit. Increase its limit before uploading.','NEEDS_REVIEW');
    }
    return result;
  }
  async setUpload(locator,file) {
    const wc=this.browser.wc;
    const inspector='('+require('./dom.cjs').helpers.toString()+')()';
    const expression=`(()=>{const H=${inspector};const e=H.resolve(${JSON.stringify(locator)},true);if(e.tagName!=='INPUT'||e.type!=='file'||e.webkitdirectory)throw new Error('Choose a normal file input');return e;})()`;
    if(!wc.debugger.isAttached())wc.debugger.attach('1.3');
    const target=await wc.debugger.sendCommand('Runtime.evaluate',{expression,returnByValue:false});
    if(target.exceptionDetails||!target.result.objectId)throw new TaskError('The reviewed upload file input is missing.');
    try{await wc.debugger.sendCommand('DOM.setFileInputFiles',{objectId:target.result.objectId,files:[file]});}
    finally{await wc.debugger.sendCommand('Runtime.releaseObject',{objectId:target.result.objectId}).catch(()=>{});}
  }
  async transfer(task) {
    const run=this.active.run,target=task.target;
    const expected=new Set(this.store.data.runs.filter(r=>r.taskId===task.id).flatMap(r=>r.items
      .filter(i=>r.id===run.id||['CONFIRMED','UPLOADING','NEEDS_REVIEW'].includes(i.state)).map(i=>i.sha256)).filter(Boolean));
    let inventory=await this.inventory(target,expected);
    const uncertain=this.store.data.runs.filter(r=>r.taskId===task.id).flatMap(r=>r.items.filter(i=>['UPLOADING','NEEDS_REVIEW'].includes(i.state)));
    for(const item of uncertain){if(inventory.has(item.sha256)){item.state='CONFIRMED';item.targetId=inventory.get(item.sha256);this.store.flush();}else throw new TaskError('An earlier upload has an unknown outcome. Inspect the destination and acknowledge the run before sending anything else.','NEEDS_REVIEW');}
    for(const item of run.items) {
      this.check();if(inventory.has(item.sha256)){item.state='CONFIRMED';item.targetId=inventory.get(item.sha256);this.store.flush();continue;}
      const bytes=fs.readFileSync(item.file),meta=await imageInfo(bytes);if(meta.sha256!==item.sha256)throw new TaskError('A downloaded file changed before upload.');
      await this.navigate(target.url);
      await this.until(()=>this.browser.wc.executeJavaScript(script('findTarget',{locator:target.fileInput,hidden:true})), 'The upload file input did not appear.');
      item.state='UPLOADING';this.store.flush();this.active.effectStarted=true;
      await this.setUpload(target.fileInput,item.file);await delay(400);
      if(target.submit)await this.step({op:'click',locator:target.submit,label:'Upload'},run.inputs,0);
      await delay(750);
      // Leaving the page aborts many fetch/XHR uploads. Wait for the original request;
      // never repeat a write just because its response or gallery update is slow.
      if(this.browser.waitForUploads){this.event('Waiting for the destination to finish receiving the image');await this.browser.waitForUploads(this.active.abort.signal);this.check();}
      let found=false;
      for(let n=0;n<6;n++) {inventory=await this.inventory(target,expected);if(inventory.has(item.sha256)){found=true;break;}await delay(750);}
      if(!found){item.state='NEEDS_REVIEW';this.store.flush();throw new TaskError('The uploaded original could not be independently verified. The app will not resend it automatically.','NEEDS_REVIEW');}
      item.state='CONFIRMED';item.targetId=inventory.get(item.sha256);this.event('Confirmed uploaded image '+run.items.filter(i=>i.state==='CONFIRMED').length+'/'+run.items.length);
    }
    inventory=await this.inventory(target,expected);if(!run.items.every(i=>inventory.has(i.sha256)))throw new TaskError('A destination image changed before final verification.','NEEDS_REVIEW');
  }
  async recheck(runId){
    if(this.active)throw new TaskError('Wait for the active run first.');
    const run=this.store.data.runs.find(r=>r.id===runId);if(!run||run.status!=='NEEDS_REVIEW')throw new TaskError('Choose an upload run that needs review.');
    const task=clone(this.store.get(run.taskId));
    if(task.type!=='transfer'||task.sha!==run.sha||task.approvedSha!==task.sha)throw new TaskError('Rechecking needs the same approved transfer definition as the original run.');
    const unresolved=run.items.filter(i=>['UPLOADING','NEEDS_REVIEW'].includes(i.state));if(!unresolved.length)throw new TaskError('This run has no unresolved uploads.');
    const abort=new AbortController();this.active={task,run,abort,deadline:Date.now()+60000,effectStarted:false};this.browser.beginRun(task);this.notify();
    const timer=setTimeout(()=>{abort.abort();this.browser.wc.stop();},60000);
    try{
      const found=await this.inventory(task.target,new Set(unresolved.map(i=>i.sha256)));let confirmed=0;
      for(const item of unresolved)if(found.has(item.sha256)){item.state='CONFIRMED';item.targetId=found.get(item.sha256);confirmed++;}
      const missing=unresolved.length-confirmed;run.reviewOutcome=missing?`${missing} upload(s) are still unverified.`:'The persisted originals were independently confirmed after the run.';
      if(!missing){run.acknowledged=true;run.acknowledgedAt=new Date().toISOString();}
      this.event(run.reviewOutcome);return {confirmed,missing};
    }finally{
      clearTimeout(timer);try{this.store.flush();if(run.folder)atomicWrite(path.join(run.folder,'manifest.json'),{runId:run.id,status:run.status,items:run.items,error:run.error,reviewOutcome:run.reviewOutcome||null});}
      finally{this.browser.endRun();this.active=null;this.notify();}
    }
  }
  start(id,rowIndex=0,trigger='manual',requestId=null) {
    if(this.active)throw new TaskError('A workflow is already running. Stop it or wait for it to finish.');
    const task=clone(this.store.get(id));
    if(this.store.data.runs.some(r=>r.taskId===id&&r.status==='NEEDS_REVIEW'&&!r.acknowledged))throw new TaskError('Review the interrupted or uncertain run in History before running this workflow again.');
    const run=this.store.begin(id,rowIndex,trigger,requestId),abort=new AbortController();
    this.active={task,run,abort,deadline:Date.now()+600000,effectStarted:false};this.browser.beginRun(task);this.notify();
    return {run,completion:this.execute()};
  }
  async run(id,rowIndex=0,trigger='manual',requestId=null){return this.start(id,rowIndex,trigger,requestId).completion;}
  async execute(){
    const {task,run,abort}=this.active;
    const timer=setTimeout(()=>{abort.abort();this.browser.wc.stop();},600000);
    try {
      await this.navigate(siteUrl(task.startUrl,run.inputs));
      for(let i=0;i<task.steps.length;i++)await this.step(task.steps[i],run.inputs,i);
      // Image-result checks also gate reading the gallery. Otherwise a delayed
      // search could save old images and pass its check only after they changed.
      if(task.type==='images'&&task.steps.length)await this.checks(task,run.inputs);
      if(['images','transfer'].includes(task.type)) {
        const complete=await this.collect(task);
        if(!complete){this.store.finish(run,'PARTIAL',`Found ${run.items.length} eligible new images; ${task.count} requested.`);return clone(run);}
        if(task.type==='transfer')await this.transfer(task);
        for(const item of run.items){this.check();const meta=await imageInfo(fs.readFileSync(item.file));if(meta.sha256!==item.sha256)throw new TaskError('A saved image changed before final validation.');}
      }
      await this.checks(task,run.inputs);this.check();this.store.finish(run,'VERIFIED');return clone(run);
    }catch(e) {
      const uncertain=run.items.some(i=>['UPLOADING','NEEDS_REVIEW'].includes(i.state))||task.type==='replay'&&this.active.effectStarted;
      const status=uncertain?'NEEDS_REVIEW':e.code==='AUTH_REQUIRED'?'AUTH_REQUIRED':abort.signal.aborted?'CANCELLED':e.code==='NEEDS_REVIEW'?'NEEDS_REVIEW':'HALTED';
      this.store.finish(run,status,e.message||'The browser task stopped.');return clone(run);
    }finally {
      clearTimeout(timer);try{if(run.folder)atomicWrite(path.join(run.folder,'manifest.json'),{runId:run.id,status:run.status,items:run.items,error:run.error});}
      finally{this.browser.endRun();this.active=null;this.notify();}
    }
  }
  stop(){if(this.active){this.active.abort.abort();this.browser.wc.stop();this.notify();}}
}
module.exports={Runner,imageInfo,fetchImage,duplicateImage,MAX_BYTES,MAX_PIXELS,delay};
