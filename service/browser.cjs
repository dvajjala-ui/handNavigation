'use strict';
const path=require('node:path'),fs=require('node:fs');
const {chromium}=require('playwright');
const {TaskError,webUrl}=require('../desktop/core.cjs');
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
class ServiceBrowser{
  static async open(profile,options={}){
    fs.mkdirSync(profile,{recursive:true});
    const context=await chromium.launchPersistentContext(profile,{headless:options.headless!==false,acceptDownloads:false,serviceWorkers:'block',viewport:{width:1360,height:900},
      ...(options.channel?{channel:options.channel}:{}),...(options.executablePath?{executablePath:options.executablePath}:{})});
    const page=context.pages()[0]||await context.newPage(),browser=new ServiceBrowser(context,page,options,await context.newCDPSession(page));await browser.routeReady;return browser;
  }
  constructor(context,page,options,cdp){
    this.context=context;this.page=page;this.options=options;this.cdp=cdp;this.pending=new Set();this.mutations=new Set();this.lastNetworkAt=Date.now();this.runTask=null;this.effectError=null;
    page.on('request',r=>{this.pending.add(r);this.lastNetworkAt=Date.now();if(!['GET','HEAD','OPTIONS'].includes(r.method()))this.mutations.add(r);});
    const done=r=>{this.pending.delete(r);this.mutations.delete(r);this.lastNetworkAt=Date.now();};page.on('requestfinished',done);page.on('requestfailed',done);
    page.on('download',download=>{download.cancel().catch(()=>{});this.effectError='Unexpected site download; only verified image reads are supported.';});
    page.on('crash',()=>{this.effectError='The source browser stopped.';this.runner?.stop();});
    // Chromium pauses every redirect hop here. Playwright route.continue() only
    // intercepts the initial request and otherwise lets redirects leave scope.
    cdp.on('Fetch.requestPaused',event=>this.routeRequest(event).catch(()=>{}));
    cdp.on('Page.frameNavigated',({frame})=>{if(!frame.parentId)this.mainFrameId=frame.id;});
    this.routeReady=(async()=>{this.mainFrameId=(await cdp.send('Page.getFrameTree')).frameTree.frame.id;await cdp.send('Fetch.enable',{patterns:[{urlPattern:'*',requestStage:'Request'}]});})();
    context.on('page',popup=>{if(this.runTask&&!this.authPhase&&popup!==page){this.effectError='A source opened an unexpected popup. Sign in before running.';popup.close().catch(()=>{});}});
    this.wc={getURL:()=>page.url(),executeJavaScript:async expression=>{
      if(expression.includes('function imageCandidates')){
        await this.waitForAccess();
        const result=await page.evaluate(expression);
        if(result.authRequired){await this.waitForAccess(true);return page.evaluate(expression);}
        return result;
      }
      return page.evaluate(expression);
    },stop:()=>cdp.send('Page.stopLoading').catch(()=>{}),debugger:{isAttached:()=>!page.isClosed(),attach:()=>{},sendCommand:(method,params)=>cdp.send(method,params)}};
    this.session={fetch:async(url,init)=>{
      const cookies=await context.cookies(url),headers={...init.headers};if(cookies.length)headers.Cookie=cookies.map(c=>c.name+'='+c.value).join('; ');
      return fetch(url,{...init,headers});
    }};
  }
  async routeRequest(event){
    let allowed=true;
    try{
      const u=new URL(event.request.url);
      if(this.runTask&&!this.authPhase&&['http:','https:'].includes(u.protocol)){
        allowed=[...this.runTask.allowedOrigins,...this.runTask.imageOrigins].includes(u.origin);
        if(!allowed&&event.resourceType==='Document'&&event.frameId===this.mainFrameId)this.effectError='Navigation tried to leave the reviewed source websites: '+u.origin;
      }
    }catch{allowed=false;}
    if(event.resourceType==='Media')allowed=false;
    await this.cdp.send(allowed?'Fetch.continueRequest':'Fetch.failRequest',{
      requestId:event.requestId,...(allowed?{}:{errorReason:'BlockedByClient'})});
  }
  async gated(){for(let attempt=0;attempt<10;attempt++)try{return await this.page.evaluate(selector=>{
    const title=document.title||'',text=(document.body?.innerText||'').slice(0,2500);
    if(/prove your humanity|access denied|just a moment/i.test(title)||/we.re committed to safety and security[\s\S]{0,120}not for bots/i.test(text))return true;
    const publicImages=selector&&[...document.querySelectorAll(selector)].some(e=>{const i=e.tagName==='IMG'?e:e.querySelector('img');return i&&!i.closest('[data-test-id="gated-pin-image"]')&&!!(i.currentSrc||i.src||i.srcset);});
    if(publicImages)return false;
    if(/blocked by network security|verify you are human/i.test(text)&&!document.querySelector('.search-media-post-image img,shreddit-post'))return true;
    return !!document.querySelector('[data-test-id="gated-pin-image"]')||[...document.querySelectorAll('input[type=password]')].some(e=>e.getClientRects().length);
  },this.runTask?.sourceSelector||null);}catch(error){if(!/Execution context was destroyed|navigation/i.test(error.message)||attempt===9)throw error;await pause(250);}}
  async load(url){
    webUrl(url);this.effectError=null;const response=await this.page.goto(url,{waitUntil:'commit',timeout:45000});
    if(this.effectError)throw new TaskError(this.effectError);
    await this.waitForAccess();
    if(response&&response.status()>=400&&await this.gated())throw new TaskError('Source access requires manual attention.','AUTH_REQUIRED');
  }
  async waitForAccess(force=false){
    if(force||await this.gated()){
      this.options.onAuth?.(new URL(this.page.url()).origin);
      const end=Date.now()+(this.options.interactiveWaitMs||0);
      if(this.options.interactiveWaitMs){this.authPhase=true;await this.page.reload({waitUntil:'domcontentloaded'});}
      while(Date.now()<end&&(await this.gated()||this.runTask&&!this.runTask.allowedOrigins.includes(new URL(this.page.url()).origin))){if(this.runner?.active?.abort.signal.aborted)break;await pause(1000);}
      this.authPhase=false;
      if(await this.gated())throw new TaskError('Public browsing is blocked by this source. A human check or optional saved sign-in may be needed; no API account is required. Resume after access is available.','AUTH_REQUIRED');
    }
  }
  async settle(){const end=Date.now()+8000;while(Date.now()<end){if(this.runner?.active?.abort.signal.aborted)return;if(!this.pending.size&&Date.now()-this.lastNetworkAt>=250)return;await pause(100);}}
  beginRun(task){this.runTask=task;this.effectError=null;}
  endRun(){this.runTask=null;this.effectError=null;}
  close(){return this.context.close();}
}
module.exports={ServiceBrowser};
