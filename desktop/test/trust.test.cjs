'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const {sameLocalDocument}=require('../trust.cjs');
test('packaged Windows UI identity accepts Chromium drive-letter case and URL escaping',()=>{
  const expected='file:///C:/Users/runneradmin/AppData/Local/Temp/HandNavigate/resources/app.asar/desktop/index.html';
  assert.equal(sameLocalDocument(expected.replace('C:','c:'),expected,'win32'),true);
  assert.equal(sameLocalDocument('file:///D:/Project%20Files/desktop/index.html','file:///d:/Project Files/desktop/index.html','win32'),true);
});
test('local UI identity rejects remote pages, other files, queries, fragments and invalid encodings',()=>{
  const expected='file:///C:/App/desktop/index.html';
  for(const url of ['https://site.example/index.html','file:///C:/Other/desktop/index.html',expected+'?changed=1',expected+'#changed','file://remote/C:/App/desktop/index.html','file:///C:/App/desktop/%ZZindex.html'])assert.equal(sameLocalDocument(url,expected,'win32'),false,url);
  assert.equal(sameLocalDocument('file:///app/index.html','file:///App/index.html','linux'),false);
});
