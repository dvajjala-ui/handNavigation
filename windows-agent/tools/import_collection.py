"""One-time VM-only import of an independently verified collection batch.

Accepts a result.json from the Pinterest or Reddit collector, re-decodes and
re-hashes every file it lists, uploads to the private bucket with a read-back
check, and only then marks that topic verified for that source. A batch whose
URL is not the topic's configured source for that exact source is refused.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT.parent)]

from core.browser import LIMITS
from core.collections import CollectionDB
from core.sources import SOURCES, source_config
from handnavigate.transfer.files import image_metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--result', required=True, help='Existing VM result.json from a collector run')
    parser.add_argument('--topic', required=True)
    parser.add_argument('--source', default='pinterest', choices=sorted(SOURCES))
    args = parser.parse_args()
    if os.environ.get('HANDNAVIGATE_REMOTE_RUNNER') != '1':
        parser.error('Import must run on the remote VM.')
    config = source_config(args.source)
    file = Path(args.result).resolve(strict=True)
    report = json.loads(file.read_text(encoding='utf-8'))
    page = report.get('source_url', '')
    origin = urlsplit(page)
    hosts = set()
    for root in config['browser_origins']:
        hosts.add(urlsplit(root).netloc)
    if report.get('status') != 'VERIFIED':
        parser.error('Only a verified batch is importable. This one is ' + str(report.get('status')) + '.')
    if origin.scheme != 'https' or origin.hostname not in hosts:
        parser.error('The batch did not come from an exact ' + config['label'] + ' HTTPS page.')
    items = report.get('items', [])
    if not items or len(items) != report.get('requested') or len(items) != report.get('downloaded'):
        parser.error('The manifest does not list the exact batch it claims.')
    verified = []
    seen = set()
    for item in items:
        relative = Path(item['file'])
        if relative.is_absolute() or '..' in relative.parts:
            parser.error('Manifest contains an unsafe path.')
        image = (file.parent / relative).resolve(strict=True)
        if not image.is_relative_to(file.parent):
            parser.error('Image left its result folder.')
        data = image.read_bytes()
        meta = image_metadata(data, LIMITS)
        if meta['sha256'] != item['sha256'] or meta['sha256'] in seen:
            parser.error('Image hash mismatch or duplicate.')
        seen.add(meta['sha256'])
        verified.append((item, data))

    db = CollectionDB()
    db.ensure_bucket()
    with db.connect() as conn:
        row = conn.execute('select ' + config['url_column'] + ' as url from public.collection_topics where key=%s',
                           (args.topic,)).fetchone()
        if not row:
            parser.error('Unknown content topic.')
        if row['url'] != page:
            parser.error('The batch URL is not the configured ' + config['label'] + ' source for topic "'
                         + args.topic + '".')
        run = conn.execute('insert into public.collection_runs(source,topic_key,requested,status) '
                           "values (%s,%s,%s,'RUNNING') returning id",
                           (args.source, args.topic, len(items))).fetchone()
    run_id = str(run['id'])
    stored = 0
    try:
        for item, data in verified:
            result = db.store_image(run_id, args.source, args.topic, page, item['source'], data)
            if not result['duplicate']:
                stored += 1
            print(json.dumps({'batch': len(verified), 'stored': stored, 'duplicate': result['duplicate']}), flush=True)
        db.finish_run(run_id, 'VERIFIED', len(verified), stored)
        db.mark_verified(args.topic, page, args.source)
    except Exception as error:
        db.finish_run(run_id, 'HALTED', len(verified), stored, str(error)[:500])
        raise
    print(json.dumps({'run_id': run_id, 'status': 'VERIFIED', 'source': args.source, 'topic': args.topic,
                      'batch': len(verified), 'new_rows': stored,
                      config['verified_column']: True}), flush=True)


if __name__ == '__main__':
    main()
