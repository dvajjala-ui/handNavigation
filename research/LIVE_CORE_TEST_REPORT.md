# Browser core qualification report

## Result

This is a development code delivery, not a qualified real-site release.

| Layer | Result | Meaning |
| --- | --- | --- |
| New component suite | 42 passed; 0 failed; 0 errors; 0 skipped | Contracts, importer, recorder, browser actions, checks and model protocol on explicit offline documents |
| Chromium controls | Exercised | Actual fill/click/select/check/press/scroll and local download interactions |
| Tool loop | Exercised with scripted provider | Requests/actions/observations connected; not model reasoning quality |
| Groq transport | Request shape tested with mocked HTTP transport | No live API call; no account charge |
| Vision request path | Implemented, unqualified | No live vision model test |
| AI-free replay | Exercised | Zero provider calls; exact approved recipe/input binding |
| Real URL probe | ENVIRONMENT_BLOCKED | Ordinary `https://example.com` navigation denied by administrator policy |
| Complete older suite | Incomplete | Execution limit terminated rerun after 19 passed and 1 skipped; no full regression claim |
| Original user's capture session | Not imported | ZIP contains source tool, no captured session output |
| Original uploaded key | Not used | No validity test, no provider request, not redistributed |

## Test coverage details

The new suite tests exact origin scoping, request-method rules, rejected nonweb/credential URLs, secret query redaction, rejected arbitrary code/tool arguments, strict booleans and action bounds, approval invalidation, missing completion checks, actual DOM observation/screenshots, basic form actions, stale snapshots, operator refusal, changed page/target during approval, ambiguous replay locators, sensitive controls, independent verification, local file integrity, the observe/tool/act loop, failure to infer success from prose, provider consent and transport shape, conservative import, multi-flow selection, per-field recording, explicit checkbox state, keyboard-click deduplication, and the external demo recipe's schema.

The public TodoMVC workflow is authored from official Playwright documentation and shipped as an external acceptance test. Its schema was validated. It was not executed on that website here.

## Saved evidence

- `evidence/live-core/component-results.xml`: pytest JUnit output.
- `evidence/live-core/test-console.txt`: final new-suite console output.
- `evidence/live-core/real-url-probe/result.json`: blocked normal browser probe.
- `evidence/live-core/baseline-regression-console.txt`: incomplete older-suite run, including termination output.
- `evidence/live-core/measured-component-example/`: real screenshots/action logs from an explicitly offline scripted-provider loop and subsequent AI-free replay.
- `evidence/live-core/qualification.json`: machine-readable qualification summary.

Historical v0.1-v0.4 evidence is preserved for provenance and is not fresh validation of this patch.

## Required acceptance gate

On a permitted, policy-compliant execution environment: run the public-site example, then one user-authorized target workflow; exercise the real Groq path with a fresh local key; review the actual draft; repeat with different inputs without a provider call; verify the real output; test session expiry and an intentional UI mismatch. Only those observed results can establish live-site capability. None are replaced by a high offline test count.

No claim is made of production reliability, arbitrary-site support, cross-platform qualification, malicious-site isolation, or unattended operation.
