'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),sharp=require('sharp');
const {Collections}=require('../collections.cjs'),{FlickrFeed,postUrl,imageUrl}=require('../flickr.cjs');
const post=n=>'https://www.flickr.com/photos/owned/'+n+'/',photo=n=>'https://live.staticflickr.com/65535/'+n+'_abc123_b.jpg';
test('Flickr public feed uses advertised photo URLs, decoded Runner downloads and persistent deduplication',async()=>{
  const folder=fs.mkdtempSync(path.join(os.tmpdir(),'hand-flickr-'));let collector;
  try{
    const image=await sharp({create:{width:300,height:240,channels:3,background:'#43a9bc'}}).jpeg().toBuffer(),calls=[];
    collector=new Collections(folder,{dailyLimit:4,catalogFetch:async value=>{const url=new URL(value);calls.push(url.href);
      if(url.pathname==='/services/feeds/photos_public.gne'){assert.equal(url.searchParams.get('tags'),'cat,dog');assert.equal(url.searchParams.get('tagmode'),'all');return Response.json({items:[{link:post(11)},{link:post(11)},{link:'https://foreign.invalid/11'},{link:post(12)},{link:post(13)}]});}
      if(url.pathname==='/services/oembed/'){const source=url.searchParams.get('url');return Response.json({type:'photo',url:source===post(11)?photo(11):source===post(12)?'https://unreviewed.invalid/12.jpg':photo(999),width:300,height:240});}
      assert.equal(url.href,photo(11));return new Response(image);
    }});
    const run=async requestId=>{const {job}=collector.create({requestId,topics:['cat,dog'],sources:['flickr'],limit:1,destination:'local'});await collector.pumpTask;return collector.get(job.id);};
    const first=await run('flickr-first-owned');assert.equal(first.status,'VERIFIED_LOCAL',JSON.stringify(first));assert.equal(first.items[0].platform,'flickr');assert.equal(first.items[0].imageUrl,photo(11));assert.equal(first.items[0].postUrl,post(11));
    const second=await run('flickr-second-owned');assert.equal(second.items.length,0);assert.equal(calls.filter(u=>u===photo(11)).length,1);assert.equal(calls.filter(u=>u.includes('url='+encodeURIComponent(post(11)))).length,1);assert.equal(calls.some(u=>u.includes('unreviewed.invalid')),false);
  }finally{await collector?.close();if(path.resolve(folder).startsWith(path.resolve(os.tmpdir())+path.sep))fs.rmSync(folder,{recursive:true,force:true});}
});
test('Flickr rejects unreviewed URLs, malformed feeds, rate limits and unsafe photo representations',async()=>{
  assert.equal(postUrl('https://www.flickr.com/photos/user/123/'),'https://www.flickr.com/photos/user/123/');assert.equal(postUrl('https://www.flickr.com.evil.test/photos/user/123/'),null);assert.equal(imageUrl('https://live.staticflickr.com@evil.test/65535/12_abc.jpg'),null);
  const adapter=new FlickrFeed(async()=>Response.json({items:[]}));adapter.beginRun({count:2});await assert.rejects(adapter.load('https://evil.test/?tags=cat'),/Unreviewed/);await assert.rejects(adapter.load('https://www.flickr.com/services/feeds/photos_public.gne?tags='),/tags/);await adapter.load('https://www.flickr.com/services/feeds/photos_public.gne?tags=cat');assert.deepEqual(adapter.items,[]);
  adapter.transport=async()=>Response.json({items:'changed'});await assert.rejects(adapter.load('https://www.flickr.com/services/feeds/photos_public.gne?tags=cat'),/unexpected/);
  let calls=0;adapter.transport=async()=>{calls++;return new Response('rate limited',{status:429});};await assert.rejects(adapter.load('https://www.flickr.com/services/feeds/photos_public.gne?tags=cat'),/429/);assert.equal(calls,1);await adapter.close();
});
