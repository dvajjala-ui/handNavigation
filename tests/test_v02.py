"""v0.2 checks: pure clocks/storage, injected crash, HTTP API, actual local browser."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from uuid import uuid4

from handnavigate.contracts import ContractError, digest, load_default, validate_recipe
from handnavigate.controller import Controller
from handnavigate.fixture import running_fixture
from handnavigate.recorder import compile_recording
from handnavigate.scheduling import iso, next_due, latest_due, occurrence_on, parse, preview, validate_schedule
from handnavigate.store import Store
from handnavigate.studio import running_studio

UTC = timezone.utc
BASE = datetime(2026, 10, 23, 2, 0, tzinfo=UTC)
OBSERVATIONS = []
SPEC = {"name": "Morning collection", "timezone": "Asia/Kolkata", "time": "08:00", "misfire": "run_once", "grace_seconds": 300}
REQUEST = {"topic": "architecture", "limit": 2, "case": "normal", "fixture_transport": "memory", "pause_after": None}
ROOT = Path(__file__).resolve().parent.parent


def simulated_report(attempt, status="VERIFIED"):
    request = attempt["request"]
    return {"run_id": str(uuid4()), "status": status, "recipe_sha256": digest(attempt["recipe"]),
            "parameters": {"topic": request["topic"], "limit": request["limit"]},
            "scenario": request["case"], "fixture_transport": request["fixture_transport"],
            "verified_count": request["limit"] if status == "VERIFIED" else 0,
            "verified_files": [], "model_calls": 0,
            "test_double": "Storage test only; no browser or files in this report"}


class ScheduleClockTests(unittest.TestCase):
    def test_india_conversion_and_strict_next(self):
        due = next_due(SPEC, BASE)
        self.assertEqual(due, datetime(2026, 10, 23, 2, 30, tzinfo=UTC))
        self.assertEqual(next_due(SPEC, due), due + timedelta(days=1))
        self.assertEqual(latest_due(SPEC, due), due)

    def test_spring_gap_is_skipped_not_shifted(self):
        spec = {**SPEC, "timezone": "America/New_York", "time": "02:30"}
        after = datetime(2026, 3, 8, 0, 0, tzinfo=UTC)
        self.assertEqual(next_due(spec, after), datetime(2026, 3, 9, 6, 30, tzinfo=UTC))

    def test_fall_repeat_runs_only_first_occurrence(self):
        spec = {**SPEC, "timezone": "America/New_York", "time": "01:30"}
        first = next_due(spec, datetime(2026, 11, 1, 0, 0, tzinfo=UTC))
        self.assertEqual(first, datetime(2026, 11, 1, 5, 30, tzinfo=UTC))
        self.assertEqual(next_due(spec, first), datetime(2026, 11, 2, 6, 30, tzinfo=UTC))
        self.assertEqual(latest_due(spec, first + timedelta(hours=1)), first)

    def test_naive_clock_rejected(self):
        with self.assertRaises(ContractError):
            next_due(SPEC, datetime(2026, 1, 1))

    def test_invalid_specs_rejected(self):
        for field, value in [("timezone", "Not/AZone"), ("time", "25:00"), ("time", "8:00"),
                             ("misfire", "run_all"), ("grace_seconds", True), ("name", " ")]:
            with self.subTest(field=field), self.assertRaises(ContractError):
                validate_schedule({**SPEC, field: value})

    def test_preview_has_explicit_local_offsets(self):
        values = preview(SPEC, BASE)
        self.assertEqual(len(values), 3)
        self.assertTrue(all(x["local"].endswith("+05:30") for x in values))


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.store = Store(self.root)
        self.recipe = self.store.recipe()

    def rehearse(self, request=None):
        request = request or REQUEST
        self.store.submit_manual(self.recipe, request, BASE)
        attempt = self.store.claim(BASE)
        self.store.finish(attempt["id"], simulated_report(attempt), BASE)

    def schedule(self, spec=None):
        self.rehearse()
        return self.store.create_schedule(spec or SPEC, self.recipe, REQUEST, BASE)

    def test_schedule_requires_matching_verified_rehearsal(self):
        with self.assertRaisesRegex(ContractError, "verified rehearsal"):
            self.store.create_schedule(SPEC, self.recipe, REQUEST, BASE)
        self.rehearse()
        with self.assertRaises(ContractError):
            self.store.create_schedule(SPEC, self.recipe, {**REQUEST, "topic": "other"}, BASE)
        with self.assertRaises(ContractError):
            self.store.create_schedule(SPEC, self.recipe, {**REQUEST, "fixture_transport": "http"}, BASE)

    def test_due_occurrence_materialized_once(self):
        self.schedule()
        at = next_due(SPEC, BASE)
        self.assertEqual(len(self.store.enqueue_due(at)), 1)
        self.assertEqual(self.store.enqueue_due(at), [])
        self.assertEqual(sum(a["state"] == "QUEUED" for a in self.store.attempts()), 1)

    def test_missed_days_coalesce_to_latest_once(self):
        self.schedule()
        at = next_due(SPEC, BASE) + timedelta(days=6, hours=3)
        self.assertEqual(len(self.store.enqueue_due(at)), 1)
        attempt = self.store.claim(at)
        self.assertEqual(parse(attempt["due_at"]), latest_due(SPEC, at))
        self.assertEqual(len([a for a in self.store.attempts() if a["source"] == "schedule"]), 1)

    def test_skip_policy_does_not_catch_up_after_grace(self):
        self.schedule({**SPEC, "misfire": "skip"})
        at = next_due(SPEC, BASE) + timedelta(minutes=6)
        self.assertEqual(self.store.enqueue_due(at), [])
        self.assertIn("MISSED_RUN_SKIPPED", [e["event"] for e in self.store.audit()])

    def test_skip_policy_runs_current_due_not_old_backlog(self):
        self.schedule({**SPEC, "misfire": "skip"})
        at = next_due(SPEC, BASE) + timedelta(days=8, minutes=1)
        self.assertEqual(len(self.store.enqueue_due(at)), 1)
        self.assertEqual(parse(self.store.claim(at)["due_at"]), latest_due(SPEC, at))

    def test_concurrent_claim_has_single_winner(self):
        self.store.submit_manual(self.recipe, REQUEST, BASE)
        barrier = threading.Barrier(8)
        def claim(_):
            barrier.wait()
            return Store(self.root).claim(BASE)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(claim, range(8)))
        self.assertEqual(sum(r is not None for r in results), 1)

    def test_manual_overlap_is_rejected(self):
        self.store.submit_manual(self.recipe, REQUEST, BASE)
        with self.assertRaises(ContractError):
            self.store.submit_manual(self.recipe, REQUEST, BASE)
        self.store.claim(BASE)
        with self.assertRaises(ContractError):
            self.store.submit_manual(self.recipe, REQUEST, BASE)

    def test_history_and_schedules_survive_reopen(self):
        key = self.schedule()
        other = Store(self.root)
        self.assertEqual(other.history()[0]["status"], "VERIFIED")
        self.assertEqual(other.schedules()[0]["id"], key)

    def test_failure_pauses_schedule_no_hidden_retry(self):
        key = self.schedule()
        due = next_due(SPEC, BASE)
        self.store.enqueue_due(due)
        attempt = self.store.claim(due)
        self.store.finish(attempt["id"], simulated_report(attempt, "HALTED"), due)
        self.assertFalse(self.store.schedules()[0]["enabled"])
        self.assertEqual(self.store.enqueue_due(due + timedelta(days=1)), [])

    def test_interrupted_attempt_blocks_all_work_until_acknowledged(self):
        self.store.submit_manual(self.recipe, REQUEST, BASE)
        attempt = self.store.claim(BASE)
        self.assertEqual(self.store.recover_interrupted(BASE), 1)
        self.assertIsNone(self.store.claim(BASE))
        with self.assertRaises(ContractError):
            self.store.submit_manual(self.recipe, REQUEST, BASE)
        with self.assertRaises(ContractError):
            self.store.resolve_interrupted(attempt["id"], "retry it", BASE)
        self.store.resolve_interrupted(attempt["id"], "I checked the outcome; do not retry this attempt", BASE)
        self.assertEqual(self.store.attempts()[0]["state"], "ABANDONED")
        self.assertIsNone(self.store.claim(BASE))

    def test_unstarted_queue_is_not_marked_uncertain(self):
        self.store.submit_manual(self.recipe, REQUEST, BASE)
        self.assertEqual(self.store.recover_interrupted(BASE), 0)
        self.assertIsNotNone(self.store.claim(BASE))

    def test_approving_new_recipe_pauses_schedules_and_cancels_queued(self):
        self.schedule()
        self.store.enqueue_due(next_due(SPEC, BASE))
        recipe = deepcopy(self.recipe)
        recipe["revision"] = 2
        recipe["name"] = "Reviewed version two"
        draft = self.store.create_draft(recipe, "unit test", BASE)
        with self.assertRaises(ContractError):
            self.store.activate_draft(draft["id"], "wrong hash", BASE)
        self.store.activate_draft(draft["id"], draft["sha256"], BASE)
        self.assertFalse(self.store.schedules()[0]["enabled"])
        self.assertIsNone(self.store.claim(BASE))
        self.assertEqual(self.store.recipe()["revision"], 2)

    def test_stale_parallel_draft_cannot_overwrite_newer_version(self):
        recipe = {**self.recipe, "revision": 2}
        a = self.store.create_draft(recipe, "a", BASE)
        b = self.store.create_draft({**recipe, "name": "other"}, "b", BASE)
        self.store.activate_draft(a["id"], a["sha256"], BASE)
        with self.assertRaisesRegex(ContractError, "stale"):
            self.store.activate_draft(b["id"], b["sha256"], BASE)

    def test_resume_schedule_requires_review_and_no_backfill(self):
        key = self.schedule()
        self.store.toggle_schedule(key, False, None, BASE)
        with self.assertRaises(ContractError):
            self.store.toggle_schedule(key, True, "wrong", BASE)
        future = BASE + timedelta(days=3)
        self.store.toggle_schedule(key, True, digest(self.recipe), future)
        self.assertGreater(parse(self.store.schedules()[0]["next_due_at"]), future)
        self.assertEqual(self.store.enqueue_due(future), [])

    def test_overlapping_days_do_not_queue_same_schedule_twice(self):
        self.schedule()
        due = next_due(SPEC, BASE)
        self.store.enqueue_due(due)
        self.store.claim(due)
        self.assertEqual(self.store.enqueue_due(due + timedelta(days=1)), [])
        self.assertIn("OCCURRENCE_SKIPPED_OVERLAP", [a["event"] for a in self.store.audit()])

    def test_skip_policy_is_rechecked_when_queued_work_is_claimed(self):
        self.schedule({**SPEC, "misfire": "skip"})
        due = next_due(SPEC, BASE)
        self.store.enqueue_due(due)
        self.assertIsNone(self.store.claim(due + timedelta(minutes=6)))
        self.assertEqual(self.store.attempts()[0]["state"], "MISSED")

    def test_unstarted_old_day_is_replaced_not_replayed_after_downtime(self):
        self.schedule()
        due = next_due(SPEC, BASE)
        self.store.enqueue_due(due)
        later = due + timedelta(days=3)
        self.assertEqual(len(self.store.enqueue_due(later)), 1)
        claimed = self.store.claim(later)
        self.assertEqual(parse(claimed["due_at"]), later)
        self.assertEqual(sum(a["state"] == "SUPERSEDED" for a in self.store.attempts()), 1)

    def test_search_only_recipe_cannot_be_scheduled_as_verified(self):
        recipe = deepcopy(self.recipe)
        recipe["steps"].pop()
        with self.assertRaisesRegex(ContractError, "file-effect contract"):
            self.store.create_schedule(SPEC, recipe, REQUEST, BASE)


class TeachingValidationTests(unittest.TestCase):
    def test_redacted_required_step_is_not_silently_dropped(self):
        with self.assertRaisesRegex(ContractError, "private step"):
            compile_recording([{"op": "redacted", "reason": "sensitive_field"},
                               {"op": "click", "target": [{"by": "role", "role": "button", "name": "Search"}]}], example_topic="x")

    def test_malformed_recording_rejected(self):
        for events in (None, "events", [5], [{"op": []}]):
            with self.subTest(events=events), self.assertRaises(ContractError):
                compile_recording(events, example_topic="x")

    def test_malformed_locator_or_operation_is_contract_error(self):
        for kind in ("op", "by"):
            recipe = load_default()
            if kind == "op":
                recipe["steps"][0]["op"] = []
            else:
                recipe["steps"][0]["target"][0]["by"] = []
            with self.assertRaises(ContractError):
                validate_recipe(recipe)

    def test_boolean_schema_version_rejected(self):
        recipe = load_default()
        recipe["schema_version"] = True
        with self.assertRaises(ContractError):
            validate_recipe(recipe)


class OwnershipAndRecoveryTests(unittest.TestCase):
    def test_two_studios_cannot_own_same_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = Controller(Path(directory), "http://127.0.0.1:12345", autostart=False)
            try:
                with self.assertRaises(ContractError):
                    Controller(Path(directory), "http://127.0.0.1:12345", autostart=False)
            finally:
                controller.close()
            reopened = Controller(Path(directory), "http://127.0.0.1:12345", autostart=False)
            reopened.close()

    def test_forced_process_exit_does_not_repeat_simulated_effect(self):
        with tempfile.TemporaryDirectory() as directory:
            script = '''
import os
from pathlib import Path
from datetime import datetime, timezone
from handnavigate.controller import Controller
root=Path(os.environ['HN_CRASH_ROOT'])
def effect(attempt,cancel):
    with (root/'simulated-effect.txt').open('a') as f:
        f.write('performed\\n'); f.flush(); os.fsync(f.fileno())
    os._exit(27)
c=Controller(root,'http://127.0.0.1:12345',execute=effect,autostart=False)
c.store.submit_manual(c.store.recipe(), {'topic':'x','limit':1,'case':'normal','fixture_transport':'memory'}, datetime.now(timezone.utc))
c.tick()
'''
            result = subprocess.run([sys.executable, "-c", script], cwd=ROOT,
                                    env={**os.environ, "HN_CRASH_ROOT": directory}, timeout=15)
            self.assertEqual(result.returncode, 27)
            reopened = Controller(Path(directory), "http://127.0.0.1:12345", autostart=False)
            try:
                self.assertIsNone(reopened.tick())
                self.assertEqual(reopened.store.attempts()[0]["state"], "NEEDS_REVIEW")
                self.assertEqual((Path(directory)/"simulated-effect.txt").read_text(), "performed\n")
            finally:
                reopened.close()
            OBSERVATIONS.append({"check": "forced process exit", "result": "NEEDS_REVIEW; simulated effect not repeated", "scope": "injected local effect, not a remote website transaction"})


class ScheduledBrowserTests(unittest.TestCase):
    def test_rehearse_schedule_advance_clock_run_and_reopen(self):
        with tempfile.TemporaryDirectory() as directory, running_fixture() as fixture:
            clock = [BASE]
            controller = Controller(Path(directory), fixture.origin, clock=lambda: clock[0], autostart=True)
            try:
                recipe = controller.store.recipe()
                controller.store.submit_manual(recipe, REQUEST, clock[0])
                controller.notify()
                deadline = time.monotonic() + 20
                while controller.store.busy() and time.monotonic() < deadline:
                    time.sleep(.05)
                rehearsal = controller.store.history()[0]
                self.assertEqual(rehearsal["status"], "VERIFIED", rehearsal)
                controller.store.create_schedule(SPEC, recipe, REQUEST, clock[0])
                clock[0] = next_due(SPEC, clock[0])
                controller.notify()
                deadline = time.monotonic() + 20
                while len(controller.store.history()) < 2 and time.monotonic() < deadline:
                    time.sleep(.05)
                scheduled = controller.store.history()[0]
                self.assertEqual(scheduled["status"], "VERIFIED", scheduled)
                self.assertEqual(scheduled["verified_count"], 2)
                time.sleep(.6)
                self.assertEqual(len(controller.store.history()), 2)
                scheduled_history = controller.store.history()[0]
                self.assertEqual(scheduled_history["trigger"], "schedule")
                for item in scheduled["verified_files"]:
                    self.assertEqual(sha256((Path(directory)/item["path"]).read_bytes()).hexdigest(), item["sha256"])
                OBSERVATIONS.append({"check": "scheduled browser workflow", "transport": "memory", "clock": "injected UTC clock, actual background controller thread; not an overnight soak", "rehearsal": rehearsal["status"], "scheduled": scheduled_history, "duplicate_tick": "no second execution"})
            finally:
                controller.close()
            reopened = Controller(Path(directory), fixture.origin, clock=lambda: clock[0], autostart=False)
            try:
                self.assertEqual(len(reopened.store.history()), 2)
                self.assertIsNone(reopened.tick())
            finally:
                reopened.close()


class NewStudioApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.fixture_ctx = running_fixture()
        self.fixture = self.fixture_ctx.__enter__()
        self.addCleanup(self.fixture_ctx.__exit__, None, None, None)
        self.ctx = running_studio(self.fixture.origin, Path(self.directory.name), port=0)
        self.studio = self.ctx.__enter__()
        self.addCleanup(self.ctx.__exit__, None, None, None)

    def request(self, path, body=None, raw=None):
        headers = {}
        data = raw
        if body is not None:
            data = json.dumps(body).encode()
        if data is not None:
            headers = {"Content-Type": "application/json", "Origin": self.studio.origin,
                       "X-HandNavigate-Token": self.studio.csrf}
        request = urllib.request.Request(self.studio.origin+path, data=data, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                content = response.read()
                return response.status, json.loads(content) if 'json' in response.headers.get('Content-Type','') else content
        except urllib.error.HTTPError as response:
            return response.code, json.loads(response.read())

    def payload(self):
        return {"topic": "api teaching", "limit": 2, "case": "normal", "reviewed_sha256": digest(self.studio.recipe)}

    def wait_run(self):
        deadline = time.monotonic()+20
        while self.studio.busy and time.monotonic()<deadline:
            time.sleep(.05)
        self.assertFalse(self.studio.busy)
        return self.studio.store.history()[0]

    def test_schedule_preview_and_missing_rehearsal_gate(self):
        status, data = self.request('/api/schedules/preview', SPEC)
        self.assertEqual(status, 200)
        self.assertEqual(len(data['occurrences']), 3)
        self.assertEqual(self.request('/api/schedules', {"spec": SPEC, "run": self.payload()})[0], 400)

    def test_compiled_teaching_draft_approved_rehearsed_and_scheduled(self):
        events = [{"op":"fill","target":[{"by":"label","value":"Topic"}],"value":"example"},
                  {"op":"click","target":[{"by":"role","role":"button","name":"Search"}]}]
        status, draft = self.request('/api/drafts/compile', {"events":events,"example_topic":"example","ready_test_id":"results-ready","append_collection":True})
        self.assertEqual(status, 201, draft)
        self.assertEqual(self.studio.recipe['revision'], 1)
        self.assertEqual(self.request('/api/drafts/approve', {"id":draft['id'],"reviewed_sha256":"wrong"})[0], 400)
        self.assertEqual(self.request('/api/drafts/approve', {"id":draft['id'],"reviewed_sha256":draft['sha256']})[0], 200)
        self.assertEqual(self.studio.recipe['revision'], 2)
        self.assertEqual(self.request('/api/run', self.payload())[0], 202)
        report = self.wait_run()
        self.assertEqual(report['status'], 'VERIFIED', report)
        self.assertEqual(self.request('/api/schedules', {"spec":SPEC,"run":self.payload()})[0], 201)
        self.assertTrue(self.request('/api/status')[1]['schedules'][0]['enabled'])
        OBSERVATIONS.append({"check":"teaching API pipeline","result":"import -> explicit parameter -> authored collection selection -> checksum approval -> VERIFIED rehearsal -> daily schedule saved","scope":"actual HTTP API and offline Chromium; not inferred intent"})

    def test_tampered_artifact_is_not_served_as_verified(self):
        self.request('/api/run', self.payload())
        report = self.wait_run()
        item = report['verified_files'][0]
        (Path(self.directory.name)/item['path']).write_bytes(b'changed')
        self.assertEqual(self.request('/api/artifact?run='+report['run_id']+'&index=0')[0], 409)

    def test_malformed_json_and_wrong_types_return_validation_error(self):
        for body in (b'[]', b'{"topic":NaN}', b'{"recipe":{"steps":[]}}'):
            self.assertEqual(self.request('/api/drafts', raw=body)[0], 400)
        self.assertEqual(self.request('/api/schedules/toggle', {"id":"x","enabled":"true"})[0], 400)

    def test_compile_refuses_secret_omission(self):
        status, data = self.request('/api/drafts/compile', {"events":[{"op":"redacted","reason":"private"}],"example_topic":"example","append_collection":False})
        self.assertEqual(status,400)
        self.assertIn('private',data['error'])
