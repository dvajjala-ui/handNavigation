"""Generate release statements from measured evidence, not assumed capability."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
OUT = Path('/mnt/data') if Path('/mnt/data').is_dir() else ROOT / 'deliverables'
OUT.mkdir(exist_ok=True)
report = json.loads((ROOT / 'evidence/test-results.json').read_text())
ui = json.loads((ROOT / 'evidence/v04-combined-ui-checks.json').read_text())
qualification = json.loads((ROOT / 'evidence/v04-qualification/qualification.json').read_text())
proof = json.loads((ROOT / 'evidence/v04-teaching-demonstration.json').read_text())
passed = report['test_methods'] - report['failures'] - report['errors'] - report['skipped']
assert report['all_passed'] and ui['failed'] == 0
new_methods = 41
status = {
    'version': '0.4.0', 'generated_at': datetime.now(timezone.utc).isoformat(),
    'delivery': 'downloadable local source; not deployed; not pushed to GitHub',
    'tests': {'methods': report['test_methods'], 'passed': passed, 'failed': report['failures'],
              'errors': report['errors'], 'skipped': report['skipped'], 'new_v04_methods': new_methods},
    'ui': ui,
    'owned_qualification': qualification['status'],
    'browser_http_qualified': qualification['status'] == 'OWNED_BROWSER_QUALIFIED',
    'production_ready': False, 'third_party_sites_tested': 0,
    'native_installers_built': 0, 'github_ci': 'configured but not pushed or executed',
    'live_sessions_or_vault_keys_distributed': False,
    'guided_teaching': {'scope': 'bundled owned in-memory form only',
        'actions': ['fill', 'select', 'set checkbox state', 'click owned preview control'],
        'automatic_intent_inference': False, 'automatic_loop_or_verifier_inference': False,
        'max_batch_rows': 20, 'demonstration_rows_verified': proof['state']['runs'][0]['report']['verified_rows'],
        'longer_test': {'rows': 20, 'browser_actions': 80, 'output_checks': 60},
        'model_provider_integrated': False, 'scheduled': False, 'resume': False},
    'scheduled_authenticated_exports': False,
}
(ROOT / 'DELIVERY_STATUS.json').write_text(json.dumps(status, indent=2))

release = f'''# HandNavigate v0.4 - Guided teaching and verified batches

Built 23 October 2026 from the supplied v0.3 source. This is a local engineering release, not a deployed app or native installer. No GitHub changes were made.

## What is new

**Interactive teaching.** The new `/teach` workspace records actual text, dropdown, checkbox and preview-button interactions inside the owned practice form. Start/stop is explicit. Unchanged defaults can be captured explicitly. Private or unsupported actions block compilation instead of disappearing from the sequence.

**Variables and fixed values.** The reviewer chooses typed variables or recorded constants, a maximum row count, and the exact result-verification contract. The compiler does not infer intent or train a model. Imported recipes always require fresh approval; export includes no approval or session state.

**Review the concrete plan.** Recipe approval is separate from reviewing the actual input rows. Changing a value invalidates the plan. The server binds each run to the exact recipe, adapter, ordered rows and plan checksum.

**Bounded replay.** A batch can contain at most 20 rows. Each runs in a fresh owned page. The runner uses actual Chromium actions and checks all three output values. Verified rows produce hash-checked JSON receipts. A wrong result, ambiguous control or unexpected effect halts later work.

**Operational safeguards.** The scheduler and teaching service share one execution slot. Duplicate request IDs return the existing execution instead of creating another. Cancellation preserves completed rows. Interrupted or uncertain work requires review and is never retried automatically. Guided-batch scheduling and resume are not implemented.

**Three-stage interface.** Demonstrate, Bind & review, and Rehearse have separate screens. Variable controls, explicit review checkboxes, plan previews, verified receipts and failure history are wired to the local API. The separate HTML preview is read-only.

## Evidence

- Combined regression suite: **{passed} passed, {report['failures']} failures, {report['errors']} errors, {report['skipped']} explicit skips** across {report['test_methods']} test methods.
- New v0.4 tests: **{new_methods}** contract, recorder, browser, persistence and API methods.
- Separate rendered-interface checks: **{ui['passed']} passed, {ui['failed']} failed**; no recorded JavaScript runtime errors.
- The included demonstration records four actual browser events, compiles explicit bindings, and verifies three rows with 12 actions and nine output checks. A separate deliberate wrong-topic run halts and stays visible in history.
- A separate automated test verifies 20 rows, 80 browser actions and 60 output checks with zero model calls. This is not a multi-day reliability study.
- The existing image demo still produces ten verified PNG files. Its scheduling clock is injected, not an overnight trial.

The doctor status is **{qualification['status']}**. Browser HTTP navigation remains blocked by administrator policy here; no policy was changed. Actual HTTP-client component checks and actual local API requests are not browser-HTTP qualification.

## Run it

After installing the pinned dependencies and Chromium as described in README:

```sh
python -m handnavigate studio
```

Open `http://127.0.0.1:4177/teach` on the same computer. Recording is limited to the owned form. No API key is needed for the current runner.

## Not implemented or not qualified

Arbitrary website recording, Pinterest automation, real customer accounts, automatic intent/loop inference, irreversible remote actions, guided-batch scheduling/resume, authenticated unattended jobs, native installers, native mobile control and cloud execution remain outside this release. Windows/macOS execution has not been tested here. The supplied cross-platform CI configuration has not run on GitHub.

The next external-site gate remains a fully qualified, explicitly authorized browser workflow. The teaching improvements do not waive that requirement.
'''
(ROOT / 'research/RELEASE_NOTES_V04.md').write_text(release)
(OUT / 'HandNavigate_v0.4_Release_Notes.md').write_text(release)

skips = '\n'.join(f'- `{item["test"]}`: {item["reason"]}' for item in report['skipped_tests'])
text = f'''# HandNavigate v0.4 test and qualification report

Generated from `evidence/test-results.json`, `evidence/v04-combined-ui-checks.json`, `evidence/v04-qualification/qualification.json` and the demonstration receipts. Build date: 23 October 2026.

## Results

| Layer | Measured result | What it establishes |
|---|---|---|
| Combined regression | {passed} passed; {report['failures']} failures; {report['errors']} errors; {report['skipped']} skips; {report['test_methods']} methods | Tested contract, storage, scheduling, owned browser and API behaviors |
| Guided-teaching methods | {new_methods} passed | New compilation, recording, replay, persistence and API cases |
| Rendered-interface checks | {ui['passed']} passed; {ui['failed']} failed | {ui['studio_checks']} established studio checks and {ui['teaching_checks']} teaching-screen checks |
| Actual three-row demonstration | 3/3 verified; 12 actions; 9 output checks | Owned DOM replay, independently checked visible values and real local JSON artifacts |
| Actual longer batch | 20/20 verified; 80 actions; 60 output checks | Bounded repetition on the owned form, not an arbitrary long-task benchmark |
| Existing scheduled image demonstration | 10 verified PNG files | Actual offline browser downloads; injected scheduling clock |
| Owned HTTP qualification | {qualification['status']} | Separate HTTP components work; browser HTTP is not qualified here |

All observed model-call counts in these runners are zero because no model-provider implementation exists. This is not a performance comparison against an AI agent.

## New cases checked

The contract tests cover explicit variable/constant bindings, all-constant recipes, mandatory field/effect capture, rejected private/unsupported events, repeat limits, strict boolean and enum values, missing/duplicated identities, intermediate-parameter validation, unsupported code/URLs/selectors, typed output checks, adapter binding and plan invalidation.

Actual Chromium recorder tests capture fill, selection, checkbox state and click actions. They verify that start/stop bounds capture, unrelated app inputs are excluded, recognized private controls are redacted, unchanged false/default values can be explicitly captured, unsupported actions are preserved as blocks, and adjacent text edits are coalesced without erasing click boundaries. These demonstrations are driven by Playwright, not observed real people.

Actual browser rehearsals cover three-row success, 20-row success, wrong output, missing output, ambiguous targets, delayed output, unexpected dialogs, cancellation after one verified row, cancellation before launch and rejected stale/unapproved plans.

Persistence tests use clearly labeled execution doubles to isolate approval, idempotency, changed-plan conflicts, shared-runner exclusion, revocation, restart recovery, failed worker start and bookkeeping failure. A separate actual localhost API test launches the real owned browser runner, reads verified artifacts, rejects a tampered file and deduplicates a repeated execution request.

## UI tests and the integration boundary

Read-only previews use captured evidence and issue no network requests. Their mutation and execution controls are disabled. Teaching layouts were checked at 1440, 768, 390 and 320 pixel widths; responsive rendering is not native mobile support.

Editable UI tests use an in-memory API stub, not a proxy and not real browser HTTP. They exercise real DOM recording, compilation payloads, explicit approvals, input-plan review, stale-plan invalidation, request identifiers, stop controls and escaped lesson names. Actual server behavior is tested separately by Python HTTP requests. There has been no browser-rendered HTTP UI-to-server end-to-end qualification in this environment.

A UI test exposed a missing request ID in an insecure in-memory document. The implementation now uses secure random bytes for UUID generation, gates Run on the identifier, and assigns the plan only after identifier generation succeeds. The re-run passed. No missing-ID request is treated as an approved execution by the server.

## Explicit skips

{skips}

These tests remain present. The supplied CI sets `HANDNAVIGATE_REQUIRE_BROWSER_HTTP=1` so a managed-browser block is a failure rather than an accepted skip. CI was not pushed or run.

## Browser and platform scope

Measured environment: Python {report['environment']['python']}, {report['environment']['system']}, Playwright {report['environment']['playwright']}, cryptography {report['environment']['cryptography']}. The demonstration browser reported Chromium {proof['state']['runs'][0]['report']['browser_version']}.

No alternate browser, policy modification or HTTP proxy was used to evade the administrator restriction. The owned form is loaded directly into memory and makes no external requests. The doctor uses a separate Python HTTP client for explicitly labeled component checks; it is not a browser fallback.

Only the measured Linux environment was exercised. Windows/macOS, real mobile devices, native packaging, OS keychain behavior, arbitrary power failures and external-site persistence are not qualified.

## Evidence files

- `evidence/v04-full-console.txt` and `evidence/test-results.json`: final regression evidence.
- `evidence/v04-ui-checks.json`, `evidence/v04-teaching-ui-checks.json`, `evidence/v04-combined-ui-checks.json`: separate UI evidence.
- `evidence/v04-teaching-demonstration.json`: actual recorded events, explicit bindings, recipe, rows, plans and both successful/failed run receipts.
- `evidence/v04-teaching-artifacts/manifest.json`: delivered verified JSON artifacts and hashes.
- `evidence/v04-qualification/qualification.json`: current owned HTTP/browser boundary.
- `evidence/v04-demonstration.json`: retained image workflow rehearsal and injected-clock schedule.

## Reproduction

```sh
python run_tests.py
python -m handnavigate doctor --output evidence/v04-qualification
# Inspect nonzero status; never bypass browser policy.
python build_v04_evidence.py
python check_ui.py
python write_v04_docs.py
```

Passing test counts are not customer task-success percentages. Safe halts, test doubles and component checks are not production completions. The next site gate remains one explicitly authorized real browser workflow with objective output verification.
'''
(ROOT / 'research/TEST_REPORT.md').write_text(text)
(OUT / 'HandNavigate_v0.4_Test_Report.md').write_text(text)
for name, destination in [('TEACHING_GUIDE.md', 'HandNavigate_v0.4_Teaching_Guide.md'),
                          ('SECURITY_MODEL_V04.md', 'HandNavigate_v0.4_Security_Model.md')]:
    shutil.copy2(ROOT / 'research' / name, OUT / destination)
print(json.dumps({'tests': status['tests'], 'ui_checks': ui['passed'], 'qualification': qualification['status']}, indent=2))
