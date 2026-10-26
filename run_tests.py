"""Run reproducible local Chromium checks and export honest test evidence."""
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys
import xml.etree.ElementTree as ET
import pytest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tests"))
import test_lab
import test_v02
import test_v03
import test_v04

(ROOT / 'evidence').mkdir(exist_ok=True)
junit = ROOT / 'evidence' / 'pytest-results.xml'
exit_code = pytest.main([str(ROOT / 'tests'), '-q', '--junitxml=' + str(junit)])
cases = ET.parse(junit).findall('.//testcase') if junit.exists() else []
failed = [case for case in cases if case.find('failure') is not None]
errors = [case for case in cases if case.find('error') is not None]
skipped = [case for case in cases if case.find('skipped') is not None]
report = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "scope": "Complete legacy/live/transfer suite, including real browser HTTP uploads between owned sites; not third-party site qualification.",
    "fixture_transport": test_lab.TRANSPORT,
    "environment": {"python": platform.python_version(), "system": platform.system(),
                    "playwright": importlib.metadata.version("playwright"),
                    "cryptography": importlib.metadata.version("cryptography")},
    "test_methods": len(cases),
    "failures": len(failed), "errors": len(errors),
    "skipped": len(skipped), "all_passed": exit_code == 0,
    "skipped_tests": [{"test": case.attrib.get('classname', '') + '.' + case.attrib['name'],
                       "reason": case.find('skipped').attrib.get('message', '')} for case in skipped],
    "browser_observations": test_lab.OBSERVATIONS,
    "v02_observations": test_v02.OBSERVATIONS,
    "v03_observations": test_v03.OBSERVATIONS,
    "v04_observations": test_v04.OBSERVATIONS,
    "failure_details": [{"test": case.attrib.get('classname', '') + '.' + case.attrib['name'],
                         "traceback": ''.join(case.itertext())} for case in failed + errors],
    "limitations": ["Recorder actions in tests are driven by Playwright, not observed real-user teaching.",
                    "Guided teaching supports the owned form only, with explicit bindings and a selected verifier, not arbitrary site inference.",
                    "A 20-row owned batch is not a multi-day or remote-site reliability trial.",
                    "The collection loop and PNG verifier are explicitly authored, not inferred.",
                    "Controlled pause/resume and an injected process exit are tested; arbitrary power-loss and remote exactly-once effects are not.",
                    "Scheduling tests use injected clocks, including one actual offline Chromium scheduled execution; no overnight soak.",
                    "No OS-level egress isolation or adversarial-site security certification.",
                    "Windows is locally tested; macOS/Linux CI and third-party site qualification are separate gates.",
                    "Owned HTTP-client checks do not qualify browser HTTP; full browser sign-in/export test is a separate gate.",
                    "Legacy vault is passphrase-based. Live transfer schedules use dedicated browser profiles, not an OS keychain.",
                    "Transfer verification requires byte-identical destination originals; sites that recompress images need another reviewed verifier."]
}
(ROOT / "evidence").mkdir(exist_ok=True)
(ROOT / "evidence" / "test-results.json").write_text(json.dumps(report, indent=2))
sys.exit(int(exit_code))
