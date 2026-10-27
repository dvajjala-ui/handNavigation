'use strict';
const fs=require('node:fs'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const {chromium}=require('playwright');
async function main(){
  const base='https://stickerdock.vercel.app';
  const admin=async p=>{const r=await fetch(base+'/api/admin',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p),signal:AbortSignal.timeout(90000)});const x=await r.json();if(!r.ok)throw new Error(x.error);return x;};
  const before=await admin({action:'collection_dashboard'});assert.ok(before.items.length,'No production images to inspect yet');
  const target=before.items.find(i=>i.rights_status==='UNREVIEWED'&&!i.generation_eligible);assert.ok(target,'No unreviewed candidate available for the isolated UI check');
  const browser=await chromium.launch({headless:true,...(process.platform==='win32'?{channel:'chrome'}:{})}),planName='QA collection workspace '+Date.now();
  let temporaryPlan=null,editedCandidate=false,archivedByTest=false,result;
  try{
    const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto(base+'/admin?verify='+Date.now());await page.getByRole('button',{name:'Collect images',exact:false}).click();
    await page.locator('.collect-image').first().waitFor();
    await page.locator('#collection-form input[name=name]').fill(planName);await page.locator('#collection-form textarea').fill('Distracted\nCat');await page.locator('#collection-form input[name=image_limit]').fill('2');await page.locator('#collection-form input[name=daily]').uncheck();await page.locator('#collection-form input[name=use_planner]').check();await page.locator('#collection-form input[name=sources][value=imgflip]').check();
    await page.getByRole('button',{name:'Save plan',exact:true}).click();await page.getByText('Topic plan saved.',{exact:true}).waitFor();
    temporaryPlan=(await admin({action:'collection_dashboard'})).plans.find(p=>p.name===planName);assert.ok(temporaryPlan);assert.equal(temporaryPlan.use_planner,true);assert.equal(temporaryPlan.daily,false);assert.ok(temporaryPlan.sources.includes('imgflip'));
    await page.locator(`[data-action="collect-plan-edit"][data-id="${temporaryPlan.id}"]`).click();await page.locator('#collection-form textarea').fill('Unsaved topic that must survive refresh');await page.getByRole('button',{name:'Refresh',exact:true}).click();assert.equal(await page.locator('#collection-form textarea').inputValue(),'Unsaved topic that must survive refresh');
    const card=page.locator('.collect-image').filter({has:page.locator(`[data-action="collect-edit"][data-id="${target.id}"]`)});
    await card.getByRole('button',{name:'Edit',exact:true}).click();await page.locator('#collection-edit-form input[name=title]').fill('QA verified candidate');await page.getByRole('button',{name:'Save image details'}).click();await page.getByText('Image details saved.',{exact:true}).waitFor();editedCandidate=true;
    const download=page.waitForEvent('download');await page.locator(`[data-action="collect-download"][data-id="${target.id}"]`).click();const downloaded=await download;
    fs.mkdirSync('runtime/ui-evidence',{recursive:true});const file='runtime/ui-evidence/verified-candidate.webp';await downloaded.saveAs(file);assert.equal(crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex'),target.stored_sha256);
    await page.locator(`[data-action="collect-archive"][data-id="${target.id}"]`).click();await page.locator(`[data-action="collect-edit"][data-id="${target.id}"]`).waitFor({state:'detached'});archivedByTest=true;
    await page.locator('#collection-filter input[name=archived]').check();await page.getByRole('button',{name:'Filter',exact:true}).click();await page.locator(`[data-action="collect-archive"][data-id="${target.id}"]`).click();await page.locator(`[data-action="collect-edit"][data-id="${target.id}"]`).waitFor({state:'detached'});archivedByTest=false;
    await page.locator('#collection-filter input[name=archived]').uncheck();await page.getByRole('button',{name:'Filter',exact:true}).click();await page.locator(`[data-action="collect-edit"][data-id="${target.id}"]`).waitFor();
    await page.locator('.collect-preview').first().scrollIntoViewIfNeeded();await page.waitForFunction(()=>document.querySelector('.collect-image img')?.naturalWidth>0,null,{timeout:30000});
    await page.screenshot({path:'runtime/ui-evidence/production-desktop.png',fullPage:true,animations:'disabled'});await page.setViewportSize({width:390,height:844});await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:'runtime/ui-evidence/production-mobile.png',animations:'disabled'});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);assert.deepEqual(errors,[]);
    const after=await admin({action:'collection_dashboard'}),saved=after.items.find(i=>i.id===target.id);assert.equal(saved.archived,false);assert.equal(saved.rights_status,'UNREVIEWED');
    result={checkedAt:new Date().toISOString(),scope:'Live hosted Admin and Supabase, real HandNavigate-downloaded candidate; test plan archived and original candidate title restored',passed:true,checks:['temporary plan with planner mode and Imgflip source','unsaved plan edits survive refresh','candidate title edit','downloaded original SHA256 equals database digest','archive','restore','decoded thumbnail gallery','desktop/mobile layout'],candidate:target.id,plan:temporaryPlan.id,pageErrors:errors};
  }finally{
    try{
      if(editedCandidate||archivedByTest){let current=(await admin({action:'intake_thumbnail',id:target.id})).item;if(archivedByTest&&current.archived)current=(await admin({action:'intake_archive',id:current.id,version:current.version,archived:false})).item;if(editedCandidate&&current.title==='QA verified candidate')await admin({action:'intake_update',id:current.id,version:current.version,title:target.title,topic:current.topic,tags:current.tags,rights_status:current.rights_status});}
      if(temporaryPlan){const current=(await admin({action:'collection_dashboard'})).plans.find(p=>p.id===temporaryPlan.id);if(current&&!current.archived)await admin({action:'collection_plan_archive',id:current.id,version:current.version,archived:true});}
    }finally{await browser.close();}
  }
  fs.writeFileSync('service/evidence/admin-live-20261028.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
}
main().catch(e=>{console.error(e.message);process.exitCode=1;});
