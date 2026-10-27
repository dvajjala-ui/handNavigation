'use strict';
const path=require('node:path');
function localDocument(url,platform=process.platform){
  try{
    const u=new URL(url);if(u.protocol!=='file:'||u.search||u.hash||u.username||u.password||u.host&&u.host!=='localhost')return null;
    const file=decodeURIComponent(u.pathname);if(file.includes('\0'))return null;
    // Chromium lowercases a Windows drive in some packaged file URLs.
    return platform==='win32'?path.win32.normalize(file.replace(/^\/([a-z]:)/i,'$1')).toLowerCase():path.posix.normalize(file);
  }catch{return null;}
}
function sameLocalDocument(actual,expected,platform=process.platform){const a=localDocument(actual,platform),b=localDocument(expected,platform);return a!==null&&b!==null&&a===b;}
module.exports={localDocument,sameLocalDocument};
