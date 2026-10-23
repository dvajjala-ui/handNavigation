"""Run reproducible local Chromium checks and export honest test evidence."""
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys
import unittest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tests"))
import test_lab
import test_v02
import test_v03
import test_v04

suite = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromModule(test_lab), unittest.defaultTestLoader.loadTestsFromModule(test_v02), unittest.defaultTestLoader.loadTestsFromModule(test_v03), unittest.defaultTestLoader.loadTestsFromModule(test_v04)])
result = unittest.TextTestRunner(verbosity=2).run(suite)
report = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "scope": "Synthetic owned fixture only; not a benchmark on real third-party websites.",
    "fixture_transport": test_lab.TRANSPORT,
    "environment": {"python": platform.python_version(), "system": platform.system(),
                    "playwright": importlib.metadata.version("playwright"),
                    "cryptography": importlib.metadata.version("cryptography")},
    "test_methods": result.testsRun,
    "failures": len(result.failures), "errors": len(result.errors),
    "skipped": len(result.skipped), "all_passed": result.wasSuccessful(),
    "skipped_tests": [{"test": str(test), "reason": reason} for test, reason in result.skipped],
    "browser_observations": test_lab.OBSERVATIONS,
    "v02_observations": test_v02.OBSERVATIONS,
    "v03_observations": test_v03.OBSERVATIONS,
    "v04_observations": test_v04.OBSERVATIONS,
    "failure_details": [{"test": str(test), "traceback": text} for test, text in result.failures + result.errors],
    "limitations": ["Recorder actions in tests are driven by Playwright, not observed real-user teaching.",
                    "Guided teaching supports the owned form only, with explicit bindings and a selected verifier, not arbitrary site inference.",
                    "A 20-row owned batch is not a multi-day or remote-site reliability trial.",
                    "The collection loop and PNG verifier are explicitly authored, not inferred.",
                    "Controlled pause/resume and an injected process exit are tested; arbitrary power-loss and remote exactly-once effects are not.",
                    "Scheduling tests use injected clocks, including one actual offline Chromium scheduled execution; no overnight soak.",
                    "No OS-level egress isolation or adversarial-site security certification.",
                    "No claim of Windows, macOS, mobile, or production-site validation.",
                    "Owned HTTP-client checks do not qualify browser HTTP; full browser sign-in/export test is a separate gate.",
                    "Session vault is passphrase-based, not an OS keychain; no authenticated recurring schedules."]
}
(ROOT / "evidence").mkdir(exist_ok=True)
(ROOT / "evidence" / "test-results.json").write_text(json.dumps(report, indent=2))
sys.exit(0 if result.wasSuccessful() else 1)
