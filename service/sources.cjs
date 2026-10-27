'use strict';
const {webUrl,validate,draft}=require('../desktop/core.cjs');
const BUILTINS=[
  {id:'pinterest',name:'Pinterest',searchUrl:'https://www.pinterest.com/search/pins/?q={{topic}}',selector:'a[href*="/pin/"] img',
    allowedOrigins:['https://www.pinterest.com','https://in.pinterest.com','https://s.pinimg.com'],imageOrigins:['https://i.pinimg.com'],pagination:{kind:'scroll',maxPages:35}},
  {id:'reddit',name:'Reddit',searchUrl:'https://www.reddit.com/search/?q={{topic}}&type=media&sort=relevance',selector:'.search-media-post-image img:not([role="presentation"]), shreddit-post img[alt^="r/"]',
    allowedOrigins:['https://www.reddit.com','https://www.redditstatic.com','https://styles.redditmedia.com'],imageOrigins:['https://i.redd.it','https://preview.redd.it'],pagination:{kind:'scroll',maxPages:40}}
];
function sources(input=BUILTINS){
  if(!Array.isArray(input)||!input.length||input.length>20)throw new Error('Configure 1–20 source recipes.');
  const seen=new Set();
  for(const s of input){
    if(!/^[a-z][a-z0-9_-]{1,39}$/.test(s.id)||seen.has(s.id))throw new Error('Source IDs must be short and unique.');seen.add(s.id);
    if(typeof s.searchUrl!=='string'||!s.searchUrl.includes('{{topic}}'))throw new Error('A source needs an encoded {{topic}} search URL.');
    validate({...draft({startUrl:s.searchUrl,outputFolder:require('node:os').tmpdir(),imageOrigins:s.imageOrigins||[]}),sourceSelector:s.selector,allowedOrigins:s.allowedOrigins,pagination:s.pagination||{kind:'scroll',maxPages:30}});
    webUrl(s.searchUrl.replace('{{topic}}','example'));
  }
  return input;
}
function request(body,registry,maxImages=100){
  if(!body||typeof body.requestId!=='string'||!(/^[A-Za-z0-9._:-]{8,128}$/).test(body.requestId))throw new Error('Use an 8–128 character requestId.');
  if(!Array.isArray(body.topics)||!body.topics.length||body.topics.length>10||body.topics.some(t=>typeof t!=='string'||!t.trim()||t.length>240||/[\x00-\x1f]/.test(t)))throw new Error('Supply 1–10 short topic strings.');
  if(!Array.isArray(body.sources)||!body.sources.length||new Set(body.sources).size!==body.sources.length||body.sources.some(id=>!registry.some(s=>s.id===id)))throw new Error('Choose configured source IDs.');
  const limit=body.limit??20;if(!Number.isInteger(limit)||limit<1||limit>maxImages)throw new Error('Image limit is outside the configured bound.');
  if(body.destination!==undefined&&!['local','stickerdock'].includes(body.destination))throw new Error('Choose local or stickerdock storage.');
  return {requestId:body.requestId,topics:body.topics.map(t=>t.trim()),sources:body.sources,limit,destination:body.destination||'stickerdock'};
}
module.exports={BUILTINS,sources,request};
