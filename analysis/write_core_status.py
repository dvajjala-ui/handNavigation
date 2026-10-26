"""Package the measured core implementation evidence without overwriting the earlier audit."""
from collections import Counter
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
out = ROOT/'evidence'/'transfer-core'
out.mkdir(parents=True, exist_ok=True)
files = {'full-suite.xml': ROOT/'evidence'/'pytest-results.xml',
         'full-suite-console.txt': ROOT/'analysis'/'core-full-tests-console.txt',
         'final-edge-cases.xml': ROOT/'analysis'/'transfer-final-edge-tests.xml',
         'final-edge-console.txt': ROOT/'analysis'/'transfer-final-edge-console.txt',
         'demo-result.json': ROOT/'runtime'/'core-evidence'/'demo-result.json'}
for name, source in files.items(): shutil.copy2(source, out/name)
cases = {}
for name in ('full-suite.xml', 'final-edge-cases.xml'):
    for c in ET.parse(out/name).findall('.//testcase'):
        cases[(c.attrib.get('classname'), c.attrib['name'])] = c
stats = Counter('failed' if c.find('failure') is not None else 'error' if c.find('error') is not None else
                'skipped' if c.find('skipped') is not None else 'passed' for c in cases.values())
demo = json.loads((out/'demo-result.json').read_text())
summary = {'build': 'core image transfer implementation', 'review_date': '2026-10-25',
           'environment': 'Windows, Python 3.12.14, Playwright 1.57.0, Pillow 12.3.0',
           'test_results': {'distinct_cases': len(cases), **dict(stats),
                            'full_suite': '238 passed, 1 skipped; 91 passing subtests',
                            'later_regression_checks': '2 passed: reuse existing files and empty listing'},
           'owned_http_demo': {k: demo[k] for k in ('status', 'requested', 'downloaded', 'uploaded', 'confirmed', 'model_calls',
                                                    'demo_http_upload_requests', 'demo_persisted_images')},
           'implemented': ['real PNG/JPEG/WebP validation', 'bounded listing/pagination', 'browser file upload',
                           'persisted destination byte verification', 'durable per-item journal',
                           'duplicate prevention and interruption reconciliation', 'real-site setup recording and image-group picker',
                           'separate persistent login profiles', 'pinned daily schedule and process watchdog',
                           'complete test entry point and CI integration'],
           'third_party_site_pairs_qualified': [], 'live_model_requests': 0,
           'limits': ['exact original-image bytes required for destination verification',
                      'main-frame controls and a unique normal file input',
                      'site-specific selectors, dependencies and account rules require review',
                      'no multi-day soak or human usability study',
                      'application network guard is not OS isolation',
                      'persistent browser sessions are sensitive; no OS credential-store integration']}
(out/'qualification.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
status_path = ROOT/'DELIVERY_STATUS.json'
old = json.loads(status_path.read_text())
summary['previous_delivery_status'] = old
status_path.write_text(json.dumps(summary, indent=2), encoding='utf-8')
report = f'''# Core workflow implementation status

25 October 2026. Based on the original teach-once/repeat-without-AI brief in ORIGINAL_PRODUCT_REQUEST.md.

## Delivered

The new handnavigate/transfer package executes a complete source-to-destination image transfer. It discovers a bounded set of images with scroll or click pagination, downloads authenticated image bytes with per-hop origin checks, validates decoded PNG/JPEG/WebP content, submits verified bytes through the destination's browser file input, reloads its gallery and fetches persisted images independently to check their SHA-256 hashes. It does not substitute the owned demo for a failed real-site run.

SQLite records READY, UPLOADING, NEEDS_REVIEW and CONFIRMED states. An interruption after acceptance is reconciled from the remote files before retrying. Repeated jobs do not duplicate already-confirmed outputs. New daily jobs can either select unseen images or confirm existing copies, according to the reviewed new_only setting. Fewer eligible images produce PARTIAL without starting a new incomplete batch of uploads.

The teaching command records real setup actions and selects the source image group and destination gallery. Login uses separate dedicated browser profiles. This is explicit recipe authoring from demonstration, not automatic intent or arbitrary-loop inference. Routine execution makes no model calls.

Daily scheduling pins recipes/inputs/approvals and requires a verified rehearsal. Occurrences are deduplicated, missed days produce at most the latest job, non-verified jobs pause the schedule, and workers have a hard process lifetime. The Windows launcher provides one command for normal execution after setup.

## Measured verification

- Complete regression: 238 passed, 1 skipped, plus 91 passing unittest subtests.
- Two later edge regressions: 2 passed. These cover confirming an existing remote image without resending it, and an empty source producing PARTIAL with no upload.
- Total distinct automated cases across the two recorded runs: {stats['passed']} passed, {stats['skipped']} skipped, {stats['failed'] + stats['error']} failures/errors.
- The skipped legacy redirect integration case cannot represent HTTP redirects in its offline Blob fixture. The new real-HTTP cross-origin image redirect test passed; this is separate evidence, not a relabeling of the old skip.
- Actual explicit demo: {demo['downloaded']} downloaded, {demo['uploaded']} browser upload requests, {demo['confirmed']} independently confirmed remote images, {demo['model_calls']} AI calls. Both sites ran over real local HTTP, on separate origins, using real multipart uploads and mixed image formats.
- The Playwright-driven teaching picker smoke check passed on actual owned HTTP pages. No real-person teaching study was performed.
- Authenticated image reads, delayed pagination/gallery loading, upload-on-file-selection, wrong account, local tampering, fake success, interrupted upload, same-day replay, second-day new selection, real subprocess execution and worker termination are covered.
- Dependency consistency, Python compilation and git whitespace checks passed.

## Scope still requiring user site trials

The user chose to test their own sites. No third-party site pair has been qualified by this change. Selectors must identify original image URLs, the intended upload form/account and persisted destination originals. Byte-changing recompression/resizing cannot pass the exact-byte verifier and needs a different reviewed site contract. Main-frame controls and standard file inputs are supported; iframe/new-tab/custom upload widgets, image-onload-dependent pages and additional API/CDN/login origins may need an adapter. Sessions remain sensitive dedicated browser profiles rather than an OS credential service. No overnight reliability or other-platform qualification is claimed.

## Run

Windows: `handnavigate.cmd demo` for the explicit owned acceptance demonstration. For actual sites use `init`, `teach`, then `run image-transfer.json`. See ../CORE_WORKFLOW.md for commands and limits.

Evidence: ../evidence/transfer-core/qualification.json, full-suite.xml, final-edge-cases.xml, demo-result.json and teaching-picker-smoke.json. `python run_tests.py` now includes legacy, live and transfer suites; CI uses that complete entry point. No Git commit, push or deployment was performed.
'''
(ROOT/'research'/'CORE_WORKFLOW_STATUS.md').write_text(report, encoding='utf-8')
print(json.dumps(summary['test_results'], indent=2))
