"""Actual browser/HTTP source-to-destination transfers, not set_content or stubbed uploads."""
from contextlib import contextmanager
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import threading
import time
from urllib.parse import parse_qs, urlsplit

from PIL import Image

from .contracts import template


@contextmanager
def running_demo(*, count=24, page_size=4, corrupt=False, upload_mode='normal', auth=False,
                 async_gallery=False, auto_upload=False, async_pagination=False):
    images = {}
    formats = ['PNG', 'JPEG', 'WEBP']
    for index in range(count):
        out = BytesIO()
        Image.new('RGB', (32+index, 35+index), (index*7 % 255, index*13 % 255, 65)).save(out, format=formats[index % 3])
        images[str(index)] = out.getvalue()
    uploads = []
    state = {'post_count': 0, 'blocked_hits': 0}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass

        def send(self, body, content='text/html', status=200, headers=None):
            self.send_response(status)
            self.send_header('Content-Type', content)
            self.send_header('Content-Length', str(len(body)))
            for key, val in (headers or {}).items(): self.send_header(key, val)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            url = urlsplit(self.path)
            if url.path == '/login':
                self.send(b'<p>Test account</p>', headers={'Set-Cookie': 'owned=synthetic; Path=/; SameSite=Lax'})
                return
            if auth and 'owned=synthetic' not in self.headers.get('Cookie', ''):
                self.send(b'<input type="password" aria-label="Password">', status=401)
                return
            if url.path == '/source':
                page = int(parse_qs(url.query).get('page', ['0'])[0])
                indices = list(images)[page*page_size:(page+1)*page_size]
                # Repeated source identities exercise pagination/deduplication.
                if page and indices: indices.insert(0, str(page*page_size-1))
                cards = ''.join(f'<article><img src="/image/{i}"></article>' for i in indices)
                more = f'<a href="/source?page={page+1}">Next</a>' if (page+1)*page_size < count else ''
                if more and async_pagination:
                    more = more.replace('<a ', '<a onclick="event.preventDefault();setTimeout(()=>fetch(this.href).then(r=>r.text()).then(s=>document.body.innerHTML=s),650)" ')
                self.send(f'<p id="account">Test account</p>{cards}{more}'.encode())
            elif url.path.startswith('/image/'):
                if state.get('image_redirect'):
                    self.send(b'', status=302, headers={'Location': state['image_redirect']})
                    return
                data = images[url.path.split('/')[-1]]
                self.send(b'<html>not an image</html>' if corrupt else data, 'application/octet-stream')
            elif url.path == '/target':
                cards = ''.join(f'<article data-id="{i}"><img src="/uploaded/{i}"></article>' for i in range(len(uploads)))
                if async_gallery:
                    cards = '<script>fetch("/gallery-data").then(r=>r.text()).then(s=>document.getElementById("gallery").innerHTML=s)</script>'
                change = '<script>document.querySelector("input[type=file]").onchange=()=>fetch("/upload",{method:"POST",body:new FormData(document.querySelector("form"))})</script>' if auto_upload else ''
                self.send(('''<p id="account">Test account</p><form method="POST" action="/upload" enctype="multipart/form-data">
                    <label>Image <input name="file" type="file" accept="image/*"></label>
                    <button>Upload image</button></form><div id="gallery">'''+cards+'</div>'+change).encode())
            elif url.path == '/gallery-data':
                time.sleep(.65)
                cards = ''.join(f'<article data-id="{i}"><img src="/uploaded/{i}"></article>' for i in range(len(uploads)))
                self.send(cards.encode())
            elif url.path.startswith('/uploaded/'):
                self.send(uploads[int(url.path.split('/')[-1])], 'application/octet-stream')
            elif url.path == '/forbidden':
                state['blocked_hits'] += 1
                self.send(b'forbidden')
            else: self.send(b'not found', status=404)

        def do_POST(self):
            raw = self.rfile.read(int(self.headers['Content-Length']))
            if auth and 'owned=synthetic' not in self.headers.get('Cookie', ''):
                self.send(b'Login required', status=401)
                return
            state['post_count'] += 1
            message = BytesParser(policy=default).parsebytes(('Content-Type: '+self.headers['Content-Type']+'\r\nMIME-Version: 1.0\r\n\r\n').encode()+raw)
            file = next(p.get_payload(decode=True) for p in message.iter_parts() if p.get_filename())
            if upload_mode != 'fake_success': uploads.append(file)
            self.send(b'<p>Uploaded successfully</p><a href="/target">Gallery</a>')

    servers = [ThreadingHTTPServer(('127.0.0.1', 0), Handler) for _ in range(2)]
    threads = [threading.Thread(target=s.serve_forever, daemon=True) for s in servers]
    for t in threads: t.start()
    src, dst = [f'http://127.0.0.1:{s.server_port}' for s in servers]
    recipe = template(src+'/source', dst+'/target', 10)
    recipe['source'].update(items='article', image_selector='img', next={'kind': 'click', 'locator': {'kind': 'role', 'role': 'link', 'name': 'Next'}})
    recipe['target']['submit'] = {'kind': 'role', 'role': 'button', 'name': 'Upload image'}
    recipe['target']['verify'].update(items='#gallery article', image_selector='img', id_attribute='data-id')
    recipe['limits']['verify_seconds'] = 1
    recipe['limits']['max_pages'] = 10
    recipe['limits']['timeout_seconds'] = 90
    for side in ('source', 'target'):
        recipe[side]['identity'] = {'locator': {'kind': 'css', 'value': '#account'}, 'text': 'Test account'}
    try:
        yield recipe, uploads, images, state
    finally:
        for s in servers: s.shutdown(); s.server_close()
        for t in threads: t.join()
