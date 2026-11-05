"""Opt-in real Ollama acceptance. Uses disposable files and owned HTTP sites only."""
from __future__ import annotations
import argparse
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT.parent),str(ROOT/'tests')]
from core.llm import Ollama
from core.models import Permissions
from core.policy import Policy
from core.runtime import Runner
from core.storage import Store
from test_browser import BrowserTests


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--model',default='qwen3.5:4b')
    parser.add_argument('--output',default=str(ROOT/'evidence'/'local-model.json'))
    parser.add_argument('--skip-browser',action='store_true')
    parser.add_argument('--include-instagram-syntax',action='store_true',help='Parser-only legacy case; no account access')
    args=parser.parse_args()
    llm=Ollama(args.model)
    report={'checked_at':datetime.now(timezone.utc).isoformat(),'model':args.model,
            'scope':'Real local inference; disposable cleanup and owned HTTP browser tasks; no Instagram connection',
            'health':llm.health(),'checks':[]}
    fixture=BrowserTests();fixture.setUp()
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    def save():output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    def check(name,operation):
        started=time.monotonic()
        try:
            data=operation()
            result={'name':name,'passed':True,'seconds':round(time.monotonic()-started,2),'metrics':dict(llm.last_metrics),**data}
        except Exception as error:
            result={'name':name,'passed':False,'seconds':round(time.monotonic()-started,2),'error':str(error),
                    'observed_output':llm.last_output,'metrics':dict(llm.last_metrics)}
        report['checks'].append(result);save()
        print(json.dumps(result),flush=True)
    def require(condition,message):
        if not condition:raise AssertionError(message)
    try:
        with tempfile.TemporaryDirectory(prefix='handnavigate-real-model-') as folder:
            files=Path(folder)/'cleanup';files.mkdir()
            policy=Permissions(cleanup_roots=[str(files)],browser_origins=[fixture.origin],allow_upload=True,allow_browser_changes=True)
            def cleanup_plan():
                instruction=f'Every day at 18:00 Asia/Kolkata recycle only *.tmp files older than 7 days in the exact folder {files}. No subfolders. At most 3 files.'
                plan=llm.plan(instruction,policy)
                require(plan.kind=='cleanup' and plan.folder==str(files),'Wrong cleanup task or folder')
                require(plan.pattern=='*.tmp' and plan.older_than_days==7 and plan.max_items==3,'Wrong cleanup bounds')
                require(plan.schedule is not None and plan.schedule.time=='18:00' and plan.schedule.timezone=='Asia/Kolkata','Wrong schedule')
                Policy(policy).plan(plan)
                target=files/'discard.tmp';target.write_text('Disposable model acceptance file')
                old=time.time()-8*86400;os.utime(target,(old,old))
                keep=files/'keep.txt';keep.write_text('Must remain')
                store=Store(Path(folder)/'cleanup-state');store.set_setting('permissions',policy.model_dump())
                result=Runner(store,llm,headless=True).run(store.save(plan)['id'])
                require(result['status']=='VERIFIED' and not target.exists() and keep.exists(),'Cleanup execution did not match the instruction')
                return {'plan':plan.model_dump(),'execution':{'status':result['status'],'matched':result['matched']}}
            check('instruction_to_verified_disposable_cleanup',cleanup_plan)
            def missing():
                plan=llm.plan('Delete old files every day. I have not provided the folder, age, filename pattern or daily time.',policy)
                require(bool(plan.missing_information),'Model invented missing task details')
                return {'missing_information':plan.missing_information}
            check('missing_information_is_not_invented',missing)
            def download():
                plan=llm.plan(f'Download exactly 2 images from {fixture.origin}/source now. The image selector is img. Save locally; do not upload or schedule.',policy)
                require(plan.kind=='images' and plan.start_url==fixture.origin+'/source' and plan.max_items==2,'Wrong download target or count')
                require(not plan.upload_url and plan.schedule is None and not plan.missing_information,'Invented upload or schedule')
                store=Store(Path(folder)/'download-state');store.set_setting('permissions',policy.model_dump())
                result=Runner(store,llm,headless=True).run(store.save(plan)['id'])
                require(result['status']=='VERIFIED' and result['downloaded']==2,'Real model plan did not produce two decoded images')
                return {'plan':plan.model_dump(),'execution':{'status':result['status'],'downloaded':result['downloaded']}}
            check('instruction_to_verified_image_download',download)
            def transfer():
                instruction=f'Download exactly 2 images from {fixture.origin}/source using img, then upload them to {fixture.origin}/upload using input[type=file] and the button named Send. Verify originals at {fixture.origin}/gallery using img. Expected visible account text is owned account. Run once now, no schedule.'
                plan=llm.plan(instruction,policy)
                require(plan.kind=='images' and plan.max_items==2 and plan.start_url==fixture.origin+'/source','Wrong transfer source/count')
                require(plan.upload_url==fixture.origin+'/upload' and plan.gallery_url==fixture.origin+'/gallery','Wrong transfer destination')
                require(plan.account_marker=='owned account' and plan.submit_name=='Send' and plan.schedule is None,'Wrong destination assertion or schedule')
                store=Store(Path(folder)/'transfer-state');store.set_setting('permissions',policy.model_dump())
                result=Runner(store,llm,headless=True).run(store.save(plan)['id'])
                require(result['status']=='VERIFIED' and len(fixture.uploads)==2,'Real model plan failed upload/read-back')
                return {'plan':plan.model_dump(),'execution':{'status':result['status'],'confirmed':result['confirmed']}}
            check('instruction_to_verified_image_transfer',transfer)
            def instagram():
                plan=llm.plan('Every day at 20:00 Asia/Kolkata like at most 5 unliked posts on my own profile https://www.instagram.com/agent_acceptance_demo/. My username is agent_acceptance_demo.',policy)
                require(plan.kind=='instagram_like_own' and plan.start_url=='https://www.instagram.com/agent_acceptance_demo/' and plan.account_marker=='agent_acceptance_demo','Wrong own-profile task')
                require(plan.max_items==5 and plan.schedule is not None and plan.schedule.time=='20:00','Wrong like count or schedule')
                return {'plan':plan.model_dump(),'execution':'not executed; parser acceptance only, no Instagram request'}
            if args.include_instagram_syntax:check('own_profile_instruction_parsing_only',instagram)
            if not args.skip_browser:
                def browser():
                    instruction=f'Open {fixture.origin}/task, verify the visible account text owned account, and click Save. The goal is to save the owned item. The exact result selector is #result and the expected new text is done. Run once now, no schedule, at most 6 browser actions.'
                    plan=llm.plan(instruction,policy)
                    require(plan.kind=='browser' and plan.start_url==fixture.origin+'/task' and plan.account_marker=='owned account','Wrong browser task target/account')
                    require(plan.result_selector=='#result' and plan.expected_result=='done','Missing independent result verifier')
                    plan=plan.model_copy(update={'max_steps':min(plan.max_steps,6)})
                    store=Store(Path(folder)/'browser-state');store.set_setting('permissions',policy.model_dump())
                    result=Runner(store,llm,headless=True).run(store.save(plan)['id'])
                    require(result['status']=='VERIFIED','Real model browser loop did not create the independently checked result: '+json.dumps(result))
                    with store.db() as db:events=[json.loads(row[0]) for row in db.execute('SELECT data FROM events')]
                    return {'plan':plan.model_dump(),'execution':result,'actions':events}
                check('real_model_browser_actions_and_fresh_result',browser)
    finally:
        fixture.doCleanups()
        report['passed']=sum(c['passed'] for c in report['checks'])
        report['total']=len(report['checks']);save()
    raise SystemExit(0 if report['passed']==report['total'] else 2)


if __name__=='__main__':main()
