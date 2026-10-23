"""Run a local demonstration and assemble a read-only UI snapshot from real reports.

The scheduler clock is injected. This is not a claim of an overnight deployment.
No active runtime database or enabled live schedule is shipped in the release.
"""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import tempfile

from playwright.sync_api import sync_playwright

from handnavigate.contracts import digest, load_default
from handnavigate.controller import Controller
from handnavigate.fixture import CASES, running_fixture, load_memory_fixture
from handnavigate.recorder import Recorder, compile_recording
from handnavigate.runner import launch_browser
from handnavigate.scheduling import next_due

ROOT = Path(__file__).resolve().parent
OUT = Path('/mnt/data') if Path('/mnt/data').is_dir() else ROOT / 'deliverables'
OUT.mkdir(parents=True, exist_ok=True)
EVIDENCE = ROOT / 'evidence'


def build():
    spec = {'name': 'Morning inspiration', 'timezone': 'Asia/Kolkata', 'time': '08:00',
            'misfire': 'run_once', 'grace_seconds': 300}
    clock = [datetime(2026, 10, 23, 2, 0, tzinfo=timezone.utc)]
    with tempfile.TemporaryDirectory(prefix='hn-v04-demo-') as directory, running_fixture() as fixture:
        root = Path(directory)
        controller = Controller(root, fixture.origin, clock=lambda: clock[0], autostart=False)
        try:
            recipe = controller.store.recipe()
            request = {'topic': 'architecture', 'limit': 10, 'case': 'normal', 'fixture_transport': 'memory'}
            controller.store.submit_manual(recipe, request, clock[0])
            rehearsal = controller.tick()
            assert rehearsal['status'] == 'VERIFIED', rehearsal
            controller.store.create_schedule(spec, recipe, request, clock[0])
            clock[0] = next_due(spec, clock[0])
            scheduled = controller.tick()
            assert scheduled['status'] == 'VERIFIED', scheduled
            assert controller.tick() is None
            # Record actual browser events, driven by Playwright and clearly labeled.
            with sync_playwright() as p:
                browser = launch_browser(p)
                page = browser.new_page()
                load_memory_fixture(page)
                recorder = Recorder()
                recorder.attach(page)
                page.get_by_label('Topic', exact=True).fill('architecture')
                page.get_by_role('button', name='Search', exact=True).click()
                page.get_by_test_id('results-ready').wait_for()
                page.wait_for_timeout(80)
                events = recorder.events
                browser.close()
            draft = compile_recording(events, example_topic='architecture', ready_test_id='results-ready')
            draft['revision'] = recipe['revision'] + 1
            draft['name'] = 'Recorded search + explicitly selected collection contract'
            draft['steps'].append(deepcopy(load_default()['steps'][-1]))
            controller.store.create_draft(draft, 'Automated local demonstration; explicit topic binding and authored collection template. Not human teaching or learned intent.', clock[0])
            state = {'busy': controller.store.busy(), 'history': controller.store.history(),
                     'recipe': recipe, 'recipe_sha256': digest(recipe), 'cases': CASES,
                     'fixture_transport': 'memory', 'fixture_origin': fixture.origin,
                     'schedules': controller.store.schedules(), 'attempts': controller.store.attempts(),
                     'drafts': controller.store.drafts(), 'audit': controller.store.audit(), 'needs_review': [],
                     'scheduler': {'running': False, 'error': None, 'last_tick_at': clock[0].isoformat(),
                                   'scope': 'Recorded injected-clock demonstration; no live runner in this preview'},
                     'notice': 'Owned synthetic fixture with real browser file downloads. Scheduling uses an injected clock.'}
            for report in state['history']:
                report.pop('report_path', None)
            for attempt in state['attempts']:
                if attempt['report']:
                    attempt['report'].pop('report_path', None)
            artifacts = EVIDENCE / 'v04-sample-files'
            artifacts.mkdir(exist_ok=True)
            manifest = []
            for item in scheduled['verified_files']:
                target = artifacts / Path(item['path']).name
                shutil.copy2(root / item['path'], target)
                manifest.append({**item, 'package_path': str(target.relative_to(ROOT))})
            (artifacts/'manifest.json').write_text(json.dumps(manifest, indent=2))
            proof = {'generated_at': datetime.now(timezone.utc).isoformat(),
                     'clock_basis': 'Injected October 23 clock; two real offline browser runs; not an overnight soak',
                     'automated_recording': True, 'recorded_events': events,
                     'rehearsal': state['history'][1], 'scheduled': state['history'][0],
                     'duplicate_tick': 'No second execution for the same occurrence',
                     'live_runtime_database_included': False}
            (EVIDENCE/'v04-demonstration.json').write_text(json.dumps(proof, indent=2))
            (EVIDENCE/'v04-preview-state.json').write_text(json.dumps(state, indent=2))
        finally:
            controller.close()
    from handnavigate.connectors import ConnectionRegistry, demo_profile
    with tempfile.TemporaryDirectory(prefix='hn-v04-profiles-') as directory:
        record = ConnectionRegistry(directory).put(demo_profile())
        record['session'] = {'encrypted_file_present': False, 'validity': 'NOT_CHECKED'}
        state['connections'] = [record]
        state['connection_example'] = demo_profile()
        state['qualification'] = json.loads((EVIDENCE/'v04-qualification/qualification.json').read_text())
        state['notice'] = 'Measured owned fixture runs plus separate HTTP component checks. No live schedules or sessions are distributed.'
    (EVIDENCE/'v04-preview-state.json').write_text(json.dumps(state, indent=2))
    evidence = json.loads((EVIDENCE/'test-results.json').read_text())
    payload = json.dumps({'state': state, 'evidence': evidence}).replace('<', '\\u003c')
    html = (ROOT/'ui/index.html').read_text().replace('__CSRF_TOKEN__', 'READ_ONLY_PREVIEW')
    html = html.replace('<head>', '<head><script>window.__HANDNAVIGATE_PREVIEW='+payload+';</script>', 1)
    (ROOT/'ui/read-only-preview.html').write_text(html)
    (OUT/'HandNavigate_v0.4_Studio_Preview.html').write_text(html)
    print('Generated verified rehearsal, scheduled 10-file run, recorded draft and read-only preview.')





def build_teaching():
    from handnavigate.teaching import ADAPTER, compile_lesson, example_bindings, example_rows, make_plan
    from handnavigate.teaching_runner import execute_lesson, load_practice, record_example
    from handnavigate.teaching_service import TeachingService
    from handnavigate.studio import teaching_html
    from uuid import uuid4
    with tempfile.TemporaryDirectory(prefix='hn-v04-teaching-') as directory:
        root = Path(directory)
        controller = Controller(root, 'http://127.0.0.1:49999', autostart=False)
        service = TeachingService(controller.store, root, controller.execution_lock)
        try:
            with sync_playwright() as p:
                browser = launch_browser(p)
                page = browser.new_page()
                load_practice(page)
                events = record_example(page)
                browser.close()
            recipe = compile_lesson(events, example_bindings(), name='Daily topic previews',
                                    verification_contract=ADAPTER['verifier'], max_rows=10)
            lesson = service.create(recipe, 'Actual Chromium events driven by an automated example, not human teaching; explicit bindings and verification selected')
            lesson = service.approve(lesson['id'], lesson['sha256'], True)
            rows = example_rows()
            plan = service.plan(lesson['id'], rows)
            # Preserve a real wrong-output failure, then a separate clean run.
            original = service.execute
            service.execute = lambda *a, **kw: execute_lesson(*a, case='wrong-topic', **kw)
            service.start(lesson['id'], rows, plan['plan_sha256'], str(uuid4()))
            service.thread.join(25)
            assert service.snapshot()['runs'][0]['state'] == 'HALTED'
            service.execute = original
            service.start(lesson['id'], rows, plan['plan_sha256'], str(uuid4()))
            service.thread.join(25)
            snapshot = service.snapshot()
            assert snapshot['runs'][0]['state'] == 'VERIFIED', snapshot
            report = snapshot['runs'][0]['report']
            artifacts = EVIDENCE / 'v04-teaching-artifacts'
            artifacts.mkdir(exist_ok=True)
            manifest = []
            for item in report['rows']:
                source = root / item['artifact']['path']
                target = artifacts / source.name
                shutil.copy2(source, target)
                manifest.append({**item['artifact'], 'row_id': item['row_id'], 'package_path': str(target.relative_to(ROOT))})
            (artifacts / 'manifest.json').write_text(json.dumps(manifest, indent=2))
            proof = {'generated_at': datetime.now(timezone.utc).isoformat(),
                     'automated_demonstration': True,
                     'scope': 'Owned form in memory, actual Chromium interaction and local JSON evidence; no HTTP website',
                     'recording': events, 'bindings': example_bindings(),
                     'recipe': recipe, 'recipe_sha256': digest(recipe), 'rows': rows,
                     'plan': plan, 'state': snapshot, 'artifacts': manifest,
                     'limitations': ['Not a human usability trial', 'No learned loops, intent or verifier',
                                     'No third-party website, account or long-running job',
                                     'No model-provider integration; model-call count is structurally zero']}
            (EVIDENCE / 'v04-teaching-demonstration.json').write_text(json.dumps(proof, indent=2))
            (ROOT / 'recipes' / 'guided-topic-preview.json').write_text(json.dumps(recipe, indent=2))
            (ROOT / 'recipes' / 'guided-topic-rows.json').write_text(json.dumps(rows, indent=2))
            payload = json.dumps({'state': snapshot, 'recording': events, 'lesson_id': lesson['id'],
                                  'rows': rows, 'plan': plan, 'stage': 'rehearse'}).replace('<', '\\u003c')
            html = teaching_html('READ_ONLY_PREVIEW')
            html = html.replace('<head>', '<head><script>window.__HANDNAVIGATE_TEACHING_PREVIEW=' + payload + ';</script>', 1)
            (ROOT / 'ui' / 'teaching-read-only-preview.html').write_text(html)
            (OUT / 'HandNavigate_v0.4_Teaching_Preview.html').write_text(html)
            (OUT / 'HandNavigate_v0.4_Example_Recipe.json').write_text(json.dumps(recipe, indent=2))
            (OUT / 'HandNavigate_v0.4_Verified_Row.json').write_bytes((root / report['rows'][0]['artifact']['path']).read_bytes())
            print('Recorded four browser actions, compiled explicit bindings, verified three rows and preserved one real wrong-output halt.')
        finally:
            service.close()
            controller.close()


if __name__ == '__main__':
    build()
    build_teaching()
