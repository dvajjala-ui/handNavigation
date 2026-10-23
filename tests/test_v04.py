"""Guided teaching qualification: contracts, owned DOM, persistence and HTTP API.

Automated demonstrations are explicitly not human usability studies. No test
in this module claims actual website navigation, authentication or downloads.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request
from uuid import uuid4

from playwright.sync_api import sync_playwright

from handnavigate.contracts import ContractError, digest
from handnavigate.controller import Controller
from handnavigate.runner import launch_browser
from handnavigate.studio import running_studio, teaching_html
from handnavigate.teaching import (ADAPTER, compile_lesson, example_bindings, example_events,
                                   example_recipe, example_rows, make_plan, validate_lesson,
                                   validate_rows)
from handnavigate.teaching_runner import attach_recorder, execute_lesson, load_practice, record_example
from handnavigate.teaching_service import TeachingService

OBSERVATIONS = []


class LessonContractTests(unittest.TestCase):
    def setUp(self):
        self.recipe, self.rows = example_recipe(), example_rows()

    def test_explicit_bindings_produce_typed_variables_and_assertions(self):
        self.assertEqual(self.recipe['parameters']['captions'], {'type': 'boolean'})
        self.assertEqual(len(self.recipe['verification']['expected']), 3)
        self.assertEqual(make_plan(self.recipe, self.rows)['action_count'], 12)

    def test_recorded_constant_stays_fixed_in_every_row(self):
        bindings = example_bindings(); bindings['layout'] = {'mode': 'constant'}
        recipe = compile_lesson(example_events(), bindings, name='Fixed layout',
                                verification_contract=ADAPTER['verifier'])
        self.assertNotIn('layout', recipe['parameters'])
        rows = deepcopy(self.rows)
        for row in rows: del row['values']['layout']
        self.assertEqual([r['expected']['layout'] for r in make_plan(recipe, rows)['rows']], ['detailed'] * 3)

    def test_all_constants_require_no_fake_input_variables(self):
        recipe = compile_lesson(example_events(), {f: {'mode': 'constant'} for f in ADAPTER['fields']},
                                name='Fixed preview', verification_contract=ADAPTER['verifier'])
        self.assertEqual(recipe['parameters'], {})
        self.assertEqual(make_plan(recipe, [{'row_id': 'one', 'values': {}}])['row_count'], 1)

    def test_private_and_unsupported_events_block_compilation(self):
        for event in [{'op': 'blocked', 'reason': 'private_control'}, {'op': 'javascript', 'code': 'alert(1)'}]:
            events = example_events(); events.insert(1, event)
            with self.subTest(event=event), self.assertRaises(ContractError):
                compile_lesson(events, example_bindings(), name='No', verification_contract=ADAPTER['verifier'])

    def test_every_field_and_final_effect_must_be_explicit(self):
        for events in [example_events()[:-1], example_events()[1:], example_events() + example_events(), []]:
            with self.subTest(events=events), self.assertRaises(ContractError):
                compile_lesson(events, example_bindings(), name='No', verification_contract=ADAPTER['verifier'])

    def test_repeat_is_bounded_and_always_stops_on_error(self):
        for value in [True, 0, 21, '10']:
            recipe = deepcopy(self.recipe); recipe['repeat']['max_rows'] = value
            with self.subTest(value=value), self.assertRaises(ContractError): validate_lesson(recipe)
        recipe = deepcopy(self.recipe); recipe['repeat']['stop_on_error'] = False
        with self.assertRaises(ContractError): validate_lesson(recipe)

    def test_verifier_cannot_be_replaced_by_a_success_banner(self):
        recipe = deepcopy(self.recipe); recipe['verification']['contract'] = 'page_says_success'
        with self.assertRaises(ContractError): validate_lesson(recipe)
        recipe = deepcopy(self.recipe); recipe['verification']['expected']['topic'] = {'literal': 'other'}
        with self.assertRaises(ContractError): validate_lesson(recipe)

    def test_executable_code_urls_and_selectors_cannot_enter_recipe(self):
        for key, value in [('script', 'fetch(document.cookie)'), ('origin', 'https://example.com'), ('selector', '*')]:
            recipe = {**self.recipe, key: value}
            with self.subTest(key=key), self.assertRaises(ContractError): validate_lesson(recipe)
        recipe = deepcopy(self.recipe); recipe['steps'][0]['value'] = {'expression': '1+1'}
        with self.assertRaises(ContractError): validate_lesson(recipe)

    def test_reserved_and_duplicate_variable_names_are_rejected(self):
        for name in ['constructor', '__proto__', 'a.b', 'row_id', 'layout']:
            bindings = example_bindings(); bindings['topic']['name'] = name
            with self.subTest(name=name), self.assertRaises(ContractError):
                compile_lesson(example_events(), bindings, name='No', verification_contract=ADAPTER['verifier'])

    def test_input_types_missing_keys_duplicates_and_limits_are_checked(self):
        bad_rows = []
        for key, value in [('captions', 'false'), ('captions', 1), ('topic', ''), ('topic', 'x' * 81), ('layout', 'unknown')]:
            rows = deepcopy(self.rows); rows[0]['values'][key] = value; bad_rows.append(rows)
        rows = deepcopy(self.rows); del rows[0]['values']['topic']; bad_rows.append(rows)
        bad_rows.extend([[], self.rows * 2, [{'row_id': '../escape', 'values': self.rows[0]['values']}], self.rows * 8])
        for rows in bad_rows:
            with self.subTest(rows=rows), self.assertRaises(ContractError): validate_rows(self.recipe, rows)

    def test_intermediate_parameter_values_are_type_checked_too(self):
        recipe = deepcopy(self.recipe)
        recipe['steps'].insert(3, {'id': 'fixed-topic', 'op': 'fill', 'field': 'topic', 'value': {'literal': 'fixed'}})
        recipe['verification']['expected']['topic'] = {'literal': 'fixed'}
        validate_lesson(recipe)
        rows = deepcopy(self.rows); rows[0]['values']['topic'] = {'unsafe': 'value'}
        with self.assertRaises(ContractError): validate_rows(recipe, rows)

    def test_changes_to_recipe_rows_order_and_adapter_invalidate_plan(self):
        original = make_plan(self.recipe, self.rows)['plan_sha256']
        for rows in [self.rows[::-1], [{**self.rows[0], 'row_id': 'changed'}] + self.rows[1:]]:
            self.assertNotEqual(make_plan(self.recipe, rows)['plan_sha256'], original)
        recipe = deepcopy(self.recipe); recipe['name'] = 'A new reviewed version'
        self.assertNotEqual(make_plan(recipe, self.rows)['plan_sha256'], original)
        recipe['adapter_sha256'] = '0' * 64
        with self.assertRaises(ContractError): validate_lesson(recipe)


class OwnedRecorderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manager = sync_playwright().start(); cls.browser = launch_browser(cls.manager)
    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.manager.stop()
    def setUp(self):
        self.page = self.browser.new_page(); self.addCleanup(self.page.close); load_practice(self.page)

    def test_actual_fill_select_check_click_events_compile(self):
        events = record_example(self.page)
        self.assertEqual(events, example_events())
        recipe = compile_lesson(events, example_bindings(), name='Browser example', verification_contract=ADAPTER['verifier'])
        self.assertEqual(len(recipe['steps']), 4)
        OBSERVATIONS.append({'test': self.id(), 'layer': 'real Chromium owned DOM; actions driven by Playwright, not a human', 'recorded_events': events})

    def test_start_stop_bounds_capture_and_excludes_other_ui(self):
        attach_recorder(self.page)
        self.page.evaluate('lessonRecorder.stop()')
        self.page.get_by_label('Topic', exact=True).fill('not recorded')
        self.assertEqual(self.page.evaluate('lessonRecorder.snapshot().events'), [])
        self.page.evaluate('lessonRecorder.start();document.body.insertAdjacentHTML("beforeend",\'<input aria-label="Outside">\')')
        self.page.get_by_label('Outside', exact=True).fill('outside secret')
        self.assertEqual(self.page.evaluate('lessonRecorder.snapshot().events'), [])

    def test_private_ancestor_password_and_autocomplete_values_never_captured(self):
        attach_recorder(self.page)
        for code in ["el.type='password'", "el.parentElement.setAttribute('data-private','')", "el.autocomplete='one-time-code'"]:
            self.page.evaluate('(code)=>{const el=document.querySelector("[data-hn-field=topic]");el.type="text";el.parentElement.removeAttribute("data-private");el.autocomplete="off";}', code)
            # Owned test-only mutation, never recipe-generated script.
            self.page.locator('[data-hn-field=topic]').evaluate('(el)=>{'+code+'}')
            self.page.get_by_label('Topic', exact=True).fill('TEST_SECRET_DO_NOT_CAPTURE')
            self.page.evaluate('lessonRecorder.captureInputs()')
        events = self.page.evaluate('lessonRecorder.stop().events')
        self.assertNotIn('TEST_SECRET', json.dumps(events))
        self.assertTrue(any(e['op'] == 'blocked' for e in events))

    def test_capture_current_values_includes_explicit_false_default(self):
        attach_recorder(self.page)
        self.page.get_by_label('Topic', exact=True).fill('gardens')
        self.page.evaluate('lessonRecorder.captureInputs()')
        self.page.get_by_role('button', name='Prepare preview', exact=True).click()
        events = self.page.evaluate('lessonRecorder.stop().events')
        self.assertIn({'op': 'check', 'field': 'captions', 'value': False}, events)
        self.assertEqual(len(compile_lesson(events, example_bindings(), name='Defaults', verification_contract=ADAPTER['verifier'])['steps']), 4)

    def test_unknown_button_is_not_silently_ignored(self):
        attach_recorder(self.page)
        self.page.evaluate('document.querySelector("#owned-workspace").insertAdjacentHTML("beforeend","<button>Unapproved</button>")')
        self.page.get_by_role('button', name='Unapproved', exact=True).click()
        self.assertEqual(self.page.evaluate('lessonRecorder.snapshot().events')[0]['op'], 'blocked')

    def test_adjacent_typing_is_coalesced_without_erasing_click_boundaries(self):
        attach_recorder(self.page)
        self.page.get_by_label('Topic', exact=True).press_sequentially('architecture')
        self.assertEqual(len(self.page.evaluate('lessonRecorder.snapshot().events')), 1)
        self.page.get_by_role('button', name='Prepare preview', exact=True).click()
        self.page.get_by_label('Topic', exact=True).fill('gardens')
        self.assertEqual([e['op'] for e in self.page.evaluate('lessonRecorder.snapshot().events')], ['fill', 'click', 'fill'])


class OwnedRehearsalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.recipe = example_recipe(); self.rows = example_rows()
    def run_owned(self, **kwargs):
        return execute_lesson(self.recipe, {'recipe_sha256': digest(self.recipe)}, self.rows,
                              output=self.root, reviewed_plan_sha256=make_plan(self.recipe, self.rows)['plan_sha256'], **kwargs)

    def test_three_rows_replayed_and_verified_with_actual_files(self):
        result = self.run_owned()
        self.assertEqual((result['status'], result['verified_rows'], result['model_calls'], result['network_requests']), ('VERIFIED', 3, 0, 0))
        self.assertEqual(len(result['steps']), 12)
        for row in result['rows']:
            saved = json.loads((self.root / row['artifact']['path']).read_text())
            self.assertEqual(saved['observed'], saved['expected'])
        OBSERVATIONS.append({'test': self.id(), 'layer': 'real Chromium owned DOM + local verified JSON files', 'report': result})

    def test_twenty_row_bound_supports_a_longer_deterministic_batch(self):
        self.recipe['repeat']['max_rows'] = 20
        self.rows = [{'row_id': f'item-{i}', 'values': {**example_rows()[i % 3]['values'], 'topic': f'topic {i}'}} for i in range(20)]
        result = self.run_owned()
        self.assertEqual((result['status'], result['verified_rows'], len(result['steps'])), ('VERIFIED', 20, 80))
        OBSERVATIONS.append({'test': self.id(), 'layer': 'real Chromium owned DOM, not a long-running remote-site trial',
                             'verified_rows': 20, 'executed_actions': 80, 'output_checks': 60, 'model_calls': result['model_calls']})

    def test_wrong_output_stops_before_later_rows(self):
        result = self.run_owned(case='wrong-topic')
        self.assertEqual((result['status'], result['verified_rows']), ('HALTED', 0))
        self.assertEqual(result['error']['code'], 'OUTPUT_MISMATCH')
        self.assertEqual({e['row_id'] for e in result['steps']}, {'architecture'})

    def test_missing_output_does_not_count_click_as_success(self):
        result = self.run_owned(case='missing-output')
        self.assertEqual(result['status'], 'HALTED'); self.assertEqual(result['verified_rows'], 0)

    def test_ambiguous_target_is_not_resolved_by_first_match(self):
        result = self.run_owned(case='ambiguous-control')
        self.assertEqual(result['error']['code'], 'AMBIGUOUS_TARGET')
        self.assertFalse(any(s['op'] == 'click' for s in result['steps']))

    def test_delayed_output_waits_for_expected_state(self):
        result = self.run_owned(case='delayed-output')
        self.assertEqual(result['status'], 'VERIFIED')

    def test_unexpected_dialog_halts_without_acceptance(self):
        result = self.run_owned(case='dialog')
        self.assertEqual(result['error']['code'], 'UNEXPECTED_EFFECT')

    def test_cancel_after_verified_row_preserves_evidence_and_skips_rest(self):
        cancel = threading.Event()
        result = self.run_owned(cancel_event=cancel, on_progress=lambda report: cancel.set())
        self.assertEqual((result['status'], result['verified_rows']), ('CANCELLED', 1))
        self.assertEqual(len(list((self.root / 'lesson-artifacts').glob('*.json'))), 1)

    def test_stale_plan_and_unapproved_recipe_never_launch_browser(self):
        with patch('handnavigate.teaching_runner.launch_browser') as launch:
            with self.assertRaises(ContractError):
                execute_lesson(self.recipe, {}, self.rows, output=self.root, reviewed_plan_sha256='x')
            with self.assertRaises(ContractError):
                execute_lesson(self.recipe, {'recipe_sha256': digest(self.recipe)}, self.rows, output=self.root, reviewed_plan_sha256='x')
            launch.assert_not_called()

    def test_cancelled_before_start_does_not_launch_browser(self):
        event = threading.Event(); event.set()
        with patch('handnavigate.teaching_runner.launch_browser') as launch:
            result = self.run_owned(cancel_event=event)
            launch.assert_not_called()
        self.assertEqual(result['status'], 'CANCELLED')


class TeachingPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.controller = Controller(self.root, 'http://127.0.0.1:49999', autostart=False)
        self.addCleanup(self.controller.close)
        self.calls = []
        def simulated(recipe, approval, rows, **kwargs):
            self.calls.append(kwargs['run_id'])
            return {'run_id': kwargs['run_id'], 'status': 'VERIFIED', 'verified_rows': len(rows), 'input_rows': len(rows),
                    'model_calls': 0, 'rows': [], 'test_double': 'Persistence test, not browser evidence'}
        self.service = TeachingService(self.controller.store, self.root, self.controller.execution_lock, execute=simulated)
        self.addCleanup(self.service.close)
        self.lesson = self.service.create(example_recipe())
        self.service.approve(self.lesson['id'], self.lesson['sha256'], True)
        self.rows = example_rows(); self.plan = self.service.plan(self.lesson['id'], self.rows)

    def start(self, key=None):
        return self.service.start(self.lesson['id'], self.rows, self.plan['plan_sha256'], key or str(uuid4()))

    def test_import_is_unapproved_and_checksum_acknowledgement_is_required(self):
        lesson = self.service.create(example_recipe())
        self.assertFalse(lesson['approved'])
        for checksum, consent in [('wrong', True), (lesson['sha256'], False), (lesson['sha256'], 'yes')]:
            with self.subTest(checksum=checksum), self.assertRaises(ContractError):
                self.service.approve(lesson['id'], checksum, consent)

    def test_repeated_request_id_does_not_repeat_the_effect(self):
        key = str(uuid4()); first = self.start(key); self.service.thread.join(5)
        second = self.start(key)
        self.assertEqual(first['run_id'], second['run_id']); self.assertTrue(second['deduplicated'])
        self.assertEqual(len(self.calls), 1)

    def test_reused_request_id_cannot_mean_different_inputs(self):
        key = str(uuid4()); self.start(key); self.service.thread.join(5)
        self.rows[0]['values']['topic'] = 'changed'; self.plan = self.service.plan(self.lesson['id'], self.rows)
        with self.assertRaises(ContractError): self.start(key)

    def test_shared_execution_lock_blocks_scheduler_and_second_teaching_run(self):
        entered, release = threading.Event(), threading.Event()
        original = self.service.execute
        def controlled(*args, **kwargs):
            entered.set(); release.wait(5); return original(*args, **kwargs)
        self.service.execute = controlled
        self.addCleanup(release.set)
        self.start(); self.assertTrue(entered.wait(3))
        self.assertIsNone(self.controller.tick())
        with self.assertRaises(ContractError): self.start()
        release.set(); self.service.thread.join(5)
        self.assertFalse(self.controller.execution_lock.locked())

    def test_revoked_approval_blocks_new_execution(self):
        self.service.revoke(self.lesson['id'])
        with self.assertRaises(ContractError): self.start()
        self.assertEqual(self.calls, [])

    def test_interruption_requires_review_and_never_auto_retries(self):
        key = str(uuid4())
        with self.controller.store.connection(write=True) as db:
            db.execute('INSERT INTO teaching_runs VALUES(?,?,?,?,?,?,?,?,?)',
                       (key, str(uuid4()), self.lesson['id'], self.plan['plan_sha256'], json.dumps(self.rows), 'RUNNING', '2026-10-23T00:00:00Z', None, None))
        recovered = TeachingService(self.controller.store, self.root, self.controller.execution_lock, execute=self.service.execute)
        self.addCleanup(recovered.close)
        self.assertEqual(recovered.snapshot()['runs'][0]['state'], 'NEEDS_REVIEW')
        with self.assertRaises(ContractError): recovered.start(self.lesson['id'], self.rows, self.plan['plan_sha256'], str(uuid4()))
        recovered.acknowledge(key, 'REVIEWED_WITHOUT_RETRY')
        self.assertEqual(self.calls, [])
        self.assertEqual(recovered.snapshot()['runs'][0]['state'], 'ACKNOWLEDGED')

    def test_failed_worker_start_preserves_review_state_and_releases_slot(self):
        with patch('handnavigate.teaching_service.threading.Thread.start', side_effect=RuntimeError('injected thread failure')):
            with self.assertRaises(RuntimeError): self.start()
        self.assertEqual(self.service.snapshot()['runs'][0]['state'], 'NEEDS_REVIEW')
        self.assertFalse(self.controller.execution_lock.locked())
        self.assertEqual(self.calls, [])
        # An unstarted Thread cannot be joined; no worker actually exists here.
        self.service.thread = None
        with self.assertRaises(ContractError): self.start()

    def test_worker_bookkeeping_failure_is_uncertain_not_automatic_retry(self):
        self.service.execute = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('injected failure'))
        self.start(); self.service.thread.join(5)
        self.assertEqual(self.service.snapshot()['runs'][0]['state'], 'NEEDS_REVIEW')
        self.assertTrue(self.service.error)


class TeachingStudioAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.ctx = running_studio('http://127.0.0.1:49999', Path(self.temp.name), port=0)
        self.server = self.ctx.__enter__(); self.addCleanup(self.ctx.__exit__, None, None, None)

    def request(self, path, body=None, token=True, raw=False):
        headers, data = {}, None
        if body is not None:
            data = json.dumps(body).encode()
            headers = {'Origin': self.server.origin, 'Content-Type': 'application/json'}
            if token: headers['X-HandNavigate-Token'] = self.server.csrf
        try: response = urllib.request.urlopen(urllib.request.Request(self.server.origin + path, data=data, headers=headers), timeout=10)
        except urllib.error.HTTPError as exc: response = exc
        with response:
            content = response.read()
            return response.status, content if raw else json.loads(content)

    def test_teaching_screen_is_served_with_real_token_and_no_unresolved_assets(self):
        status, content = self.request('/teach', raw=True)
        self.assertEqual(status, 200)
        self.assertNotIn(b'__CSRF_TOKEN__', content); self.assertNotIn(b'__TEACHING_APP__', content)
        self.assertIn(self.server.csrf.encode(), content)
        self.assertIn(b'HandNavigateTeachingRecorder', content)

    def test_mutations_require_origin_and_csrf_token(self):
        status, _ = self.request('/api/teaching/import', {'recipe': example_recipe()}, token=False)
        self.assertEqual(status, 403)

    def test_import_cannot_smuggle_approval_and_unknown_fields_are_rejected(self):
        status, _ = self.request('/api/teaching/import', {'recipe': example_recipe(), 'approved': True})
        self.assertEqual(status, 400)
        status, lesson = self.request('/api/teaching/import', {'recipe': example_recipe()})
        self.assertEqual(status, 201); self.assertFalse(lesson['approved'])

    def test_compile_endpoint_uses_explicit_bindings_and_verifier(self):
        status, lesson = self.request('/api/teaching/compile', {'events': example_events(), 'bindings': example_bindings(),
            'name': 'API draft', 'max_rows': 10, 'verification_contract': ADAPTER['verifier']})
        self.assertEqual(status, 201); self.assertFalse(lesson['approved'])
        self.assertEqual(lesson['recipe']['parameters']['captions']['type'], 'boolean')

    def test_http_api_starts_actual_owned_browser_run_and_checks_artifact_tamper(self):
        _, lesson = self.request('/api/teaching/import', {'recipe': example_recipe()})
        _, plan = self.request('/api/teaching/plan', {'lesson_id': lesson['id'], 'rows': example_rows()})
        request = {'lesson_id': lesson['id'], 'rows': example_rows(), 'reviewed_plan_sha256': plan['plan_sha256'], 'request_id': str(uuid4())}
        self.assertEqual(self.request('/api/teaching/run', request)[0], 400)
        self.assertEqual(self.request('/api/teaching/approve', {'lesson_id': lesson['id'], 'reviewed_sha256': lesson['sha256'], 'acknowledgement': True})[0], 200)
        status, result = self.request('/api/teaching/run', request)
        self.assertEqual(status, 202)
        self.server.teaching.thread.join(20)
        _, state = self.request('/api/teaching')
        report = state['runs'][0]['report']; self.assertEqual(report['status'], 'VERIFIED')
        url = '/api/teaching/artifact?run=' + result['run_id'] + '&row=architecture'
        status, artifact = self.request(url)
        self.assertEqual(status, 200); self.assertEqual(artifact['observed']['topic'], 'architecture')
        path = Path(self.temp.name) / report['rows'][0]['artifact']['path']; path.write_text('tampered')
        self.assertEqual(self.request(url)[0], 409)
        duplicate = self.request('/api/teaching/run', request)[1]
        self.assertTrue(duplicate['deduplicated'])
        OBSERVATIONS.append({'test': self.id(), 'layer': 'actual localhost HTTP API + real in-memory browser runner, not browser HTTP navigation',
                             'status': report['status'], 'verified_rows': report['verified_rows'], 'artifact_tamper_rejected': True, 'duplicate_request_replayed': False})


if __name__ == '__main__':
    unittest.main(verbosity=2)
