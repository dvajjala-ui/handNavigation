const {contextBridge,ipcRenderer}=require('electron');
const methods=['state','saveTask','approve','open','back','forward','reload','record','stopRecord','pick','chooseUpload','run','stop','schedule','chooseFolder','showFolder','newTask','selectTask','setBrowserBounds','hideBrowser','acknowledge','deleteTask'];
const api=Object.fromEntries(methods.map(method=>[method,arg=>ipcRenderer.invoke('app:'+method,arg)]));
api.onState=callback=>{const fn=(_e,state)=>callback(state);ipcRenderer.on('app:state',fn);return ()=>ipcRenderer.removeListener('app:state',fn);};
contextBridge.exposeInMainWorld('handnavigate',api);
