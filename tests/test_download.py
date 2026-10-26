"""Actual browser/HTTP local Downloads checks, independent of Pinterest availability."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import json
from pathlib import Path
import threading

from PIL import Image

from handnavigate.live.contracts import Scope
from handnavigate.transfer.download import LocalDownload, image_urls


@contextmanager
def listing(count=25, gated=False):
    assets = []
    for index in range(count):
        data = BytesIO()
        Image.new('RGB', (200+index, 180+index), (index*9%255, 100, 75)).save(data, format=['PNG','JPEG','WEBP'][index%3])
        assets.append(data.getvalue())
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_GET(self):
            if self.path == '/images':
                body = ''.join(f'<img src="/image/{i}">' for i in range(count))
                if gated: body = '<div data-test-id="gated-pin-image">'+body+'</div><input type="password">'
                data = body.encode(); content = 'text/html'
            else:
                data = assets[int(self.path.split('/')[-1])]; content = 'application/octet-stream'
            self.send_response(200); self.send_header('Content-Type', content); self.send_header('Content-Length', str(len(data))); self.end_headers()
            self.wfile.write(data)
    server = ThreadingHTTPServer(('127.0.0.1',0), Handler)
    thread = threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    try: yield origin, assets
    finally: server.shutdown(); server.server_close(); thread.join()


def test_twenty_real_images_are_saved_verified_and_reused(tmp_path):
    with listing() as (origin, assets):
        options = {'url':origin+'/images', 'scope':Scope((origin,)), 'count':20,
                   'folder':tmp_path/'Downloads', 'root':tmp_path/'state'}
        result = LocalDownload(**options).run()
        assert result['status'] == 'VERIFIED', result
        assert result['downloaded'] == 20
        assert len([p for p in options['folder'].iterdir() if p.suffix in {'.png','.jpg','.webp'}]) == 20
        assert {r['format'] for r in result['items']} == {'PNG','JPEG','WEBP'}
        assert {Path(options['folder']/r['file']).read_bytes() for r in result['items']} == set(assets[:20])
        repeated = LocalDownload(**options).run()
        assert repeated['status'] == 'VERIFIED', repeated
        assert repeated['items'] == result['items']


def test_gated_pinterest_preview_is_not_downloaded(tmp_path):
    with listing(count=3,gated=True) as (origin, _):
        result = LocalDownload(url=origin+'/images', scope=Scope((origin,)), count=20,
                               folder=tmp_path/'Downloads', root=tmp_path/'state', pinterest=True).run()
        assert result['status'] == 'AUTH_REQUIRED', result
        assert result['downloaded'] == 0
        assert not list((tmp_path/'Downloads').glob('*.png'))


def test_foreign_manifest_and_existing_files_are_preserved(tmp_path):
    folder = tmp_path/'Downloads'; folder.mkdir()
    manifest = folder/'handnavigate-manifest.json'
    content = json.dumps({'schema':'another-application','items':['keep me']})
    manifest.write_text(content)
    with listing(count=1) as (origin,_):
        result = LocalDownload(url=origin+'/images',scope=Scope((origin,)),count=1,folder=folder,root=tmp_path/'state').run()
        assert result['status'] == 'HALTED'
        assert manifest.read_text() == content


def test_tampered_download_is_rejected_without_overwrite(tmp_path):
    with listing(count=1) as (origin,_):
        options = {'url':origin+'/images','scope':Scope((origin,)), 'count':1,'folder':tmp_path/'Downloads','root':tmp_path/'state'}
        first = LocalDownload(**options).run()
        path = options['folder']/first['items'][0]['file']
        path.write_bytes(b'changed content')
        again = LocalDownload(**options).run()
        assert again['status'] == 'HALTED'
        assert path.read_bytes() == b'changed content'
        assert len(again['items']) == 1


def test_only_advertised_resolutions_are_selected():
    assert image_urls({'src':'https://i.pinimg.com/small.jpg','srcset':'https://i.pinimg.com/large.jpg 3x, https://i.pinimg.com/medium.jpg 2x'}) == [
        'https://i.pinimg.com/large.jpg','https://i.pinimg.com/medium.jpg','https://i.pinimg.com/small.jpg']
