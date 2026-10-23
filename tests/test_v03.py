"""Connection contracts, secret handling, owned HTTP, browser components and API.

Full browser HTTP test skips only an observed administrator block, unless CI
requires it. Browser helper checks load owned HTML directly and do not claim HTTP.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from unittest.mock import MagicMock, patch

from playwright.sync_api import sync_playwright, Error as BrowserError

from handnavigate.connectors import ConnectionRegistry, demo_profile, request_allowed, validate_profile
from handnavigate.contracts import ContractError, digest
from handnavigate.portal import running_portal, csv_bytes
from handnavigate.portal_runner import BrowserGuard, assert_account, error_report, locate, require_approved, run_export, verify_csv
from handnavigate.qualification import OwnedHttpClient, browser_probe
from handnavigate.runner import Halt, launch_browser
from handnavigate.studio import running_studio
from handnavigate.vault import SessionError, SessionVault, validate_state

OBSERVATIONS = []
PHRASE = 'this-is-a-synthetic-test-passphrase'


def state_for(profile, token='synthetic-cookie-never-public'):
    return {'cookies': [{'name': 'demo', 'value': token, 'domain': urllib.parse.urlsplit(profile['origin']).hostname,
                         'path': '/', 'expires': -1, 'httpOnly': True, 'secure': profile['scope'] == 'authorized_https',
                         'sameSite': 'Strict'}], 'origins': []}


class ConnectionContractTests(unittest.TestCase):
    def setUp(self):
        self.profile = demo_profile()

    def test_owned_and_remote_profile_shapes(self):
        validate_profile(self.profile)
        remote = {**self.profile, 'origin': 'https://portal.example.com', 'scope': 'authorized_https'}
        validate_profile(remote)

    def test_unsafe_origins_are_rejected(self):
        for origin, scope in [('http://example.com', 'authorized_https'), ('https://user:pass@example.com', 'authorized_https'),
                              ('https://example.com/extra', 'authorized_https'), ('https://127.0.0.1', 'authorized_https'),
                              ('https://foo.local', 'authorized_https'), ('http://localhost:4181', 'owned_local'),
                              ('http://127.0.0.1', 'owned_local'), ('https://Example.com', 'authorized_https')]:
            with self.subTest(origin=origin), self.assertRaises(ContractError):
                validate_profile({**self.profile, 'origin': origin, 'scope': scope})

    def test_scripts_credentials_and_wildcards_are_rejected(self):
        for key, value in [('script', 'fetch(document.cookie)'), ('password', 'secret')]:
            with self.subTest(key=key), self.assertRaises(ContractError):
                validate_profile({**self.profile, key: value})
        p = deepcopy(self.profile)
        p['routes'][0]['path'] = '/*'
        with self.assertRaises(ContractError):
            validate_profile(p)

    def test_fixed_asset_paths_can_be_reviewed_without_wildcards(self):
        p = deepcopy(self.profile)
        p['routes'].append({'path': '/assets/app.js', 'methods': ['GET'], 'query_keys': ['version']})
        validate_profile(p)
        self.assertTrue(request_allowed(p, p['origin'] + '/assets/app.js?version=3', 'GET'))
        self.assertFalse(request_allowed(p, p['origin'] + '/assets/other.js', 'GET'))

    def test_duplicate_and_encoded_paths_rejected(self):
        for path in ['/a/../b', '/a%2Fb', '//session']:
            p = deepcopy(self.profile)
            p['routes'][0]['path'] = path
            with self.subTest(path=path), self.assertRaises(ContractError):
                validate_profile(p)
        p = deepcopy(self.profile)
        p['routes'].append(p['routes'][0])
        with self.assertRaises(ContractError):
            validate_profile(p)

    def test_csv_schema_and_budgets_are_explicit(self):
        for key, value in [('format', 'javascript'), ('max_rows', True), ('max_bytes', 99999999),
                           ('columns', ['item_id', 'item_id']), ('unique_column', 'topic')]:
            p = deepcopy(self.profile)
            p['file_contract'][key] = value
            with self.subTest(key=key), self.assertRaises(ContractError):
                validate_profile(p)

    def test_only_reviewed_queries_and_methods_allowed(self):
        origin = self.profile['origin']
        self.assertTrue(request_allowed(self.profile, origin + '/api/reports?topic=parks', 'GET'))
        for url in [origin + '/api/reports?token=secret', origin + '/api/reports?topic=a&topic=b',
                    origin + '/download?topic=x#fragment', origin + '/download%2f?topic=x',
                    'https://example.invalid/download?topic=x', 'http://127.0.0.1:4182/download?topic=x']:
            with self.subTest(url=url):
                self.assertFalse(request_allowed(self.profile, url, 'GET'))
        self.assertFalse(request_allowed(self.profile, origin + '/session', 'POST'))
        self.assertTrue(request_allowed(self.profile, origin + '/session', 'POST', phase='login'))
        self.assertFalse(request_allowed(self.profile, origin + '/reports', 'POST', phase='login'))


class ConnectionRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.registry = ConnectionRegistry(self.temp.name)
        self.profile = demo_profile()
        self.record = self.registry.put(self.profile)

    def test_import_is_unapproved_and_durable(self):
        record = ConnectionRegistry(self.temp.name).get(self.profile['id'])
        self.assertEqual(record['status'], 'DRAFT')
        self.assertIsNone(record['approved_sha256'])
        with self.assertRaises(ContractError):
            require_approved(record)

    def test_permission_and_current_checksum_required(self):
        for checksum, consent in [('0' * 64, True), (self.record['sha256'], False), (self.record['sha256'], 1)]:
            with self.subTest(consent=consent), self.assertRaises(ContractError):
                self.registry.approve(self.profile['id'], checksum, consent)
        approved = self.registry.approve(self.profile['id'], self.record['sha256'], True)
        self.assertEqual(approved['status'], 'APPROVED_NOT_QUALIFIED')
        self.assertFalse(approved['scheduled_execution'])

    def test_revision_change_revokes_approval(self):
        self.registry.approve(self.profile['id'], self.record['sha256'], True)
        p = {**self.profile, 'revision': 2, 'name': 'Revised portal'}
        new = self.registry.put(p, self.record['sha256'])
        self.assertIsNone(new['approved_sha256'])
        with self.assertRaises(ContractError):
            self.registry.approve(p['id'], self.record['sha256'], True)

    def test_compare_and_swap_rejects_concurrent_edit(self):
        p = {**self.profile, 'revision': 2}
        def write():
            try:
                self.registry.put(p, self.record['sha256'])
                return 'saved'
            except ContractError:
                return 'rejected'
        with ThreadPoolExecutor(max_workers=2) as executor:
            self.assertCountEqual(list(executor.map(lambda _: write(), range(2))), ['saved', 'rejected'])

    def test_forgotten_approval_cannot_be_used_for_future_runs(self):
        self.registry.approve(self.profile['id'], self.record['sha256'], True)
        self.registry.revoke(self.profile['id'])
        with self.assertRaises(ContractError):
            require_approved(self.registry.get(self.profile['id']))


class SessionVaultTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.vault = SessionVault(Path(self.temp.name) / 'vault')
        self.profile = demo_profile()
        self.state = state_for(self.profile)
        self.at = datetime.now(timezone.utc)

    def save(self):
        return self.vault.save(self.profile, self.state, PHRASE, now=self.at)

    def test_encrypted_roundtrip_has_no_plaintext_secrets(self):
        self.save()
        content = self.vault.path(self.profile).read_text()
        self.assertNotIn(self.state['cookies'][0]['value'], content)
        self.assertNotIn(PHRASE, content)
        self.assertNotIn('demo@handnavigate.local', content)
        self.assertEqual(self.vault.load(self.profile, PHRASE, now=self.at), self.state)
        if os.name == 'posix':
            self.assertEqual(self.vault.path(self.profile).stat().st_mode & 0o777, 0o600)

    def test_wrong_passphrase_and_tamper_fail_closed(self):
        self.save()
        with self.assertRaises(SessionError) as caught:
            self.vault.load(self.profile, 'not-the-correct-passphrase')
        self.assertEqual(caught.exception.code, 'SESSION_LOCKED')
        path = self.vault.path(self.profile)
        envelope = json.loads(path.read_text())
        token = envelope['ciphertext']
        envelope['ciphertext'] = token[:70] + ('A' if token[70] != 'A' else 'B') + token[71:]
        path.write_text(json.dumps(envelope))
        with self.assertRaises(SessionError):
            self.vault.load(self.profile, PHRASE)

    def test_profile_change_requires_new_signin(self):
        self.save()
        p = {**self.profile, 'revision': 2}
        with self.assertRaises(SessionError) as caught:
            self.vault.load(p, PHRASE)
        self.assertEqual(caught.exception.code, 'SESSION_SCOPE_CHANGED')

    def test_ttl_expiry_and_expired_cookies_stop_reuse(self):
        self.save()
        with self.assertRaises(SessionError) as caught:
            self.vault.load(self.profile, PHRASE, now=self.at + timedelta(hours=8))
        self.assertEqual(caught.exception.code, 'AUTH_REQUIRED')
        self.state['cookies'][0]['expires'] = self.at.timestamp() - 1
        self.save()
        with self.assertRaises(SessionError):
            self.vault.load(self.profile, PHRASE, now=self.at)

    def test_state_cannot_include_other_origins_or_parent_cookies(self):
        for domain in ['.handnavigate.local', 'example.com']:
            s = deepcopy(self.state)
            s['cookies'][0]['domain'] = domain
            with self.subTest(domain=domain), self.assertRaises(ContractError):
                validate_state(self.profile, s)
        s = {'cookies': [], 'origins': [{'origin': 'https://example.com', 'localStorage': []}]}
        with self.assertRaises(ContractError):
            validate_state(self.profile, s)

    def test_unsupported_auth_storage_is_not_silently_dropped(self):
        s = {'cookies': [], 'origins': [{'origin': self.profile['origin'], 'localStorage': [], 'indexedDB': []}]}
        with self.assertRaises(ContractError):
            validate_state(self.profile, s)
        with self.assertRaises(ContractError):
            validate_state(self.profile, {'cookies': [], 'origins': []})

    def test_secure_cookie_required_for_remote_https(self):
        p = {**self.profile, 'scope': 'authorized_https', 'origin': 'https://portal.example.com'}
        state = state_for(p)
        state['cookies'][0]['secure'] = False
        with self.assertRaises(ContractError):
            validate_state(p, state)

    def test_weak_passphrase_and_unbounded_ttl_rejected(self):
        with self.assertRaises(SessionError):
            self.vault.save(self.profile, self.state, 'weak')
        with self.assertRaises(ContractError):
            self.vault.save(self.profile, self.state, PHRASE, ttl_hours=999)
        self.assertFalse(self.vault.path(self.profile).exists())

    def test_local_forget_is_not_remote_logout(self):
        self.save()
        result = self.vault.forget(self.profile)
        self.assertTrue(result['local_copy_removed'])
        self.assertFalse(result['remote_session_revoked'])
        with self.assertRaises(SessionError):
            self.vault.load(self.profile, PHRASE)

    def test_untrusted_kdf_parameters_are_not_executed(self):
        self.save()
        p = self.vault.path(self.profile)
        e = json.loads(p.read_text())
        e['kdf'] = 'scrypt-n999999999999'
        p.write_text(json.dumps(e))
        with self.assertRaises(SessionError):
            self.vault.load(self.profile, PHRASE)


class CSVVerificationTests(unittest.TestCase):
    def setUp(self):
        self.contract = demo_profile()['file_contract']

    def test_actual_csv_content_passes_with_recorded_hash(self):
        data = csv_bytes('parks, gardens')
        result = verify_csv(data, self.contract, 'parks, gardens')
        self.assertEqual(result['rows'], 5)
        self.assertEqual(result['sha256'], sha256(data).hexdigest())

    def test_wrong_topic_is_not_success(self):
        with self.assertRaises(Halt) as c:
            verify_csv(csv_bytes('parks', 'wrong_topic'), self.contract, 'parks')
        self.assertEqual(c.exception.code, 'CSV_TOPIC')

    def test_duplicate_identity_is_rejected(self):
        with self.assertRaises(Halt) as c:
            verify_csv(csv_bytes('parks', 'duplicate'), self.contract, 'parks')
        self.assertEqual(c.exception.code, 'CSV_IDENTITY')

    def test_formula_like_cells_are_rejected(self):
        with self.assertRaises(Halt) as c:
            verify_csv(csv_bytes('parks', 'formula'), self.contract, 'parks')
        self.assertEqual(c.exception.code, 'CSV_FORMULA')

    def test_login_html_and_wrong_headers_are_not_csv(self):
        for data in [b'<html>Sign in</html>', b'item_id,topic,topic\n1,parks,parks\n', b'\xff\x00']:
            with self.subTest(data=data), self.assertRaises(Halt):
                verify_csv(data, self.contract, 'parks')

    def test_rows_and_file_budget_checked(self):
        data = csv_bytes('parks')
        for altered in [data * 2, data.splitlines(keepends=True)[0], b'x' * (self.contract['max_bytes'] + 1)]:
            with self.subTest(length=len(altered)), self.assertRaises(Halt):
                verify_csv(altered, self.contract, 'parks')


class OwnedHTTPTests(unittest.TestCase):
    def setUp(self):
        self.ctx = running_portal()
        self.portal = self.ctx.__enter__()
        self.addCleanup(self.ctx.__exit__, None, None, None)
        self.client = OwnedHttpClient(self.portal)

    def test_authentication_cookie_and_real_download(self):
        self.assertEqual(self.client.request('/reports')[0], 401)
        self.assertEqual(self.client.login()[0], 200)
        self.assertEqual(self.client.request('/reports')[0], 200)
        status, headers, content = self.client.request('/download?topic=parks')
        result = verify_csv(content, demo_profile()['file_contract'], 'parks')
        self.assertEqual(status, 200)
        self.assertEqual(result['rows'], 5)
        OBSERVATIONS.append({'layer': 'real HTTP client -> owned server, NOT browser', 'scenario': 'authenticated export', 'rows': 5, 'sha256': result['sha256']})

    def test_server_expiry_requires_reauthentication(self):
        self.client.login()
        self.portal.expire_sessions()
        self.assertEqual(self.client.request('/reports')[0], 401)
        self.assertEqual(self.client.request('/download?topic=parks')[0], 401)

    def test_csrf_rejection_and_cookie_flags(self):
        self.assertEqual(self.client.request('/session', {'account': 'demo@handnavigate.local', 'csrf': 'wrong'})[0], 400)
        status, headers, _ = self.client.login()
        self.assertIn('HttpOnly', headers['Set-Cookie'])
        self.assertIn('SameSite=Strict', headers['Set-Cookie'])
        self.assertTrue(self.client.storage_state()['cookies'][0]['httpOnly'])

    def test_fixture_redirect_is_observed_not_followed(self):
        self.client.login()
        self.portal.case = 'redirect'
        status, headers, _ = self.client.request('/download?topic=parks')
        self.assertEqual(status, 302)
        self.assertIn('example.invalid', headers['Location'])
        self.assertNotIn('Cookie', json.dumps(self.portal.hits))

    def test_expiry_during_search_denies_export(self):
        self.client.login()
        self.portal.case = 'expire_on_search'
        self.assertEqual(self.client.request('/api/reports?topic=parks')[0], 401)
        self.assertEqual(self.client.request('/download?topic=parks')[0], 401)

    def test_report_query_is_not_reflected_as_html(self):
        self.client.login()
        topic = '<script>alert(1)</script>'
        status, _, body = self.client.request('/download?' + urllib.parse.urlencode({'topic': topic}))
        self.assertEqual(status, 200)
        self.assertEqual(verify_csv(body, demo_profile()['file_contract'], topic)['rows'], 5)


class GuardAndFailureTests(unittest.TestCase):
    def test_unapproved_request_is_blocked_before_fetch(self):
        guard = BrowserGuard(demo_profile())
        route = MagicMock()
        route.request.url = 'https://example.invalid/steal?token=SECRET'
        route.request.method = 'GET'
        guard.route(route)
        route.fetch.assert_not_called()
        route.abort.assert_called_once()
        self.assertNotIn('SECRET', json.dumps(guard.blocked))

    def test_redirect_is_not_followed_by_application_route(self):
        guard = BrowserGuard(demo_profile())
        route = MagicMock()
        route.request.url = demo_profile()['origin'] + '/reports'
        route.request.method = 'GET'
        route.fetch.return_value.status = 302
        guard.route(route)
        route.fetch.assert_called_once_with(max_redirects=0, timeout=10000)
        route.fulfill.assert_not_called()
        with self.assertRaises(Halt):
            guard.check()

    def test_runtime_errors_do_not_leak_tokens(self):
        result = error_report(BrowserError('Failed https://example.com/?token=VERY_SECRET'))
        self.assertNotIn('VERY_SECRET', json.dumps(result))
        self.assertEqual(error_report(BrowserError('net::ERR_BLOCKED_BY_ADMINISTRATOR'))['code'], 'ENVIRONMENT_BLOCKED')

    def test_missing_session_does_not_launch_browser(self):
        with tempfile.TemporaryDirectory() as temp:
            p = demo_profile()
            record = {'profile': p, 'sha256': digest(p), 'approved_sha256': digest(p)}
            with patch('handnavigate.portal_runner.launch_browser') as launch:
                result = run_export(record, SessionVault(Path(temp) / 'vault'), PHRASE, topic='parks', output=temp)
            launch.assert_not_called()
            self.assertEqual(result['error']['code'], 'AUTH_REQUIRED')
            self.assertEqual(result['verified_files'], [])


class BrowserSemanticComponentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manager = sync_playwright().start()
        cls.browser = launch_browser(cls.manager)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.manager.stop()

    def setUp(self):
        self.page = self.browser.new_page()
        self.addCleanup(self.page.close)
        self.profile = demo_profile()

    def test_exact_account_identity_from_actual_dom(self):
        self.page.set_content('<strong data-testid="account-id">demo@handnavigate.local</strong>')
        assert_account(self.page, self.profile)
        self.page.locator('strong').evaluate('(el)=>el.textContent="someone-else"')
        with self.assertRaises(Halt) as c:
            assert_account(self.page, self.profile)
        self.assertEqual(c.exception.code, 'ACCOUNT_MISMATCH')

    def test_signin_indicator_prevents_action(self):
        self.page.set_content('<div data-testid="login-required">Session expired</div>')
        with self.assertRaises(Halt) as c:
            assert_account(self.page, self.profile)
        self.assertEqual(c.exception.code, 'AUTH_REQUIRED')

    def test_ambiguous_control_halts_instead_of_first_match(self):
        self.page.set_content('<button>Find reports</button><button>Find reports</button>')
        with self.assertRaises(Halt) as c:
            locate(self.page, self.profile['controls']['submit'])
        self.assertEqual(c.exception.code, 'AMBIGUOUS_TARGET')

    def test_hidden_control_does_not_override_visible_control(self):
        self.page.set_content('<button hidden>Find reports</button><button>Find reports</button>')
        self.assertTrue(locate(self.page, self.profile['controls']['submit']).is_visible())


class ConnectionStudioAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ctx = running_studio('http://127.0.0.1:49999', Path(self.temp.name), port=0)
        self.server = self.ctx.__enter__()
        self.addCleanup(self.ctx.__exit__, None, None, None)
        self.profile = demo_profile()

    def request(self, path, body=None, token=True):
        headers = {}
        data = None
        if body is not None:
            headers = {'Origin': self.server.origin, 'Content-Type': 'application/json'}
            if token:
                headers['X-HandNavigate-Token'] = self.server.csrf
            data = json.dumps(body).encode()
        req = urllib.request.Request(self.server.origin + path, data=data, headers=headers)
        try:
            response = urllib.request.urlopen(req, timeout=5)
        except urllib.error.HTTPError as e:
            response = e
        with response:
            return response.status, json.loads(response.read())

    def test_import_review_and_forget_api(self):
        status, draft = self.request('/api/connections', {'profile': self.profile})
        self.assertEqual(status, 201)
        self.assertEqual(draft['status'], 'DRAFT')
        status, approved = self.request('/api/connections/approve', {'connection_id': self.profile['id'], 'reviewed_sha256': draft['sha256'], 'permission_confirmed': True})
        self.assertEqual(status, 200)
        self.assertEqual(approved['status'], 'APPROVED_NOT_QUALIFIED')
        status, result = self.request('/api/connections/forget', {'connection_id': self.profile['id']})
        self.assertFalse(result['remote_session_revoked'])
        self.assertIsNone(self.server.connections.get(self.profile['id'])['approved_sha256'])

    def test_profile_mutation_requires_local_origin_and_token(self):
        self.assertEqual(self.request('/api/connections', {'profile': self.profile}, token=False)[0], 403)
        self.assertEqual(self.server.connections.list(), [])

    def test_status_never_exposes_session_bytes(self):
        self.server.connections.put(self.profile)
        self.server.vault.save(self.profile, state_for(self.profile), PHRASE)
        status, body = self.request('/api/status')
        self.assertEqual(status, 200)
        self.assertTrue(body['connections'][0]['session']['encrypted_file_present'])
        self.assertEqual(body['connections'][0]['session']['validity'], 'NOT_CHECKED')
        serialized = json.dumps(body)
        self.assertNotIn('synthetic-cookie-never-public', serialized)
        self.assertNotIn(PHRASE, serialized)
        self.assertNotIn('ciphertext', serialized)

    def test_private_fields_rejected_before_persistence(self):
        status, body = self.request('/api/connections', {'profile': {**self.profile, 'password': 'private'}})
        self.assertEqual(status, 400)
        self.assertEqual(self.server.connections.list(), [])


class RealBrowserHTTPGateTests(unittest.TestCase):
    def test_browser_signin_capture_and_separate_context_export(self):
        with running_portal() as portal, tempfile.TemporaryDirectory() as temp:
            probe = browser_probe(portal.origin)
            OBSERVATIONS.append(probe)
            if probe['status'] == 'BLOCKED':
                if os.environ.get('HANDNAVIGATE_REQUIRE_BROWSER_HTTP') == '1':
                    self.fail('CI requires real browser HTTP, but administrator policy blocked navigation')
                self.skipTest('Observed ERR_BLOCKED_BY_ADMINISTRATOR; no policy bypass; browser HTTP remains unqualified')
            self.assertEqual(probe['status'], 'PASS', probe)
            p = demo_profile(portal.origin)
            vault = SessionVault(Path(temp) / 'vault')
            with sync_playwright() as pw:
                browser = launch_browser(pw)
                try:
                    context = browser.new_context(service_workers='block')
                    guard = BrowserGuard(p, phase='login')
                    guard.install(context)
                    page = context.new_page()
                    page.goto(portal.origin + '/login')
                    page.get_by_role('button', name='Sign in to demo', exact=True).click()
                    page.goto(portal.origin + '/reports')
                    guard.check()
                    assert_account(page, p)
                    vault.save(p, context.storage_state(), PHRASE)
                finally:
                    browser.close()
            record = {'profile': p, 'sha256': digest(p), 'approved_sha256': digest(p)}
            report = run_export(record, vault, PHRASE, topic='parks', output=temp)
            self.assertEqual(report['status'], 'VERIFIED_EXPORT', report)
            self.assertEqual(report['verified_files'][0]['rows'], 5)
            portal.expire_sessions()
            expired = run_export(record, vault, PHRASE, topic='parks', output=temp)
            self.assertEqual(expired['error']['code'], 'AUTH_REQUIRED')
            self.assertEqual(expired['verified_files'], [])
            OBSERVATIONS.append({'layer': 'real browser HTTP', 'status': report['status'], 'rows': 5, 'expired_session': expired['error']['code']})
