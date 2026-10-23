"""Create explicitly labeled component evidence; this is NOT live-site or real-model testing."""
from pathlib import Path
import json
import sys
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tests/live'))
from test_core import HTML, ORIGIN, ScriptedProvider, workflow
from handnavigate.runner import launch_browser
from handnavigate.live.browser import Driver
from handnavigate.live.contracts import Scope, approval, save_json
from handnavigate.live.agent import run_agent
from handnavigate.live.workflows import replay

out=ROOT/'evidence/live-core/measured-component-example'
with sync_playwright() as p:
    browser=launch_browser(p,headless=True)
    c=browser.new_context(service_workers='block')
    page=c.new_page();page.set_content(HTML)
    d=Driver(page,Scope((ORIGIN,)),out/'scripted-tool-loop',test_document=True);d.install_guard()
    loop=run_agent(d,ScriptedProvider(d),start_url=ORIGIN+'/form',goal='Explicit offline scripted-provider test',
                   checks=workflow()['checks'],approve=lambda _:True)
    draft=json.loads((d.output/'workflow.draft.json').read_text())
    c.close()
    c=browser.new_context(service_workers='block')
    page=c.new_page();page.set_content(HTML)
    d=Driver(page,Scope((ORIGIN,)),out/'no-ai-replay',test_document=True);d.install_guard()
    result=replay(d,draft,{},approval(draft,{}))
    c.close();browser.close()
    summary={'scope':'Offline owned HTML loaded with set_content; scripted tool provider, not a live LLM',
             'third_party_navigation':False,'real_provider_requests':0,'tool_loop':loop,'deterministic_replay':result}
    save_json(out/'summary.json',summary)
    print(json.dumps(summary,indent=2))
    if loop['status']!='VERIFIED' or result['status']!='VERIFIED':raise SystemExit(2)
