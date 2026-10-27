const {contextBridge,ipcRenderer}=require('electron');
const methods=['state','saveTask','approve','open','back','forward','reload','record','stopRecord','pick','chooseUpload','run','stop','schedule','configureAPI','copyAPIToken','exportAPIClient','recheckUploads','chooseFolder','showFolder','newTask','selectTask','setBrowserBounds','hideBrowser','acknowledge','deleteTask'];
const api=Object.fromEntries(methods.map(method=>[method,arg=>ipcRenderer.invoke('app:'+method,arg)]));
for(const method of ['collectionStatus','collectionConfigure','collectionStart','collectionStop','collectionRun','collectionStopJob','collectionResumeJob','collectionChooseFolder','collectionShowFolder','collectionOpenAdmin'])api[method]=arg=>ipcRenderer.invoke('app:'+method,arg);
api.onState=callback=>{const fn=(_e,state)=>callback(state);ipcRenderer.on('app:state',fn);return ()=>ipcRenderer.removeListener('app:state',fn);};
contextBridge.exposeInMainWorld('handnavigate',api);
