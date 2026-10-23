# HandNavigate Lab: test and qualification report

**Research date:** 22 October 2026  
**Execution timestamp:** 2026-10-22T13:41:48.250850+00:00  
**Scope:** Owned synthetic fixture only. No third-party site was automated.

## Result

**49 passed, 0 failed, 0 errors, 1 explicitly skipped out of 50 test methods.**

The method count includes browser-fixture checks, contract validation, mock-based network-policy tests, and direct localhost studio API tests. It is not 50 completed customer workflows.

There are 35 recorded run observations, including refusals before browser work. Their outcome counts are `{'VERIFIED': 14, 'PARTIAL': 1, 'HALTED': 14, 'PAUSED': 4, 'CANCELLED': 1, 'REPLAYED': 1}`. Safe halts and deliberate pauses are expected outcomes in fault tests, not completed tasks.

## Exact execution boundary

The browser was real Chromium. The default test adapter populated an owned HTML fixture directly and used local Blob links for actual PNG download events. Browser input, click, DOM lookup, file persistence, file checking, and controlled checkpoint resume were exercised.

**HTTP browser navigation was blocked by administrator policy in the build environment.** That policy was not changed. Therefore actual HTTP website navigation, HTTP download integration, account authentication and real-site reliability are not validated by this report.

A separate direct localhost HTTP client tested the studio API, including a real request that initiated the offline browser runner and returned a checked artifact. That does not substitute for browser navigation validation.

The browser HTTP redirect integration test is explicitly skipped. A fake-route unit test checks that redirect fetching is configured with `max_redirects=0` and that a redirect response is rejected. It is not an observed network-level redirect integration result.

## Environment

- Python: 3.13.5
- Playwright: 1.57.0
- OS: Linux
- Chromium: 144.0.7559.96 reported by the installed browser during setup.
- Test adapter: `memory`
- Synthetic PNG profile: 24 by 24 pixels, 8-bit RGB, generated locally.

These small files are not representative of large image downloads, variable networks, or public website behavior. Windows, macOS and mobile execution were not tested.

## Sample executed collection

The standalone CLI run in `evidence/sample-run.json` produced **10 verified files**, reported **0 model calls**, and ended with **VERIFIED**. Its elapsed time was **3.232 seconds** in the offline fixture. Do not extrapolate that time to internet tasks.

The zero-model observation is structural: the runner has no model provider code or API client. The report's zero field is not a general inference-cost metering implementation.

## What the teaching test actually did

Playwright drove a Topic input and a Search click. The recorder captured those browser events. The compiler replaced the explicitly identified example topic with a variable, added a reviewer-supplied result-ready check, and produced a reviewable recipe. A checksum receipt was required before replaying that recipe with a new topic.

The generated search recipe reported `REPLAYED`, not `VERIFIED`: it did not include a file-effect contract. The collection loop and file verifier in the separate download recipe were engineer-authored. No generalized intent inference, model training, or human usability study took place.

## Selected assurance claims

| Mechanism | Observed evidence | Not established |
|---|---|---|
| Targeting | Moved controls and changed IDs retained exact semantic targets | Arbitrary redesign tolerance |
| Alternatives | An explicitly approved exact label worked | Learned or AI-authored repair |
| Ambiguity | Multiple Search matches stopped before download | Universal target identity resolution |
| File verification | Wrong hash, invalid/truncated PNG and byte-budget failures were rejected | Independent semantic image identity or rights |
| Duplicate handling | Duplicate IDs and matching file content were skipped | Global cross-day deduplication |
| Resume | Three checked files were reused and seven new ones downloaded | Arbitrary power-loss recovery or exactly-once remote writes |
| False success | A banner with no download did not satisfy the contract | Verification for every application type |
| Page text | A fixture instruction could not change the deterministic plan | General prompt-injection resistance of a future AI path |
| API controls | Unreviewed/unauthorized local mutation requests were rejected | Multi-user production authorization |

## Full recorded run observations

| Scenario | Expected | Observed | Verified files |
|---|---|---|---|
| normal | VERIFIED | VERIFIED | 10 |
| normal | VERIFIED | VERIFIED | 1 |
| normal | VERIFIED | VERIFIED | 5 |
| normal | VERIFIED | VERIFIED | 12 |
| layout | VERIFIED | VERIFIED | 10 |
| alternative | VERIFIED | VERIFIED | 10 |
| slow | VERIFIED | VERIFIED | 10 |
| duplicates | VERIFIED | VERIFIED | 10 |
| few | PARTIAL | PARTIAL | 3 |
| ambiguous | HALTED | HALTED | 0 |
| unknown | HALTED | HALTED | 0 |
| corrupt | HALTED | HALTED | 0 |
| wrong file | HALTED | HALTED | 0 |
| truncated | HALTED | HALTED | 0 |
| fake success | HALTED | HALTED | 0 |
| expired | HALTED | HALTED | 0 |
| egress | HALTED | HALTED | 0 |
| injection | VERIFIED | VERIFIED | 10 |
| conflicting id | HALTED | HALTED | 0 |
| missing download | VERIFIED | VERIFIED | 10 |
| oversized | HALTED | HALTED | 0 |
| reordered | VERIFIED | VERIFIED | 10 |
| normal | PAUSED | PAUSED | 3 |
| normal | VERIFIED | VERIFIED | 10 |
| normal | VERIFIED | VERIFIED | 10 |
| normal | VERIFIED | VERIFIED | 10 |
| normal | PAUSED | PAUSED | 2 |
| normal | HALTED | HALTED | 0 |
| normal | PAUSED | PAUSED | 1 |
| normal | HALTED | HALTED | 0 |
| normal | HALTED | HALTED | 0 |
| normal | CANCELLED | CANCELLED | 0 |
| record compile review replay | REPLAYED | REPLAYED | 0 |
| normal | PAUSED | PAUSED | 1 |
| normal | HALTED | HALTED | 0 |

## Qualification limits

No real account, paid service, external customer data, Pinterest workflow, Instagram action, unattended daily schedule, remote write, mobile app, cloud worker or model-assisted repair was tested.

The expected content hash is provided by the owned fixture. Agreement with that metadata is not an independent statement about the truth of a website's description. The PNG verifier intentionally supports a minimal fixture profile, not every valid PNG variant or arbitrary media formats.

The initial failed HTTP attempt is retained in `evidence/http-environment-attempt.json` and its console output. It is historical environment evidence from an earlier build, not the latest suite result and not a successful integration qualification.

A shared-browser test run also stalled during development. The final suite uses a fresh browser per test, matching isolated-run behavior more closely. Passing the final suite does not establish the exact cause of the earlier stall or resolve every possible browser resource leak.

## Reproduction

Run `python run_tests.py` for the measured offline adapter. Set `HANDNAVIGATE_TEST_TRANSPORT=http` to qualify the localhost browser-HTTP adapter on a supported unrestricted machine. Keep those result sets separate.

A test report is evidence for its recorded environment and cases, not a promise of future error-free automation.


## Separate UI inspection

Eight read-only offline UI checks passed: receipt display, disabled preview execution, navigation tabs, evidence count display, absence of horizontal overflow at 1440px and 390px, and absence of page script errors. These are additional UI checks, not part of the 50-method suite. The desktop and mobile-width screenshots were visually inspected. They do not establish native mobile execution.
