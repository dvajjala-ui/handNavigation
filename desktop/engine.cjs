'use strict';
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const sharp=require('sharp');
const {TaskError,hash,clone,webUrl,interpolate,siteUrl,atomicWrite}=require('./core.cjs');
const {script}=require('./dom.cjs');
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const MAX_BYTES=25*1024*1024, MAX_PIXELS=40000000;

async function imageInfo(bytes) {
  if(!Buffer.isBuffer(bytes)||!bytes.length||bytes.length>MAX_BYTES)throw new TaskError('An image is empty or exceeds the 25 MB limit.');
  let meta;
  try {
    meta=await sharp(bytes,{failOn:'warning',limitInputPixels:MAX_PIXELS,animated:true}).metadata();
    if(!['jpeg','png','webp'].includes(meta.format)||meta.pages>1||!meta.width||!meta.height||meta.width*meta.height>MAX_PIXELS)throw new Error('format');
    await sharp(bytes,{failOn:'warning',limitInputPixels:MAX_PIXELS}).stats();
  }catch{throw new TaskError('The downloaded content is not a valid bounded JPEG, PNG, or WebP image.');}
  return {sha256:crypto.createHash('sha256').update(bytes).digest('hex'),bytes:bytes.length,width:meta.width,height:meta.height,
    format:meta.format,extension:{jpeg:'.jpg',png:'.png',webp:'.webp'}[meta.format],mime:'image/'+meta.format};
}
async function fetchImage(browserSession,url,origins,signal) {
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
    if(!response.ok){await response.body?.cancel();throw new TaskError(`Image request returned HTTP ${response.status}.`,'HTTP_'+response.status);}
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
  check() {
    if(!this.active||this.active.abort.signal.aborted)throw new TaskError('Run stopped.','CANCELLED');
    if(Date.now()>this.active.deadline)throw new TaskError('This run reached its 10 minute limit.','NEEDS_REVIEW');
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
  }
  async step(step,row,index) {
    this.check();const wc=this.browser.wc;
    this.event(`Step ${index+1}: ${step.op}${step.label?' '+step.label:''}`);
    if(step.op==='navigate'){await this.navigate(siteUrl(step.value,row));return;}
    if(step.op==='wait'){await delay(step.amount);this.check();return;}
    wc.focus();
    const info=await this.until(()=>wc.executeJavaScript(script('findTarget',{locator:step.locator})), 'The taught control did not appear.');
    this.check();
    if(step.op==='select') {
      this.active.effectStarted=true;
      await wc.executeJavaScript(script('selectTarget',{...info,locator:step.locator,value:interpolate(step.value,row)}),true);
    } else {
      await wc.executeJavaScript(script('focusTarget',{...info,locator:step.locator}),true);this.check();
      if(step.op==='fill') {
        this.active.effectStarted=true;
        await Promise.race([wc.insertText(interpolate(step.value,row)),delay(8000).then(()=>{throw new TaskError('The browser did not accept text input. Open the app browser and try again.');})]);
      } else if(step.op==='press') {
        this.active.effectStarted=true;
        wc.sendInputEvent({type:'keyDown',keyCode:step.value});wc.sendInputEvent({type:'keyUp',keyCode:step.value});
      } else if(step.op==='click'||step.op==='check'&&info.checked!==step.checked) {
        const fresh=await wc.executeJavaScript(script('findTarget',{locator:step.locator}));
        if(fresh.fingerprint!==info.fingerprint||fresh.url!==info.url)throw new TaskError('The control changed before the click.');
        this.check();this.active.effectStarted=true;
        wc.sendInputEvent({type:'mouseDown',x:Math.round(fresh.x),y:Math.round(fresh.y),button:'left',clickCount:1});
        wc.sendInputEvent({type:'mouseUp',x:Math.round(fresh.x),y:Math.round(fresh.y),button:'left',clickCount:1});
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
    try {const data=await fetchImage(this.browser.session,url,[...new Set([...this.active.task.allowedOrigins,...this.active.task.imageOrigins])],controller.signal);this.check();return data;}
    finally{clearTimeout(timer);parent.removeEventListener('abort',abort);}
  }
  async candidates(selector) {
    const result=await this.browser.wc.executeJavaScript(script('imageCandidates',{selector}));
    if(result.authRequired)throw new TaskError('Sign in inside the app browser first, then run again. Your login is kept in this browser.','AUTH_REQUIRED');
    return result.items;
  }
  async collect(task) {
    const run=this.active.run,seen=new Set(),known=task.newOnly?this.store.known(task.id):new Set();
    const hashes=new Set();const safeName=task.name.replace(/[^a-zA-Z0-9_-]+/g,'-').slice(0,70)||'images';
    const folder=path.join(task.outputFolder,safeName,new Date(run.startedAt).toISOString().slice(0,10)+'-'+run.id.slice(0,8));
    fs.mkdirSync(folder,{recursive:true});run.folder=folder;this.store.flush();
    let stagnant=0,validCandidates=0,invalidCandidates=0;
    for(let page=0;page<50&&run.items.length<task.count;page++) {
      this.check();let items=await this.candidates(task.sourceSelector);
      if(page===0&&!items.length)items=await this.until(async()=>{const value=await this.candidates(task.sourceSelector);return value.length?value:false;}, 'The selected image group did not appear.',15000);
      const before=seen.size;
      for(const item of items) {
        this.check();if(run.items.length>=task.count)break;
        if(item.gated||!item.sourceId||seen.has(item.sourceId))continue;seen.add(item.sourceId);
        if(seen.size>1000)break;
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
        if(known.has(meta.sha256)||hashes.has(meta.sha256))continue;
        const file=String(run.items.length+1).padStart(2,'0')+'-'+meta.sha256.slice(0,16)+meta.extension;
        const filePath=path.join(folder,file);fs.writeFileSync(filePath+'.part',data,{flag:'wx'});fs.renameSync(filePath+'.part',filePath);
        run.items.push({...meta,file:filePath,source:item.sourceId,imageUrl:chosen,state:'DOWNLOADED'});hashes.add(meta.sha256);
        this.event(`Downloaded and validated ${run.items.length}/${task.count}`);atomicWrite(path.join(folder,'manifest.json'),{runId:run.id,status:'RUNNING',items:run.items});
      }
      if(run.items.length>=task.count||seen.size>1000)break;
      const signature=JSON.stringify(items.map(i=>i.sourceId));
      await this.browser.wc.executeJavaScript(script('scrollPage'));
      let changed=false;
      const until=Math.min(Date.now()+7000,this.active.deadline);
      while(Date.now()<until){this.check();await delay(350);items=await this.candidates(task.sourceSelector);if(JSON.stringify(items.map(i=>i.sourceId))!==signature){changed=true;break;}}
      stagnant=(!changed||before===seen.size)?stagnant+1:0;if(stagnant>=2)break;
    }
    if(run.items.length===0&&validCandidates===0&&invalidCandidates>0)throw new TaskError('No valid JPEG, PNG, or WebP images were found in the chosen image group.');
    return run.items.length===task.count;
  }
  async inventory(target,expectedHashes) {
    await this.navigate(target.galleryUrl);await delay(500);
    const items=await this.candidates(target.gallerySelector),result=new Map();
    for(const item of items.slice(0,500)) {
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
      let found=false;
      for(let n=0;n<6;n++) {inventory=await this.inventory(target,expected);if(inventory.has(item.sha256)){found=true;break;}await delay(750);}
      if(!found){item.state='NEEDS_REVIEW';this.store.flush();throw new TaskError('The uploaded original could not be independently verified. The app will not resend it automatically.','NEEDS_REVIEW');}
      item.state='CONFIRMED';item.targetId=inventory.get(item.sha256);this.event('Confirmed uploaded image '+run.items.filter(i=>i.state==='CONFIRMED').length+'/'+run.items.length);
    }
    inventory=await this.inventory(target,expected);if(!run.items.every(i=>inventory.has(i.sha256)))throw new TaskError('A destination image changed before final verification.','NEEDS_REVIEW');
  }
  async run(id,rowIndex=0,trigger='manual') {
    if(this.active)throw new TaskError('A workflow is already running. Stop it or wait for it to finish.');
    const task=clone(this.store.get(id));
    if(this.store.data.runs.some(r=>r.taskId===id&&r.status==='NEEDS_REVIEW'&&!r.acknowledged))throw new TaskError('Review the interrupted or uncertain run in History before running this workflow again.');
    const run=this.store.begin(id,rowIndex,trigger),abort=new AbortController();
    this.active={task,run,abort,deadline:Date.now()+600000,effectStarted:false};this.browser.beginRun(task);this.notify();
    const timer=setTimeout(()=>{abort.abort();this.browser.wc.stop();},600000);
    try {
      await this.navigate(siteUrl(task.startUrl,run.inputs));
      for(let i=0;i<task.steps.length;i++)await this.step(task.steps[i],run.inputs,i);
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
      clearTimeout(timer);if(run.folder)atomicWrite(path.join(run.folder,'manifest.json'),{runId:run.id,status:run.status,items:run.items,error:run.error});
      this.browser.endRun();this.active=null;this.notify();
    }
  }
  stop(){if(this.active){this.active.abort.abort();this.browser.wc.stop();this.notify();}}
}
module.exports={Runner,imageInfo,fetchImage,MAX_BYTES,MAX_PIXELS,delay};
