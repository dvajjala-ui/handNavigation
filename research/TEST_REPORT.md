# HandNavigate v0.4 test and qualification report

Generated from `evidence/test-results.json`, `evidence/v04-combined-ui-checks.json`, `evidence/v04-qualification/qualification.json` and the demonstration receipts. Build date: 23 October 2026.

## Results

| Layer | Measured result | What it establishes |
|---|---|---|
| Combined regression | 172 passed; 0 failures; 0 errors; 2 skips; 174 methods | Tested contract, storage, scheduling, owned browser and API behaviors |
| Guided-teaching methods | 41 passed | New compilation, recording, replay, persistence and API cases |
| Rendered-interface checks | 83 passed; 0 failed | 41 established studio checks and 42 teaching-screen checks |
| Actual three-row demonstration | 3/3 verified; 12 actions; 9 output checks | Owned DOM replay, independently checked visible values and real local JSON artifacts |
| Actual longer batch | 20/20 verified; 80 actions; 60 output checks | Bounded repetition on the owned form, not an arbitrary long-task benchmark |
| Existing scheduled image demonstration | 10 verified PNG files | Actual offline browser downloads; injected scheduling clock |
| Owned HTTP qualification | COMPONENTS_PASS_BROWSER_BLOCKED | Separate HTTP components work; browser HTTP is not qualified here |

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

- `test_16_redirect_blocked (test_lab.BrowserTests.test_16_redirect_blocked)`: HTTP redirect integration cannot be represented by an offline Blob fixture; policy unit-tested separately
- `test_browser_signin_capture_and_separate_context_export (test_v03.RealBrowserHTTPGateTests.test_browser_signin_capture_and_separate_context_export)`: Observed ERR_BLOCKED_BY_ADMINISTRATOR; no policy bypass; browser HTTP remains unqualified

These tests remain present. The supplied CI sets `HANDNAVIGATE_REQUIRE_BROWSER_HTTP=1` so a managed-browser block is a failure rather than an accepted skip. CI was not pushed or run.

## Browser and platform scope

Measured environment: Python 3.13.5, Linux, Playwright 1.57.0, cryptography 46.0.4. The demonstration browser reported Chromium 144.0.7559.96.

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
