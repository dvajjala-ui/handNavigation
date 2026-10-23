"""Consent-based, main-frame recording. Captures are drafts, not approved programs."""
from __future__ import annotations

import json
from pathlib import Path
import threading
from .browser import DESCRIBE
from .contracts import LiveError, Scope, public_url, save_json


def instrumentation() -> str:
    return r'''(() => {
      if(window.__hnRecordingInstalled) return;
      window.__hnRecordingInstalled=true;
      const describe=DESCRIBE_PLACEHOLDER;
      const pending=new Map(); let sequence=0; let lastEnter=null;
      const send=(op,el,extra={})=>{
        const meta=describe(el);
        const event={sequence:++sequence,at:Date.now(),url:location.href,op,
          element:meta.sensitive ? {sensitive:true} : meta,...extra};
        if(meta.sensitive){event.op='blocked';delete event.value;delete event.checked;}
        window.__hnLiveRecord(event).catch(()=>{});
      };
      const flush=el=>{const entry=pending.get(el);if(!entry)return;
        clearTimeout(entry.timer);pending.delete(el);send('fill',el,{value:el.value});};
      const flushAll=()=>[...pending.keys()].forEach(flush);
      document.addEventListener('input',e=>{
        if(!e.isTrusted || !e.target.matches('input,textarea')) return;
        const el=e.target;
        if(describe(el).sensitive){send('blocked',el);return;}
        if(['checkbox','radio'].includes(el.type)) return;
        if(pending.has(el))clearTimeout(pending.get(el).timer);
        pending.set(el,{timer:setTimeout(()=>flush(el),250)});
      },true);
      document.addEventListener('change',e=>{
        if(!e.isTrusted || !e.target.matches('input,textarea,select'))return;
        const el=e.target;
        if(el.type==='checkbox'||el.type==='radio')send('check',el,{checked:el.checked});
        else if(el.tagName==='SELECT')send('select',el,{value:el.value});
        else if(pending.has(el))flush(el);
      },true);
      document.addEventListener('click',e=>{
        if(!e.isTrusted)return;flushAll();
        const el=e.target.closest('button,a[href],[role=button],[role=tab],[role=menuitem]');
        if(el && e.detail===0 && lastEnter && Date.now()-lastEnter.at<700 &&
          (el===lastEnter.el || (el.form && el.form===lastEnter.el.form)))return;
        if(el)send('click',el);
      },true);
      document.addEventListener('keydown',e=>{
        if(!e.isTrusted||!['Enter','Escape'].includes(e.key))return;
        const el=e.target;if(!el.matches('input,textarea,button,[role=button]'))return;
        flushAll();if(e.key==='Enter')lastEnter={at:Date.now(),el};send('press',el,{value:e.key});
      },true);
      window.__hnFlushRecording=flushAll;
    })();'''.replace('DESCRIBE_PLACEHOLDER', DESCRIBE)


def wait_for_operator(page, message: str):
    """Keep Playwright's event loop active while the operator uses the browser."""
    stopped = threading.Event()
    def wait():
        try: input(message)
        except EOFError: pass
        finally: stopped.set()
    thread = threading.Thread(target=wait, daemon=True)
    thread.start()
    while not stopped.is_set() and not page.is_closed():
        page.wait_for_timeout(100)


def compile_events(events: list, *, start_url: str, scope: Scope, checks: list) -> tuple[dict, dict]:
    steps, blockers, notes = [], [], []
    for e in events:
        if e['op'] == 'checkpoint':
            continue
        meta = e.get('element', {})
        if e.get('op') == 'blocked' or meta.get('sensitive'):
            blockers.append('A private or unsupported control was used; recording is not replayable')
            continue
        try:
            scope.check(e['url'])
        except LiveError:
            blockers.append('An event occurred outside the allowed scope')
            continue
        candidates = meta.get('candidates', [])
        if not candidates:
            blockers.append('A control has no replay locator')
            continue
        step = {'op':e['op'], 'locator':candidates[0], 'source_action':str(e['sequence'])}
        for field in ('value','checked'):
            if field in e:
                step[field] = e[field]
        if steps and step['op'] == 'fill' and all(step.get(k) == steps[-1].get(k) for k in ('op','locator','value')):
            continue
        steps.append(step)
    if len(steps) > scope.max_actions:
        blockers.append('Recording exceeds the action budget')
    notes.extend(['Recorder observations after human actions can lag rapid interactions; these are checkpoints, not exact pre-action screenshots.',
                  'Recorder does not prove a causal relationship between clicks and network activity.',
                  'Review Enter plus click sequences: browsers may emit both for keyboard activation.',
                  'Success checks and parameter bindings are supplied explicitly, not learned automatically.'])
    recipe = {'schema':'handnavigate.live.v1','name':'Recorded live-site demonstration',
              'start_url':start_url,'scope':scope.as_dict(),'steps':steps,'checks':checks,
              'provenance':{'source':'human-recording','reviewed':False,'blockers':len(blockers)}}
    return recipe, {'blockers':blockers,'notes':notes,'events':len(events),'steps':len(steps)}


def record(driver, *, start_url: str, checks: list) -> dict:
    events = []
    queue = []
    def notify(source, payload):
        if source.get('frame') != driver.page.main_frame:
            queue.append({'op':'blocked','sequence':len(events)+len(queue),'url':driver.page.url,'element':{'sensitive':True}})
            return
        # A webpage can spoof instrumentation. This is untrusted draft input only.
        if isinstance(payload,dict) and len(json.dumps(payload)) < 14000:
            payload['url'] = public_url(str(payload.get('url','')))
            meta = payload.get('element')
            if isinstance(meta,dict) and meta.get('href'):
                meta['href'] = public_url(str(meta['href']))
            queue.append(payload)
    driver.page.expose_binding('__hnLiveRecord', notify)
    driver.page.add_init_script(script=instrumentation())
    driver.page.evaluate(instrumentation())
    driver.observe('recording-start')
    stopped = threading.Event()
    def stop():
        try: input('Demonstrate the task in the browser. Press ENTER here to stop recording: ')
        except EOFError: pass
        finally: stopped.set()
    threading.Thread(target=stop,daemon=True).start()
    try:
        while not stopped.is_set() and not driver.page.is_closed():
            driver.page.wait_for_timeout(100)
            if queue:
                events.extend(queue)
                queue.clear()
                save_json(driver.output/'recording.json', {'events':events,'source':'human-browser-recording'})
                driver.observe('after-recorded-events')
            if len(events) >= 200:
                raise LiveError('Recording event budget exhausted')
        if not driver.page.is_closed():
            driver.page.evaluate('window.__hnFlushRecording && window.__hnFlushRecording()')
            driver.page.wait_for_timeout(150)
        events.extend(queue)
    finally:
        save_json(driver.output/'recording.json', {'events':events,'source':'human-browser-recording'})
    workflow, report = compile_events(events,start_url=start_url,scope=driver.scope,checks=checks)
    save_json(driver.output/'workflow.draft.json',workflow)
    save_json(driver.output/'recording-report.json',report)
    return {'status':'DRAFT_REQUIRES_REVIEW' if not report['blockers'] else 'BLOCKED', 'model_calls':0,**report}
