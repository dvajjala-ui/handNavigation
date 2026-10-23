"""Import captured observations conservatively, then replay reviewed programs without AI."""
from __future__ import annotations

from pathlib import Path
from .contracts import (LiveError, Scope, TARGET_OPS, SECRET, origin, resolve_value,
                        require_approval, save_json, validate_locator)


def import_trustudio(capture: dict, flow_id: str | None = None) -> tuple[dict, dict]:
    """Consumes capture.json OUTPUT, not the tool's source ZIP. Never imports HAR or keys."""
    if capture.get('version') != 4 or not isinstance(capture.get('actions'), list):
        raise LiveError('Expected TruStudio v4 capture.json output')
    flows = {x['id'] for x in capture.get('flows', [])}
    if len(flows) > 1 and flow_id is None:
        raise LiveError('Select one --flow; multiple feature flows are not one safe recipe')
    if flow_id is not None and flow_id not in flows:
        raise LiveError('Unknown flow ID')
    actions = [a for a in capture['actions'] if flow_id is None or a.get('flowId') == flow_id]
    if not 1 <= len(actions) <= 200:
        raise LiveError('Selected flow has no actions or exceeds the import budget')
    start = capture.get('targetUrl', '')
    states = {s.get('id'):s for s in capture.get('states', [])}
    first_state = states.get(actions[0].get('beforeStateId'), {})
    start = first_state.get('url') or start
    allowed = (origin(start),)
    steps, blockers, notes = [], [], []
    for a in actions:
        identifier = str(a.get('id', 'unknown'))
        e = a.get('element') or {}
        hint = ' '.join(str(e.get(k, '')) for k in ('name','id','type','ariaLabel'))
        value = a.get('value')
        if SECRET.search(hint) or value == '[REDACTED]':
            blockers.append({'action':identifier,'reason':'Sensitive/redacted field; cannot replay safely'})
            continue
        if a.get('kind') == 'manual-checkpoint':
            notes.append({'action':identifier,'reason':'Checkpoint retained as evidence, not converted into an action'})
            continue
        before = states.get(a.get('beforeStateId'), {})
        after = states.get(a.get('afterStateId'), {})
        for state in (before,after):
            if state.get('url') and origin(state['url']) not in allowed:
                blockers.append({'action':identifier,'reason':'Captured navigation left the single approved origin'})
        if a.get('kind') == 'click' and e.get('tag') in {'input','textarea','select'} and e.get('type') not in {'button','submit','checkbox','radio'}:
            notes.append({'action':identifier,'reason':'Field-focus click omitted; fill/select focuses the field'})
            continue
        if e.get('type') in {'checkbox','radio'}:
            blockers.append({'action':identifier,'reason':'Original capture does not reliably record checked state; demonstrate again'})
            continue
        spec = None
        if e.get('ariaLabel') and e.get('tag') in {'input','textarea','select'}:
            spec = {'kind':'label','value':e['ariaLabel']}
        elif e.get('role') and (e.get('ariaLabel') or e.get('text')):
            spec = {'kind':'role','role':e['role'],'name':e.get('ariaLabel') or e['text']}
        elif e.get('tag') in {'button','a'} and (e.get('ariaLabel') or e.get('text')):
            spec = {'kind':'role','role':'button' if e['tag']=='button' else 'link','name':e.get('ariaLabel') or e['text']}
        elif e.get('selector'):
            spec = {'kind':'css','value':e['selector']}
            notes.append({'action':identifier,'reason':'CSS fallback must be checked for stability and uniqueness'})
        if spec is None:
            blockers.append({'action':identifier,'reason':'No usable locator was captured'})
            continue
        try:
            validate_locator(spec)
        except LiveError:
            blockers.append({'action':identifier,'reason':'Captured locator is outside the supported contract'})
            continue
        kind = a.get('kind')
        if kind in {'input','change'} and isinstance(value,str):
            if e.get('tag') not in {'input','textarea','select'}:
                blockers.append({'action':identifier,'reason':'Unsupported editable widget; recapture or define adapter'})
                continue
            step = {'op':'select' if e.get('tag')=='select' else 'fill','locator':spec,'value':value,'source_action':identifier}
            # Coalesce duplicate input/change events only when value AND locator are identical.
            if steps and all(steps[-1].get(k) == step.get(k) for k in ('op','locator','value')):
                notes.append({'action':identifier,'reason':'Duplicate identical input/change event coalesced'})
                continue
        elif kind == 'click':
            step = {'op':'click','locator':spec,'source_action':identifier}
        else:
            blockers.append({'action':identifier,'reason':'Action kind or field value cannot be mapped without guessing'})
            continue
        steps.append(step)
    report = {'source':'TruStudio v4 capture.json','flow':flow_id,'blockers':blockers,'notes':notes,
              'status':'BLOCKED' if blockers else 'DRAFT_REQUIRES_REVIEW',
              'warnings':['Timing-based network correlation is evidence, not a proven API contract',
                          'Click-driven downloads must be changed explicitly to download actions',
                          'Add explicit completion checks; no success rule is inferred from screenshots']}
    workflow = {'schema':'handnavigate.live.v1','name':capture.get('name','Imported capture'),
                'start_url':start,'scope':Scope(allowed,max_actions=min(200,max(30,len(steps)))).as_dict(),
                'steps':steps,'checks':[],'provenance':{'source':'trustudio-v4','reviewed':False,'blockers':len(blockers)}}
    return workflow, report


def replay(driver, workflow: dict, inputs: dict, receipt: dict) -> dict:
    scope = require_approval(workflow, inputs, receipt)
    if driver.scope != scope:
        raise LiveError('Browser scope differs from the approved workflow')
    if workflow.get('provenance', {}).get('blockers', 0):
        raise LiveError('Resolve import/recording blockers before approving or replaying')
    result = {'status':'HALTED','model_calls':0,'actions':0,'checks':[]}
    try:
        driver.observe('replay-initial')
        for step in workflow['steps']:
            action = {k:resolve_value(v, inputs) for k,v in step.items() if k not in {'locator','source_action'}}
            action['snapshot'] = driver.latest['snapshot']
            if action['op'] in TARGET_OPS:
                action['target'] = driver.bind_locator(step['locator'])
            driver.execute(action, lambda proposal: True)
        result['checks'] = driver.verify(workflow['checks'], inputs)
        result['status'] = 'VERIFIED'
    except Exception as exc:
        result['error_type'] = type(exc).__name__
        result['error'] = str(exc)[:500] if isinstance(exc,LiveError) else 'Action or verification failed; no automatic retry'
    result['actions'] = driver.action_count
    result['downloads'] = driver.downloads
    save_json(driver.output/'result.json', result)
    return result
