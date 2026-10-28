'use strict';
// Public tag feed + provider-advertised oEmbed photo URLs. Never guess an original.
const {ImgflipCatalog}=require('./imgflip.cjs');
const {TaskError}=require('../desktop/core.cjs');
const {boundedText}=require('./http.cjs');
const ORIGIN='https://www.flickr.com',FEED='/services/feeds/photos_public.gne';
function postUrl(value){try{const u=new URL(value);return u.origin===ORIGIN&&!u.username&&!u.password&&/^\/photos\/[^/]+\/\d+\/$/.test(u.pathname)&&!u.search&&!u.hash?u.href:null;}catch{return null;}}
function imageUrl(value){try{const u=new URL(value);return u.origin==='https://live.staticflickr.com'&&!u.username&&!u.password&&/^\/\d+\/\d+_[a-z0-9]+(?:_[a-z])?\.(?:jpe?g|png|webp)$/i.test(u.pathname)&&!u.search&&!u.hash?u.href:null;}catch{return null;}}
class FlickrFeed extends ImgflipCatalog{
  static async open(_profile,options={}){return new FlickrFeed(options.catalogFetch||fetch,options.catalogHistory||[]);}
  constructor(transport,history=[]){super(transport);this.history=new Set(history);this.cache=new Map();}
  async json(url,signal,limit){
    const response=await this.transport(url,{redirect:'error',signal,headers:{Accept:'application/json'}});
    if(!response.ok){const error=new TaskError('Flickr public source HTTP '+response.status+'.');error.status=response.status;throw error;}
    try{return JSON.parse(await boundedText(response,limit));}catch{throw new TaskError('Flickr returned invalid or oversized source metadata.');}
  }
  async load(value){
    const url=new URL(value);if(url.origin!==ORIGIN||url.pathname!==FEED||url.username||url.password)throw new TaskError('Unreviewed Flickr feed navigation.');
    const tags=(url.searchParams.get('tags')||'').split(',').map(t=>t.trim()).filter(Boolean);
    if(!tags.length||tags.length>10||tags.some(t=>t.length>80||/[\x00-\x1f]/.test(t)))throw new TaskError('Enter 1–10 comma-separated Flickr tags.');
    const query=new URL(ORIGIN+FEED);query.search=new URLSearchParams({format:'json',nojsoncallback:'1',tags:tags.join(','),tagmode:'all'}).toString();
    this.url=query.href;this.items=[];
    const signal=AbortSignal.any([this.controller.signal,AbortSignal.timeout(90000)]),result=await this.json(query.href,signal,1500000);
    if(!Array.isArray(result.items)||result.items.length>100)throw new TaskError('Flickr returned an unexpected public feed.');
    const seen=new Set();
    for(const item of result.items){
      const post=postUrl(item?.link);if(!post||this.history.has(post)||seen.has(post))continue;seen.add(post);
      let photo=this.cache.get(post);
      if(!photo){
        const endpoint=new URL(ORIGIN+'/services/oembed/');endpoint.search=new URLSearchParams({format:'json',url:post,maxwidth:'1600',maxheight:'1600'}).toString();
        try{photo=await this.json(endpoint.href,signal,50000);this.cache.set(post,photo);}catch(error){if([404,410].includes(error.status))continue;throw error;}
      }
      const image=imageUrl(photo?.url),identity=new URL(post).pathname.split('/').at(-2);
      if(photo?.type!=='photo'||!image||!new URL(image).pathname.split('/').at(-1).startsWith(identity+'_')||!Number.isInteger(photo.width)||!Number.isInteger(photo.height)||Math.min(photo.width,photo.height)<128)continue;
      this.items.push({sourceId:post,postUrl:post,urls:[image],alt:typeof photo.title==='string'?photo.title.slice(0,240):'',gated:false});
    }
  }
}
module.exports={FlickrFeed,postUrl,imageUrl};
