'use strict';
// These functions run in the website renderer. They expose observations/drafts only.
function helpers() {
  const clean=s=>String(s||'').replace(/\s+/g,' ').trim().slice(0,500);
  const sensitive=e=>/password|passwd|secret|token|api[-_ ]?key|credential|one[-_ ]?time|credit.?card|cc-number|cc-csc|cvv/i.test([e.type,e.name,e.id,e.getAttribute('autocomplete'),e.getAttribute('aria-label')].join(' '))||!!e.closest('[data-private],[data-sensitive]');
  const visible=e=>!!e.getClientRects().length&&getComputedStyle(e).visibility!=='hidden'&&getComputedStyle(e).display!=='none';
  const role=e=>e.getAttribute('role')||({BUTTON:'button',A:'link',TEXTAREA:'textbox',SELECT:'combobox'})[e.tagName]||(e.tagName==='INPUT'?({checkbox:'checkbox',radio:'radio',submit:'button',button:'button',search:'searchbox'})[e.type]||'textbox':'');
  const name=e=>clean(e.getAttribute('aria-label')||(e.labels?[...e.labels].map(l=>l.textContent).join(' '):'')||e.getAttribute('alt')||e.innerText||e.title);
  const resolve=(spec,hidden=false)=>{
    let nodes;
    if(spec.kind==='css')nodes=[...document.querySelectorAll(spec.value)];
    else if(spec.kind==='testid')nodes=[...document.querySelectorAll('[data-testid],[data-test-id]')].filter(e=>e.getAttribute('data-testid')===spec.value||e.getAttribute('data-test-id')===spec.value);
    else if(spec.kind==='label')nodes=[...document.querySelectorAll('input,textarea,select')].filter(e=>name(e)===spec.value);
    else if(spec.kind==='placeholder')nodes=[...document.querySelectorAll('input,textarea')].filter(e=>e.getAttribute('placeholder')===spec.value);
    else if(spec.kind==='role')nodes=[...document.querySelectorAll('button,a,input,select,textarea,[role]')].filter(e=>role(e)===spec.role&&name(e)===spec.name);
    else nodes=[...document.querySelectorAll('button,a,label,span,p,h1,h2,h3,div')].filter(e=>clean(e.innerText)===spec.value&&!e.querySelector('button,a,p,h1,h2,h3,div'));
    nodes=nodes.filter(e=>hidden||visible(e));
    if(nodes.length!==1)throw new Error(nodes.length?'This control is ambiguous. Teach it again.':'The taught control is missing. Open the site and teach the changed step again.');
    return nodes[0];
  };
  const locate=e=>{
    const candidates=[];
    if(e.getAttribute('data-testid'))candidates.push({kind:'testid',value:e.getAttribute('data-testid')});
    if(e.getAttribute('data-test-id'))candidates.push({kind:'testid',value:e.getAttribute('data-test-id')});
    if(name(e)&&['INPUT','TEXTAREA','SELECT'].includes(e.tagName))candidates.push({kind:'label',value:name(e)});
    if(role(e)&&name(e))candidates.push({kind:'role',role:role(e),name:name(e)});
    if(e.getAttribute('placeholder'))candidates.push({kind:'placeholder',value:e.getAttribute('placeholder')});
    if(e.id)candidates.push({kind:'css',value:'#'+CSS.escape(e.id)});
    if(e.name)candidates.push({kind:'css',value:e.tagName.toLowerCase()+'[name='+JSON.stringify(e.name)+']'});
    for(const s of candidates){try{if(resolve(s,true)===e)return s;}catch{}}
    return null;
  };
  const fingerprint=e=>JSON.stringify([e.tagName,e.type,role(e),name(e),e.id,e.name,e.getAttribute('href'),e.form?.action,e.disabled,e.getAttribute('aria-disabled')]);
  return {clean,sensitive,visible,role,name,resolve,locate,fingerprint};
}
function recorder(args) {
  const H=HELPERS();
  if(window.__hnRecorderStop)window.__hnRecorderStop();
  let pending=new Map(),lastKey=null;const handlers=[];
  const send=(op,el,more={})=>{
    const private_=H.sensitive(el),loc=H.locate(el);
    const unsupported=['file','range','color'].includes(el.type)||el.isContentEditable;
    window.handnavigateRecord?.send({token:args.token,op:private_||unsupported||!loc?'blocked':op,
      blocked:private_?'Private fields are excluded from teaching.':unsupported?'This control needs a supported adapter.':!loc?'This control has no unique locator.':null,
      locator:loc,label:H.name(el)||el.tagName.toLowerCase(),url:location.href,...(private_?{}:more)});
  };
  const flush=e=>{const entry=pending.get(e);if(entry){clearTimeout(entry);pending.delete(e);send('fill',e,{value:e.value});}};
  const flushAll=()=>[...pending.keys()].forEach(flush);
  const on=(event,callback)=>{document.addEventListener(event,callback,true);handlers.push([event,callback]);};
  on('input',e=>{if(!e.isTrusted||!e.target.matches('input,textarea,[contenteditable=true]'))return;const el=e.target;if(H.sensitive(el)){send('blocked',el);return;}if(['checkbox','radio'].includes(el.type))return;clearTimeout(pending.get(el));pending.set(el,setTimeout(()=>flush(el),200));});
  on('change',e=>{if(!e.isTrusted)return;const el=e.target;if(el.matches('input[type=checkbox],input[type=radio]'))send('check',el,{checked:el.checked});else if(el.tagName==='SELECT')send('select',el,{value:el.value});else if(el.type==='file')send('blocked',el,{blocked:'File selection cannot be replayed as a raw local path. Use the verified upload destination.'});else flush(el);});
  on('click',e=>{if(!e.isTrusted)return;flushAll();const el=e.target.closest('button,a[href],[role=button],[role=tab],[role=menuitem]');if(!el)return;if(e.detail===0&&lastKey&&Date.now()-lastKey.at<700&&(el===lastKey.el||el.form&&el.form===lastKey.el.form))return;send('click',el);});
  on('keydown',e=>{if(!e.isTrusted||!['Enter','Escape','Tab','ArrowDown','ArrowUp'].includes(e.key))return;const el=e.target;if(!el.matches('input,textarea,button,select,[role=button]'))return;flushAll();lastKey={at:Date.now(),el};send('press',el,{value:e.key});});
  window.__hnRecorderStop=()=>{flushAll();handlers.forEach(([e,fn])=>document.removeEventListener(e,fn,true));delete window.__hnRecorderStop;};
  return true;
}
function picker(args) {
  const H=HELPERS();
  if(window.__hnPickerStop)window.__hnPickerStop();
  const banner=document.createElement('div');banner.textContent=args.purpose==='gallery'?'HandNavigate: click a saved gallery image or its empty container. Esc cancels.':'HandNavigate: click one image from the group you want to download. Esc cancels.';
  banner.style.cssText='position:fixed;top:0;left:0;right:0;z-index:2147483647;background:#172f29;color:white;font:14px system-ui;padding:16px;pointer-events:none;';document.documentElement.appendChild(banner);
  function stop(){document.removeEventListener('click',click,true);document.removeEventListener('keydown',key,true);banner.remove();delete window.__hnPickerStop;}
  const group=e=>{
    const classes=[...e.classList].filter(c=>/^[A-Za-z_][\w-]{0,45}$/.test(c)).slice(0,3);
    return e.tagName.toLowerCase()+classes.map(c=>'.'+CSS.escape(c)).join('');
  };
  function click(e){e.preventDefault();e.stopImmediatePropagation();const image=e.target.closest('img');if(!image&&args.purpose!=='gallery')return;
    let selector;
    if(image&&image.closest('a[href*="/pin/"]'))selector='a[href*="/pin/"] img';
    else {const container=(image?image.parentElement:e.target).closest('[id]');const own=image?group(image):'img';selector=container?'#'+CSS.escape(container.id)+' '+own:own;if(image&&document.querySelectorAll(selector).length===1&&document.querySelectorAll(own).length>1)selector=own;}
    const origins=new Set();for(const img of document.querySelectorAll(selector)){for(const s of [img.currentSrc||img.src,...String(img.srcset||'').split(',').map(s=>s.trim().split(/\s+/)[0])]){try{const u=new URL(s,location.href);if(/^https?:$/.test(u.protocol))origins.add(u.origin);}catch{}}}
    const payload={token:args.token,kind:'picked',purpose:args.purpose,selector,matches:document.querySelectorAll(selector).length,origins:[...origins],url:location.href};stop();window.handnavigateRecord?.send(payload);
  }
  function key(e){if(e.key==='Escape'){stop();window.handnavigateRecord?.send({token:args.token,kind:'pick-cancelled'});}}
  document.addEventListener('click',click,true);document.addEventListener('keydown',key,true);window.__hnPickerStop=stop;
  return true;
}
function findTarget(args) {
  const H=HELPERS(),el=H.resolve(args.locator,!!args.hidden);
  if(H.sensitive(el))throw new Error('Private controls require manual interaction.');
  if(el.disabled||el.getAttribute('aria-disabled')==='true')throw new Error('The taught control is disabled.');
  el.scrollIntoView({block:'center',inline:'center'});
  const r=el.getBoundingClientRect();
  return {x:r.x+r.width/2,y:r.y+r.height/2,tag:el.tagName,type:el.type,checked:el.checked,value:el.value,
    fingerprint:H.fingerprint(el),url:location.href};
}
function focusTarget(args) {
  const H=HELPERS(),el=H.resolve(args.locator,!!args.hidden);
  if(H.sensitive(el)||H.fingerprint(el)!==args.fingerprint||location.href!==args.url)throw new Error('The page or control changed before this action.');
  el.focus();if(el.select)el.select();
  return true;
}
function selectTarget(args) {
  const H=HELPERS(),el=H.resolve(args.locator);
  if(H.sensitive(el)||H.fingerprint(el)!==args.fingerprint||el.tagName!=='SELECT'||![...el.options].some(o=>o.value===args.value))throw new Error('The selected option or control changed.');
  el.value=args.value;el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));return true;
}
function imageCandidates(args) {
  const H=HELPERS();
  if(document.querySelector('[data-test-id="gated-pin-image"]')||[...document.querySelectorAll('input[type=password]')].some(H.visible))return {authRequired:true,items:[]};
  const items=[...document.querySelectorAll(args.selector)].slice(0,1000).map(i=>{
    const img=i.tagName==='IMG'?i:i.querySelector('img');if(!img)return null;
    const pin=img.closest('a[href*="/pin/"]')||img.closest('[data-test-id="pin"]')?.querySelector('a[href*="/pin/"]');
    const linked=img.closest('a[href]')?.href;
    let linkedOriginal='';
    if(linked)try {const u=new URL(linked,location.href);if(/^https?:$/.test(u.protocol)&&u.origin===location.origin)linkedOriginal=u.href;}catch{}
    const raw=[...String(img.srcset||'').split(',').map(s=>{const p=s.trim().split(/\s+/);return {url:p[0],score:Number.parseFloat(p[1])||1};}).sort((a,b)=>b.score-a.score).map(a=>a.url),img.currentSrc||img.src,linkedOriginal].filter(Boolean);
    const urls=[...new Set(raw.map(s=>{try{return new URL(s,location.href).href;}catch{return '';}}).filter(s=>/^https?:/.test(s)))];
    return {sourceId:pin?.href||urls[0],pin:pin?.href||null,urls,alt:H.clean(img.alt),gated:!!img.closest('[data-test-id="gated-pin-image"]')};
  }).filter(Boolean);
  return {authRequired:false,url:location.href,items};
}
function inspectUpload() {
  const H=HELPERS(),inputs=[...document.querySelectorAll('input[type=file]')];
  if(inputs.length!==1)throw new Error('Open an upload form with one file input before choosing it.');
  const input=inputs[0],spec=H.locate(input)||{kind:'css',value:'input[type=file]'};
  const buttons=[...document.querySelectorAll('button,input[type=submit]')].filter(e=>H.visible(e)&&/^(upload|upload image|upload images|save|publish)$/i.test(H.name(e)));
  return {fileInput:spec,submit:buttons.length===1?H.locate(buttons[0]):null,url:location.href};
}
function verifyCheck(args) {
  const H=HELPERS();
  if(args.kind==='url')return location.href===args.expected;
  const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);let n;
  while(n=walker.nextNode()){const p=n.parentElement;if(p&&!p.closest('script,style,noscript,input,textarea')&&H.visible(p)&&H.clean(n.textContent).includes(args.expected))return true;}
  return false;
}
function scrollPage(){const node=document.scrollingElement||document.documentElement;node.scrollBy({top:Math.max(600,innerHeight*.85),behavior:'instant'});return {top:node.scrollTop,height:node.scrollHeight};}
const functions={recorder,picker,findTarget,focusTarget,selectTarget,imageCandidates,inspectUpload,verifyCheck,scrollPage};
function script(name,args={}) {
  if(!functions[name])throw new Error('Unknown browser operation.');
  return '('+functions[name].toString().replace('HELPERS()', '('+helpers.toString()+')()')+')('+JSON.stringify(args)+')';
}
module.exports={script,helpers};
