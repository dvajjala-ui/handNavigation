'use strict';
// Product UI smoke with an owned, disposable API. Live Supabase is checked separately.
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict'),crypto=require('node:crypto'),sharp=require('sharp');
const {chromium}=require('playwright');
async function main(){
  const repo=path.resolve(process.argv[2]||'../sticker'),raw=await sharp({create:{width:300,height:240,channels:3,background:'#afcd84'}}).webp().toBuffer(),image='data:image/webp;base64,'+raw.toString('base64'),thumbnail='data:image/webp;base64,'+(await sharp(raw).resize(50).webp().toBuffer()).toString('base64');
  const candidate={id:crypto.randomUUID(),title:'',topic:'cat reactions',platform:'reddit',version:1,rights_status:'UNREVIEWED',tags:[],source_url:'https://www.reddit.com/r/cats/',archived:false};
  const plans=[],jobs=[],calls=[];
  const server=http.createServer(async(req,res)=>{
    if(req.method==='GET'){
      const file=path.join(repo,req.url==='/admin'?'admin/index.html':req.url.slice(1));
      if(!file.startsWith(path.join(repo,'admin')+path.sep)&&file!==path.join(repo,'admin/index.html')){res.writeHead(404);res.end();return;}
      res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':'text/html');res.end(fs.readFileSync(file));return;
    }
    const parts=[];for await(const part of req)parts.push(part);const p=JSON.parse(Buffer.concat(parts));calls.push(p);let result={};
    if(p.action==='health')result={admin_ready:true};
    if(p.action==='overview')result={packs:[],factory_packs:[],runs:[],requests:[],events:[],briefs:[{topic_plans:[{topic:'cat reactions'}]}],settings:{},catalog:{packs:[]}};
    if(p.action==='collection_dashboard')result={items:candidate.archived===!!p.archived?[candidate]:[],plans,jobs,next_offset:null,source_options:[{id:'pinterest',name:'Pinterest'},{id:'reddit',name:'Reddit'},{id:'imgflip',name:'Imgflip meme templates'}],capabilities:{candidate_thumbnail:true}};
    if(p.action==='collection_plan_save'){const plan={...p,action:undefined,id:p.id||crypto.randomUUID(),version:1};plans.splice(0,plans.length,plan);result={plan};}
    if(p.action==='collection_create'){const job={...p,id:crypto.randomUUID(),status:'QUEUED',delivered:0,saved:0,created_at:new Date().toISOString()};jobs.unshift(job);result={job};}
    if(p.action==='intake_preview')result={image,item:candidate};
    if(p.action==='intake_thumbnail')result={image:thumbnail,item:candidate};
    if(p.action==='intake_update')Object.assign(candidate,p,{version:2});
    if(p.action==='intake_archive')candidate.archived=p.archived;
    res.setHeader('Content-Type','application/json');res.end(JSON.stringify(result));
  });await new Promise(r=>server.listen(0,'127.0.0.1',r));
  let browser;
  try{
    browser=await chromium.launch({headless:true,...(process.platform==='win32'?{channel:'chrome'}:{})});
    const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto('http://127.0.0.1:'+server.address().port+'/admin');await page.getByRole('button',{name:'Collect images',exact:false}).click();
    await page.locator('#collection-form textarea').fill('funny cat reaction');await page.locator('#collection-form input[name=name]').fill('Daily cats');
    await page.locator('#collection-form input[name=use_planner]').check();await page.locator('#collection-form input[name=sources][value=imgflip]').check();
    await page.getByRole('button',{name:'Save plan',exact:true}).click();await page.locator('.collect-plan').waitFor();
    assert.equal(plans[0].use_planner,true);assert.ok(plans[0].sources.includes('imgflip'));
    await page.locator('.collect-plan').getByRole('button',{name:'Edit',exact:true}).click();await page.locator('#collection-form textarea').fill('An unsaved topic edit');await page.getByRole('button',{name:'Refresh',exact:true}).click();assert.equal(await page.locator('#collection-form textarea').inputValue(),'An unsaved topic edit');
    await page.locator('.collect-plan').getByRole('button',{name:'Run',exact:true}).click();await page.getByText('queued',{exact:true}).waitFor();
    await page.locator('.collect-preview').first().scrollIntoViewIfNeeded();try{await page.waitForFunction(()=>document.querySelector('.collect-image img')?.naturalWidth>0,null,{timeout:15000});}catch(error){console.error(JSON.stringify({errors,calls:calls.map(c=>c.action),state:await page.locator('.collect-preview').first().evaluate(e=>({html:e.outerHTML,rect:e.getBoundingClientRect().toJSON(),height:innerHeight}))}));throw error;}
    await page.locator('.collect-image').getByRole('button',{name:'Edit',exact:true}).click();await page.locator('#collection-edit-form input[name=title]').fill('Happy cat');
    await page.getByRole('button',{name:'Save image details'}).click();await page.locator('.collect-image strong').getByText('Happy cat',{exact:true}).waitFor();
    const download=page.waitForEvent('download');await page.locator('.collect-image').getByRole('button',{name:'Download',exact:true}).click();const file=await download;assert.ok(file.suggestedFilename().endsWith('.webp'));assert.equal(crypto.createHash('sha256').update(fs.readFileSync(await file.path())).digest('hex'),crypto.createHash('sha256').update(raw).digest('hex'));
    fs.mkdirSync('runtime/ui-evidence',{recursive:true});await page.screenshot({path:'runtime/ui-evidence/collect-desktop.png',fullPage:true});
    await page.locator('.collect-image').getByRole('button',{name:'Archive',exact:true}).click();await page.getByText('No images on this page',{exact:true}).waitFor();
    await page.locator('#collection-filter input[name=archived]').check();await page.getByRole('button',{name:'Filter',exact:true}).click();await page.locator('.collect-image').getByRole('button',{name:'Restore',exact:true}).click();
    await page.setViewportSize({width:390,height:844});await page.screenshot({path:'runtime/ui-evidence/collect-mobile.png',fullPage:true});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'mobile layout overflow');assert.deepEqual(errors,[]);
    for(const action of ['collection_plan_save','collection_create','intake_update','intake_archive','intake_thumbnail'])assert.ok(calls.some(c=>c.action===action),action);
    console.log(JSON.stringify({scope:'Owned Admin UI fixture, not live database',checks:['save plan','run plan','edit candidate','download image','archive','filter','restore','mobile layout'],passed:true,pageErrors:errors}));
  }finally{await browser?.close();await new Promise(r=>server.close(r));}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
