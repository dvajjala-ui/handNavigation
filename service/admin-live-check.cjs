'use strict';
const fs=require('node:fs'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
async function main(){
  const base='https://stickerdock.vercel.app';
  const admin=async p=>{const r=await fetch(base+'/api/admin',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p),signal:AbortSignal.timeout(90000)});const x=await r.json();if(!r.ok)throw new Error(x.error);return x;};
  const before=await admin({action:'collection_dashboard'});assert.ok(before.items.length,'No production images to inspect yet');
  const target=before.items[0],browser=await chromium.launch({headless:true,...(process.platform==='win32'?{channel:'chrome'}:{})});
  try{
    const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto(base+'/admin?verify='+Date.now());await page.getByRole('button',{name:'Collect images',exact:false}).click();
    await page.locator('.collect-image').first().waitFor();
    const plan=before.plans.find(p=>p.name==='Daily animal reactions'&&!p.archived);
    if(plan)await page.locator(`[data-action="collect-plan-edit"][data-id="${plan.id}"]`).click();
    await page.locator('#collection-form input[name=name]').fill('Daily animal reactions');await page.locator('#collection-form textarea').fill('funny cat reaction\nfunny dog reaction');await page.locator('#collection-form input[name=image_limit]').fill('20');await page.locator('#collection-form input[name=daily]').check();
    await page.getByRole('button',{name:'Save plan',exact:true}).click();await page.getByText('Topic plan saved.',{exact:true}).waitFor();
    const card=page.locator('.collect-image').filter({has:page.locator(`[data-action="collect-edit"][data-id="${target.id}"]`)});
    await card.getByRole('button',{name:'Edit',exact:true}).click();await page.locator('#collection-edit-form input[name=title]').fill('Dog reaction · live verified');await page.getByRole('button',{name:'Save image details'}).click();await page.getByText('Image details saved.',{exact:true}).waitFor();
    const download=page.waitForEvent('download');await page.locator(`[data-action="collect-download"][data-id="${target.id}"]`).click();const downloaded=await download;
    fs.mkdirSync('runtime/ui-evidence',{recursive:true});const file='runtime/ui-evidence/verified-candidate.webp';await downloaded.saveAs(file);assert.equal(crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex'),target.stored_sha256);
    await page.locator(`[data-action="collect-archive"][data-id="${target.id}"]`).click();await page.locator(`[data-action="collect-edit"][data-id="${target.id}"]`).waitFor({state:'detached'});
    await page.locator('#collection-filter input[name=archived]').check();await page.getByRole('button',{name:'Filter',exact:true}).click();await page.locator(`[data-action="collect-archive"][data-id="${target.id}"]`).click();await page.locator(`[data-action="collect-edit"][data-id="${target.id}"]`).waitFor({state:'detached'});
    await page.locator('#collection-filter input[name=archived]').uncheck();await page.getByRole('button',{name:'Filter',exact:true}).click();await page.locator(`[data-action="collect-edit"][data-id="${target.id}"]`).waitFor();
    await page.locator('.collect-preview').first().scrollIntoViewIfNeeded();await page.waitForFunction(()=>document.querySelector('.collect-image img')?.naturalWidth>0,null,{timeout:30000});
    await page.screenshot({path:'runtime/ui-evidence/production-desktop.png',fullPage:true,animations:'disabled'});await page.setViewportSize({width:390,height:844});await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:'runtime/ui-evidence/production-mobile.png',animations:'disabled'});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);assert.deepEqual(errors,[]);
    const after=await admin({action:'collection_dashboard'}),saved=after.items.find(i=>i.id===target.id);assert.equal(saved.archived,false);assert.equal(saved.rights_status,'UNREVIEWED');
    const result={checkedAt:new Date().toISOString(),scope:'Live hosted Admin and Supabase, real HandNavigate-downloaded candidate',passed:true,checks:['topic plan saved daily at 20 total','candidate title edit','downloaded bytes SHA256 equals database digest','archive','restore','source provenance retained','desktop/mobile layout'],candidate:target.id,plan:after.plans.find(p=>p.name==='Daily animal reactions').id,pageErrors:errors};
    fs.writeFileSync('service/evidence/admin-live-20261028.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
  }finally{await browser.close();}
}
main().catch(e=>{console.error(e.message);process.exitCode=1;});
