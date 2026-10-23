"""Experimental supervised CSV export. Separate from the qualified fixture scheduler.

Application request interception is defense-in-depth, not an OS network boundary.
No model, credentials prompt in the webpage, auto repair, or write-task API exists.
"""
from __future__ import annotations
import csv
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import tempfile
import time
from urllib.parse import urljoin
from uuid import uuid4

from playwright.sync_api import Error as BrowserError, TimeoutError as BrowserTimeout, sync_playwright

from .contracts import ContractError, digest
from .connectors import request_allowed, timestamp, validate_profile
from .runner import Halt, launch_browser
from .vault import SessionError


def verify_csv(data, contract, topic):
    if not isinstance(data, bytes) or not 1 <= len(data) <= contract['max_bytes']:
        raise Halt('FILE_SIZE', 'Export is outside the approved byte budget')
    try:
        text = data.decode('utf-8-sig')
        if '\x00' in text:
            raise ValueError()
        reader = csv.reader(io.StringIO(text, newline=''), strict=True)
        header = next(reader)
        if header != contract['columns']:
            raise Halt('CSV_SCHEMA', 'Export columns do not match the reviewed contract')
        identities, count = set(), 0
        index = header.index(contract['unique_column'])
        topic_index = header.index(contract['topic_column'])
        for row in reader:
            count += 1
            if count > contract['max_rows'] or len(row) != len(header):
                raise Halt('CSV_ROWS', 'Export row shape or count exceeds the reviewed contract')
            if any(value.lstrip().startswith(('=', '+', '-', '@')) for value in row):
                raise Halt('CSV_FORMULA', 'Spreadsheet-formula-like cell rejected by the conservative export contract')
            if any(any(ord(c) < 32 for c in value) for value in row):
                raise Halt('CSV_CONTROL', 'Control characters are not supported by this CSV profile')
            if row[topic_index] != topic:
                raise Halt('CSV_TOPIC', 'Export does not match the requested topic')
            key = row[index]
            if not key.strip() or key in identities:
                raise Halt('CSV_IDENTITY', 'Export contains missing or duplicated item identities')
            identities.add(key)
        if count < contract['min_rows']:
            raise Halt('CSV_ROWS', 'Export contains fewer rows than required')
        return {'sha256': sha256(data).hexdigest(), 'bytes': len(data), 'rows': count,
                'columns': header, 'verification': 'schema, bounded rows, unique IDs, exact topic, conservative cell checks'}
    except (UnicodeError, csv.Error, StopIteration, ValueError) as exc:
        raise Halt('CSV_FORMAT', 'Export is not a supported UTF-8 CSV') from exc


def locate(scope, strategies, *, required=True):
    for strategy in strategies:
        if strategy['by'] == 'label':
            target = scope.get_by_label(strategy['value'], exact=True)
        elif strategy['by'] == 'role':
            target = scope.get_by_role(strategy['role'], name=strategy['name'], exact=True)
        else:
            target = scope.get_by_test_id(strategy['value'])
        if target.count() > 20:
            raise Halt('AMBIGUOUS_TARGET', 'Too many matching controls')
        matches = [target.nth(i) for i in range(target.count()) if target.nth(i).is_visible()]
        if len(matches) > 1:
            raise Halt('AMBIGUOUS_TARGET', 'Multiple visible controls match the approved target')
        if matches:
            return matches[0]
    if required:
        raise Halt('TARGET_NOT_FOUND', 'No unique visible approved control was found')
    return None


def assert_account(page, profile):
    if locate(page, profile['controls']['auth_required'], required=False) is not None:
        raise Halt('AUTH_REQUIRED', 'Human sign-in is required; no automatic login or retry')
    target = locate(page, profile['account']['target'], required=False)
    if target is None:
        raise Halt('AUTH_REQUIRED', 'The reviewed signed-in account indicator is missing')
    if target.inner_text().strip() != profile['account']['expected']:
        raise Halt('ACCOUNT_MISMATCH', 'The displayed account differs from the reviewed account')


class BrowserGuard:
    def __init__(self, profile, phase='run'):
        self.profile, self.phase = profile, phase
        self.blocked = []

    def install(self, context):
        context.route('**/*', self.route)
        context.route_web_socket('**/*', self.socket)
        context.on('page', self.new_page)

    def new_page(self, page):
        page.on('dialog', self.dialog)
        if len(page.context.pages) > 1:
            self.blocked.append('POPUP')
            page.close()

    def dialog(self, dialog):
        self.blocked.append('DIALOG')
        dialog.dismiss()

    def socket(self, socket):
        self.blocked.append('WEBSOCKET')
        socket.close()

    def route(self, route):
        request = route.request
        if not request_allowed(self.profile, request.url, request.method, self.phase):
            self.blocked.append('REQUEST_OUTSIDE_REVIEWED_POLICY')
            return route.abort('blockedbyclient')
        try:
            response = route.fetch(max_redirects=0, timeout=10000)
            if 300 <= response.status < 400:
                self.blocked.append('REDIRECT_REQUIRES_REVIEW')
                route.abort('blockedbyclient')
            else:
                route.fulfill(response=response)
        except BrowserError:
            self.blocked.append('NETWORK_FAILURE')
            route.abort('failed')

    def check(self):
        if self.blocked:
            raise Halt('NETWORK_POLICY', 'A request, redirect or browser surface needs review')


def error_report(exc):
    if isinstance(exc, (Halt, SessionError)):
        return {'code': exc.code, 'message': str(exc)}
    if isinstance(exc, BrowserError) and 'ERR_BLOCKED_BY_ADMINISTRATOR' in str(exc):
        return {'code': 'ENVIRONMENT_BLOCKED', 'message': 'Browser navigation is blocked by administrator policy. No policy was changed.'}
    if isinstance(exc, BrowserTimeout):
        return {'code': 'TIMEOUT', 'message': 'Expected state or download did not arrive; no automatic retry'}
    # Browser errors can contain URL tokens, form data and page text. Never persist them.
    return {'code': 'RUNTIME_ERROR', 'message': f'{type(exc).__name__}: details withheld to protect session data; no automatic retry'}


def require_approved(record):
    profile = record['profile']
    validate_profile(profile)
    if record.get('approved_sha256') != digest(profile) or record.get('sha256') != digest(profile):
        raise ContractError('Approve this exact connection version before browser access')
    return profile


def capture_session(record, vault, passphrase, *, confirm=input, ttl_hours=8):
    """Human performs sign-in in a visible isolated browser; no input recording."""
    profile = require_approved(record)
    with sync_playwright() as playwright:
        browser = launch_browser(playwright, headless=False)
        try:
            context = browser.new_context(service_workers='block', accept_downloads=False)
            guard = BrowserGuard(profile, phase='login')
            guard.install(context)
            page = context.new_page()
            page.set_default_timeout(10000)
            page.goto(profile['origin'] + profile['login_path'], wait_until='domcontentloaded')
            if confirm('Complete sign-in in the browser. Type SAVE to check the account and save encrypted state: ').strip() != 'SAVE':
                raise ContractError('Session capture cancelled; no session saved')
            guard.check()
            page.goto(profile['origin'] + profile['entry_path'], wait_until='domcontentloaded')
            guard.check()
            assert_account(page, profile)
            return vault.save(profile, context.storage_state(), passphrase, ttl_hours=ttl_hours)
        finally:
            browser.close()


def run_export(record, vault, passphrase, *, topic, output, browser=None):
    profile = require_approved(record)
    if not isinstance(topic, str) or not topic.strip() or len(topic) > 80 or any(ord(c) < 32 for c in topic):
        raise ContractError('Topic must be 1-80 printable characters')
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=True)
    run_id = str(uuid4())
    report = {'run_id': run_id, 'connection_id': profile['id'], 'profile_sha256': digest(profile),
              'status': 'HALTED', 'started_at': timestamp(), 'transport': 'browser_http',
              'browser_navigation_completed': False, 'model_calls': 0, 'verified_files': [],
              'scheduled': False, 'error': None, 'blocked_events': [],
              'notice': 'Experimental supervised export, not production-site qualification'}
    started = time.monotonic()
    context = owned_browser = manager = None
    guard = None
    try:
        state = vault.load(profile, passphrase)
        if browser is None:
            manager = sync_playwright().start()
            owned_browser = launch_browser(manager)
            browser = owned_browser
        context = browser.new_context(storage_state=state, accept_downloads=True, service_workers='block')
        guard = BrowserGuard(profile)
        guard.install(context)
        page = context.new_page()
        page.set_default_timeout(8000)
        response = page.goto(profile['origin'] + profile['entry_path'], wait_until='domcontentloaded')
        guard.check()
        report['browser_navigation_completed'] = True
        assert_account(page, profile)
        if response is not None and response.status >= 400:
            raise Halt('HTTP_STATUS', 'Entry page returned an error status')
        controls = profile['controls']
        locate(page, controls['topic']).fill(topic)
        locate(page, controls['submit']).click()
        deadline = time.monotonic() + 8
        while locate(page, controls['ready'], required=False) is None:
            guard.check()
            assert_account(page, profile)
            if time.monotonic() >= deadline:
                raise Halt('TIMEOUT', 'Report-ready state was not reached')
            page.wait_for_timeout(50)
        guard.check()
        assert_account(page, profile)
        link = locate(page, controls['download'])
        href = link.get_attribute('href')
        if not href or not request_allowed(profile, urljoin(page.url, href), 'GET'):
            raise Halt('DOWNLOAD_DESTINATION', 'Export link is outside the reviewed route contract')
        with page.expect_download(timeout=10000) as pending:
            link.click()
        download = pending.value
        with tempfile.TemporaryDirectory(prefix='handnavigate-export-') as temp:
            temporary = Path(temp) / 'download.bin'
            download.save_as(temporary)
            guard.check()
            assert_account(page, profile)
            if temporary.stat().st_size > profile['file_contract']['max_bytes']:
                raise Halt('FILE_SIZE', 'Export exceeded the reviewed byte budget')
            content = temporary.read_bytes()
            checked = verify_csv(content, profile['file_contract'], topic)
            artifacts = root / 'exports'
            artifacts.mkdir(exist_ok=True)
            target = artifacts / (run_id + '.csv')
            fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            report['verified_files'].append({**checked, 'path': str(target.relative_to(root))})
            report['status'] = 'VERIFIED_EXPORT'
    except Exception as exc:
        report['error'] = error_report(exc)
    finally:
        for obj, method in [(context, 'close'), (owned_browser, 'close'), (manager, 'stop')]:
            if obj is not None:
                try:
                    getattr(obj, method)()
                except Exception:
                    pass
        if guard:
            report['blocked_events'] = guard.blocked
        report['finished_at'] = timestamp()
        report['elapsed_seconds'] = round(time.monotonic() - started, 3)
        reports = root / 'connection-reports'
        reports.mkdir(exist_ok=True)
        (reports / (run_id + '.json')).write_text(json.dumps(report, indent=2))
    return report
