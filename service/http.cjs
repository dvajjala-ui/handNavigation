'use strict';
async function boundedText(response,limit=4500000){
  const declared=Number(response.headers.get('content-length'));
  if(declared>limit){await response.body?.cancel();throw new Error('Response exceeded its byte limit.');}
  if(!response.body)return '';
  const reader=response.body.getReader(),parts=[];let bytes=0;
  try{while(true){const part=await reader.read();if(part.done)break;bytes+=part.value.byteLength;if(bytes>limit){await reader.cancel();throw new Error('Response exceeded its byte limit.');}parts.push(Buffer.from(part.value));}}
  finally{reader.releaseLock();}
  return Buffer.concat(parts,bytes).toString('utf8');
}
function wait(ms,signal){return new Promise((resolve,reject)=>{
  if(signal?.aborted)return reject(signal.reason||new Error('Request cancelled.'));
  const abort=()=>{clearTimeout(timer);reject(signal.reason||new Error('Request cancelled.'));};
  const timer=setTimeout(()=>{signal?.removeEventListener('abort',abort);resolve();},ms);
  signal?.addEventListener('abort',abort,{once:true});
});}
module.exports={boundedText,wait};
