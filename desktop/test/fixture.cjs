const http=require('node:http'),crypto=require('node:crypto');
const sharp=require('sharp');
async function fixture(){
  const images=[];for(let i=0;i<50;i++)images.push(await sharp({create:{width:200+i,height:180+i,channels:3,background:{r:i*4,g:120,b:75}}}).toFormat(['png','jpeg','webp'][i%3]).toBuffer());
  const uploaded=[];let writes=0;const controls={fakeUpload:false,corrupt:false,limit:2};
  const html=body=>`<!doctype html><html><head><title>HandNavigate owned acceptance site</title><style>body{font:16px system-ui;padding:25px;color:#244333}input,button,select{font:inherit;padding:10px;margin:8px}#gallery{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}img{width:100%;max-width:200px}h1{font-weight:500}</style></head><body>${body}</body></html>`;
  const server=http.createServer(async(req,res)=>{
    const u=new URL(req.url,'http://localhost');const send=(data,type='text/html',code=200)=>{res.writeHead(code,{'Content-Type':type,'Content-Length':Buffer.byteLength(data)});res.end(data);};
    if(u.pathname==='/login'){res.setHeader('Set-Cookie','owned=synthetic; Path=/; Max-Age=3600; HttpOnly; SameSite=Lax');send(html('<h1>Signed in to the owned test site</h1><a href="/images">Images</a>'));}
    else if(u.pathname==='/form')send(html(`<h1>Teach a search</h1><form action="/images"><label>Topic <input name="topic" id="topic" placeholder="A topic"></label><label>Layout <select id="layout" name="layout"><option value="brief">Brief</option><option value="full">Full</option></select></label><label>Captions <input type="checkbox" id="captions" name="captions"></label><button>Find images</button></form><label>Password <input id="password" type="password"></label>`));
    else if(u.pathname==='/result')send(html('<h1>Repeat a taught task</h1><label>Topic <input id="topic"></label><button id="prepare">Prepare preview</button><p id="result"></p><script>document.querySelector("#prepare").onclick=()=>{document.querySelector("#result").textContent="Ready: "+document.querySelector("#topic").value}</script>'));
    else if(u.pathname==='/images') {
      const topic=u.searchParams.get('topic')||'landscape';let count=Number(u.searchParams.get('count')||25),offset=topic==='architecture'?25:0;
      let cards=Array.from({length:Math.min(count,25)},(_,i)=>`<a href="/image/${offset+i}"><img class="original" src="${u.searchParams.get('external')||'/image/'+(offset+i)}" alt="${topic} ${i+1}"></a>`).join('');
      if(u.searchParams.get('duplicate'))cards+=cards;
      send(html(`<h1>Results: ${topic}</h1><div id="gallery">${cards}</div>`));
    }
    else if(u.pathname==='/pages'){
      const page=Math.max(1,Number(u.searchParams.get('page')||1)),per=5,total=50,start=(page-1)*per;
      const cards=Array.from({length:Math.max(0,Math.min(per,total-start))},(_,i)=>`<img class="original" src="/image/${start+i}">`).join('');
      send(html(`<h1>Page ${page}</h1><div id="gallery">${cards}</div>${start+per<total?`<a id="next" rel="next" href="/pages?page=${page+1}">Next page</a>`:'<button disabled id="next">Next page</button>'}`));
    }
    else if(u.pathname==='/limited')send(html(`<h1>Recover incomplete source</h1><div id="gallery">${Array.from({length:controls.limit},(_,i)=>`<img src="/image/${25+i}">`).join('')}</div>`));
    else if(u.pathname.startsWith('/image/')){const n=Number(u.pathname.split('/').pop());send(controls.corrupt?Buffer.from('<html>not an image</html>'):images[n]||Buffer.from('not found'),'application/octet-stream');}
    else if(u.pathname==='/empty')send(html('<h1>No available images</h1>'));
    else if(u.pathname==='/ambiguous')send(html('<h1>Ambiguous controls</h1><label>Topic <input id="topic"></label><button>Prepare preview</button><button>Prepare preview</button><p>Ready</p>'));
    else if(u.pathname==='/private'){
      if(!String(req.headers.cookie).includes('owned=synthetic'))send(html('<label>Password<input type="password"></label>'));
      else send(html('<h1>Private gallery</h1><div id="gallery"><img src="/image/0"><img src="/image/1"></div>'));
    }
    else if(u.pathname==='/target'){
      const page=Number(u.searchParams.get('page')||1),per=Number(u.searchParams.get('per')||500),start=(page-1)*per;
      const gallery=uploaded.slice(start,start+per).map((_,i)=>`<img src="/uploaded/${start+i}">`).join('');
      const next=start+per<uploaded.length?`<a id="next" rel="next" href="/target?per=${per}&page=${page+1}">Next page</a>`:'';
      send(html(`<h1>Image destination</h1><label>Upload image <input id="upload" type="file" accept="image/*"></label><button id="send">Upload image</button><p id="status"></p><div id="gallery">${u.searchParams.has('delay')?'':gallery}</div>${next}<script>${u.searchParams.has('delay')?`fetch('/gallery-html').then(r=>r.text()).then(s=>document.querySelector('#gallery').innerHTML=s);`:''}document.querySelector('#send').onclick=async()=>{const file=document.querySelector('#upload').files[0];if(!file)return;await fetch('/upload',{method:'POST',body:file});document.querySelector('#status').textContent='Upload received'}</script>`));
    }
    else if(u.pathname==='/gallery-html')setTimeout(()=>send(uploaded.map((_,i)=>`<img src="/uploaded/${i}">`).join('')),900);
    else if(u.pathname==='/upload'&&req.method==='POST'){const chunks=[];for await(const c of req)chunks.push(c);if(!controls.fakeUpload)uploaded.push(Buffer.concat(chunks));writes++;send('ok','text/plain');}
    else if(u.pathname.startsWith('/uploaded/'))send(uploaded[Number(u.pathname.split('/').pop())]||Buffer.from('missing'),'application/octet-stream');
    else send(html('<h1>Not found</h1>'),'text/html',404);
  });
  await new Promise(r=>server.listen(0,'127.0.0.1',r));const origin='http://127.0.0.1:'+server.address().port;
  return {origin,images,uploaded,controls,get writes(){return writes;},close:()=>new Promise(r=>server.close(r))};
}
module.exports={fixture};
