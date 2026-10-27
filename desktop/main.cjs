'use strict';
const {app,BrowserWindow,WebContentsView,ipcMain,session,dialog,shell,Menu,clipboard}=require('electron');
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const {pathToFileURL}=require('node:url');
const {Store,TaskError,clone,webUrl,taskHash,draft,DailyQueue,PRIVATE,siteUrl}=require('./core.cjs');
const {Runner}=require('./engine.cjs');
const {script}=require('./dom.cjs');
const {LocalAPI,validRequestId}=require('./integration.cjs');
const {sameLocalDocument}=require('./trust.cjs');
const {CollectionManager}=require('./collection-manager.cjs');

if(process.env.HANDNAVIGATE_USER_DATA)app.setPath('userData',path.resolve(process.env.HANDNAVIGATE_USER_DATA));
app.setName('HandNavigate');
const ownUI=pathToFileURL(path.join(__dirname,'index.html')).href;
let win,browser,store,runner,queue,timer,localAPI,collectionManager,selectedId=null,recording=null,picking=null,lastError=null,browserHidden=false,exitAllowed=false;
let flushedExit=false;
const popups=new Set();
function apiClientPath(){return app.isPackaged?path.join(process.resourcesPath,'Invoke-HandNavigate.ps1'):path.join(__dirname,'..','Invoke-HandNavigate.ps1');}
function snapshot(){return {...store.snapshot(),selectedId,recording:recording?{taskId:recording.taskId,events:recording.events.length}:null,
  picking:picking?.purpose||null,busy:runner.active?{taskId:runner.active.task.id,runId:runner.active.run.id}:null,
  browser:{url:browser.wc.getURL().startsWith('data:')?'about:blank':browser.wc.getURL(),title:browser.wc.getTitle(),loading:browser.wc.isLoading(),hidden:browserHidden},
  downloads:app.getPath('downloads'),integration:{...(localAPI?.snapshot()||{enabled:false,port:47831}),clientAvailable:fs.existsSync(apiClientPath())},appVersion:app.getVersion(),error:lastError};}
function notify(){if(win&&!win.isDestroyed()&&store&&runner&&browser)win.webContents.send('app:state',snapshot());}
function fail(error){lastError=error.message||String(error);notify();}
function idle(){if(runner.active)throw new TaskError('Wait for the active run or stop it first.');}
function current(){if(!selectedId)throw new TaskError('Choose a workflow first.');return store.get(selectedId);}
function sourceSender(event){return win&&!win.isDestroyed()&&event.sender.id===win.webContents.id&&event.senderFrame===win.webContents.mainFrame&&sameLocalDocument(event.senderFrame?.url,ownUI);}
async function action(event,fn,arg){if(!sourceSender(event))throw new Error('Only the local HandNavigate interface may perform this action.');lastError=null;try{const value=await fn(arg||{});notify();return {ok:true,value};}catch(e){fail(e);return {ok:false,error:e.message};}}
function startSavedRun(id,rowIndex=0,requestId=null,trigger='manual'){
  const task=store.get(id);
  if(requestId){
    if(!validRequestId(requestId))throw new TaskError('Enter a valid request ID.');
    const previous=store.data.runs.find(r=>r.requestId===requestId);
    if(previous){if(previous.taskId!==id||previous.rowIndex!==rowIndex||previous.sha!==task.sha)throw new TaskError('That request ID belongs to a different workflow, value row, or revision.');return {run:previous,reused:true};}
  }
  idle();if(recording||picking||popups.size)throw new TaskError('Finish teaching, choosing images, or signing in before starting a run.');
  const started=runner.start(id,rowIndex,trigger,requestId);started.completion.catch(fail);return {run:started.run,reused:false};
}

class Browser {
  constructor() {
    this.session=session.fromPartition('persist:handnavigate-browser');this.observed=new Set();this.pending=new Set();this.mutations=new Set();this.lastNetworkAt=Date.now();this.runTask=null;this.effectError=null;
    this.session.setPermissionRequestHandler((_wc,_permission,callback)=>callback(false));
    this.session.setPermissionCheckHandler(()=>false);
    this.view=new WebContentsView({webPreferences:{session:this.session,preload:path.join(__dirname,'preload-browser.cjs'),nodeIntegration:false,contextIsolation:true,sandbox:true,webSecurity:true,backgroundThrottling:false}});
    this.wc=this.view.webContents;
    this.session.webRequest.onBeforeRequest((details,callback)=>{
      let u;try{u=new URL(details.url);}catch{return callback({cancel:true});}
      if(['http:','https:'].includes(u.protocol)&&details.webContentsId===this.wc.id)this.observed.add(u.origin);
      if(this.runTask&&['http:','https:','ws:','wss:'].includes(u.protocol)){
        const allowed=[...this.runTask.allowedOrigins,...this.runTask.imageOrigins];
        if(['ws:','wss:'].includes(u.protocol)||!allowed.includes(u.origin))return callback({cancel:true});
      }
      if(!['http:','https:','data:','blob:','about:','devtools:'].includes(u.protocol))return callback({cancel:true});
      if(details.webContentsId===this.wc.id&&['http:','https:'].includes(u.protocol)){this.pending.add(details.id);this.lastNetworkAt=Date.now();}
      if(this.runTask&&details.webContentsId===this.wc.id&&['http:','https:'].includes(u.protocol)&&!['GET','HEAD','OPTIONS'].includes(details.method))this.mutations.add(details.id);
      callback({cancel:false});
    });
    const finished=details=>{this.mutations.delete(details.id);if(this.pending.delete(details.id))this.lastNetworkAt=Date.now();};
    this.session.webRequest.onCompleted(finished);this.session.webRequest.onErrorOccurred(finished);
    this.session.on('will-download',(event,item,wc)=>{
      if(this.runTask){event.preventDefault();this.effectError='The site triggered an unexpected file download. Use the verified image download workflow.';return;}
      // Ordinary manual downloads stay in this app's local Downloads folder.
      const basename=path.basename(item.getFilename()).replace(/[<>:"/\\|?*]/g,'_');
      let file=path.join(app.getPath('downloads'),basename),n=1;
      while(fs.existsSync(file)){file=path.join(app.getPath('downloads'),path.parse(basename).name+'-'+n+path.extname(basename));n++;}
      item.setSavePath(file);
    });
    const nav=(_event,url)=>{
      try{const u=webUrl(url);if(this.runTask&&!this.runTask.allowedOrigins.includes(u.origin)){_event.preventDefault();this.effectError='The task tried to navigate to an unreviewed website.';}}
      catch{_event.preventDefault();}
    };
    this.wc.on('will-navigate',nav);this.wc.on('will-redirect',nav);
    this.wc.setWindowOpenHandler(({url})=>{
      try{webUrl(url);}catch{return {action:'deny'};}
      if(this.runTask||recording){this.effectError='A new tab or sign-in popup requires manual attention. Open it before teaching or running.';return {action:'deny'};}
      // Human sign-in popups share the persistent site session, without any app bridge.
      return {action:'allow',overrideBrowserWindowOptions:{title:'HandNavigate · sign in',width:600,height:760,
        webPreferences:{session:this.session,nodeIntegration:false,contextIsolation:true,sandbox:true,webSecurity:true}}};
    });
    this.wc.on('did-create-window',child=>{popups.add(child);child.setMenu(null);child.on('closed',()=>popups.delete(child));});
    this.wc.on('did-finish-load',async()=>{
      if(recording)try{await this.injectRecorder();}catch(e){fail(e);}
      notify();
    });
    this.wc.on('did-navigate',()=>notify());this.wc.on('did-navigate-in-page',()=>notify());this.wc.on('page-title-updated',()=>notify());
    this.wc.on('did-start-loading',()=>notify());this.wc.on('did-stop-loading',()=>notify());
    this.wc.on('render-process-gone',()=>{this.effectError='The browser process stopped. Restart the workflow after reviewing its outcome.';runner?.stop();fail(new TaskError(this.effectError));});
    this.wc.on('will-attach-webview',event=>event.preventDefault());
  }
  async load(url){webUrl(url);this.effectError=null;this.pending.clear();await this.wc.loadURL(url);}
  async settle(){const until=Date.now()+8000;while(Date.now()<until){if(runner?.active?.abort.signal.aborted)break;if(!this.pending.size&&Date.now()-this.lastNetworkAt>=250)return;await new Promise(resolve=>setTimeout(resolve,100));}}
  async waitForUploads(signal){
    const until=Date.now()+45000;
    while(Date.now()<until){
      if(signal.aborted)throw new TaskError('Run stopped.','CANCELLED');
      if(this.effectError)throw new TaskError(this.effectError,'NEEDS_REVIEW');
      const quiet=Date.now()-this.lastNetworkAt;
      if(!this.mutations.size&&(!this.pending.size&&quiet>=250||quiet>=8000))return;
      await new Promise(resolve=>setTimeout(resolve,100));
    }
    throw new TaskError('The destination upload did not finish within 45 seconds. Check its outcome in History before retrying.','NEEDS_REVIEW');
  }
  beginRun(task){this.runTask=task;this.effectError=null;}
  endRun(){this.runTask=null;this.effectError=null;}
  async injectRecorder(){if(recording)await this.wc.executeJavaScript(script('recorder',{token:recording.token}));}
}
async function stopRecording() {
  if(!recording)return null;const record=recording;
  try{await browser.wc.executeJavaScript('window.__hnRecorderStop && window.__hnRecorderStop()');}catch{}
  // Deliver the last debounced event before persisting the draft.
  await new Promise(r=>setTimeout(r,80));recording=null;
  const task=clone(store.get(record.taskId));task.steps=record.events.map(({op,locator,label,value,checked,blocked,amount})=>({op,...(locator?{locator}:{}),...(label?{label}:{}),...(value!==undefined?{value}:{}),...(checked!==undefined?{checked}:{}),...(blocked?{blocked}:{}),...(amount!==undefined?{amount}:{})}));
  // Blocked events stay visible to the user; drafts can be edited before validation.
  const blocked=task.steps.filter(s=>s.blocked);
  if(blocked.length){recording=null;task.approvedSha=null;task.sha=taskHash(task);const index=store.data.tasks.findIndex(t=>t.id===task.id);store.data.tasks[index]=task;store.flush();lastError='The recording includes unsupported/private controls. Remove those steps in Review before saving.';return task;}
  return store.save(task);
}

function registerIPC(){
  const handlers={
    collectionStatus:()=>collectionManager.status(),
    collectionConfigure:arg=>collectionManager.configure(arg),
    collectionStart:()=>collectionManager.start(),
    collectionStop:()=>collectionManager.stop(true),
    collectionRun:arg=>collectionManager.collect(arg),
    collectionStopJob:arg=>collectionManager.stopJob(arg.id),
    collectionResumeJob:arg=>collectionManager.resumeJob(arg.id),
    collectionChooseFolder:async()=>{const result=await dialog.showOpenDialog(win,{properties:['openDirectory','createDirectory'],defaultPath:collectionManager.settings.folder});return result.canceled?null:result.filePaths[0];},
    collectionShowFolder:async()=>{const info=await collectionManager.status(),folder=info.downloadFolder;fs.mkdirSync(folder,{recursive:true});if(!fs.statSync(folder).isDirectory())throw new TaskError('This is not a download folder.');return shell.openPath(folder);},
    collectionOpenAdmin:()=>{const url=collectionManager.config().baseUrl;if(!url)throw new TaskError('Connect StickerDock first.');new (require('../service/stickerdock.cjs').StickerDock)(url,collectionManager.config().token);return shell.openExternal(url.replace(/\/$/,'')+'/admin');},
    state:()=>snapshot(),
    newTask:arg=>{idle();if(recording)throw new TaskError('Stop teaching before creating another workflow.');const options={...arg,outputFolder:app.getPath('downloads')};const t=store.save(draft(options));selectedId=t.id;return t;},
    selectTask:arg=>{idle();if(recording)throw new TaskError('Stop teaching first.');store.get(arg.id);selectedId=arg.id;return current();},
    saveTask:arg=>{idle();if(recording)throw new TaskError('Stop teaching before editing its steps.');const task=clone(arg.task);delete task.approvedSha;delete task.rehearsals;const t=store.save(task);selectedId=t.id;return t;},
    approve:arg=>{idle();return store.approve(arg.id,arg.sha);},
    open:async arg=>{idle();if(recording)throw new TaskError('Stop teaching before changing the address.');webUrl(arg.url);await browser.load(arg.url);browserHidden=false;browser.view.setVisible(true);return true;},
    back:()=>{idle();if(browser.wc.navigationHistory.canGoBack())browser.wc.navigationHistory.goBack();},
    forward:()=>{idle();if(browser.wc.navigationHistory.canGoForward())browser.wc.navigationHistory.goForward();},
    reload:()=>{idle();browser.wc.reload();},
    record:async()=>{idle();const task=current(),url=browser.wc.getURL();webUrl(url);if(recording)throw new TaskError('Teaching is already recording.');
      const login=await browser.wc.executeJavaScript('Array.from(document.querySelectorAll("input[type=password]")).some(e=>e.getClientRects().length)');
      if(login)throw new TaskError('Finish signing in before starting the demonstration.');
      browser.observed.clear();recording={taskId:task.id,token:crypto.randomBytes(24).toString('hex'),events:[]};
      // Record from the actual starting screen, not from a prior typed URL.
      task.startUrl=url;task.allowedOrigins=[...new Set([...task.allowedOrigins,new URL(url).origin])];task.approvedSha=null;task.rehearsals=[];if(task.schedule)task.schedule.enabled=false;task.sha=taskHash(task);store.flush();
      await browser.injectRecorder();return true;},
    stopRecord:()=>stopRecording(),
    pick:async arg=>{idle();if(recording)throw new TaskError('Stop teaching before choosing controls.');const task=current();picking={taskId:task.id,purpose:['gallery','next','galleryNext'].includes(arg.purpose)?arg.purpose:'source',token:crypto.randomBytes(24).toString('hex')};await browser.wc.executeJavaScript(script('picker',picking));return true;},
    chooseUpload:async()=>{idle();if(recording)throw new TaskError('Stop teaching first.');const task=clone(current()),info=await browser.wc.executeJavaScript(script('inspectUpload'));
      task.type='transfer';task.target={...info,galleryUrl:info.url,gallerySelector:'img'};task.allowedOrigins=[...new Set([...task.allowedOrigins,webUrl(info.url).origin,...browser.observed])].slice(0,30);return store.save(task);},
    run:arg=>{const result=startSavedRun(arg.id,Number(arg.rowIndex??0));return {started:true,runId:result.run.id};},
    stop:()=>{runner.stop();return true;},
    schedule:arg=>{idle();queue.enable(arg.id,!!arg.enabled,arg.time,arg.timezone);return store.get(arg.id);},
    configureAPI:async arg=>{idle();if(!localAPI)throw new TaskError('The API settings need repair before enabling integration.');return arg.enabled?localAPI.enable(Number(arg.port)):localAPI.disable();},
    copyAPIToken:()=>{if(!localAPI?.server)throw new TaskError('Turn on the local API first.');clipboard.writeText(localAPI.config.token);return true;},
    exportAPIClient:async()=>{const result=await dialog.showSaveDialog(win,{title:'Save the HandNavigate script client',defaultPath:path.join(app.getPath('downloads'),'Invoke-HandNavigate.ps1'),filters:[{name:'PowerShell script',extensions:['ps1']}]});if(result.canceled||!result.filePath)return null;fs.copyFileSync(apiClientPath(),result.filePath);return result.filePath;},
    recheckUploads:arg=>{idle();if(recording||picking||popups.size)throw new TaskError('Finish teaching, choosing controls, or signing in first.');return runner.recheck(arg.runId);},
    chooseFolder:async()=>{idle();const result=await dialog.showOpenDialog(win,{title:'Choose where image files should be saved',defaultPath:app.getPath('downloads'),properties:['openDirectory','createDirectory']});return result.canceled?null:result.filePaths[0];},
    showFolder:async arg=>{const task=store.data.tasks.find(t=>t.id===arg.id),run=store.data.runs.find(r=>r.id===arg.runId);const folder=run?.folder||task?.outputFolder;if(!folder||!path.isAbsolute(folder))throw new TaskError('No output folder is available.');fs.mkdirSync(folder,{recursive:true});const error=await shell.openPath(folder);if(error)throw new TaskError(error);return true;},
    setBrowserBounds:arg=>{const [w,h]=win.getContentSize();const bounds={x:Math.max(0,Math.floor(arg.x||0)),y:Math.max(0,Math.floor(arg.y||0)),width:Math.max(0,Math.min(w,Math.floor(arg.width||0))),height:Math.max(0,Math.min(h,Math.floor(arg.height||0)))};bounds.width=Math.min(bounds.width,w-bounds.x);bounds.height=Math.min(bounds.height,h-bounds.y);if(bounds.width>0&&bounds.height>0)browser.view.setBounds(bounds);return true;},
    hideBrowser:arg=>{browserHidden=!!arg.hidden;browser.view.setVisible(!browserHidden);return true;},
    acknowledge:arg=>{idle();store.acknowledge(arg.runId,{confirmedAbsent:arg.confirmedAbsent===true});return true;},
    deleteTask:arg=>{idle();if(recording)throw new TaskError('Stop teaching first.');const t=store.get(arg.id);t.archived=true;if(t.schedule)t.schedule.enabled=false;selectedId=null;store.flush();return true;}
  };
  for(const [name,fn] of Object.entries(handlers))ipcMain.handle('app:'+name,(event,arg)=>{
    if(name==='setBrowserBounds'){if(!sourceSender(event))throw new Error('Untrusted caller');return {ok:true,value:fn(arg||{})};}
    return action(event,fn,arg);
  });
  ipcMain.on('recorder:event',(event,payload)=>{
    try {
      if(event.sender.id!==browser.wc.id||event.senderFrame!==browser.wc.mainFrame||!payload||typeof payload!=='object'||JSON.stringify(payload).length>15000)return;
      if(picking&&payload.token===picking.token){
        if(payload.kind==='pick-cancelled'){picking=null;notify();return;}
        if(payload.kind==='picked-next'&&['next','galleryNext'].includes(picking.purpose)){
          const task=clone(store.get(picking.taskId)),pagination={kind:'next',maxPages:50,locator:payload.locator};
          if(picking.purpose==='galleryNext'){if(!task.target)throw new TaskError('Choose an upload form first.');task.target.pagination=pagination;}else task.pagination=pagination;
          task.allowedOrigins=[...new Set([...task.allowedOrigins,webUrl(payload.url).origin,...browser.observed])].slice(0,30);
          store.save(task);picking=null;notify();return;
        }
        if(payload.kind!=='picked'||typeof payload.selector!=='string'||payload.selector.length>500)return;
        const task=clone(store.get(picking.taskId));
        if(picking.purpose==='gallery'){if(!task.target)throw new TaskError('Choose the upload form first.');task.target.galleryUrl=webUrl(payload.url).href;task.target.gallerySelector=payload.selector;}
        else task.sourceSelector=payload.selector;
        task.allowedOrigins=[...new Set([...task.allowedOrigins,webUrl(payload.url).origin,...browser.observed])].slice(0,30);
        task.imageOrigins=[...new Set([...task.imageOrigins,...(payload.origins||[]).map(o=>webUrl(o).origin)])].slice(0,30);
        store.save(task);picking=null;notify();return;
      }
      if(!recording||payload.token!==recording.token||recording.events.length>=200)return;
      if(!['click','fill','select','check','press','blocked'].includes(payload.op))return;
      const task=store.get(recording.taskId);const origin=webUrl(payload.url).origin;task.allowedOrigins=[...new Set([...task.allowedOrigins,origin,...browser.observed])].slice(0,30);
      const e={op:payload.op,label:String(payload.label||'').slice(0,500),locator:payload.locator};
      if(payload.blocked||payload.op==='blocked'){e.blocked=String(payload.blocked||'Unsupported action');e.op='blocked';}
      else {
        if(PRIVATE.test(e.label+' '+JSON.stringify(e.locator))){e.blocked='Private field excluded';e.op='blocked';}
        else {if(typeof payload.value==='string'&&payload.value.length<=4000)e.value=payload.value;if(typeof payload.checked==='boolean')e.checked=payload.checked;}
      }
      const previous=recording.events.at(-1);
      if(e.op==='fill'&&previous?.op==='fill'&&JSON.stringify(previous.locator)===JSON.stringify(e.locator))recording.events[recording.events.length-1]=e;else recording.events.push(e);
      notify();
    }catch(e){fail(e);}
  });
}

async function main(){
  if(!app.requestSingleInstanceLock()){app.quit();return;}
  await app.whenReady();
  store=new Store(app.getPath('userData'));
  const legacyFolders=process.env.HANDNAVIGATE_TEST?[]:[path.join(app.getAppPath(),'runtime/service-live'),...(process.env.PORTABLE_EXECUTABLE_DIR?[path.resolve(process.env.PORTABLE_EXECUTABLE_DIR,'..','runtime/service-live')]:[])];
  collectionManager=new CollectionManager(app.getPath('userData'),{downloads:process.env.HANDNAVIGATE_TEST&&process.env.HANDNAVIGATE_TEST_DOWNLOADS?path.resolve(process.env.HANDNAVIGATE_TEST_DOWNLOADS):app.getPath('downloads'),legacyFolders,headless:process.env.HANDNAVIGATE_TEST==='1'});
  const saved=store.data.tasks.find(t=>!t.archived);if(saved)selectedId=saved.id;
  else {const t=store.save(draft({outputFolder:app.getPath('downloads')}));selectedId=t.id;}
  win=new BrowserWindow({width:1520,height:980,minWidth:1100,minHeight:740,title:'HandNavigate',icon:path.join(__dirname,'assets/icon.png'),backgroundColor:'#f4f4ee',show:false,
    webPreferences:{preload:path.join(__dirname,'preload-ui.cjs'),contextIsolation:true,nodeIntegration:false,sandbox:true,webSecurity:true}});
  Menu.setApplicationMenu(null);browser=new Browser();win.contentView.addChildView(browser.view);browser.view.setBounds({x:650,y:138,width:850,height:800});
  runner=new Runner(store,browser,notify);queue=new DailyQueue(store,(id,row,trigger)=>runner.run(id,row,trigger),()=>Date.now(),()=>!runner.active&&!recording&&!picking&&!popups.size);
  try{localAPI=new LocalAPI(app.getPath('userData'),{store,busy:()=>!!runner.active,start:(id,row,requestId)=>startSavedRun(id,row,requestId,'api'),stop:id=>{if(runner.active?.run.id!==id)throw new TaskError('That run is not active.');runner.stop();},error:fail});}catch(error){lastError=error.message;}
  registerIPC();
  win.webContents.on('will-navigate',(e,url)=>{if(url!==ownUI)e.preventDefault();});win.webContents.setWindowOpenHandler(()=>({action:'deny'}));
  win.on('close',event=>{
    if(!exitAllowed&&(runner.active||store.data.tasks.some(t=>t.schedule?.enabled)||collectionManager.app)){
      const choice=dialog.showMessageBoxSync(win,{type:'question',title:'Close HandNavigate?',message:runner.active?'A workflow is running. Closing stops the runner.':collectionManager.app?'Closing stops this app’s image collection worker.':'Daily workflows run while HandNavigate is open.',detail:'You can minimize the app to keep the local worker running. Closing keeps your saved workflows and pauses work until you reopen it.',buttons:['Keep open','Close app'],defaultId:0,cancelId:0});
      if(choice===0){event.preventDefault();return;}exitAllowed=true;runner.stop();
    }
  });
  win.on('closed',()=>{clearInterval(timer);for(const popup of popups)if(!popup.isDestroyed())popup.destroy();if(browser&&!browser.wc.isDestroyed())browser.wc.close();app.quit();});
  app.on('second-instance',()=>{if(win.isMinimized())win.restore();win.show();win.focus();});
  await win.loadFile(path.join(__dirname,'index.html'));win.show();
  if(!process.env.HANDNAVIGATE_TEST)await browser.wc.loadURL('data:text/html,'+encodeURIComponent('<!doctype html><html><head><meta charset="utf-8"><title>Your browser</title></head><body style="font:16px Segoe UI,system-ui;color:#274f3b;background:#fafbf6;display:grid;place-content:center;min-height:90vh;margin:0;padding:40px;box-sizing:border-box"><div style="max-width:430px"><h1 style="font-size:30px;font-weight:600">Your workflow starts here.</h1><p style="line-height:1.7;color:#75806e">Enter a website in the address bar, or use Open website in Set up. Sign in here once, choose your images and the way to load more, then review and run.</p><p style="font-size:13px;color:#89937e">Saved workflows use this same local browser.</p></div></body></html>')).catch(fail);
  if(localAPI?.config.enabled)await localAPI.enable().catch(fail);
  timer=setInterval(()=>{if(!runner.active&&!recording&&!picking)queue.tick().then(()=>notify()).catch(fail);},5000);timer.unref();
  if(process.env.HANDNAVIGATE_TEST)global.__handnavigateTest={get store(){return store;},get browser(){return browser;},get runner(){return runner;},get queue(){return queue;},get localAPI(){return localAPI;},get collectionManager(){return collectionManager;},get window(){return win;},setSelected:id=>{selectedId=id;notify();},flush:()=>notify(),shutdown:async()=>{exitAllowed=true;runner.stop();await collectionManager.close();await localAPI?.close();await browser.session.cookies.flushStore();browser.session.flushStorageData();win.destroy();}};
}
main().catch(e=>{dialog.showErrorBox('HandNavigate could not start',e.message);app.quit();});
app.on('before-quit',event=>{if(browser&&!flushedExit){event.preventDefault();flushedExit=true;Promise.allSettled([collectionManager?.close(),localAPI?.close(),browser.session.cookies.flushStore()]).finally(()=>{browser.session.flushStorageData();app.quit();});}});
app.on('window-all-closed',()=>app.quit());
