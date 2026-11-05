from __future__ import annotations
import argparse
import json
import os
import sys
import threading
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent))
from core.models import Permissions
from core.storage import Store
from core.llm import Ollama
from core.runtime import ProcessLock, Runner


def main():
    parser=argparse.ArgumentParser(description='HandNavigate Windows local-agent core')
    default_data=Path(os.environ.get('LOCALAPPDATA',str(ROOT)))/'HandNavigateAgent' if getattr(sys,'frozen',False) else ROOT/'runtime'/'data'
    parser.add_argument('--data',default=str(default_data))
    parser.add_argument('--headless',action='store_true')
    parser.add_argument('--channel',default='chrome')
    commands=parser.add_subparsers(dest='command',required=True)
    serve=commands.add_parser('serve');serve.add_argument('--port',type=int,default=47841);serve.add_argument('--open-ui',action='store_true')
    commands.add_parser('doctor')
    plan=commands.add_parser('plan');plan.add_argument('instruction')
    run=commands.add_parser('run');run.add_argument('id');run.add_argument('--request-id')
    login=commands.add_parser('login');login.add_argument('url')
    if len(sys.argv)==1:sys.argv.extend(['serve','--open-ui'])
    args=parser.parse_args()
    store=Store(args.data);llm=Ollama(store.setting('model','qwen3.5:4b'))
    if args.command=='doctor':
        report={'platform':sys.platform,'python':sys.version.split()[0],'data':str(store.folder),'model':llm.model}
        try:report['ollama']=llm.health()
        except Exception as error:report['ollama_error']=str(error)
        print(json.dumps(report,indent=2));return
    if args.command=='plan':
        print(llm.plan(args.instruction,Permissions.model_validate(store.setting('permissions',{}))).model_dump_json(indent=2));return
    with ProcessLock(store.folder):
        store.recover()
        runner=Runner(store,llm,args.headless,args.channel)
        if args.command=='run':
            result=runner.run(args.id,args.request_id);print(json.dumps(result,indent=2))
            if result['status']!='VERIFIED':sys.exit(2)
            return
        if args.command=='login':
            runner.policy().url(args.url)
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser=p.chromium.launch_persistent_context(str(store.folder/'browser-profile'),headless=False,channel=args.channel or None)
                page=browser.pages[0] if browser.pages else browser.new_page();page.goto(args.url)
                print('Sign in manually, then close the browser window. Credentials are not sent to the model.',flush=True)
                while browser.pages:
                    try:browser.pages[0].wait_for_timeout(500)
                    except Exception:break
                browser.close()
            return
        from core.server import create_server
        server=create_server(store,runner,llm,args.port)
        stopped=threading.Event()
        def schedule_loop():
            while not stopped.wait(5):
                try:runner.tick()
                except Exception as error:store.event(None,{'scheduler_error':str(error)})
        scheduler=threading.Thread(target=schedule_loop,daemon=True);scheduler.start()
        print('Open http://127.0.0.1:'+str(server.server_port),flush=True)
        if args.open_ui:
            import webbrowser
            threading.Timer(.5,lambda:webbrowser.open('http://127.0.0.1:'+str(server.server_port))).start()
        try:server.serve_forever(poll_interval=.5)
        except KeyboardInterrupt:pass
        finally:
            stopped.set();runner.cancel.set();server.server_close()
            # Wait for effects to settle before releasing the data-folder lock.
            while runner.busy.locked():time.sleep(.2)


if __name__=='__main__':main()
