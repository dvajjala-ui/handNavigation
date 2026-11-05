"""Remote Pinterest collector. Optional saved session; no alternate source or upload."""
from __future__ import annotations
import argparse
import json
import os
import platform
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlsplit

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT.parent)]
from core.browser import Browser, LIMITS
from core.models import Permissions, Plan
from core.policy import Policy, checked_path
from core.runtime import ProcessLock
from handnavigate.transfer.files import image_metadata

ORIGINS=['https://www.pinterest.com','https://in.pinterest.com','https://s.pinimg.com','https://s1.pinimg.com','https://s2.pinimg.com']
IMAGE_ORIGINS=['https://i.pinimg.com']


def source_url(topic,page_url=''):
    if not page_url:
        return 'https://www.pinterest.com/search/pins/?'+urlencode({'q':topic})
    parsed=urlsplit(page_url)
    if (parsed.scheme!='https' or parsed.netloc not in ('www.pinterest.com','in.pinterest.com')
        or parsed.username or parsed.password or parsed.fragment or parsed.path in ('','/')):
        raise ValueError('Choose an exact public HTTPS Pinterest page without credentials, ports or fragments.')
    return page_url


def verified_inventory(folder,items,expected):
    files=list(folder.glob('*'))
    actual={p.name for p in files if p.is_file() and p.suffix.lower() in ('.jpg','.jpeg','.png','.webp')}
    hashes=set()
    for item in items:
        file=checked_path(item['file'])
        if not file.is_relative_to(folder.resolve()):raise ValueError('Image path left the chosen result folder.')
        meta=image_metadata(file.read_bytes(),LIMITS)
        if meta['sha256']!=item['sha256']:raise ValueError('Image changed before final verification.')
        if meta['sha256'] in hashes:raise ValueError('Duplicate bytes in result folder.')
        hashes.add(meta['sha256'])
    if actual!={Path(i['file']).name for i in items}:raise ValueError('Result files differ from the manifest.')
    return len(hashes)==expected


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--topic',default='nature landscape')
    parser.add_argument('--page-url',default='',help='An exact public Pinterest board/page; no login is attempted')
    parser.add_argument('--profile-data',default='',help='Existing VM data folder after the user manually signs in; never exported')
    parser.add_argument('--count',type=int,default=20,choices=range(1,21))
    parser.add_argument('--output',required=True)
    parser.add_argument('--channel',default='chrome')
    args=parser.parse_args()
    if not os.environ.get('GITHUB_ACTIONS') and os.environ.get('HANDNAVIGATE_REMOTE_RUNNER')!='1':
        parser.error('This acceptance target runs remotely. Set HANDNAVIGATE_REMOTE_RUNNER=1 on the chosen VM.')
    if not args.topic.strip() or len(args.topic)>200:parser.error('Topic must be 1–200 characters.')
    try:url=source_url(args.topic,args.page_url)
    except ValueError as error:parser.error(str(error))
    runtime=checked_path(args.profile_data) if args.profile_data else None
    if runtime and not (runtime/'browser-profile').is_dir():parser.error('The chosen VM profile does not exist. Complete manual login first.')
    output=checked_path(args.output)
    output.mkdir(parents=True,exist_ok=True)
    if any(output.iterdir()):parser.error('Choose a new empty output folder for this run.')
    images=output/'pictures';images.mkdir()
    report={'checked_at':datetime.now(timezone.utc).isoformat(),'executor':platform.platform(),
            'remote':True,'github_run':os.environ.get('GITHUB_RUN_ID'),'topic':args.topic,'requested':args.count,
            'session_mode':'saved_profile' if runtime else 'guest','upload_used':False,
            'source':'Pinterest browser','source_url':url,'status':'RUNNING','items':[]}
    report_file=output/'result.json'
    def save():report_file.write_text(json.dumps(report,indent=2),encoding='utf-8')
    save();cancel=threading.Event();timer=threading.Timer(240,cancel.set);timer.start()
    started=time.monotonic()
    try:
        policy=Policy(Permissions(browser_origins=ORIGINS,image_origins=IMAGE_ORIGINS))
        plan=Plan(name='Pinterest guest collection',instruction='Download public Pinterest images into the chosen folder',
                  kind='images',start_url=url,image_selector='a[href*="/pin/"] img:not([data-test-id="gated-pin-image"])',max_items=args.count)
        with ProcessLock(runtime or output/'private-runtime'), Browser(runtime or output/'private-runtime',policy,cancel,headless=True,channel=args.channel) as browser:
            try:
                def record(item):
                    report['items'].append(item);save()
                    print(json.dumps({'downloaded':len(report['items']),'requested':args.count}),flush=True)
                browser.collect(plan,images,set(),record)
            finally:
                try:
                    report['blocked_requests']=browser.blocked_requests
                    report['page']={'url':browser.page.url,'title':browser.page.title(),
                        'image_matches':browser.page.locator(plan.image_selector).count(),
                        'password_fields':browser.page.locator('input[type=password]').count(),
                        'gated_images':browser.page.locator('[data-test-id="gated-pin-image"]').count(),
                        'text':browser.page.locator('body').inner_text(timeout=3000)[:1800]}
                    browser.page.screenshot(path=str(output/'page.png'),timeout=5000)
                except Exception as error:report['observation_error']=str(error)[:300]
        complete=verified_inventory(images,report['items'],args.count)
        report['status']='VERIFIED' if complete else 'PARTIAL'
        page=report.get('page',{})
        if not report['items'] and (page.get('password_fields') or page.get('gated_images') or any(s in page.get('text','').lower() for s in ('log in','sign up','access denied','not for bots'))):
            report['status']='ACCESS_REQUIRED'
        elif not report['items'] and any(r.get('resource_type')=='Script' and '.pinimg.com/' in r.get('url','') for r in report.get('blocked_requests',[])):
            report['status']='SOURCE_CONFIGURATION_REQUIRED'
    except Exception as error:
        report['status']='CANCELLED' if cancel.is_set() else 'FAILED';report['error']=str(error)[:1000]
    finally:
        timer.cancel();report['downloaded']=len(report['items']);report['seconds']=round(time.monotonic()-started,2)
        # Only relative paths belong in the downloadable manifest; profiles and
        # browser state are excluded from the workflow's artifact upload.
        for item in report['items']:item['file']='pictures/'+Path(item['file']).name
        save()
    print(json.dumps({k:v for k,v in report.items() if k!='items'},indent=2),flush=True)
    raise SystemExit(0 if report['status']=='VERIFIED' else 2)


if __name__=='__main__':main()
