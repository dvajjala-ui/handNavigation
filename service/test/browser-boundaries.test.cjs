'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),http=require('node:http'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {ServiceBrowser}=require('../browser.cjs'),{script}=require('../../desktop/dom.cjs');
test('browser blocks an unapproved redirect before transmission and accepts public images beside optional login',async t=>{
  let requests=0;
  const target=http.createServer((q,s)=>{requests++;s.end('unapproved');});
  await new Promise(r=>target.listen(0,'127.0.0.1',r));
  const site=http.createServer((q,s)=>{
    if(q.url==='/leave'){s.writeHead(302,{Location:'http://127.0.0.1:'+target.address().port+'/'});return s.end();}
    if(q.url==='/inside'){s.writeHead(302,{Location:'/public'});return s.end();}
    s.setHeader('Content-Type','text/html');s.end(q.url==='/blocked'?'<title>Access denied</title><input type="password">':'<title>Public gallery</title><input type="password"><div id="gallery"><img src="/image.png"></div>');
  });
  await new Promise(r=>site.listen(0,'127.0.0.1',r));
  const folder=fs.mkdtempSync(path.join(os.tmpdir(),'hand-boundaries-'));
  const browser=await ServiceBrowser.open(folder,{headless:true,...(process.platform==='win32'?{channel:'chrome'}:{})});
  t.after(async()=>{await browser.close();await Promise.all([site,target].map(s=>new Promise(r=>s.close(r))));if(path.resolve(folder).startsWith(path.resolve(os.tmpdir())+path.sep))fs.rmSync(folder,{recursive:true,force:true,maxRetries:10,retryDelay:200});});
  const origin='http://127.0.0.1:'+site.address().port;
  browser.beginRun({allowedOrigins:[origin],imageOrigins:[],sourceSelector:'#gallery img'});
  await assert.rejects(browser.load(origin+'/leave'));assert.equal(requests,0);
  await browser.page.waitForURL('chrome-error://chromewebdata/').catch(()=>{});
  browser.beginRun({allowedOrigins:[origin],imageOrigins:[],sourceSelector:'#gallery img'});
  await browser.load(origin+'/inside');await browser.page.waitForSelector('#gallery img');assert.equal(await browser.gated(),false);
  const candidates=await browser.wc.executeJavaScript(script('imageCandidates',{selector:'#gallery img'}));assert.equal(candidates.authRequired,false);assert.equal(candidates.items.length,1);
  await browser.page.goto(origin+'/blocked');assert.equal(await browser.gated(),true);
});
