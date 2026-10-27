'use strict';
// Read-only adapter for Imgflip's documented, finite popular-template catalog.
// Runner still performs downloads, pixel validation, deduplication and journaling.
const {TaskError}=require('../desktop/core.cjs');
const {boundedText}=require('./http.cjs');
const CATALOG='https://api.imgflip.com/get_memes';
const IGNORE=new Set(['a','an','and','the','of','for','funny','reaction','reactions','meme','memes','image','images','picture','pictures','sticker','stickers','template','templates','popular','trending','daily']);
function candidates(memes,topic){
  const terms=String(topic).toLowerCase().match(/[\p{L}\p{N}]+/gu)?.filter(w=>!IGNORE.has(w)).map(w=>w.length>3&&w.endsWith('s')?w.slice(0,-1):w)||[];
  return memes.filter(m=>/^\d{1,20}$/.test(String(m.id))&&typeof m.name==='string'&&m.name.length<=240&&typeof m.url==='string')
    .filter(m=>{try{const u=new URL(m.url);return u.origin==='https://i.imgflip.com'&&!u.username&&!u.password&&/\.(?:jpe?g|png|webp)$/i.test(u.pathname);}catch{return false;}})
    .filter(m=>terms.every(t=>m.name.toLowerCase().includes(t)))
    .map(m=>{const url='https://imgflip.com/memegenerator/'+m.id;return {sourceId:url,postUrl:url,urls:[m.url],alt:m.name,gated:false};});
}
class ImgflipCatalog{
  static async open(_profile,options={}){return new ImgflipCatalog(options.catalogFetch||fetch);}
  constructor(transport){
    this.transport=transport;this.items=[];this.url='about:blank';this.catalogExhausted=true;this.controller=new AbortController();
    this.session={fetch:(url,init)=>transport(url,init)};
    this.wc={getURL:()=>this.url,stop:()=>this.controller.abort(),executeJavaScript:async expression=>{
      if(expression==='document.readyState!=="loading"')return true;
      if(expression.includes('function imageCandidates'))return {authRequired:false,items:this.items};
      throw new TaskError('This catalog supports read-only image collection.');
    }};
  }
  async load(url){
    const query=new URL(url);if(query.origin!=='https://imgflip.com'||query.pathname!=='/memetemplates')throw new TaskError('Unreviewed catalog navigation.');
    this.url=query.href;const signal=AbortSignal.any([this.controller.signal,AbortSignal.timeout(20000)]);
    const response=await this.transport(CATALOG,{redirect:'error',signal,headers:{Accept:'application/json'}});
    if(!response.ok)throw new TaskError('Imgflip catalog HTTP '+response.status+'.');
    let result;try{result=JSON.parse(await boundedText(response,500000));}catch{throw new TaskError('Imgflip returned an invalid catalog.');}
    if(result.success!==true||!Array.isArray(result.data?.memes)||result.data.memes.length>500)throw new TaskError('Imgflip returned an unexpected catalog.');
    this.items=candidates(result.data.memes,query.searchParams.get('query')||'');
  }
  beginRun(){this.controller=new AbortController();}
  endRun(){}
  async close(){this.controller.abort();}
}
module.exports={ImgflipCatalog,candidates,CATALOG};
