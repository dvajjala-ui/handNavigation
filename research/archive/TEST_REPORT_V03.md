# HandNavigate v0.3 test and qualification report

Generated from completed evidence on 2026-10-23T06:23:52.594453+00:00. This report distinguishes execution layers. A mock, an owned HTTP service and a real browser workflow are not interchangeable evidence.

## Combined suite

| Measure | Result |
|---|---:|
| Test methods executed | 133 |
| Passed | 131 |
| Failures | 0 |
| Errors | 0 |
| Explicit skips | 2 |

Command: `python run_tests.py`.

Environment: Linux, Python 3.13.5, Playwright 1.57.0, cryptography 46.0.4. Dependency pins reflect this environment, not a current security audit.

The supplied v0.2 baseline was rerun first: 85 passed, one skipped. The final suite contains the original and v0.2 regressions plus v0.3 connection tests. No tests were removed to obtain a passing result.

### Skipped methods

- `test_16_redirect_blocked (test_lab.BrowserTests.test_16_redirect_blocked)`: HTTP redirect integration cannot be represented by an offline Blob fixture; policy unit-tested separately
- `test_browser_signin_capture_and_separate_context_export (test_v03.RealBrowserHTTPGateTests.test_browser_signin_capture_and_separate_context_export)`: Observed ERR_BLOCKED_BY_ADMINISTRATOR; no policy bypass; browser HTTP remains unqualified

The full browser-HTTP test requires an actual owned login, interactive browser actions, encrypted capture, a second browser context, a verified CSV download and rejection after server expiry. An observed administrator block causes a documented skip here. Setting `HANDNAVIGATE_REQUIRE_BROWSER_HTTP=1` makes that condition fail, as configured in the supplied but unexecuted CI workflow.

## What each layer demonstrates

| Layer | Actual execution | Does not demonstrate |
|---|---|---|
| Contract/registry/vault tests | Python validation, SQLite transactions, encrypted files, wrong-key/tamper/expiry checks | Browser login, production key management, remote site authorization |
| Browser semantic components | Real Chromium DOM checks using directly loaded owned HTML | HTTP navigation, browser session reuse, internet sites |
| Owned HTTP component tests | Real localhost server, real cookie jar, login requests, CSV bytes, expired-session rejection | Browser clicks or browser download integration |
| Application request-policy tests | Mock request/response callbacks verifying no follow/fulfill on disallowed routes | OS egress isolation or behavior of all browser protocols |
| Existing image workflow | Real Chromium interactions on in-memory owned HTML and generated Blob downloads | A third-party website or actual HTTP downloads |
| Studio API | Actual localhost HTTP requests, CSRF checks, connection persistence, approved fixture runner integration | End-to-end rendered UI over browser HTTP |
| Editable UI controls | Real DOM and clicks against an explicitly in-memory fetch stub | Browser-to-server HTTP integration |

## Owned portal doctor

Report: `evidence/v03-qualification/qualification.json`.

Observed status: **COMPONENTS_PASS_BROWSER_BLOCKED**.

Seven component checks passed: unauthenticated access denied; synthetic sign-in issued an HttpOnly cookie; session reuse displayed the expected account; authenticated search returned the export link; a real HTTP CSV matched the content contract; session encryption round-tripped; and server-side expiry rejected subsequent access.

The artifact `evidence/v03-qualification/owned-http-component-export.csv` contains five actual generated rows downloaded by a Python HTTP client. Its SHA-256 is `577071fcdfa85aa654fa93d4cee8da4a2d05309525e4eaa312a2afe8c11f3032` and its size is 235 bytes. It is not represented as a browser download.

Ordinary browser navigation to the owned portal returned **ERR_BLOCKED_BY_ADMINISTRATOR**. The full authenticated browser flow was **not run** in that doctor invocation. No policy was disabled, no browser engine was substituted to evade the policy, and HTTP-client success was not used to claim browser qualification.

## New checks of particular importance

Review scopes reject credentials, scripts, wildcards, unsafe origins and unknown paths/query keys. Concurrent edits preserve only one valid next revision. Profile changes invalidate approval and encrypted session binding. Unapproved or missing-session execution stops before launching a browser.

Encrypted files were checked for absence of the synthetic cookie plaintext and passphrase. Wrong passphrases and tampered tokens fail closed. TTL expiry, expired cookies, cross-origin storage, parent-domain cookies, non-Secure remote cookies and unsupported auth storage are rejected. Local forget reports that remote logout was not performed.

The CSV verifier rejects wrong topics, duplicate IDs, schema changes, formula-like cells, malformed UTF-8, login HTML, row-count violations and excessive file size. The file-size check is after transfer; it does not prove bounded ingress or disk consumption during a hostile download.

Actual Chromium component tests verify exact account labels, login-required sentinels, ambiguous-target halts and hidden-control exclusion. They load owned HTML directly and do not replace the skipped HTTP integration.

## Rendered interface checks

Command: `python check_ui.py`.

Results: **41 passed, 0 failed**; 0 JavaScript runtime errors recorded. The read-only preview made no external browser requests. Checks include desktop/phone-width overflow, navigation, disabled execution, exact recipe consent, scheduling payloads, teaching draft payloads, connection approval consent, checksum binding, credential-free import and distinct HTTP/browser verdicts.

Desktop and phone-width screenshots were visually inspected. Phone width is emulation, not a native phone app or physical-device test. Editable controls use a declared in-memory API stub; the test suite separately exercises the real API via an HTTP client.

## Retained recurring image demonstration

`evidence/v03-demonstration.json` records a real offline browser rehearsal and a real scheduled ten-file collection. The scheduler clock is injected. The copied PNG outputs and manifest are in `evidence/v03-sample-files/`. This is not an overnight or multi-day deployment. No enabled runtime database is distributed.

## Unestablished claims

No third-party site, real customer account, authenticated unattended schedule, Windows/macOS installation, native phone execution, OS credential store, complete network sandbox, all-crash reconciliation, or production reliability rate was validated. The new CI configuration has not been executed. Tests of safe stopping are counted as passing methods, not successful task completion.

## Raw evidence

`evidence/test-results.json`, `evidence/v03-full-console.txt`, `evidence/v03-focused-console.txt`, `evidence/v03-ui-checks.json`, `evidence/v03-ui-console.txt`, `evidence/v03-qualification/qualification.json`, and `evidence/v03-demonstration.json` are included. Earlier release evidence is retained and labeled separately.
