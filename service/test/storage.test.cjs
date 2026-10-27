'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),http=require('node:http'),sharp=require('sharp');
const {StickerDock}=require('../stickerdock.cjs'),{imageInfo}=require('../../desktop/engine.cjs');
test('storage handoff verifies actual decoded read-back, metadata and candidate admission status',async t=>{
  const folder=fs.mkdtempSync(path.join(os.tmpdir(),'handnavigate-sink-')),file=path.join(folder,'photo.png');
  const bytes=await sharp({create:{width:300,height:240,channels:3,background:'#8345cb'}}).png().toBuffer();fs.writeFileSync(file,bytes);let writes=0,corrupt=false,eligible=false,missing=false;const token='fixture-intake-token-'.repeat(3);
  const row={id:'12345678-1234-1234-1234-123456789012',storage_path:'handnavigate/candidates/'+'a'.repeat(64)+'.webp'};let image;
  const server=http.createServer(async(req,res)=>{
    assert.equal(req.headers.authorization,'Bearer '+token);const chunks=[];for await(const part of req)chunks.push(part);const p=JSON.parse(Buffer.concat(chunks));
    if(p.action==='store'){writes++;image=Buffer.from(p.image.split(',')[1],'base64');row.stored_sha256=(await imageInfo(image)).sha256;Object.assign(row,{original_sha256:p.original_sha256,platform:p.platform,source_url:p.source_url,topic:p.topic,rights_status:'UNREVIEWED',generation_eligible:false});}
    const result=p.action==='store'?{item:row,reused:writes>1}:{item:{...row,generation_eligible:eligible,source_url:missing?'https://lost.example/':row.source_url},image:'data:image/webp;base64,'+(corrupt?Buffer.from('bad'):image).toString('base64')};res.writeHead(200,{'Content-Type':'application/json'});res.end(JSON.stringify(result));
  });await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  t.after(async()=>{await new Promise(resolve=>server.close(resolve));fs.rmSync(folder,{recursive:true,force:true});});
  const sink=new StickerDock('http://127.0.0.1:'+server.address().port,token),item={...(await imageInfo(bytes)),file,platform:'reddit',topic:'happy dogs',postUrl:'https://www.reddit.com/r/aww/comments/example/example/',imageUrl:'https://i.redd.it/example.png',collectionId:'12345678-1234-1234-1234-123456789012'};
  const stored=await sink.store(item);assert.equal(stored.sha256,row.stored_sha256);assert.equal(stored.generationEligible,false);assert.equal(row.source_url,'https://www.reddit.com/comments/example/');
  eligible=true;await assert.rejects(sink.store(item),/metadata/);eligible=false;
  missing=true;await assert.rejects(sink.store(item),/metadata/);missing=false;
  corrupt=true;await assert.rejects(sink.store(item),/valid bounded/);
});
