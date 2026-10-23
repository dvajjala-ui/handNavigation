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
    state = json.loads((ROOT/'evidence/v03-preview-state.json').read_text())
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
        page.screenshot(path=str(OUT/'HandNavigate_v0.3_Studio.png'), full_page=True)
        page.screenshot(path=str(ROOT/'ui/preview.png'), full_page=True)
        for view in ('teaching','schedules','connections','activity','evidence','overview'):
            page.locator('nav [data-view="'+view+'"]').click()
            check('Navigation: '+view, page.locator('#'+view).is_visible())
            if view in ('teaching','schedules','connections'):
                page.screenshot(path=str(ROOT/'evidence'/('v03-'+view+'.png')),full_page=True)
        page.set_viewport_size({'width':390,'height':844})
        check('Phone layout has no horizontal overflow', page.evaluate('document.documentElement.scrollWidth <= innerWidth'))
        check('Phone run button remains disabled in preview', page.locator('#run').is_disabled())
        page.screenshot(path=str(OUT/'HandNavigate_v0.3_Mobile.png'),full_page=True)
        page.screenshot(path=str(ROOT/'evidence/v03-mobile.png'),full_page=True)
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
        page.screenshot(path=str(OUT/'HandNavigate_v0.3_Connections_Mobile.png'),full_page=True)
        page.set_viewport_size({'width':1480,'height':1060})
        page.screenshot(path=str(OUT/'HandNavigate_v0.3_Connections.png'),full_page=True)
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
    (ROOT/'evidence/v03-ui-checks.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({'passed':report['passed'],'failed':report['failed'],'javascript_errors':errors},indent=2))


if __name__=='__main__':
    main()
