(el) => {
  const clean = s => String(s || '').replace(/\s+/g, ' ').trim().slice(0, 400);
  const tag = el.tagName.toLowerCase(), type = (el.getAttribute('type') || '').toLowerCase();
  const labelText = node => { const c=node.cloneNode(true); c.querySelectorAll('input,textarea,select,button,script,style').forEach(x=>x.remove()); return clean(c.textContent); };
  const labels = el.labels ? [...el.labels].map(labelText).filter(Boolean) : [];
  const labelled = (el.getAttribute('aria-labelledby') || '').split(/\s+/).filter(Boolean)
    .map(id => clean(document.getElementById(id)?.innerText)).join(' ');
  const label = clean(el.getAttribute('aria-label') || labelled || labels.join(' '));
  const text = clean(el.innerText || (['button','submit'].includes(type) ? el.value : '') || el.getAttribute('alt'));
  const hint = [type, el.name, el.id, label, el.getAttribute('autocomplete')].join(' ');
  const sensitive = /password|passwd|secret|token|api[-_ ]?key|credential|one[-_ ]?time|credit.?card|cc-number|cc-csc|cvv/i.test(hint)
    || !!el.closest('[data-private],[data-sensitive]');
  const roles = {button:'button',a:'link',textarea:'textbox',select:'combobox'};
  let role = el.getAttribute('role') || roles[tag] || '';
  if(tag === 'input') role = ({checkbox:'checkbox',radio:'radio',button:'button',submit:'button',search:'searchbox'})[type] || 'textbox';
  const name = label || text, candidates = [];
  if(el.getAttribute('data-testid')) candidates.push({kind:'testid',value:el.getAttribute('data-testid')});
  if(label && ['input','select','textarea'].includes(tag)) candidates.push({kind:'label',value:label});
  if(role && name) candidates.push({kind:'role',role,name});
  if(el.getAttribute('placeholder')) candidates.push({kind:'placeholder',value:el.getAttribute('placeholder')});
  if(el.id) candidates.push({kind:'css',value:'#' + CSS.escape(el.id)});
  if(el.name) candidates.push({kind:'css',value:tag + '[name=' + JSON.stringify(el.name) + ']'});
  const r = el.getBoundingClientRect(), style = getComputedStyle(el);
  return {tag,type,role,name,label,sensitive,candidates,
    fingerprint:JSON.stringify([tag,type,role,name,el.id,el.name]),
    value:sensitive ? '[REDACTED]' : (['input','textarea','select'].includes(tag) ? String(el.value).slice(0,1000) : null),
    checked:['checkbox','radio'].includes(type) ? el.checked : null,
    options:tag === 'select' ? [...el.options].slice(0,50).map(o=>({label:clean(o.label),value:o.value})) : [],
    href:tag === 'a' ? el.href : null, disabled:!!el.disabled || el.getAttribute('aria-disabled') === 'true',
    box:{x:Math.round(r.x),y:Math.round(r.y),width:Math.round(r.width),height:Math.round(r.height)},
    style:{display:style.display,visibility:style.visibility,cursor:style.cursor},
    connected:el.isConnected};
}
