"""Explicit offline/browser-component tests. No third-party site or real model is simulated as proven."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from unittest.mock import patch
import pytest
from playwright.sync_api import sync_playwright

from handnavigate.runner import launch_browser
from handnavigate.live.contracts import (LiveError, Scope, approval, digest, origin, public_url,
    require_approval, validate_action, validate_workflow)
from handnavigate.live.browser import Driver
from handnavigate.live.agent import GroqProvider, run_agent
from handnavigate.live.recording import compile_events, instrumentation
from handnavigate.live.workflows import import_trustudio, replay

ORIGIN = 'https://owned.example'
HTML = '''<!doctype html><html><head><title>Explicit offline component test</title></head><body>
<h1>Offline test form</h1><label>Topic <input id="topic"></label>
<label>Second field <input id="second"></label>
<label>Mode <select id="mode"><option value="brief">Brief</option><option value="full">Full</option></select></label>
<label>Captions <input id="captions" type="checkbox"></label>
<label>Password <input type="password" id="password"></label>
<button id="preview" onclick="document.getElementById('result').textContent='Ready: '+document.getElementById('topic').value">Prepare preview</button>
<div id="result" role="status"></div><a id="file" download="example.txt" href="data:text/plain,owned-test">Download example</a>
</body></html>'''


def workflow():
    return {'schema':'handnavigate.live.v1','name':'Test workflow','start_url':ORIGIN+'/form',
            'scope':Scope((ORIGIN,)).as_dict(),
            'steps':[{'op':'fill','locator':{'kind':'label','value':'Topic'},'value':{'parameter':'topic'}},
                     {'op':'click','locator':{'kind':'role','role':'button','name':'Prepare preview'}}],
            'checks':[{'kind':'text_visible','expected':'Ready: architecture'}]}


@pytest.fixture(scope='module')
def browser():
    with sync_playwright() as p:
        b=launch_browser(p,headless=True)
        yield b
        b.close()


@pytest.fixture
def driver(browser,tmp_path):
    context=browser.new_context(accept_downloads=True,service_workers='block')
    page=context.new_page()
    page.set_default_timeout(3000)
    page.set_content(HTML)
    d=Driver(page,Scope((ORIGIN,)),tmp_path,test_document=True)
    d.install_guard()
    yield d
    context.close()


def find(d,name):
    return next(x['id'] for x in d.latest['elements'] if x['name']==name)


def action(d,op,name=None,**kw):
    result={'op':op,'snapshot':d.latest['snapshot'],'reason':'Explicit test action',**kw}
    if name:
        result['target']=find(d,name)
    return result


@pytest.mark.parametrize('url',['file:///etc/passwd','javascript:alert(1)','https://u:p@owned.example','data:text/html,x','https://'])
def test_nonweb_or_credential_urls_rejected(url):
    with pytest.raises(LiveError): origin(url)


def test_scope_exact_and_requests():
    s=Scope((ORIGIN,))
    assert s.permits_request(ORIGIN+'/a','GET')
    assert not s.permits_request(ORIGIN+'/a','POST')
    assert not s.permits_request('https://owned.example.evil/a','GET')
    with pytest.raises(LiveError): s.check(ORIGIN+'/?token=secret')
    assert origin('https://OWNED.example:443/a')==ORIGIN


def test_evidence_urls_do_not_include_query_values():
    assert 'sensitive-search' not in public_url(ORIGIN+'/?q=sensitive-search#private')


@pytest.mark.parametrize('a',[{'op':'evaluate','value':'bad()'}, {'op':'check','target':'e0','checked':'false'},
    {'op':'wait','amount':100000}, {'op':'press','target':'e0','value':'Control+L'},
    {'op':'click','target':'#anything'}, {'op':'click','target':'e0','script':'bad()'}])
def test_unsafe_or_invalid_actions_rejected(a):
    with pytest.raises(LiveError):validate_action(a)


def test_approval_binds_recipe_and_inputs():
    w=workflow(); r=approval(w,{'topic':'architecture'})
    require_approval(w,{'topic':'architecture'},r)
    with pytest.raises(LiveError): require_approval(w,{'topic':'changed'},r)
    w['steps'][1]['locator']['name']='Delete'
    with pytest.raises(LiveError): require_approval(w,{'topic':'architecture'},r)


def test_missing_checks_not_approvable():
    w=workflow();w['checks']=[]
    with pytest.raises(LiveError):approval(w,{'topic':'architecture'})


def test_observation_contains_real_controls_and_screenshot(driver):
    obs=driver.observe()
    assert any(x['name']=='Topic' for x in obs['elements'])
    assert not any(x['name']=='Password' for x in obs['elements'])
    assert (driver.output/obs['screenshot']).is_file()
    assert obs['url']=='about:blank'


def test_fill_click_and_verify_real_dom(driver):
    driver.observe()
    driver.execute(action(driver,'fill','Topic',value='architecture'),lambda _:True)
    driver.execute(action(driver,'click','Prepare preview'),lambda _:True)
    assert driver.verify([{'kind':'text_visible','expected':'Ready: architecture'}])==[{'kind':'text_visible','passed':True}]
    assert len(driver.events)==2
    assert all(x.get('before') and x.get('after') for x in driver.events)


def test_select_check_press_scroll(driver):
    driver.observe()
    driver.execute(action(driver,'select','Mode',value='full'),lambda _:True)
    driver.execute(action(driver,'check','Captions',checked=True),lambda _:True)
    driver.execute(action(driver,'press','Topic',value='Tab'),lambda _:True)
    driver.execute(action(driver,'scroll',amount=100),lambda _:True)
    assert driver.page.locator('#mode').input_value()=='full'
    assert driver.page.get_by_label('Captions',exact=True).is_checked()


def test_stale_snapshot_rejected(driver):
    driver.observe();old=action(driver,'click','Prepare preview');driver.observe()
    with pytest.raises(LiveError,match='Stale'):driver.execute(old,lambda _:True)


def test_declined_action_no_effect(driver):
    driver.observe()
    with pytest.raises(LiveError,match='declined'):
        driver.execute(action(driver,'fill','Topic',value='changed'),lambda _:False)
    assert driver.page.get_by_label('Topic',exact=True).input_value()==''
    assert driver.action_count==0


def test_target_change_during_approval_rejected(driver):
    driver.observe()
    def approve(_):
        driver.page.locator('#preview').evaluate("el=>el.textContent='Delete record'")
        return True
    with pytest.raises(LiveError,match='changed while awaiting approval'):
        driver.execute(action(driver,'click','Prepare preview'),approve)
    assert driver.page.locator('#result').inner_text()==''


def test_ambiguous_replay_locator_rejected(driver):
    driver.page.evaluate("document.body.insertAdjacentHTML('beforeend','<button>Prepare preview</button>')")
    driver.observe()
    with pytest.raises(LiveError,match='ambiguous'):
        driver.bind_locator({'kind':'role','role':'button','name':'Prepare preview'})


def test_no_automated_password_interaction(driver):
    driver.observe()
    with pytest.raises(LiveError,match='Sensitive'):
        driver.bind_locator({'kind':'label','value':'Password'})


def test_replay_no_provider_calls(driver):
    w=workflow();r=approval(w,{'topic':'architecture'})
    with patch.object(GroqProvider,'complete',side_effect=AssertionError('Must not call AI')):
        result=replay(driver,w,{'topic':'architecture'},r)
    assert result['status']=='VERIFIED' and result['model_calls']==0
    assert driver.page.locator('#result').inner_text()=='Ready: architecture'


def test_replay_verification_failure_does_not_claim_success(driver):
    w=workflow();w['checks']=[{'kind':'download_count','expected':1}]
    result=replay(driver,w,{'topic':'architecture'},approval(w,{'topic':'architecture'}))
    assert result['status']=='HALTED'
    assert result['error_type']=='LiveError'


def test_download_and_revalidate_bytes(driver):
    driver.observe()
    driver.execute(action(driver,'download','Download example'),lambda _:True)
    driver.verify([{'kind':'download_count','expected':1}])
    item=driver.downloads[0]
    driver.verify([{'kind':'download_sha256','expected':item['sha256']}])
    (driver.output/item['file']).write_bytes(b'changed')
    with pytest.raises(LiveError,match='missing or changed'):
        driver.verify([{'kind':'download_count','expected':1}])


class ScriptedProvider:
    """Protocol test double. Not an LLM and not a model quality evaluation."""
    def __init__(self,driver):self.driver=driver;self.calls=0
    def complete(self,messages):
        choices=[('fill','Topic',{'value':'architecture'}),('click','Prepare preview',{}),('finish',None,{})]
        op,name,extra=choices[self.calls];self.calls+=1
        a=action(self.driver,op,name,**extra)
        return {'role':'assistant','content':None,'tool_calls':[{'id':str(self.calls),'type':'function',
                'function':{'name':'browser_action','arguments':json.dumps(a)}}]}


def test_tool_loop_executes_and_creates_replayable_draft(driver):
    provider=ScriptedProvider(driver)
    result=run_agent(driver,provider,start_url=ORIGIN+'/form',goal='Prepare architecture preview',
                     checks=workflow()['checks'],approve=lambda _:True)
    assert result['status']=='VERIFIED'
    assert result['model_calls']==3 and result['provider_test_double'] is True
    draft=json.loads((driver.output/'workflow.draft.json').read_text())
    assert len(draft['steps'])==2
    assert draft['provenance']['reviewed'] is False
    validate_workflow(draft)


def test_agent_finish_without_checks_is_unverified(driver):
    result=run_agent(driver,ScriptedProvider(driver),start_url=ORIGIN+'/form',goal='Prepare preview',checks=[],approve=lambda _:True)
    assert result['status']=='EXECUTED_UNVERIFIED'


def test_agent_prose_is_not_completion(driver):
    class Prose:
        def complete(self,messages):return {'role':'assistant','content':'Done!'}
    result=run_agent(driver,Prose(),start_url=ORIGIN+'/form',goal='Task',checks=[],approve=lambda _:True)
    assert result['status']=='HALTED'


def test_model_rejects_unconsented_data_transfer():
    with pytest.raises(LiveError,match='consent'):GroqProvider('test',consent=False,key='test-key')


def test_groq_transport_tool_protocol_without_network():
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,n):return json.dumps({'choices':[{'message':{'role':'assistant','content':'stop'}}],'usage':{'total_tokens':12}}).encode()
    captured=[]
    def fake_open(request,timeout):captured.append(request);return Response()
    with patch('handnavigate.live.agent.urlopen',side_effect=fake_open):
        p=GroqProvider('explicit-test-model',consent=True,key='not-a-live-key')
        p.complete([{'role':'user','content':'test'}])
    body=json.loads(captured[0].data)
    assert body['tools'][0]['function']['name']=='browser_action'
    assert 'response_format' not in body and body['parallel_tool_calls'] is False
    assert p.calls==1


def capture_fixture():
    return {'version':4,'name':'Synthetic importer fixture','targetUrl':ORIGIN+'/form',
            'flows':[{'id':'F001'}],'states':[],
            'actions':[{'id':'A1','flowId':'F001','kind':'input','value':'architecture',
                        'element':{'tag':'input','ariaLabel':'Topic','selector':'#topic'}},
                       {'id':'A2','flowId':'F001','kind':'change','value':'architecture',
                        'element':{'tag':'input','ariaLabel':'Topic','selector':'#topic'}},
                       {'id':'A3','flowId':'F001','kind':'click',
                        'element':{'tag':'button','text':'Prepare preview'}}]}


def test_import_deduplicates_identical_field_events_only():
    w,r=import_trustudio(capture_fixture())
    assert len(w['steps'])==2 and not r['blockers']
    assert w['checks']==[]
    with pytest.raises(LiveError):approval(w,{})


def test_import_preserves_distinct_values():
    c=capture_fixture();c['actions'][1]['value']='new topic'
    w,r=import_trustudio(c)
    assert len(w['steps'])==3


def test_import_private_and_checkbox_events_blocked():
    c=capture_fixture();c['actions'][0]['value']='[REDACTED]'
    c['actions'][1]['element']['type']='checkbox'
    w,r=import_trustudio(c)
    assert len(r['blockers'])==2 and w['provenance']['blockers']==2


def test_import_multiple_flows_require_selection():
    c=capture_fixture();c['flows'].append({'id':'F002'})
    with pytest.raises(LiveError):import_trustudio(c)


def test_recorder_preserves_fast_edits_and_checked_state(driver):
    captured=[]
    driver.page.expose_binding('__hnLiveRecord',lambda source,event:captured.append(event))
    driver.page.evaluate(instrumentation())
    driver.page.get_by_label('Topic',exact=True).fill('architecture')
    driver.page.get_by_label('Second field',exact=True).fill('second')
    driver.page.get_by_label('Captions',exact=True).check()
    driver.page.get_by_role('button',name='Prepare preview',exact=True).click()
    driver.page.wait_for_timeout(350)
    values=[e.get('value') for e in captured if e['op']=='fill']
    assert 'architecture' in values and 'second' in values
    assert any(e['op']=='check' and e['checked'] is True for e in captured)
    assert captured[-1]['op']=='click'


def test_recorder_does_not_send_password_value(driver):
    captured=[]
    driver.page.expose_binding('__hnLiveRecord',lambda source,event:captured.append(event))
    driver.page.evaluate(instrumentation())
    driver.page.get_by_label('Password',exact=True).fill('NEVER_STORE_THIS')
    driver.page.wait_for_timeout(300)
    assert 'NEVER_STORE_THIS' not in json.dumps(captured)
    assert any(e['op']=='blocked' for e in captured)


def test_compile_events_keeps_explicit_false():
    events=[{'op':'check','sequence':1,'url':ORIGIN+'/form','checked':False,
             'element':{'candidates':[{'kind':'label','value':'Captions'}]}}]
    w,r=compile_events(events,start_url=ORIGIN+'/form',scope=Scope((ORIGIN,)),checks=[])
    assert w['steps'][0]['checked'] is False


def test_unresolved_blockers_cannot_be_approved():
    w=workflow();w['provenance']={'blockers':1}
    with pytest.raises(LiveError,match='blockers'):approval(w,{'topic':'architecture'})


def test_public_demo_workflow_schema():
    root=Path(__file__).resolve().parents[2]
    w=json.loads((root/'examples/live-todomvc.workflow.json').read_text())
    values=json.loads((root/'examples/live-todomvc.inputs.json').read_text())
    validate_workflow(w,values)
    assert w['provenance']['live_execution_qualified'] is False


def test_page_text_change_before_approval_blocks_action(driver):
    driver.observe()
    def approve(_):
        driver.page.locator('h1').evaluate("el=>el.textContent='Different account'")
        return True
    with pytest.raises(LiveError,match='Page content'):
        driver.execute(action(driver,'click','Prepare preview'),approve)
    assert driver.action_count==0


def test_recorder_does_not_double_record_keyboard_button_activation(driver):
    captured=[]
    driver.page.expose_binding('__hnLiveRecord',lambda source,event:captured.append(event))
    driver.page.evaluate(instrumentation())
    driver.page.get_by_role('button',name='Prepare preview',exact=True).press('Enter')
    driver.page.wait_for_timeout(300)
    assert [e['op'] for e in captured]==['press']
