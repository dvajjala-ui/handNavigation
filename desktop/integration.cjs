'use strict';
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),crypto=require('node:crypto');
const {TaskError,atomicWrite}=require('./core.cjs');

function validRequestId(value){return typeof value==='string'&&/^[A-Za-z0-9._-]{8,128}$/.test(value);}
function authenticated(value,token){
  const given=Buffer.from(String(value||'')),expected=Buffer.from('Bearer '+token);
  return given.length===expected.length&&crypto.timingSafeEqual(given,expected);
}
class LocalAPI {
  constructor(folder,callbacks){
    this.file=path.join(folder,'integration.json');this.callbacks=callbacks;this.server=null;
    this.config={enabled:false,port:47831,token:crypto.randomBytes(32).toString('hex')};
    if(fs.existsSync(this.file)){
      const saved=JSON.parse(fs.readFileSync(this.file,'utf8'));
      if(typeof saved.enabled!=='boolean'||!Number.isInteger(saved.port)||saved.port<1||saved.port>65535||!/^[a-f0-9]{64}$/.test(saved.token))throw new TaskError('The local API settings are invalid. Restore integration.json from its backup.');
      this.config=saved;
    }
  }
  snapshot(){return {enabled:!!this.server,port:this.config.port,endpoint:this.server?'http://127.0.0.1:'+this.config.port+'/v1':null};}
  async enable(port=this.config.port){
    if(!Number.isInteger(port)||port<1024||port>65535)throw new TaskError('Choose a local API port between 1024 and 65535.');
    if(this.server&&port===this.config.port)return this.snapshot();
    const server=http.createServer((req,res)=>this.handle(req,res));server.requestTimeout=10000;server.headersTimeout=10000;
    await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(port,'127.0.0.1',()=>{server.removeListener('error',reject);resolve();});}).catch(error=>{server.close();throw new TaskError(error.code==='EADDRINUSE'?'That API port is already in use. Choose another port.':'The local API could not start: '+error.message);});
    if(this.server)await this.close();this.server=server;this.config.enabled=true;this.config.port=server.address().port;
    server.on('error',error=>this.callbacks.error?.(error));
    try{atomicWrite(this.file,this.config);}catch(error){await this.close();throw error;}
    return this.snapshot();
  }
  async close(){if(!this.server)return;const server=this.server;this.server=null;server.closeIdleConnections();await new Promise(resolve=>server.close(resolve));}
  async disable(){await this.close();this.config.enabled=false;atomicWrite(this.file,this.config);return this.snapshot();}
  async handle(req,res){
    const send=(status,value)=>{res.writeHead(status,{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'});res.end(JSON.stringify(value));};
    try{
      const host=String(req.headers.host||'');
      if(!/^127\.0\.0\.1:\d+$/.test(host)||req.headers.origin){req.resume();return send(403,{error:'Only local clients without a browser Origin may use this API.'});}
      if(!authenticated(req.headers.authorization,this.config.token)){req.resume();return send(401,{error:'A local API bearer token is required.'});}
      const url=new URL(req.url,'http://'+host),method=req.method;
      if(method==='GET'&&url.pathname==='/v1/health')return send(200,{status:'ready',busy:!!this.callbacks.busy()});
      if(method==='GET'&&url.pathname==='/v1/workflows')return send(200,{workflows:this.callbacks.store.data.tasks.filter(t=>!t.archived).map(t=>({id:t.id,name:t.name,type:t.type,approved:!!t.approvedSha,rows:t.rows,count:t.count,schedule:t.schedule}))});
      const match=url.pathname.match(/^\/v1\/runs\/([0-9a-f-]{36})(\/stop)?$/);
      if(match&&method==='GET'&&!match[2]){const run=this.callbacks.store.data.runs.find(r=>r.id===match[1]);return send(run?200:404,run||{error:'Run not found.'});}
      if(method!=='POST'||url.pathname!=='/v1/runs'&&!(match&&match[2])){req.resume();return send(404,{error:'Unknown endpoint.'});}
      if(!/^application\/json(?:;|$)/i.test(String(req.headers['content-type']||''))){req.resume();return send(415,{error:'Send application/json.'});}
      let size=0;const chunks=[];
      for await(const chunk of req){size+=chunk.length;if(size>8192){send(413,{error:'Request exceeds 8 KB.'});req.destroy();return;}chunks.push(chunk);}
      let body;try{body=JSON.parse(Buffer.concat(chunks).toString('utf8'));}catch{return send(400,{error:'Invalid JSON.'});}
      if(!body||Array.isArray(body)||typeof body!=='object')return send(400,{error:'Send a JSON object.'});
      if(match&&match[2]){this.callbacks.stop(match[1]);return send(202,{id:match[1],stopping:true});}
      if(typeof body.workflowId!=='string'||!Number.isInteger(body.rowIndex??0)||!validRequestId(body.requestId))return send(400,{error:'Supply workflowId, an integer rowIndex, and a requestId of 8–128 letters, digits, dots, underscores or hyphens.'});
      const result=this.callbacks.start(body.workflowId,body.rowIndex??0,body.requestId);
      return send(result.reused?200:202,{id:result.run.id,status:result.run.status,reused:result.reused,statusUrl:'/v1/runs/'+result.run.id});
    }catch(error){if(!res.headersSent)send(error instanceof TaskError?409:500,{error:error instanceof TaskError?error.message:'The local API could not complete this request.'});}
  }
}
module.exports={LocalAPI,validRequestId};
