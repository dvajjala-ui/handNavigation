"""One-time VM-only import of an independently verified Pinterest result folder."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT.parent)]
from core.browser import LIMITS
from core.collections import CollectionDB
from handnavigate.transfer.files import image_metadata


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--result',required=True,help='Existing VM result.json from collect_pinterest.py')
    parser.add_argument('--topic',default='travel')
    args=parser.parse_args()
    if os.environ.get('HANDNAVIGATE_REMOTE_RUNNER')!='1':parser.error('Import must run on the remote VM.')
    file=Path(args.result).resolve(strict=True)
    report=json.loads(file.read_text(encoding='utf-8'))
    page=report.get('source_url','')
    origin=urlsplit(page)
    if report.get('status')!='VERIFIED' or origin.scheme!='https' or origin.hostname not in ('www.pinterest.com','in.pinterest.com'):
        parser.error('Only an existing verified Pinterest result is accepted.')
    items=report.get('items',[])
    if len(items)!=report.get('requested') or len(items)!=20:parser.error('Expected the exact twenty-image result.')
    verified=[];seen=set()
    for item in items:
        relative=Path(item['file'])
        if relative.is_absolute() or '..' in relative.parts:parser.error('Manifest contains an unsafe path.')
        image=(file.parent/relative).resolve(strict=True)
        if not image.is_relative_to(file.parent):parser.error('Image left its result folder.')
        data=image.read_bytes();meta=image_metadata(data,LIMITS)
        if meta['sha256']!=item['sha256'] or meta['sha256'] in seen:parser.error('Image hash mismatch or duplicate.')
        seen.add(meta['sha256']);verified.append((item,data))
    db=CollectionDB();db.ensure_bucket()
    with db.connect() as conn:
        topic=conn.execute('select 1 from public.collection_topics where key=%s',(args.topic,)).fetchone()
        if not topic:parser.error('Unknown content topic.')
        run=conn.execute('''insert into public.collection_runs(source,topic_key,requested,status)
            values ('pinterest',%s,20,'RUNNING') returning id''',(args.topic,)).fetchone()
    run_id=str(run['id']);stored=0
    try:
        for item,data in verified:
            result=db.store_image(run_id,'pinterest',args.topic,page,item['source'],data)
            if not result['duplicate']:stored+=1
            print(json.dumps({'verified':len(seen),'stored':stored,'duplicate':result['duplicate']}),flush=True)
        db.finish_run(run_id,'VERIFIED',20,stored)
    except Exception as error:
        db.finish_run(run_id,'HALTED',20,stored,str(error)[:500]);raise
    print(json.dumps({'run_id':run_id,'status':'VERIFIED','source':'pinterest','topic':args.topic,
        'verified':20,'new_rows':stored}),flush=True)


if __name__=='__main__':main()
