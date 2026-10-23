"""Owned HTTP report portal with synthetic sessions and CSVs, for qualification only."""
from __future__ import annotations
from contextlib import contextmanager
import csv
from html import escape
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import secrets
import threading
import time
from urllib.parse import parse_qs, urlencode, urlsplit

STYLE = '''body{margin:0;background:#f4f6fb;color:#17243a;font:15px/1.6 system-ui}main{max-width:800px;margin:60px auto;padding:32px;background:white;border:1px solid #dce2ee;border-radius:16px}h1{font-size:32px}label{display:block;margin:18px 0}input,button,a{font:inherit;padding:11px 15px;border-radius:8px}input{border:1px solid #c8cfdf}button,a{background:#5148de;color:white;border:0;cursor:pointer}a{display:inline-block;text-decoration:none}.note{color:#6b7890;font-size:13px}.tag{font-size:11px;letter-spacing:1px;text-transform:uppercase;color:#5148de}'''


def document(title, body, script=''):
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<link rel="icon" href="/favicon"><title>{escape(title)}</title><style>{STYLE}</style></head><body><main>{body}</main>{script}</body></html>').encode()


def csv_bytes(topic, case='normal'):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream, lineterminator='\n')
    writer.writerow(['item_id', 'topic', 'label'])
    for i in range(1, 6):
        writer.writerow([f'report-{1 if case == "duplicate" else i:02}',
                         'wrong-topic' if case == 'wrong_topic' else topic,
                         '=1+1' if case == 'formula' else f'Generated example {i}'])
    return stream.getvalue().encode()


class PortalServer(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, port=0):
        super().__init__(('127.0.0.1', port), PortalHandler)
        self.csrf = secrets.token_urlsafe(24)
        self.sessions = {}
        self.lock = threading.RLock()
        self.case = 'normal'
        self.hits = []

    @property
    def origin(self):
        return f'http://127.0.0.1:{self.server_port}'

    def expire_sessions(self):
        with self.lock:
            self.sessions.clear()


class PortalHandler(BaseHTTPRequestHandler):
    server: PortalServer
    def log_message(self, *_):
        pass

    def send(self, body, content_type='text/html; charset=utf-8', status=200, headers=None):
        self.send_response(status)
        for k, v in {'Content-Type': content_type, 'Content-Length': str(len(body)), 'Cache-Control': 'no-store',
                     'X-Content-Type-Options': 'nosniff', 'X-Frame-Options': 'DENY',
                     'Content-Security-Policy': "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; form-action 'self'; frame-ancestors 'none'",
                     **(headers or {})}.items():
            self.send_header(k, v)
        self.end_headers()
        with self.server.lock:
            # Never record query values, cookies, request bodies or credentials.
            self.server.hits.append({'method': self.command, 'path': urlsplit(self.path).path, 'status': status})
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def valid_host(self):
        return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'

    def account(self):
        try:
            jar = cookies.SimpleCookie(self.headers.get('Cookie', ''))
            token = jar['hn_demo'].value
        except (cookies.CookieError, KeyError):
            return None
        with self.server.lock:
            stored = self.server.sessions.get(token)
        return stored['account'] if stored and stored['expires'] > time.time() else None

    def login_page(self, status=200):
        body = ('<span class="tag">Owned qualification portal</span><h1>Connect a test account</h1>'
                '<p class="note">Synthetic session only. This form never asks for a real password.</p>'
                '<div data-testid="login-required">Sign in to continue.</div>'
                '<form action="/session" method="post">'
                f'<input type="hidden" name="csrf" value="{self.server.csrf}">'
                '<label>Demo account<input name="account" value="demo@handnavigate.local" readonly></label>'
                '<button type="submit">Sign in to demo</button></form>')
        self.send(document('Connect demo account', body), status=status)

    def do_GET(self):
        if not self.valid_host():
            return self.send(b'Invalid host', 'text/plain', 403)
        p = urlsplit(self.path)
        if p.path == '/health':
            return self.send(b'{"owned_portal":true}', 'application/json')
        if p.path == '/favicon':
            return self.send(b'', 'image/x-icon', 204)
        if p.path == '/login':
            return self.login_page()
        account = self.account()
        if not account:
            return self.login_page(401)
        if p.path == '/reports':
            body = ('<span class="tag">Owned qualification portal</span><h1>Your report library</h1>'
                    f'<p>Signed in as <strong data-testid="account-id">{escape(account)}</strong></p>'
                    '<form id="query"><label>Report topic<input name="topic" maxlength="80" required></label>'
                    '<button type="submit">Find reports</button></form><section id="result"></section>'
                    '<p class="note">Five generated rows per export. No third-party data.</p>')
            script = '''<script>document.querySelector('#query').addEventListener('submit',async e=>{e.preventDefault();
const result=document.querySelector('#result');result.replaceChildren();result.removeAttribute('data-testid');
const topic=new FormData(e.target).get('topic');const response=await fetch('/api/reports?'+new URLSearchParams({topic}));
if(response.status===401){result.dataset.testid='login-required';result.textContent='Session expired';return;}
const data=await response.json();const a=document.createElement('a');a.textContent='Download CSV';a.href=data.download;a.download='report.csv';
result.append(a);result.dataset.testid='report-ready';});</script>'''
            return self.send(document('Report library', body, script))
        try:
            query = parse_qs(p.query, keep_blank_values=True, max_num_fields=5)
        except ValueError:
            return self.send(b'Bad query', 'text/plain', 400)
        topic = query.get('topic', [''])[0]
        if set(query) != {'topic'} or len(query['topic']) != 1 or not topic.strip() or len(topic) > 80 or any(ord(c) < 32 for c in topic):
            return self.send(b'Invalid topic', 'text/plain', 400)
        if p.path == '/api/reports':
            if self.server.case == 'expire_on_search':
                self.server.expire_sessions()
                return self.send(b'{"error":"session expired"}', 'application/json', 401)
            return self.send(json.dumps({'rows': 5, 'download': '/download?' + urlencode({'topic': topic})}).encode(), 'application/json')
        if p.path == '/download':
            if self.server.case == 'redirect':
                return self.send(b'', 'text/plain', 302, {'Location': 'https://example.invalid/not-authorized'})
            if self.server.case == 'login_as_download':
                return self.send(b'<html>Sign in</html>', 'text/csv')
            return self.send(csv_bytes(topic, self.server.case), 'text/csv; charset=utf-8',
                             headers={'Content-Disposition': 'attachment; filename="report.csv"'})
        self.send(b'Not found', 'text/plain', 404)

    def do_POST(self):
        if not self.valid_host() or self.headers.get('Origin') != self.server.origin or urlsplit(self.path).path != '/session':
            return self.send(b'Forbidden', 'text/plain', 403)
        try:
            length = int(self.headers.get('Content-Length', 0))
            if not 0 < length <= 2048 or self.headers.get('Content-Type') != 'application/x-www-form-urlencoded':
                raise ValueError()
            self.connection.settimeout(5)
            data = parse_qs(self.rfile.read(length).decode(), max_num_fields=4)
            if set(data) != {'csrf', 'account'} or data['csrf'] != [self.server.csrf] or data['account'] != ['demo@handnavigate.local']:
                raise ValueError()
        except (ValueError, UnicodeError, OSError):
            return self.send(b'Invalid demo sign-in', 'text/plain', 400)
        token = secrets.token_urlsafe(32)
        with self.server.lock:
            self.server.sessions[token] = {'account': data['account'][0], 'expires': time.time() + 900}
        # No redirect: make navigation boundaries explicit in this pilot.
        body = ('<h1>Demo session connected</h1><strong data-testid="account-id">demo@handnavigate.local</strong>'
                '<p><a href="/reports">Open report library</a></p>')
        self.send(document('Connected', body), headers={'Set-Cookie': f'hn_demo={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=900'})


@contextmanager
def running_portal(port=0):
    server = PortalServer(port)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
