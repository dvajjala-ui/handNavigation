'use strict';
// Anonymous Openverse image search. Downloads are proxied through Openverse's
// fixed-origin thumbnail endpoint; arbitrary result hosts are provenance only.
const net=require('node:net');
const {ImgflipCatalog}=require('./imgflip.cjs');
const {TaskError}=require('../desktop/core.cjs');
const {boundedText,wait}=require('./http.cjs');
const API='https://api.openverse.org',SEARCH='/v1/images/';
const LICENSES={
  cc0:{name:'CC0',url:'https://creativecommons.org/publicdomain/zero/1.0/'},
  pdm:{name:'PUBLIC_DOMAIN',url:'https://creativecommons.org/publicdomain/mark/1.0/'}
};
function publicLanding(value){
  try{
    const u=new URL(value),host=u.hostname.toLowerCase();
    if(u.protocol!=='https:'||u.username||u.password||u.port||!host.includes('.')||net.isIP(host)||host==='localhost'||host.endsWith('.local')||host.endsWith('.internal'))return null;
    u.hash='';u.search='';return u.href;
  }catch{return null;}
}
function thumbUrl(value,id){
  try{const u=new URL(value);return u.origin===API&&!u.username&&!u.password&&u.pathname===`/v1/images/${id}/thumb/`&&!u.search&&!u.hash?u.href:null;}catch{return null;}
}
class OpenverseSearch extends ImgflipCatalog{
  static async open(_profile,options={}){return new OpenverseSearch(options.catalogFetch||fetch,options.catalogHistory||[]);}
  constructor(transport,history=[]){super(transport);this.history=new Set(history);this.session.imageAccept='*/*';}
  async load(value){
    const url=new URL(value);if(url.origin!==API||url.pathname!==SEARCH||url.username||url.password)throw new TaskError('Unreviewed Openverse navigation.');
    const topic=(url.searchParams.get('q')||'').trim();if(!topic||topic.length>240||/[\x00-\x1f]/.test(topic))throw new TaskError('Enter a short Openverse search topic.');
    const query=new URL(API+SEARCH);query.search=new URLSearchParams({q:topic,license:'cc0,pdm',license_type:'commercial,modification',mature:'false',page_size:'20'}).toString();
    this.url=query.href;this.items=[];const signal=AbortSignal.any([this.controller.signal,AbortSignal.timeout(90000)]);
    let response;
    for(let attempt=0;attempt<3;attempt++){
      response=await this.transport(query.href,{redirect:'error',signal,headers:{Accept:'application/json'}});
      if(response.ok)break;
      if(![429,500,502,503,504].includes(response.status)||attempt===2){const error=new TaskError('Openverse search HTTP '+response.status+'.');error.status=response.status;throw error;}
      await wait(1000*2**attempt,signal);
    }
    let result;try{result=JSON.parse(await boundedText(response,2500000));}catch{throw new TaskError('Openverse returned invalid or oversized search metadata.');}
    if(!Array.isArray(result.results)||result.results.length>20)throw new TaskError('Openverse returned an unexpected search result.');
    const seen=new Set();
    for(const item of result.results){
      const id=String(item?.id||'').toLowerCase(),license=LICENSES[item?.license],landing=publicLanding(item?.foreign_landing_url),thumb=thumbUrl(item?.thumbnail,id);
      if(!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(id)||!license||item.license_url!==license.url||!landing||!thumb||this.history.has(landing)||seen.has(landing))continue;
      if(item.mature!==false||!Number.isInteger(item.width)||!Number.isInteger(item.height)||Math.min(item.width,item.height)<128)continue;
      seen.add(landing);const title=typeof item.title==='string'?item.title.trim().slice(0,160):'';
      const creator=typeof item.creator==='string'?item.creator.trim().replace(/[\x00-\x1f]/g,' ').slice(0,120):'';
      const tags=['openverse','reported-license:'+license.name];if(creator)tags.push('creator:'+creator.slice(0,32));
      this.items.push({sourceId:landing,postUrl:landing,urls:[thumb],alt:title,title,creator,license:license.name,licenseUrl:license.url,tags,gated:false});
    }
  }
}
module.exports={OpenverseSearch,publicLanding,thumbUrl,API,SEARCH};
