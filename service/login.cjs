'use strict';
const path=require('node:path'),readline=require('node:readline');
const {ServiceBrowser}=require('./browser.cjs'),{BUILTINS}=require('./sources.cjs');
const {lock}=require('./lock.cjs');
async function main(){
  const source=BUILTINS.find(s=>s.id===process.argv[2]);if(!source)throw new Error('Choose pinterest or reddit.');
  if(source.provider)throw new Error(source.name+' does not need a browser login. Start a collection directly.');
  const folder=path.resolve(process.env.HANDNAVIGATE_DATA||path.join(__dirname,'..','runtime','service'));
  const release=lock(folder);process.once('exit',release);
  const browser=await ServiceBrowser.open(path.join(folder,'profiles',source.id),{headless:false,channel:process.env.HANDNAVIGATE_BROWSER_CHANNEL||undefined});
  try{
    await browser.page.goto(new URL(source.searchUrl).origin,{waitUntil:'domcontentloaded'});
    console.log('Complete sign-in or any human verification in the HandNavigate browser. Press Enter here when finished. Do not send credentials in chat.');
    await new Promise(resolve=>{const rl=readline.createInterface({input:process.stdin,output:process.stdout});rl.question('',()=>{rl.close();resolve();});});
    if(await browser.gated())throw new Error('The source still needs sign-in or verification.');console.log('Browser session saved for '+source.id+'.');
  }finally{await browser.close();release();}
}
main().catch(error=>{console.error(error.message);process.exitCode=1;});
