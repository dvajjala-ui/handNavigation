from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest

from playwright.sync_api import sync_playwright

from handnavigate.contracts import ContractError, approve, digest, load_default, validate_parameters, validate_recipe
from handnavigate.fixture import running_fixture, png_bytes, load_memory_fixture, MEMORY_DOWNLOAD_HITS
from handnavigate.recorder import Recorder, compile_recording
from handnavigate.runner import Runner, launch_browser, verify_png, Halt

OBSERVATIONS: list[dict] = []
TRANSPORT = os.environ.get("HANDNAVIGATE_TEST_TRANSPORT", "memory")
ROOT = Path(__file__).resolve().parent.parent


class BrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_manager = running_fixture()
        cls.fixture = cls.fixture_manager.__enter__()
        cls.playwright = sync_playwright().start()
        cls.recipe = load_default()
        cls.approval = approve(cls.recipe, "automated fixture test; not a user approval")

    @classmethod
    def tearDownClass(cls):
        cls.playwright.stop()
        cls.fixture_manager.__exit__(None, None, None)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="handnavigate-test-")
        self.addCleanup(self.directory.cleanup)
        self.output = Path(self.directory.name)
        self.runner = Runner(self.output, timeout_ms=1500)
        self.browser = launch_browser(self.playwright)
        self.addCleanup(self.browser.close)

    def run_case(self, case="normal", expected="VERIFIED", **kwargs):
        params = {"origin": self.fixture.origin, "topic": "architecture", "limit": 10,
                  "case": case, "browser": self.browser, "fixture_transport": TRANSPORT, **kwargs}
        report = self.runner.run(self.recipe, self.approval, **params)
        OBSERVATIONS.append({"test": self.id(), "case": case, "expected": expected,
                             "actual": report["status"], "verified_count": report["verified_count"],
                             "new_downloads": report["new_downloads"], "resumed_files": report["resumed_files"],
                             "error": report["error"], "model_calls": report["model_calls"],
                             "blocked_requests": report["blocked_requests"],
                             "elapsed_seconds": report["elapsed_seconds"],
                             "events": report["events"], "skipped": report["skipped"]})
        self.assertEqual(report["status"], expected, report)
        self.assertEqual(report["model_calls"], 0)
        return report

    def assert_halt(self, case, code):
        report = self.run_case(case, "HALTED")
        self.assertEqual(report["error"]["code"], code, report)
        self.assertEqual(report["verified_count"], 0)

    def test_01_normal_ten_downloads(self):
        report = self.run_case()
        self.assertEqual(report["verified_count"], 10)
        self.assertEqual(len({x["sha256"] for x in report["verified_files"]}), 10)
        for item in report["verified_files"]:
            self.assertEqual(sha256((self.output / item["path"]).read_bytes()).hexdigest(), item["sha256"])

    def test_02_variable_topic_and_count(self):
        for topic, limit in [("flowers", 1), ("spaces and + symbols", 5), ("travel", 12)]:
            with self.subTest(topic=topic):
                self.assertEqual(self.run_case(topic=topic, limit=limit)["verified_count"], limit)

    def test_03_layout_drift(self):
        self.run_case("layout")

    def test_04_approved_alternative(self):
        result = self.run_case("alternative")
        self.assertTrue(any(e["outcome"] == "approved_alternative" for e in result["events"]))

    def test_05_delayed_results(self):
        self.run_case("slow")

    def test_06_duplicate_identity_and_content(self):
        result = self.run_case("duplicates")
        reasons = {x["reason"] for x in result["skipped"]}
        self.assertEqual(reasons, {"duplicate_id", "duplicate_content"})
        self.assertEqual(result["verified_count"], 10)

    def test_07_shortfall_is_not_success(self):
        self.assertEqual(self.run_case("few", "PARTIAL")["verified_count"], 3)

    def test_08_ambiguous_search_stops(self):
        self.assert_halt("ambiguous", "AMBIGUOUS_TARGET")

    def test_09_unknown_button_stops(self):
        self.assert_halt("unknown", "TARGET_NOT_FOUND")

    def test_10_html_download_stops(self):
        self.assert_halt("corrupt", "FILE_SIZE")

    def test_11_wrong_valid_image_stops(self):
        self.assert_halt("wrong_file", "HASH_MISMATCH")

    def test_12_truncated_download_stops(self):
        self.assert_halt("truncated", "FILE_SIZE")

    def test_13_fake_success_banner_stops(self):
        self.assert_halt("fake_success", "TIMEOUT")

    def test_14_expired_session_stops(self):
        self.assert_halt("expired", "AUTH_REQUIRED")

    def test_15_egress_blocked(self):
        self.assert_halt("egress", "NETWORK_POLICY")

    def test_16_redirect_blocked(self):
        if TRANSPORT == "memory":
            self.skipTest("HTTP redirect integration cannot be represented by an offline Blob fixture; policy unit-tested separately")
        result = self.run_case("redirect", "HALTED")
        self.assertGreater(len(result["blocked_requests"]), 0, result)
        self.assertEqual(result["verified_count"], 0)

    def test_17_page_instruction_text_does_not_control_runner(self):
        self.assertEqual(self.run_case("injection")["verified_count"], 10)

    def test_18_conflicting_duplicate_ids_stop(self):
        self.assert_halt("conflicting_id", "ITEM_IDENTITY")

    def test_19_missing_download_is_explicit_skip(self):
        result = self.run_case("missing_download")
        self.assertIn("download_unavailable", {x["reason"] for x in result["skipped"]})
        self.assertEqual(result["verified_count"], 10)

    def test_20_oversized_download_stops(self):
        self.assert_halt("oversized", "FILE_SIZE")

    def test_21_reordered_results(self):
        result = self.run_case("reordered")
        self.assertEqual(result["verified_files"][0]["item_id"], "asset-14")

    def test_22_checkpoint_resume_without_redownload(self):
        topic = "resume-specific-test"
        first = self.run_case(expected="PAUSED", topic=topic, job_key="daily-job", pause_after=3)
        self.assertEqual(first["verified_count"], 3)
        second = self.run_case(topic=topic, job_key="daily-job")
        self.assertEqual(second["resumed_files"], 3)
        self.assertEqual(second["new_downloads"], 7)
        for index in range(1, 11):
            self.assertEqual((MEMORY_DOWNLOAD_HITS if TRANSPORT == "memory" else self.fixture.download_hits).get(f"{topic}|normal|{index}"), 1)

    def test_23_completed_job_resume_is_idempotent_for_files(self):
        first = self.run_case(job_key="done-job", topic="completed-job")
        second = self.run_case(job_key="done-job", topic="completed-job")
        self.assertEqual(second["new_downloads"], 0)
        self.assertEqual(second["resumed_files"], 10)

    def test_24_tampered_checkpoint_is_rejected(self):
        first = self.run_case(expected="PAUSED", job_key="tampered", pause_after=2)
        (self.output / first["verified_files"][0]["path"]).write_bytes(b"tampered")
        second = self.run_case(expected="HALTED", job_key="tampered")
        self.assertEqual(second["error"]["code"], "CHECKPOINT_TAMPERED")
        self.assertEqual(second["new_downloads"], 0)

    def test_25_resume_contract_cannot_silently_change(self):
        self.run_case(expected="PAUSED", job_key="bound", pause_after=1)
        result = self.run_case(expected="HALTED", job_key="bound", topic="different")
        self.assertEqual(result["error"]["code"], "JOB_CONTRACT_CHANGED")

    def test_26_overlap_lock(self):
        (self.output / ".execution.lock").write_text('{"pid":0}')
        result = self.run_case(expected="HALTED")
        self.assertEqual(result["error"]["code"], "RUNNER_BUSY")

    def test_27_operator_stop(self):
        self.runner.cancel_event.set()
        self.run_case(expected="CANCELLED")

    def test_28_record_compile_review_replay(self):
        page = self.browser.new_page()
        recorder = Recorder()
        if TRANSPORT == "memory":
            load_memory_fixture(page)
            recorder.attach(page)
        else:
            recorder.attach(page)
            page.goto(self.fixture.origin + "/library")
        page.get_by_label("Topic", exact=True).fill("architecture")
        page.get_by_role("button", name="Search", exact=True).click()
        page.get_by_test_id("results-ready").wait_for()
        page.wait_for_timeout(80)
        page.close()
        self.assertEqual([x["op"] for x in recorder.events], ["fill", "click"])
        draft = compile_recording(recorder.events, example_topic="architecture", ready_test_id="results-ready")
        self.assertEqual(draft["steps"][0]["value"], "{{topic}}")
        with self.assertRaises(ContractError):
            self.runner.run(draft, {}, origin=self.fixture.origin, topic="new topic", browser=self.browser)
        review = approve(draft, "automated test reviewer")
        result = self.runner.run(draft, review, origin=self.fixture.origin, topic="flowers", browser=self.browser, fixture_transport=TRANSPORT)
        self.assertEqual(result["status"], "REPLAYED", result)
        self.assertEqual(result["model_calls"], 0)
        OBSERVATIONS.append({"test": self.id(), "case": "record_compile_review_replay",
                             "expected": "REPLAYED", "actual": result["status"],
                             "captured_actions": recorder.events, "compiled_recipe": draft,
                             "model_calls": 0, "verified_count": 0,
                             "elapsed_seconds": result["elapsed_seconds"]})
        evidence = ROOT / "evidence"
        evidence.mkdir(exist_ok=True)
        (evidence / "recorded-demonstration.json").write_text(json.dumps(recorder.events, indent=2))
        (evidence / "compiled-demonstration.json").write_text(json.dumps(draft, indent=2))

    def test_29_sensitive_field_is_not_recorded(self):
        page = self.browser.new_page()
        recorder = Recorder()
        if TRANSPORT == "memory":
            load_memory_fixture(page)
            recorder.attach(page)
        else:
            recorder.attach(page)
            page.goto(self.fixture.origin + "/library")
        page.evaluate("""() => { const p=document.createElement('input');p.type='password';p.setAttribute('aria-label','Password');document.body.append(p); }""")
        page.get_by_label("Password", exact=True).fill("DO_NOT_RETAIN_THIS_SECRET")
        page.get_by_label("Topic", exact=True).click()
        page.wait_for_timeout(80)
        page.close()
        self.assertNotIn("DO_NOT_RETAIN_THIS_SECRET", json.dumps(recorder.events))
        self.assertTrue(any(e.get("op") == "redacted" for e in recorder.events))

    def test_30_missing_checkpoint_file_stops(self):
        first = self.run_case(expected="PAUSED", job_key="missing", pause_after=1)
        (self.output / first["verified_files"][0]["path"]).unlink()
        result = self.run_case(expected="HALTED", job_key="missing")
        self.assertEqual(result["error"]["code"], "CHECKPOINT_MISSING")


class ContractTests(unittest.TestCase):
    def test_31_unreviewed_change_rejected(self):
        recipe = load_default()
        receipt = approve(recipe)
        recipe["name"] += " changed"
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ContractError):
                Runner(directory).run(recipe, receipt, origin="http://127.0.0.1:1234", topic="test")

    def test_32_external_origins_rejected_before_browser(self):
        recipe = load_default()
        with tempfile.TemporaryDirectory() as directory:
            for origin in ["https://pinterest.com", "http://127.0.0.1.evil.test:123", "file:///tmp", "http://127.0.0.1:80/path", "http://user:pass@127.0.0.1:12"]:
                with self.subTest(origin=origin), self.assertRaises(ContractError):
                    Runner(directory).run(recipe, approve(recipe), origin=origin, topic="test")

            with self.assertRaises(ContractError):
                Runner(directory).run(recipe, approve(recipe), origin="http://127.0.0.1:1234", topic="test", case="redirect", fixture_transport="memory")

    def test_33_parameter_limits(self):
        for topic, limit in [("", 10), ("x" * 81, 10), ("x", 0), ("x", 21), ("x", True), ("x", "10"), ("x\n", 1)]:
            with self.subTest(topic=topic, limit=limit), self.assertRaises(ContractError):
                validate_parameters(topic, limit)

    def test_34_arbitrary_code_action_rejected(self):
        recipe = load_default()
        recipe["steps"].append({"id": "bad", "op": "evaluate", "javascript": "fetch('https://evil.test')"})
        with self.assertRaises(ContractError):
            validate_recipe(recipe)

    def test_35_unknown_fields_rejected(self):
        recipe = load_default()
        recipe["model"] = "silent-fallback"
        with self.assertRaises(ContractError):
            validate_recipe(recipe)

    def test_36_png_crc_and_hash_validation(self):
        data = png_bytes("valid fixture")
        info = verify_png(data, sha256(data).hexdigest())
        self.assertEqual(info["width"], 24)
        altered = bytearray(data)
        altered[60] ^= 1
        with self.assertRaises(Halt):
            verify_png(bytes(altered), sha256(bytes(altered)).hexdigest())

    def test_37_compiler_rejects_unsupported_actions(self):
        with self.assertRaises(ContractError):
            compile_recording([{"op": "unsupported", "reason": "download"}], example_topic="x")

    def test_38_compiler_does_not_guess_parameter_binding(self):
        with self.assertRaises(ContractError):
            compile_recording([{"op": "fill", "target": [{"by": "label", "value": "Topic"}], "value": "different"}], example_topic="x")

    def test_39_default_workflow_has_no_dynamic_code(self):
        recipe = load_default()
        validate_recipe(recipe)
        self.assertTrue(all(s["op"] in ("fill", "click", "wait", "collect") for s in recipe["steps"]))

class NetworkPolicyUnitTests(unittest.TestCase):
    """Policy logic tests with fake route objects, not network integration tests."""
    def setUp(self):
        from unittest.mock import Mock
        self.Mock = Mock
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.runner = Runner(self.directory.name)
        self.report = {"blocked_requests": []}

    def route(self, url, method="GET", status=200):
        route = self.Mock()
        route.request.url = url
        route.request.method = method
        response = self.Mock()
        response.status = status
        route.fetch.return_value = response
        return route

    def test_40_external_request_aborted_without_fetch(self):
        route = self.route("https://example.invalid/collect")
        self.runner._route(route, "http://127.0.0.1:1234", self.report)
        route.abort.assert_called_once_with("blockedbyclient")
        route.fetch.assert_not_called()

    def test_41_local_post_is_not_allowed(self):
        route = self.route("http://127.0.0.1:1234/api/search", "POST")
        self.runner._route(route, "http://127.0.0.1:1234", self.report)
        route.abort.assert_called_once()
        route.fetch.assert_not_called()

    def test_42_redirect_is_not_followed(self):
        route = self.route("http://127.0.0.1:1234/download", status=302)
        self.runner._route(route, "http://127.0.0.1:1234", self.report)
        route.fetch.assert_called_once_with(max_redirects=0, timeout=self.runner.timeout_ms)
        route.abort.assert_called_once()
        route.fulfill.assert_not_called()
        self.assertEqual(self.report["blocked_requests"][0]["method"], "REDIRECT")

    def test_43_allowed_fixture_get_is_fulfilled(self):
        route = self.route("http://127.0.0.1:1234/library")
        self.runner._route(route, "http://127.0.0.1:1234", self.report)
        route.fulfill.assert_called_once()
        route.abort.assert_not_called()

class StudioApiTests(unittest.TestCase):
    """Real localhost HTTP API tests, separate from blocked browser navigation."""
    def setUp(self):
        from handnavigate.studio import running_studio
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.fixture_context = running_fixture()
        self.fixture = self.fixture_context.__enter__()
        self.addCleanup(self.fixture_context.__exit__, None, None, None)
        self.studio_context = running_studio(self.fixture.origin, Path(self.directory.name), port=0, transport="memory")
        self.studio = self.studio_context.__enter__()
        self.addCleanup(self.studio_context.__exit__, None, None, None)

    def request(self, path, body=None, authenticated=True):
        import urllib.request
        import urllib.error
        headers = {}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
            if authenticated:
                headers["Origin"] = self.studio.origin
                headers["X-HandNavigate-Token"] = self.studio.csrf
        request = urllib.request.Request(self.studio.origin + path, data=data, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, response.read(), response.headers
        except urllib.error.HTTPError as response:
            return response.code, response.read(), response.headers

    def payload(self):
        return {"topic": "studio test", "limit": 2, "case": "normal",
                "reviewed_sha256": digest(self.studio.recipe)}

    def test_44_studio_serves_real_source_ui(self):
        status, body, headers = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn(b"Your daily collection", body)
        self.assertNotIn(b"__CSRF_TOKEN__", body)
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])

    def test_45_run_requires_local_csrf_authorization(self):
        status, body, _ = self.request("/api/run", self.payload(), authenticated=False)
        self.assertEqual(status, 403)
        self.assertFalse(self.studio.busy)

    def test_46_run_requires_exact_recipe_review(self):
        body = self.payload()
        body["reviewed_sha256"] = "unreviewed"
        self.assertEqual(self.request("/api/run", body)[0], 400)
        self.assertFalse(self.studio.busy)

    def test_47_api_drives_runner_and_serves_verified_artifact(self):
        import time
        status, _, _ = self.request("/api/run", self.payload())
        self.assertEqual(status, 202)
        deadline = time.monotonic() + 20
        while self.studio.busy and time.monotonic() < deadline:
            time.sleep(.1)
        self.assertFalse(self.studio.busy)
        status, body, _ = self.request("/api/status")
        state = json.loads(body)
        report = state["history"][0]
        self.assertEqual(report["status"], "VERIFIED", report)
        self.assertEqual(report["verified_count"], 2)
        status, image, _ = self.request(f"/api/artifact?run={report['run_id']}&index=0")
        self.assertEqual(status, 200)
        self.assertEqual(sha256(image).hexdigest(), report["verified_files"][0]["sha256"])
        self.assertEqual(self.request(f"/api/artifact?run={report['run_id']}&index=-1")[0], 404)

    def test_48_bad_input_does_not_start_a_run(self):
        body = self.payload()
        body["limit"] = True
        self.assertEqual(self.request("/api/run", body)[0], 400)
        self.assertFalse(self.studio.busy)

    def test_49_unknown_artifact_is_not_readable(self):
        self.assertEqual(self.request("/api/artifact?run=../../etc/passwd&index=0")[0], 404)

    def test_50_unknown_route_returns_not_found(self):
        self.assertEqual(self.request("/not-a-route")[0], 404)
