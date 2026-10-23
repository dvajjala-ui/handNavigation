"""Bounded browser rehearsal with independent output checks and per-row evidence.

Only the bundled owned form is loaded into about:blank. No HTTP navigation is
attempted and no network restriction is bypassed. This is not a site adapter.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import threading
import time
from uuid import UUID, uuid4

from playwright.sync_api import expect, sync_playwright

from .contracts import ContractError, digest
from .runner import Halt, launch_browser
from .teaching import ADAPTER, make_plan, timestamp

ASSETS = Path(__file__).resolve().parent / 'assets'
CASES = ('normal', 'wrong-topic', 'missing-output', 'ambiguous-control', 'delayed-output', 'dialog')


def fixture_html() -> str:
    return '<!doctype html><html><head><meta charset="utf-8"><title>HandNavigate owned practice form</title></head><body>' + (ASSETS / 'owned_form.html').read_text() + '</body></html>'


def load_practice(page, *, case='normal') -> None:
    if case not in CASES:
        raise ContractError('Unknown owned practice scenario')
    page.set_content(fixture_html(), wait_until='domcontentloaded')
    page.evaluate((ASSETS / 'owned_form.js').read_text())
    page.evaluate('(scenario)=>HandNavigatePractice.mount(document.querySelector("#owned-workspace"),scenario)', case)


def attach_recorder(page) -> None:
    page.evaluate((ASSETS / 'teaching_recorder.js').read_text())
    page.evaluate('window.lessonRecorder=new HandNavigateTeachingRecorder(document.querySelector("#owned-workspace"));lessonRecorder.start()')


def record_example(page) -> list[dict]:
    """Automated test/demo, not a claim that a human performed the teaching."""
    attach_recorder(page)
    page.get_by_label('Topic', exact=True).fill('architecture')
    page.get_by_label('Layout', exact=True).select_option('detailed')
    page.get_by_label('Include captions', exact=True).set_checked(True)
    page.get_by_role('button', name='Prepare preview', exact=True).click()
    return page.evaluate('lessonRecorder.stop().events')


def safe_report_error(exc: Exception) -> dict:
    if isinstance(exc, Halt):
        return {'code': exc.code, 'message': str(exc)}
    if isinstance(exc, AssertionError):
        return {'code': 'OUTPUT_MISMATCH', 'message': 'An expected output was missing or did not match. Later rows were not started.'}
    from .portal_runner import error_report
    detail = error_report(exc)
    return {'code': detail['code'], 'message': detail['message']}


def execute_lesson(recipe: dict, approval: dict, rows: list[dict], *, output: Path,
                   reviewed_plan_sha256: str, run_id: str | None = None,
                   cancel_event=None, on_progress=None, case='normal',
                   headless=True, budget_seconds=90.0) -> dict:
    plan = make_plan(recipe, rows)
    if not isinstance(approval, dict) or approval.get('recipe_sha256') != digest(recipe):
        raise ContractError('The exact lesson needs explicit review before execution')
    if reviewed_plan_sha256 != plan['plan_sha256']:
        raise ContractError('Inputs or lesson changed after plan review; preview and review again')
    if case not in CASES or type(budget_seconds) not in (int, float) or not 0 < budget_seconds <= 90:
        raise ContractError('Invalid practice scenario or time budget')
    key = run_id or str(uuid4())
    if str(UUID(key)) != key:
        raise ContractError('Invalid run ID')
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=True)
    artifacts = root / 'lesson-artifacts'
    if artifacts.is_symlink():
        raise ContractError('Artifact directory must not be a symlink')
    artifacts.mkdir(exist_ok=True)
    cancel = cancel_event or threading.Event()
    started = time.monotonic()
    violations = []
    report = {'schema_version': 1, 'run_id': key, 'status': 'RUNNING',
              'started_at': timestamp(), 'finished_at': None, 'recipe_sha256': digest(recipe),
              'plan_sha256': plan['plan_sha256'], 'input_rows': len(rows), 'verified_rows': 0,
              'rows': [], 'steps': [], 'model_calls': 0, 'network_requests': 0,
              'scope': 'Owned in-memory form, actual Chromium actions; no HTTP or external site',
              'verification': 'Three exact output values per row, not a success banner',
              'error': None, 'browser_version': None}
    def checkpoint():
        if violations:
            raise Halt('UNEXPECTED_EFFECT', 'A request, navigation, dialog, popup or download was blocked; review required')
        if cancel.is_set():
            raise Halt('CANCELLED', 'Stopped at a safe step boundary; verified rows remain available')
        if time.monotonic() - started > budget_seconds:
            raise Halt('TIME_BUDGET', 'Owned rehearsal exceeded its time budget; no later row was started')
    try:
        checkpoint()
        with sync_playwright() as p:
            browser = launch_browser(p, headless=headless)
            report['browser_version'] = browser.version
            try:
                context = browser.new_context(service_workers='block', accept_downloads=False)
                def deny(route):
                    report['network_requests'] += 1
                    violations.append('request')
                    route.abort()
                context.route('**/*', deny)
                context.route_web_socket('**/*', lambda ws: (violations.append('websocket'), ws.close()))
                for row in plan['rows']:
                    checkpoint()
                    page = context.new_page()
                    page.set_default_timeout(1800)
                    def on_dialog(dialog):
                        violations.append('dialog')
                        dialog.dismiss()
                    page.on('dialog', on_dialog)
                    page.on('popup', lambda popup: (violations.append('popup'), popup.close()))
                    page.on('download', lambda download: (violations.append('download'), download.cancel()))
                    page.on('framenavigated', lambda frame: violations.append('navigation') if frame.url not in ('about:blank', '') else None)
                    load_practice(page, case=case)
                    try:
                        for action in row['actions']:
                            checkpoint()
                            if action['op'] == 'click':
                                target = page.get_by_role('button', name='Prepare preview', exact=True)
                            else:
                                spec = ADAPTER['fields'][action['field']]
                                target = page.get_by_label(spec['label'], exact=True)
                            if target.count() != 1:
                                raise Halt('AMBIGUOUS_TARGET', 'The approved control was missing or not unique; no fallback click was attempted')
                            if action['op'] == 'fill':
                                target.fill(action['value'])
                            elif action['op'] == 'select':
                                target.select_option(value=action['value'])
                            elif action['op'] == 'check':
                                target.set_checked(action['value'])
                            else:
                                target.click()
                            checkpoint()
                            report['steps'].append({'row_id': row['row_id'], 'step_id': action['id'], 'op': action['op'], 'state': 'EXECUTED'})
                        observed = {}
                        expect(page.get_by_test_id('preview-output')).to_be_visible(timeout=1800)
                        for field, expected in row['expected'].items():
                            target = page.get_by_test_id(ADAPTER['outputs'][field])
                            text = ('yes' if expected else 'no') if field == 'captions' else expected
                            expect(target).to_have_text(text, use_inner_text=True, timeout=1800)
                            actual = target.inner_text()
                            if actual != text:
                                raise Halt('OUTPUT_MISMATCH', 'Output did not exactly equal the reviewed value')
                            observed[field] = (actual == 'yes') if field == 'captions' else actual
                        checkpoint()
                        artifact = {'schema_version': 1, 'run_id': key, 'row_id': row['row_id'],
                                    'recipe_sha256': digest(recipe), 'expected': row['expected'],
                                    'observed': observed, 'verified_at': timestamp(),
                                    'scope': report['scope']}
                        data = (json.dumps(artifact, indent=2, ensure_ascii=True) + '\n').encode()
                        target = artifacts / f'{key}-{row["row_id"]}.json'
                        # Exclusive creation prevents a supplied/reused run ID from overwriting evidence.
                        with target.open('xb') as stream:
                            stream.write(data)
                            stream.flush()
                            os.fsync(stream.fileno())
                        receipt = {'row_id': row['row_id'], 'state': 'VERIFIED', 'observed': observed,
                                   'artifact': {'path': str(target.relative_to(root)), 'sha256': sha256(data).hexdigest(), 'bytes': len(data)}}
                        report['rows'].append(receipt)
                        report['verified_rows'] = len(report['rows'])
                        if on_progress:
                            on_progress(json.loads(json.dumps(report)))
                    finally:
                        page.close()
                checkpoint()
                report['status'] = 'VERIFIED'
            finally:
                browser.close()
    except Exception as exc:
        report['status'] = 'CANCELLED' if isinstance(exc, Halt) and exc.code == 'CANCELLED' else 'HALTED'
        report['error'] = safe_report_error(exc)
    report['finished_at'] = timestamp()
    report['duration_ms'] = round((time.monotonic() - started) * 1000)
    report['unstarted_or_unverified_rows'] = len(rows) - report['verified_rows']
    return report
