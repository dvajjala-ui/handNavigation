'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),sharp=require('sharp');
const {Collections}=require('../collections.cjs'),{OpenverseSearch,publicLanding,thumbUrl,API}=require('../openverse.cjs');
const id='145e0b37-0577-416b-8d05-27c0b0bdde46',landing='https://photos.example.org/work/cat',thumb=API+'/v1/images/'+id+'/thumb/';
test('Openverse searches only reusable non-mature candidates through the fixed thumbnail origin and preserves review hints',async()=>{
  const folder=fs.mkdtempSync(path.join(os.tmpdir(),'hand-openverse-'));let collector;
  try{
    const image=await sharp({create:{width:600,height:400,channels:3,background:'#d9ff6a'}}).jpeg().toBuffer(),calls=[];
    collector=new Collections(folder,{dailyLimit:3,catalogFetch:async(value,options={})=>{const url=new URL(value);calls.push(url.href);
      if(url.pathname==='/v1/images/'){assert.equal(url.searchParams.get('q'),'cat reaction');assert.equal(url.searchParams.get('license'),'cc0,pdm');assert.equal(url.searchParams.get('mature'),'false');assert.equal(url.searchParams.get('page_size'),'20');assert.equal(options.redirect,'error');return Response.json({results:[
        {id,title:'Cat reaction',creator:'Open Artist',license:'cc0',license_url:'https://creativecommons.org/publicdomain/zero/1.0/',foreign_landing_url:landing,thumbnail:thumb,width:1200,height:800,mature:false},
        {id:'245e0b37-0577-416b-8d05-27c0b0bdde46',title:'Private host',creator:'Unsafe',license:'cc0',license_url:'https://creativecommons.org/publicdomain/zero/1.0/',foreign_landing_url:'https://127.0.0.1/private',thumbnail:API+'/v1/images/245e0b37-0577-416b-8d05-27c0b0bdde46/thumb/',width:800,height:800,mature:false},
        {id:'345e0b37-0577-416b-8d05-27c0b0bdde46',title:'Wrong rights',license:'by',license_url:'https://creativecommons.org/licenses/by/4.0/',foreign_landing_url:'https://example.org/by',thumbnail:API+'/v1/images/345e0b37-0577-416b-8d05-27c0b0bdde46/thumb/',width:800,height:800,mature:false}
      ]});}
      assert.equal(url.href,thumb);assert.equal(options.headers.Accept,'*/*');return new Response(image,{headers:{'Content-Type':'image/jpeg'}});
    }});
    const run=async requestId=>{const {job}=collector.create({requestId,topics:['cat reaction'],sources:['openverse'],limit:1,destination:'local'});await collector.pumpTask;return collector.get(job.id);};
    const first=await run('openverse-first-cat');assert.equal(first.status,'VERIFIED_LOCAL',JSON.stringify(first));assert.equal(first.items[0].postUrl,landing);assert.equal(first.items[0].imageUrl,thumb);assert.equal(first.items[0].title,'Cat reaction');assert.equal(first.items[0].license,'CC0');assert.deepEqual(first.items[0].tags,['openverse','reported-license:CC0','creator:Open Artist']);
    const second=await run('openverse-dedup-cat');assert.equal(second.items.length,0);assert.equal(calls.filter(u=>u===thumb).length,1);
  }finally{await collector?.close();if(path.resolve(folder).startsWith(path.resolve(os.tmpdir())+path.sep))fs.rmSync(folder,{recursive:true,force:true});}
});
test('Openverse rejects unsafe navigation and provenance hosts',async()=>{
  assert.equal(publicLanding('https://images.example.org/work/1'),'https://images.example.org/work/1');assert.equal(publicLanding('https://127.0.0.1/private'),null);assert.equal(publicLanding('https://open.example.org@127.0.0.1/private'),null);
  assert.equal(thumbUrl(thumb,id),thumb);assert.equal(thumbUrl('https://evil.example/'+id,id),null);
  const adapter=new OpenverseSearch(async()=>Response.json({results:[]}));adapter.beginRun({count:1});
  await assert.rejects(adapter.load('https://evil.example/v1/images/?q=cat'),/Unreviewed/);await assert.rejects(adapter.load(API+'/v1/images/?q='),/topic/);await adapter.load(API+'/v1/images/?q=cat');assert.deepEqual(adapter.items,[]);
  let calls=0;adapter.transport=async()=>{calls++;return new Response('limited',{status:429});};await assert.rejects(adapter.load(API+'/v1/images/?q=cat'),/429/);assert.equal(calls,3);await adapter.close();
});
