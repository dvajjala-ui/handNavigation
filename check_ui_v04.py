"""Rendered UI checks and screenshots. No browser HTTP access is bypassed.

Read-only preview is loaded directly. Editable controls are checked with an
in-memory fetch stub; actual API/runner integration is tested separately.
"""
from datetime import datetime, timezone
import json
from pathlib import Path

from playwright.sync_api import sync_playwright
from handnavigate.runner import launch_browser

ROOT = Path(__file__).resolve().parent
OUT = Path('/mnt/data') if Path('/mnt/data').is_dir() else ROOT / 'deliverables'
OUT.mkdir(parents=True, exist_ok=True)
checks = []


def check(name, result, scope='rendered read-only preview'):
    checks.append({'name': name, 'passed': bool(result), 'scope': scope})
    if not result:
        raise AssertionError(name)


def main():
    state = json.loads((ROOT/'evidence/v04-preview-state.json').read_text())
    evidence = json.loads((ROOT/'evidence/test-results.json').read_text())
    source = (ROOT/'ui/index.html').read_text().replace('__CSRF_TOKEN__','UI_TEST_TOKEN')
    errors, requests = [], []
    with sync_playwright() as p:
        browser = launch_browser(p)
        page = browser.new_page(viewport={'width':1480,'height':1060}, device_scale_factor=1)
        page.emulate_media(reduced_motion='reduce')
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('request', lambda r: requests.append(r.url))
        page.set_content((ROOT/'ui/read-only-preview.html').read_text(), wait_until='load')
        page.locator('#metric-files').filter(has_text='10 / 10').wait_for()
        check('Measured ten-file result displayed', page.locator('#metric-files').inner_text()=='10 / 10')
        check('Preview cannot run a workflow', page.locator('#run').is_disabled())
        check('Preview has an explicit read-only notice', page.locator('#preview-banner').is_visible())
        check('Preview does not claim worker is online', page.locator('#worker-label').inner_text()=='Recorded local evidence')
        check('Desktop layout has no horizontal overflow', page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
        page.screenshot(path=str(OUT/'HandNavigate_v0.4_Studio.png'), full_page=True)
        page.screenshot(path=str(ROOT/'ui/preview.png'), full_page=True)
        for view in ('teaching','schedules','connections','activity','evidence','overview'):
            page.locator('nav [data-view="'+view+'"]').click()
            check('Navigation: '+view, page.locator('#'+view).is_visible())
            if view in ('teaching','schedules','connections'):
                page.screenshot(path=str(ROOT/'evidence'/('v04-'+view+'.png')),full_page=True)
        page.set_viewport_size({'width':390,'height':844})
        check('Phone layout has no horizontal overflow', page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
        check('Phone run button remains disabled in preview', page.locator('#run').is_disabled())
        page.screenshot(path=str(OUT/'HandNavigate_v0.4_Mobile.png'),full_page=True)
        page.screenshot(path=str(ROOT/'evidence/v04-mobile.png'),full_page=True)
        for view in ('teaching','schedules','connections','activity','evidence'):
            page.locator('nav [data-view="'+view+'"]').click()
            check('Phone overflow: '+view, page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
        page.locator('nav [data-view="connections"]').click()
        q=state['qualification']; component_passes=sum(x['status']=='PASS' for x in q['checks'] if 'real browser' not in x['layer'])
        expected_browser='Policy blocked' if q['browser_probe']['status']=='BLOCKED' else ('Owned flow passed' if q['browser_workflow'].get('status')=='VERIFIED_EXPORT' else 'Not qualified')
        check('Browser outcome visibly distinguished from HTTP component success', page.locator('#browser-verdict').inner_text()==expected_browser and page.locator('#component-verdict').inner_text()==str(component_passes)+' checks passed')
        check('Imported profile is not shown as qualified', 'AWAITING REVIEW' in page.locator('#connection-list').inner_text())
        check('No stored session invented in preview', 'No encrypted session stored' in page.locator('#connection-list').inner_text())
        check('Read-only preview cannot approve connection', page.locator('[data-approve-connection]').is_disabled())
        check('Read-only preview cannot change connection consent', page.locator('[data-connection-check]').is_disabled())
        check('Credentials entry not present in studio', page.locator('input[type="password"]').count()==0)
        page.screenshot(path=str(OUT/'HandNavigate_v0.4_Connections_Mobile.png'),full_page=True)
        page.set_viewport_size({'width':1480,'height':1060})
        page.screenshot(path=str(OUT/'HandNavigate_v0.4_Connections.png'),full_page=True)
        check('No external browser requests from preview', len(requests)==0)
        page.close()
        # No requests leave the browser: this is a UI contract harness, not HTTP testing.
        payload=json.dumps({'state':state,'evidence':evidence}).replace('<','\\u003c')
        stub='''<script>
window.__uiData=PAYLOAD; window.__requests=[];
window.fetch=async (path,options={})=>{
 const body=options.body?JSON.parse(options.body):undefined;
 window.__requests.push({path,body,method:options.method||'GET'});
 let result=path==='/api/evidence'?window.__uiData.evidence:window.__uiData.state;
 if(body!==undefined){result={ok:true};if(path==='/api/schedules/preview')result={occurrences:[{utc:'2026-10-24T02:30:00+00:00',local:'2026-10-24T08:00:00+05:30'}]};}
 return {ok:true,json:async()=>result};
};</script>'''.replace('PAYLOAD',payload)
        page=browser.new_page(viewport={'width':1440,'height':1024})
        page.emulate_media(reduced_motion='reduce')
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content(source.replace('<head>','<head>'+stub,1),wait_until='load')
        page.locator('#metric-files').filter(has_text='10 / 10').wait_for()
        scope='editable UI with in-memory API stub; no network'
        check('Rehearsal requires unchecked-by-default review',page.locator('#run').is_disabled(),scope)
        page.locator('#review').check()
        check('Reviewed rehearsal becomes enabled',page.locator('#run').is_enabled(),scope)
        page.locator('#topic').fill('city gardens')
        page.locator('#limit').fill('3')
        page.locator('#run').click()
        page.wait_for_function('window.__requests.some(x=>x.path==="/api/run")')
        request=page.evaluate('window.__requests.find(x=>x.path==="/api/run")')
        check('Run payload binds topic, count and exact checksum', request['body']['topic']=='city gardens' and request['body']['limit']==3 and request['body']['reviewed_sha256']==state['recipe_sha256'],scope)
        page.locator('nav [data-view="schedules"]').click()
        check('Schedule consent is initially required',page.locator('#create-schedule').is_disabled(),scope)
        page.locator('#preview-schedule').click()
        page.locator('#schedule-preview').wait_for(state='visible')
        check('Schedule preview displays explicit timezone offset','+05:30' in page.locator('#schedule-preview').inner_text(),scope)
        page.locator('#schedule-review').check()
        page.locator('#create-schedule').click()
        page.wait_for_function('window.__requests.some(x=>x.path==="/api/schedules")')
        request=page.evaluate('window.__requests.find(x=>x.path==="/api/schedules")')
        check('Daily schedule request preserves IANA timezone and policy',request['body']['spec']['timezone']=='Asia/Kolkata' and request['body']['spec']['misfire']=='run_once',scope)
        page.locator('nav [data-view="teaching"]').click()
        page.locator('#load-example').click()
        check('Sample trace is explicitly labeled synthetic','not recorded from your actions' in page.locator('#recording-origin').inner_text(),scope)
        page.locator('#append-collection').check()
        page.locator('#compile').click()
        page.wait_for_function('window.__requests.some(x=>x.path==="/api/drafts/compile")')
        request=page.evaluate('window.__requests.find(x=>x.path==="/api/drafts/compile")')
        check('Compiler request records explicit effect-contract selection',request['body']['append_collection'] is True and len(request['body']['events'])==2,scope)
        page.locator('#load-recipe').click()
        editor=json.loads(page.locator('#recipe-editor').input_value())
        check('Editor starts a new revision, not an in-place edit',editor['revision']==state['recipe']['revision']+1,scope)
        page.locator('#save-draft').click()
        page.wait_for_function('window.__requests.some(x=>x.path==="/api/drafts")')
        request=page.evaluate('window.__requests.find(x=>x.path==="/api/drafts")')
        check('Editor uses optimistic base-checksum validation',request['body']['base_sha256']==state['recipe_sha256'],scope)
        page.locator('#recipe-code').scroll_into_view_if_needed()
        page.wait_for_timeout(100)
        page.locator('nav [data-view="connections"]').click()
        check('Unreviewed profile approval disabled in live UI',page.locator('[data-approve-connection]').is_disabled(),scope)
        page.locator('[data-connection-check]').check()
        check('Explicit permission acknowledgement enables exact approval',page.locator('[data-approve-connection]').is_enabled(),scope)
        page.locator('[data-approve-connection]').click()
        page.wait_for_function('window.__requests.some(x=>x.path==="/api/connections/approve")')
        payload=page.evaluate('window.__requests.find(x=>x.path==="/api/connections/approve").body')
        check('Connection approval binds profile checksum and permission acknowledgement',payload['reviewed_sha256']==state['connections'][0]['sha256'] and payload['permission_confirmed'] is True,scope)
        page.locator('#load-connection-example').click()
        check('Loaded example contains no authentication state','cookies' not in page.locator('#connection-json').input_value(),scope)
        page.locator('#save-connection').click()
        page.wait_for_function('window.__requests.some(x=>x.path==="/api/connections")')
        payload=page.evaluate('window.__requests.find(x=>x.path==="/api/connections").body')
        check('Import sends contract only, without sign-in or execution',payload['profile']['id']=='owned-report-portal' and payload['base_sha256'] is None,scope)
        check('No JavaScript runtime errors',not errors,'both rendered modes')
        browser.close()
    report={'generated_at':datetime.now(timezone.utc).isoformat(),'checks':checks,
            'passed':sum(x['passed'] for x in checks),'failed':sum(not x['passed'] for x in checks),
            'javascript_errors':errors,'preview_network_requests':requests,
            'limitations':['Browser HTTP navigation is blocked; this does not bypass that policy.',
                           'Editable controls use an in-memory fetch stub. Real localhost API integration is in run_tests.py.',
                           'Phone viewport emulation is not a native mobile app or device qualification.']}
    (ROOT/'evidence/v04-ui-checks.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({'passed':report['passed'],'failed':report['failed'],'javascript_errors':errors},indent=2))





def check_teaching():
    from handnavigate.studio import teaching_html
    proof = json.loads((ROOT / 'evidence/v04-teaching-demonstration.json').read_text())
    checks, errors, requests = [], [], []
    def check(name, passed, scope):
        checks.append({'name': name, 'passed': bool(passed), 'scope': scope})
        if not passed:
            raise AssertionError(name)
    with sync_playwright() as p:
        browser = launch_browser(p)
        page = browser.new_page(viewport={'width':1440, 'height':1000})
        page.emulate_media(reduced_motion='reduce')
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('request', lambda request: requests.append(request.url))
        page.set_content((ROOT/'ui/teaching-read-only-preview.html').read_text(), wait_until='load')
        page.locator('#metric-rows').filter(has_text='3 / 3').wait_for()
        scope = 'read-only rendered evidence, no API or browser HTTP'
        check('Three verified rows displayed from real report',page.locator('#metric-rows').inner_text()=='3 / 3',scope)
        check('Zero model calls displayed from real report',page.locator('#metric-models').inner_text()=='0',scope)
        check('Read-only notice is visible',page.locator('#preview-notice').is_visible(),scope)
        check('Read-only preview cannot run a lesson',page.locator('#run-lesson').is_disabled(),scope)
        check('Read-only preview cannot grant plan consent',page.locator('#plan-consent').is_disabled(),scope)
        check('Wrong-output halt remains visible with verified run','HALTED' in page.locator('#run-history').inner_text() and 'VERIFIED' in page.locator('#run-history').inner_text(),scope)
        check('Plan contains the reviewed false checkbox state','captions off' in page.locator('#plan-summary').inner_text(),scope)
        for stage in ['record','review','rehearse']:
            page.locator('[data-stage="'+stage+'"]').click()
            check('Stage navigation '+stage,page.locator('#stage-'+stage).is_visible(),scope)
            check('Desktop fits '+stage,page.evaluate('document.documentElement.scrollWidth<=innerWidth'),scope)
            if stage=='record':
                check('Read-only practice action is disabled',page.get_by_role('button',name='Prepare preview',exact=True).is_disabled(),scope)
            page.screenshot(path=str(OUT/('HandNavigate_v0.4_'+{'record':'Record','review':'Review','rehearse':'Rehearsal'}[stage]+'.png')),full_page=True)
        page.screenshot(path=str(ROOT/'evidence/v04-teaching-desktop.png'),full_page=True)
        for width in [390,320,768]:
            page.set_viewport_size({'width':width,'height':844})
            for stage in ['record','review','rehearse']:
                page.locator('[data-stage="'+stage+'"]').click()
                check(f'{width}px fits {stage}',page.evaluate('document.documentElement.scrollWidth<=innerWidth'),scope)
            if width==390:
                page.screenshot(path=str(OUT/'HandNavigate_v0.4_Teaching_Mobile.png'),full_page=True)
                page.screenshot(path=str(ROOT/'evidence/v04-teaching-mobile.png'),full_page=True)
        check('Read-only preview issues no requests',not requests,scope)
        page.close()
        # UI contract testing only. This stub never proxies or sends HTTP requests.
        data=json.dumps({'lesson':proof['state']['lessons'][0], 'plan':proof['plan']}).replace('<','\\u003c')
        stub=r'''<script>
window.__fixture=PAYLOAD;window.__requests=[];
window.__state={lessons:[],runs:[],active_id:null,error:null};
window.fetch=async(path,options={})=>{
 const body=options.body?JSON.parse(options.body):null;
 window.__requests.push({path,body});
 let result=window.__state;
 if(path==='/api/teaching/compile'){
   const lesson=JSON.parse(JSON.stringify(window.__fixture.lesson));lesson.approved=false;
   window.__state.lessons=[lesson];result=lesson;
 }else if(path==='/api/teaching/approve'){
   window.__state.lessons[0].approved=true;result=window.__state.lessons[0];
 }else if(path==='/api/teaching/plan'){
   result=JSON.parse(JSON.stringify(window.__fixture.plan));
   result.rows=body.rows.map(row=>({row_id:row.row_id,expected:row.values,actions:[]}));
   result.row_count=body.rows.length;result.action_count=4*body.rows.length;result.assertion_count=3*body.rows.length;
   result.plan_sha256='ui-stub-plan-'+window.__requests.length;
 }else if(path==='/api/teaching/run'){
   window.__state.active_id='ui-test-run';result={run_id:'ui-test-run',state:'RUNNING',deduplicated:false};
 }else if(path==='/api/teaching/stop'){
   window.__state.active_id=null;result={stop_requested:true};
 }
 return {ok:true,json:async()=>JSON.parse(JSON.stringify(result))};
};</script>'''.replace('PAYLOAD',data)
        source=teaching_html('UI_TEST_TOKEN')
        page=browser.new_page(viewport={'width':1440,'height':1000})
        page.emulate_media(reduced_motion='reduce')
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content(source.replace('<head>','<head>'+stub,1),wait_until='load')
        scope='editable UI with in-memory API stub; actual DOM recording, no server execution'
        check('Recording requires unchecked consent',page.locator('#record-start').is_disabled(),scope)
        page.locator('#record-consent').check();page.locator('#record-start').click()
        check('Recording indicator is active',page.locator('#record-status').inner_text()=='Recording',scope)
        page.get_by_label('Topic',exact=True).fill('architecture')
        page.get_by_label('Layout',exact=True).select_option('detailed')
        page.get_by_label('Include captions',exact=True).check()
        page.get_by_role('button',name='Prepare preview',exact=True).click()
        page.locator('#record-stop').click()
        check('All four actual DOM actions appear in timeline',page.locator('#event-list .event').count()==4,scope)
        page.screenshot(path=str(ROOT/'evidence/v04-recording-ui-harness.png'),full_page=True)
        page.locator('#continue-review').click()
        check('Compilation needs explicit verifier choice',page.locator('#compile-lesson').is_disabled(),scope)
        page.locator('#verifier-consent').check();page.locator('#compile-lesson').click()
        page.wait_for_function('window.__requests.some(r=>r.path==="/api/teaching/compile")')
        body=page.evaluate('window.__requests.find(r=>r.path==="/api/teaching/compile").body')
        check('Compilation sends four events and typed checkbox',len(body['events'])==4 and body['events'][2]['value'] is True,scope)
        check('Compilation sends explicit bindings and verification contract',body['bindings']['topic']=={'mode':'variable','name':'topic'} and body['verification_contract']=='inputs_match_preview_v1',scope)
        check('Approval remains unchecked after compile',page.locator('#approve-lesson').is_disabled(),scope)
        page.locator('#approval-consent').check();page.locator('#approve-lesson').click()
        page.wait_for_function('window.__requests.some(r=>r.path==="/api/teaching/approve")')
        body=page.evaluate('window.__requests.find(r=>r.path==="/api/teaching/approve").body')
        check('Approval submits exact checksum and acknowledgement',body['reviewed_sha256']==proof['recipe_sha256'] and body['acknowledgement'] is True,scope)
        page.locator('#to-rehearse').click();page.locator('#demo-rows').click()
        check('Demo inputs are editable row records',page.locator('.row-editor .row-top').count()==3,scope)
        page.locator('#preview-plan').click()
        check('Execution still requires input-plan consent',page.locator('#run-lesson').is_disabled(),scope)
        page.locator('#plan-consent').check()
        check('Reviewed recipe and input plan enable run',page.locator('#run-lesson').is_enabled(),scope)
        page.locator('[data-row="0"][data-key="topic"]').fill('changed topic')
        check('Editing input clears plan review and disables run',page.locator('#run-lesson').is_disabled() and not page.locator('#plan-consent').is_checked(),scope)
        page.locator('#preview-plan').click();page.locator('#plan-consent').check();page.locator('#run-lesson').click()
        page.wait_for_function('window.__requests.some(r=>r.path==="/api/teaching/run")')
        body=page.evaluate('window.__requests.find(r=>r.path==="/api/teaching/run").body')
        check('Run uses the current rows and a unique request ID',body['rows'][0]['values']['topic']=='changed topic' and len(body['request_id'])==36,scope)
        check('Accepted plan cannot be submitted again with a second click',page.locator('#run-lesson').is_disabled(),scope)
        check('Active batch exposes stop',page.locator('#stop-lesson').is_enabled(),scope)
        page.locator('#stop-lesson').click()
        page.wait_for_function('window.__requests.some(r=>r.path==="/api/teaching/stop")')
        check('Stop names the actual active run',page.evaluate('window.__requests.find(r=>r.path==="/api/teaching/stop").body.run_id')=='ui-test-run',scope)
        page.locator('[data-stage="review"]').click()
        page.evaluate('window.__state.lessons[0].recipe.name="<img src=x onerror=window.XSS_TEST=1>"')
        page.wait_for_function('document.querySelector("#recipe-summary").textContent.includes("<img")',timeout=5000)
        check('Lesson name is escaped, not executed as markup',page.locator('#recipe-summary img').count()==0 and page.evaluate('window.XSS_TEST===undefined'),scope)
        check('No JavaScript runtime errors in either mode',not errors,'all teaching UI checks')
        browser.close()
    report={'generated_at':datetime.now(timezone.utc).isoformat(),'checks':checks,
            'passed':sum(c['passed'] for c in checks),'failed':sum(not c['passed'] for c in checks),
            'javascript_errors':errors,'preview_requests':requests,
            'limitations':['Editable UI uses an in-memory API stub, not browser HTTP.',
                           'Actual HTTP API integration is separately tested by test_v04.py.',
                           'Automated browser interactions are not a human usability study.',
                           'Phone-width rendering is not native mobile automation.']}
    (ROOT/'evidence/v04-teaching-ui-checks.json').write_text(json.dumps(report,indent=2))
    legacy=json.loads((ROOT/'evidence/v04-ui-checks.json').read_text())
    combined={'passed':legacy['passed']+report['passed'],'failed':legacy['failed']+report['failed'],
              'studio_checks':legacy['passed'],'teaching_checks':report['passed'],
              'javascript_errors':legacy['javascript_errors']+errors}
    (ROOT/'evidence/v04-combined-ui-checks.json').write_text(json.dumps(combined,indent=2))
    print(json.dumps(combined,indent=2))


if __name__=='__main__':
    main()
    check_teaching()
