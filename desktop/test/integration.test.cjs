const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),net=require('node:net'),http=require('node:http');
const {LocalAPI}=require('../integration.cjs');
async function freePort(){const server=net.createServer();await new Promise(r=>server.listen(0,'127.0.0.1',r));const port=server.address().port;await new Promise(r=>server.close(r));return port;}
test('local API authenticates, rejects website origins, validates requests and keeps its token out of state',async t=>{
  const folder=fs.mkdtempSync(path.join(os.tmpdir(),'handnavigate-api-'));let starts=0;
  const run={id:'12345678-1234-1234-1234-123456789012',status:'RUNNING'};
  const api=new LocalAPI(folder,{store:{data:{tasks:[],runs:[run]}},busy:()=>false,start:()=>{starts++;return {run,reused:false};},stop:()=>{}});
  t.after(async()=>{await api.close();fs.rmSync(folder,{recursive:true,force:true});});
  await api.enable(await freePort());const endpoint=api.snapshot().endpoint,headers={Authorization:'Bearer '+api.config.token,'Content-Type':'application/json'};
  assert.equal(JSON.stringify(api.snapshot()).includes(api.config.token),false);
  assert.equal((await fetch(endpoint+'/health')).status,401);
  assert.equal((await fetch(endpoint+'/health',{headers:{...headers,Origin:'https://untrusted.example'}})).status,403);
  assert.equal(await new Promise((resolve,reject)=>{http.get(endpoint+'/health',{headers:{...headers,Host:'attacker.example'}},res=>{res.resume();resolve(res.statusCode);}).on('error',reject);}),403);
  assert.equal((await fetch(endpoint+'/runs',{method:'POST',headers,body:'{}'})).status,400);assert.equal(starts,0);
  assert.equal((await fetch(endpoint+'/runs',{method:'POST',headers,body:JSON.stringify({workflowId:'task',rowIndex:0,requestId:'owned-request-1'})})).status,202);assert.equal(starts,1);
  assert.equal((await fetch(endpoint+'/runs/'+run.id,{headers})).status,200);
  assert.equal((await fetch(endpoint+'/workflows',{headers})).status,200);
  const restored=new LocalAPI(folder,{});assert.equal(restored.config.token,api.config.token);assert.equal(restored.config.enabled,true);
  await api.disable();assert.equal(JSON.parse(fs.readFileSync(api.file,'utf8')).enabled,false);
});
