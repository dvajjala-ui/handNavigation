"""Layered checks: real owned HTTP components != real browser HTTP workflows."""
from __future__ import annotations
import http.cookiejar
import importlib.metadata
import json
from pathlib import Path
import platform
import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

from playwright.sync_api import sync_playwright

from .connectors import ConnectionRegistry, demo_profile, timestamp
from .contracts import digest
from .portal import running_portal
from .portal_runner import error_report, run_export, verify_csv
from .runner import launch_browser
from .vault import SessionVault


class OwnedHttpClient:
    """Only constructed with the owned test server. Never used as browser fallback."""
    def __init__(self, portal):
        self.portal = portal
        self.jar = http.cookiejar.CookieJar()
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(), urllib.request.HTTPCookieProcessor(self.jar))

    def request(self, path, data=None):
        if not path.startswith('/') or path.startswith('//'):
            raise ValueError('Owned fixture path required')
        headers = {}
        encoded = None
        if data is not None:
            headers = {'Origin': self.portal.origin, 'Content-Type': 'application/x-www-form-urlencoded'}
            encoded = urllib.parse.urlencode(data).encode()
        req = urllib.request.Request(self.portal.origin + path, data=encoded, headers=headers)
        try:
            response = self.opener.open(req, timeout=5)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            return response.status, dict(response.headers), response.read(1048577)

    def login(self):
        status, headers, body = self.request('/login')
        if status != 200:
            raise AssertionError('Owned login form did not load')
        match = re.search(rb'name="csrf" value="([A-Za-z0-9_-]+)"', body)
        if not match:
            raise AssertionError('Owned CSRF control missing')
        return self.request('/session', {'csrf': match[1].decode(), 'account': 'demo@handnavigate.local'})

    def storage_state(self):
        return {'cookies': [{'name': c.name, 'value': c.value, 'domain': c.domain, 'path': c.path,
                             'expires': c.expires if c.expires is not None else -1,
                             'httpOnly': c.has_nonstandard_attr('HttpOnly'), 'secure': c.secure,
                             'sameSite': 'Strict'} for c in self.jar], 'origins': []}


def browser_probe(origin):
    """Ordinary managed-browser navigation. Never alter policy, proxies or flags."""
    try:
        with sync_playwright() as p:
            browser = launch_browser(p)
            try:
                page = browser.new_page()
                response = page.goto(origin + '/health', wait_until='domcontentloaded', timeout=8000)
                body = page.text_content('body') or ''
                ok = response is not None and response.status == 200 and json.loads(body).get('owned_portal') is True
                return {'status': 'PASS' if ok else 'FAIL', 'http_status': response.status if response else None,
                        'layer': 'real browser HTTP navigation', 'policy_changed': False}
            finally:
                browser.close()
    except Exception as exc:
        error = error_report(exc)
        return {'status': 'BLOCKED' if error['code'] == 'ENVIRONMENT_BLOCKED' else 'FAIL',
                'error': error, 'layer': 'real browser HTTP navigation', 'policy_changed': False}


def qualify_owned(output):
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=True)
    report = {'schema_version': 1, 'generated_at': timestamp(), 'scope': 'owned synthetic portal only',
              'production_ready': False, 'third_party_sites_tested': 0, 'model_calls': 0,
              'checks': [], 'environment': {'python': platform.python_version(), 'system': platform.system(),
                **{name: importlib.metadata.version(name) for name in ['playwright', 'cryptography']}},
              'limitations': ['No browser-policy bypass or alternate engine', 'No third-party website or real customer account',
                              'HTTP client checks do not prove browser interactions', 'No authenticated unattended scheduling',
                              'No OS network sandbox or hardware-protected secret store',
                              'No Windows/macOS qualification unless run and reported on those platforms']}
    def check(name, passed, layer):
        report['checks'].append({'name': name, 'status': 'PASS' if passed else 'FAIL', 'layer': layer})
        if not passed:
            raise AssertionError(name)
    try:
        with running_portal() as portal, tempfile.TemporaryDirectory(prefix='handnavigate-doctor-') as temp:
            profile = demo_profile(portal.origin)
            client = OwnedHttpClient(portal)
            status, _, _ = client.request('/reports')
            check('Unauthenticated entry denied', status == 401, 'HTTP client -> owned server')
            status, _, _ = client.login()
            check('Synthetic sign-in sets an HttpOnly cookie', status == 200 and client.storage_state()['cookies'][0]['httpOnly'], 'HTTP client -> owned server')
            status, _, body = client.request('/reports')
            check('Signed-in session reused with expected account', status == 200 and b'demo@handnavigate.local' in body, 'HTTP client -> owned server')
            topic = 'architecture'
            query = urllib.parse.urlencode({'topic': topic})
            status, _, body = client.request('/api/reports?' + query)
            check('Authenticated search returns export link', status == 200 and json.loads(body)['rows'] == 5, 'HTTP client -> owned server')
            status, headers, data = client.request('/download?' + query)
            checked = verify_csv(data, profile['file_contract'], topic)
            check('Actual HTTP CSV passes content contract', status == 200 and checked['rows'] == 5, 'HTTP download + Python verifier')
            sample = root / 'owned-http-component-export.csv'
            sample.write_bytes(data)
            report['component_artifact'] = {**checked, 'path': sample.name, 'downloaded_by': 'Python HTTP client, NOT browser'}
            vault = SessionVault(Path(temp) / 'vault')
            secret = 'ephemeral-doctor-session-' + __import__('secrets').token_hex(16)
            vault.save(profile, client.storage_state(), secret)
            check('Encrypted session round trip', vault.load(profile, secret) == client.storage_state(), 'vault + real synthetic cookie')
            probe = browser_probe(portal.origin)
            report['browser_probe'] = probe
            if probe['status'] == 'PASS':
                # Real browser sign-in, capture and replay, separate from HTTP-client evidence.
                from .portal_runner import BrowserGuard, assert_account
                with sync_playwright() as p:
                    b = launch_browser(p)
                    try:
                        context = b.new_context(service_workers='block')
                        guard = BrowserGuard(profile, phase='login')
                        guard.install(context)
                        page = context.new_page()
                        page.goto(portal.origin + '/login')
                        page.get_by_role('button', name='Sign in to demo', exact=True).click()
                        page.goto(portal.origin + '/reports')
                        guard.check()
                        assert_account(page, profile)
                        vault.save(profile, context.storage_state(), secret)
                    finally:
                        b.close()
                record = {'profile': profile, 'sha256': digest(profile), 'approved_sha256': digest(profile)}
                result = run_export(record, vault, secret, topic=topic, output=root)
                report['browser_workflow'] = result
                check('Browser sign-in, encrypted capture and separate-context export', result['status'] == 'VERIFIED_EXPORT', 'real browser HTTP')
            else:
                report['browser_workflow'] = {'status': 'NOT_RUN', 'reason': probe.get('error', {}).get('code', 'BROWSER_PREFLIGHT_FAILED')}
            portal.expire_sessions()
            status, _, _ = client.request('/reports')
            check('Server-expired session rejected', status == 401, 'HTTP client -> owned server')
            report['http_request_audit'] = portal.hits
        failed = any(c['status'] == 'FAIL' for c in report['checks'])
        report['status'] = 'FAILED' if failed or report['browser_probe']['status'] == 'FAIL' else (
            'OWNED_BROWSER_QUALIFIED' if report['browser_workflow'].get('status') == 'VERIFIED_EXPORT' else 'COMPONENTS_PASS_BROWSER_BLOCKED')
    except Exception as exc:
        report['status'] = 'FAILED'
        report['error'] = error_report(exc)
    (root / 'qualification.json').write_text(json.dumps(report, indent=2))
    return report
