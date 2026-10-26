const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('handnavigateRecord',{send:payload=>{
  if(payload&&typeof payload==='object')ipcRenderer.send('recorder:event',payload);
}});
