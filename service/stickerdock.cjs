'use strict';
const fs=require('node:fs'),crypto=require('node:crypto'),sharp=require('sharp');
const {imageInfo}=require('../desktop/engine.cjs');
const {webUrl}=require('../desktop/core.cjs');
const {boundedText,wait}=require('./http.cjs');
function sourceLink(value){
  const u=webUrl(value);u.hash='';u.search='';
  if(/(^|\.)reddit\.com$/.test(u.hostname)){const id=u.pathname.match(/\/comments\/([a-z0-9]+)\//i)?.[1];if(id)return u.origin+'/comments/'+id+'/';}
  return u.href;
}
class StickerDock{
  constructor(url,token=process.env.STICKERDOCK_INGEST_TOKEN,options={}){
    const base=webUrl(url);
    if(base.protocol!=='https:'&&!['localhost','127.0.0.1','[::1]'].includes(base.hostname))throw new Error('Use HTTPS for a remote StickerDock server.');
    if(base.search||base.hash||base.pathname!=='/')throw new Error('Use the StickerDock site origin without a path, query or fragment.');
    this.url=base.origin;if(typeof token!=='string'||token.length<32)throw new Error('Configure the server-only StickerDock ingest token (32+ characters).');this.token=token;this.options=options;
  }
  async call(endpoint,payload,signal){
    const repeatable=endpoint==='ingest'&&['store','get','status','history'].includes(payload.action);
    for(let attempt=0;;attempt++)try{return await this.request(endpoint,payload,signal);}catch(error){
      if(signal?.aborted||!repeatable||attempt>=2||!error.retryable)throw error;
      const delay=error.retryAfterMs??(this.options.retryDelayMs??1000)*2**attempt;
      if(delay>30000)throw error; // Respect long Retry-After values by leaving the job resumable.
      await wait(delay,signal);
    }
  }
  async request(endpoint,payload,signal){
    const timeout=AbortSignal.timeout(60000);
    let response,text;
    try{
      response=await fetch(this.url+'/api/'+endpoint,{method:'POST',redirect:'error',headers:{'Content-Type':'application/json',Authorization:'Bearer '+this.token},body:JSON.stringify(payload),signal:signal?AbortSignal.any([timeout,signal]):timeout});
      text=await boundedText(response);
    }catch(error){error.retryable=!signal?.aborted&&(error.name==='TypeError'||error.name==='TimeoutError'||error.name==='AbortError');throw error;}
    let result;try{result=JSON.parse(text);}catch{result={error:'Server returned invalid JSON'};if(response.ok)throw new Error('StickerDock returned invalid JSON.');}
    if(!response.ok){
      const error=new Error('StickerDock HTTP '+response.status+': '+String(result.error||'storage unavailable').slice(0,200));
      error.retryable=[408,429,500,502,503,504].includes(response.status);
      const retry=response.headers.get('retry-after');if(retry){const seconds=Number(retry);error.retryAfterMs=Math.max(0,Number.isFinite(seconds)?seconds*1000:Date.parse(retry)-Date.now());if(!Number.isFinite(error.retryAfterMs))error.retryAfterMs=30001;}
      throw error;
    }return result;
  }
  async store(item,signal){
    const original=fs.readFileSync(item.file);if((await imageInfo(original)).sha256!==item.sha256)throw new Error('A downloaded image changed before delivery.');
    const staged=await sharp(original).rotate().resize(1600,1600,{fit:'inside',withoutEnlargement:true}).webp({quality:90}).toBuffer();
    if(staged.length>2800000)throw new Error('Prepared source exceeds StickerDock\'s upload bound.');
    const link=sourceLink(item.postUrl||item.source||item.imageUrl);
    const result=await this.call('ingest',{action:'store',image:'data:image/webp;base64,'+staged.toString('base64'),collection_id:item.collectionId,platform:item.platform,topic:item.topic,source_url:link,download_url:item.imageUrl,original_sha256:item.sha256},signal),receipt=result.item;
    if(!/^handnavigate\/candidates\/[0-9a-f]{64}\.webp$/.test(receipt?.storage_path||'')||!/^[0-9a-f]{64}$/.test(receipt?.stored_sha256||''))throw new Error('StickerDock returned an invalid image receipt.');
    const fetched=await this.call('ingest',{action:'get',id:receipt.id},signal),match=/^data:image\/(?:webp|png|jpeg);base64,([A-Za-z0-9+/=]+)$/.exec(fetched.image||'');
    if(!match)throw new Error('The stored source could not be independently fetched.');
    const stored=Buffer.from(match[1],'base64'),meta=await imageInfo(stored);
    if(meta.sha256!==receipt.stored_sha256)throw new Error('The stored source checksum differs from its receipt.');
    const localMeta=await imageInfo(staged);if(meta.width!==localMeta.width||meta.height!==localMeta.height)throw new Error('StickerDock changed the source geometry unexpectedly.');
    const pixels=async bytes=>sharp(bytes).resize(64,64,{fit:'fill'}).flatten({background:'#ffffff'}).removeAlpha().toColourspace('srgb').raw().toBuffer();
    const [a,b]=await Promise.all([pixels(staged),pixels(stored)]);let difference=0;for(let i=0;i<a.length;i++)difference+=Math.abs(a[i]-b[i]);
    if(difference/a.length>12)throw new Error('The persisted source no longer matches the prepared image.');
    const row=fetched.item;
    if(!['UNREVIEWED','APPROVED','REJECTED'].includes(row?.rights_status)||typeof row.generation_eligible!=='boolean'||row.generation_eligible&&row.rights_status!=='APPROVED'||row.original_sha256!==item.sha256||row.source_url!==link||row.platform!==item.platform)throw new Error('Stored source review metadata differs from this collection.');
    return {id:receipt.id,path:receipt.storage_path,sha256:receipt.stored_sha256,verifiedAt:new Date().toISOString(),rightsStatus:row.rights_status,generationEligible:row.generation_eligible,
      provenanceStorage:'Supabase media_intake_items row and HandNavigate manifest',preparedSha256:crypto.createHash('sha256').update(staged).digest('hex')};
  }
}
module.exports={StickerDock,sourceLink};
