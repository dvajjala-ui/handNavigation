"""Build a read-only gallery of the private library from expiring signed links.

Runs on the worker, which holds the Supabase secret key, and emits one
self-contained HTML file: only that file is handed to a host. Every picture is a
signed Storage link that stops working at its expiry, so the page carries no key,
token or credential of its own. Each link is fetched back without any
authorization header and hash-compared before the file is written, so a gallery is
never published with links that do not open.

The pictures are reference-only previews collected from other people's pages. The
page is unlisted, tells search engines not to index it, states that, and expires.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT.parent)]

from core.collections import BUCKET, CollectionDB, TOPIC
from core.sources import SOURCES

MAXIMUM = {'limit': 500, 'hours': 168}


def signed_link(db, path, seconds):
    """Ask Storage for a link that opens without a key, then return it as a full URL."""
    body = db.storage('POST', 'object/sign/' + BUCKET + '/' + path,
                      json.dumps({'expiresIn': int(seconds)}).encode(), 'application/json')[1]
    value = json.loads(body).get('signedURL', '')
    if not value:
        raise RuntimeError('Storage returned no signed link.')
    if value.startswith('http'):
        return value
    prefix = db.values['SUPABASE_URL'] + ('' if value.startswith('/storage/v1/') else '/storage/v1/')
    return prefix + value.lstrip('/')


def opens(url, sha256):
    """Proof the published link works on its own: no apikey, no authorization."""
    try:
        with urlopen(Request(url, headers={'User-Agent': 'HandNavigate-Gallery/1.0'}), timeout=30) as response:
            return hashlib.sha256(response.read(26 * 1024 * 1024)).hexdigest() == sha256
    except Exception:
        return False


def build(db, source, topic, limit):
    with db.connect() as conn:
        rows = conn.execute('''select source,topic_key,storage_path,sha256,mime_type,width,height,
            byte_count,rendition,rights_status,collected_at from public.collected_images
            where (%s='' or source=%s) and (%s='' or topic_key=%s)
            order by collected_at desc limit %s''', (source, source, topic, topic, int(limit))).fetchall()
    return rows


TEMPLATE = '''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow,noarchive">
<title>HandNavigate library</title>
<style>
:root{color-scheme:dark}body{margin:0;font:15px/1.45 system-ui,Segoe UI,Roboto,sans-serif;background:#12141a;color:#e8eaf0}
header{position:sticky;top:0;z-index:2;background:#12141aee;padding:14px 18px;border-bottom:1px solid #262a35}
h1{margin:0 0 4px;font-size:18px}p.meta{margin:0;color:#98a0b3;font-size:12.5px}
.controls{display:flex;gap:10px;flex-wrap:wrap;margin-top:10px}
select{background:#1b1f28;color:#e8eaf0;border:1px solid #2e3444;border-radius:8px;padding:7px 9px;font:inherit}
main{padding:16px 18px 34px}
.grid{display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(190px,1fr))}
figure{margin:0;background:#171a22;border:1px solid #242835;border-radius:10px;overflow:hidden}
img{display:block;width:100%;height:172px;object-fit:cover;background:#0f1116}
figcaption{padding:7px 9px;font-size:11.5px;color:#98a0b3;display:flex;flex-direction:column;gap:2px}
figcaption b{color:#cfd4e2;font-weight:600;text-transform:capitalize}
a{color:#7aa2f7;text-decoration:none}
.empty{color:#98a0b3;padding:30px 0}
footer{padding:0 18px 40px;color:#7f8798;font-size:12px;max-width:900px}
.expired{padding:30px 18px;color:#f0a5a5}
</style></head><body>
<header><h1>HandNavigate image library</h1>
<p class="meta"><span id="count"></span> · links were signed for <span id="window"></span></p>
<div class="controls"><select id="source"><option value="">All sources</option></select>
<select id="topic"><option value="">All content</option></select></div></header>
<main><div class="grid" id="grid"></div><p class="empty" id="empty" hidden>Nothing matches those filters.</p>
<p class="expired" id="expired" hidden>This gallery expired. Rebuild it on the worker:
<code>windows-agent/tools/make_gallery.py</code></p></main>
<footer>Read-only view of a private collection. The pictures are reference-only previews of
material that belongs to the pages they came from; they are not licensed for reuse. This page is
unlisted, is marked noindex, and its image links stop working at the expiry above.</footer>
<script>
const gallery=__MANIFEST__;
const ends=new Date(gallery.expires_at).getTime();
const grid=document.getElementById('grid'),source=document.getElementById('source'),topic=document.getElementById('topic');
document.getElementById('window').textContent=new Date(ends).toLocaleString();
[...new Set(gallery.items.map(x=>x.source))].sort().forEach(v=>source.add(new Option(v,v)));
[...new Set(gallery.items.map(x=>x.topic))].sort().forEach(v=>topic.add(new Option(v,v)));
function draw(){
 if(Date.now()>ends){document.getElementById('expired').hidden=false;return;}
 grid.replaceChildren();let shown=0;
 for(const item of gallery.items){
  if(source.value&&item.source!==source.value)continue;
  if(topic.value&&item.topic!==topic.value)continue;
  shown++;const f=document.createElement('figure'),img=document.createElement('img'),cap=document.createElement('figcaption');
  img.loading='lazy';img.alt=item.topic+' image';img.src=item.url;
  cap.append(Object.assign(document.createElement('b'),{textContent:item.topic}));
  cap.append(document.createTextNode(item.source+' · '+item.width+'×'+item.height+' · '+item.rendition));
  f.append(img,cap);grid.append(f);
 }
 document.getElementById('empty').hidden=shown>0;
 document.getElementById('count').textContent=shown+' of '+gallery.items.length+' images';
}
source.onchange=topic.onchange=draw;
document.getElementById('count').textContent=gallery.items.length+' images';
draw();
</script></body></html>
'''


def render(manifest):
    payload = json.dumps(manifest, separators=(',', ':')).replace('</', '<\\/')
    return TEMPLATE.replace('__MANIFEST__', payload)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--source', default='', choices=[''] + sorted(SOURCES))
    parser.add_argument('--topic', default='')
    parser.add_argument('--limit', type=int, default=400, choices=range(1, MAXIMUM['limit'] + 1))
    parser.add_argument('--hours', type=float, default=72,
                        help='How long the published links stay open (15 minutes to one week)')
    args = parser.parse_args()
    if os.environ.get('HANDNAVIGATE_REMOTE_RUNNER') != '1':
        parser.error('Signed links are issued on the remote worker that holds the storage key.')
    if args.topic and not TOPIC.fullmatch(args.topic):
        parser.error('Choose a content topic key such as travel.')
    if not 0.25 <= args.hours <= MAXIMUM['hours']:
        parser.error('Choose a link lifetime between 0.25 and 168 hours.')
    db = CollectionDB()
    db.ensure_bucket()
    rows = build(db, args.source, args.topic, args.limit)
    if not rows:
        parser.error('No stored image matches that filter, so there is nothing to publish.')
    expires_in = int(args.hours * 3600)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    items, failed = [], []
    for row in rows:
        url = signed_link(db, row['storage_path'], expires_in)
        if not opens(url, row['sha256']):
            failed.append(row['storage_path'])
            continue
        items.append({'url': url, 'source': row['source'], 'topic': row['topic_key'],
                      'width': row['width'], 'height': row['height'], 'bytes': row['byte_count'],
                      'mime': row['mime_type'], 'rendition': row['rendition'],
                      'rights': row['rights_status'],
                      'collected': row['collected_at'].isoformat() if row['collected_at'] else ''})
    if not items:
        parser.error('No signed link opened without a key, so nothing was published.')
    manifest = {'generated_at': datetime.now(timezone.utc).isoformat(),
                'expires_at': expires_at.isoformat(),
                'bucket': BUCKET, 'count': len(items), 'items': items}
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render(manifest), encoding='utf-8')
    print(json.dumps({'status': 'PUBLISHED_FILE', 'file': str(target),
                      'bytes': target.stat().st_size, 'signed': len(items),
                      'refused': len(rows) - len(items), 'failed_links': failed[:10],
                      'expires_at': manifest['expires_at']}, indent=2), flush=True)
    if failed:
        raise SystemExit(3)


if __name__ == '__main__':
    main()
