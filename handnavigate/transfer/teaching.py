"""Teach real browser setup once and select the image group to repeat."""
from pathlib import Path
import json
import time

from ..live.browser import open_driver
from ..live.contracts import LiveError, resolve_value, save_json
from ..live.recording import record, wait_for_operator
from .contracts import validate
from .profiles import checked_profile


PICKER = r'''({kind}) => {
  window.__hnPicked = null;
  const hint=document.createElement('div');
  hint.textContent=kind==='source' ? 'HandNavigate: click one image from the group to collect. Escape cancels.' :
    'HandNavigate: click inside the uploaded-image gallery (or its empty container). Escape cancels.';
  hint.style.cssText='position:fixed;top:0;left:0;right:0;z-index:2147483647;padding:16px;background:#142a43;color:white;font:16px system-ui;pointer-events:none';
  document.body.append(hint);
  const selector=el=>{
    if(el.id)return '#'+CSS.escape(el.id);
    const classes=[...el.classList].filter(c=>/^[a-zA-Z_][\w-]{0,50}$/.test(c)).slice(0,3);
    return el.tagName.toLowerCase()+classes.map(c=>'.'+CSS.escape(c)).join('');
  };
  const done=result=>{window.__hnPicked=result;document.removeEventListener('click',click,true);document.removeEventListener('keydown',key,true);hint.remove();};
  const click=e=>{
    e.preventDefault();e.stopImmediatePropagation();
    const image=e.target.closest('img');
    if(kind==='source'){
      if(!image)return;
      const classes=[...image.classList].filter(c=>/^[a-zA-Z_][\w-]{0,50}$/.test(c)).slice(0,3);
      const own='img'+classes.map(c=>'.'+CSS.escape(c)).join('');
      const parent=image.parentElement.closest('[id]');
      let group=parent && parent!==image ? '#'+CSS.escape(parent.id)+' '+own : own;
      if(document.querySelectorAll(group).length===1 && document.querySelectorAll(own).length>1)group=own;
      done({selector:group,attribute:'src',matches:document.querySelectorAll(group).length});
    } else {
      const container=image ? image.parentElement.closest('[id]') : e.target.closest('[id]');
      const group=container ? '#'+CSS.escape(container.id)+' img' : (image ? selector(image) : selector(e.target)+' img');
      done({selector:group,matches:document.querySelectorAll(group).length});
    }
  };
  const key=e=>{if(e.key==='Escape')done({cancelled:true});};
  document.addEventListener('click',click,true);document.addEventListener('keydown',key,true);
}'''


def pick(driver, kind):
    driver.page.evaluate(PICKER, {'kind': kind})
    until = time.monotonic()+300
    while not driver.page.is_closed() and time.monotonic() < until:
        choice = driver.page.evaluate('window.__hnPicked')
        if choice:
            if choice.get('cancelled'):
                raise LiveError('Teaching selection cancelled')
            return choice
        driver.page.wait_for_timeout(100)
    raise LiveError('Teaching timed out or the browser was closed')


def teach(recipe, inputs, root, source_profile=None, target_profile=None):
    scopes = validate(recipe, inputs)
    root = Path(root)
    profiles = [source_profile or root/'profiles'/'source', target_profile or root/'profiles'/'target']
    choices = {}
    for side, scope, profile in zip(('source', 'target'), scopes, profiles):
        profile = checked_profile(profile, scope)
        out = root/'teaching'/side
        with open_driver(scope, out, profile=profile) as driver:
            start = resolve_value(recipe[side]['url'], inputs)
            driver.goto(start)
            wait_for_operator(driver.page, f'{side}: sign in manually if needed. Press ENTER here to begin recording setup: ')
            # Begin at the post-login URL; credential-bearing URLs are rejected by the scope.
            driver.check_page()
            start = driver.page.url
            recipe[side]['url'] = start
            print('Demonstrate the search/folder/open-form steps. Stop before downloading or selecting an upload file.', flush=True)
            result = record(driver, start_url=start, checks=[])
            if result['status'] != 'DRAFT_REQUIRES_REVIEW':
                raise LiveError('This demonstration used unsupported/private controls. Inspect the recording report and teach setup again.')
            workflow = json.loads((out/'workflow.draft.json').read_text(encoding='utf-8'))
            recipe[side]['setup'] = workflow['steps']
            if side == 'source':
                choice = pick(driver, 'source')
                recipe['source'].update(items=choice['selector'], image_selector='', image_attribute=choice['attribute'])
            else:
                file_inputs = driver.page.locator('input[type=file]')
                if file_inputs.count() != 1:
                    raise LiveError('Open the upload form before stopping the demonstration. Its file input must be unique.')
                node = file_inputs.first
                id_, name = node.get_attribute('id'), node.get_attribute('name')
                if id_:
                    value = 'input[id='+json.dumps(id_)+']'
                elif name:
                    value = 'input[type=file][name='+json.dumps(name)+']'
                else:
                    value = 'input[type=file]'
                recipe['target']['file_input'] = {'kind': 'css', 'value': value}
                # A site that submits immediately on file selection needs no submit action.
                buttons = driver.page.get_by_role('button').all()
                candidates = [b for b in buttons if b.is_visible() and b.inner_text().strip().lower() in {'upload', 'upload image', 'upload images', 'save', 'publish'}]
                if len(candidates) == 1:
                    recipe['target']['submit'] = {'kind': 'role', 'role': 'button', 'name': candidates[0].inner_text().strip()}
                wait_for_operator(driver.page, 'Navigate to the destination gallery where saved images appear. Press ENTER here, then click the gallery: ')
                recipe['target']['verify']['url'] = driver.page.url
                choices['gallery_url'] = driver.page.url
                choice = pick(driver, 'target')
                recipe['target']['verify'].update(items=choice['selector'], image_selector='', image_attribute='src', id_attribute='src')
            choices[side] = choice
    validate(recipe, inputs)
    save_json(root/'teaching'/'selection.json', choices)
    return recipe
