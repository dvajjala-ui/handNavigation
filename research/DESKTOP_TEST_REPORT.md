# HandNavigate Desktop 0.6: measured test report

Date: 27 October 2026. This is a Windows Electron app with a persistent local browser. These tests use owned HTTP sources and destinations; Pinterest, Reddit, and arbitrary websites remain separately unqualified.

## Measured results

| Check | Result | Evidence |
| --- | --- | --- |
| Core contracts, recovery, image identity and local API | 21 passed, 0 failed | [unit console](../analysis/desktop-v06-unit-console.txt) |
| Existing real Electron acceptance suite | 16 passed, 0 failed | [results](../desktop/evidence/e2e-results.json) |
| Extended browser, pagination, API and script workflows | 12 passed, 0 failed | [results](../desktop/evidence/workflow-results.json), [final console](../analysis/desktop-v06-workflows-console.txt) |
| Production dependency audit | 0 reported vulnerabilities | [audit](../analysis/desktop-v06-production-audit.json) |
| Exact portable EXE smoke | 3 decoded images, real API execution, idempotency and bundled script client passed | [packaged result](../desktop/evidence/packaged-results.json), [console](../analysis/desktop-v06-packaged-console.txt) |

The portable file is `dist/HandNavigate-0.6.0-Windows.exe` (116,436,223 bytes), SHA-256 `C1B52BD07BCAA771DFFA20FF008ED4B23323D9ECEF7F2B2DB2402AD8E86C7C6D`. [Build log](../analysis/desktop-v06-package-console.txt).

The existing suite covers two 20-image topics, actual teaching and variable replay, persistent login across restart, image decoding, real uploads, remote-byte verification, duplicate upload prevention, a real scheduled execution with an injected future clock, and failure handling.

The extended suite operates the real image and Next-control pickers, saves 20 images across four pages, then scans past those pages and saves 20 different images. It verifies history across partial runs and workflows, preservation of multiple named variable columns during UI edits, and reuse of pending local files when a partial transfer resumes.

The receiving site loads its gallery asynchronously and exposes a paginated view. The app finds originals on later pages without resending files, stops before upload when the gallery exceeds its limit, and rechecks a late upload without another submission. The recheck result is checked through the app interface and in the persisted database.

The API tests cover authentication, rejected website origins and Host headers, approved rows, invalid requests and persistent request IDs. A repeated request starts only one job, including after restart. The supplied PowerShell client starts an actual download and waits for its verified result. Unit tests also check that receipt-write failure releases the browser and runner.

Some cases create workflows through a test-only main-process hook and then execute the production runner. Image/Next picking, teaching, manual execution, API enablement and upload rechecking use the real interface. This does not establish that every setup control has been exercised solely with mouse input.

## Qualification limits

- Duplicate history includes saved images from incomplete runs. Exact bytes, normalized decoded pixels and source identities are checked. Optional visual matching is approximate; older entries without visual metadata retain byte/source checks. Every crop or edit is not guaranteed to match.
- Pagination supports scrolling, a reviewed Next/Load-more control and bounds. Platform-specific content API cursors and complete social-post extraction remain separate work.
- Upload verification requires persisted original bytes. Destinations exposing only recompressed thumbnails need another explicit verifier.
- The API and daily queue require the Windows app to remain open and the computer awake. No overnight endurance run or unattended Linux-server deployment has been performed.
- Sign-in, MFA and CAPTCHA require the person. The app's profile is separate from Codex/Chrome. The earlier assisted Pinterest download does not qualify this executable.
- This is an unsigned local Windows build. CI is configured to repeat tests and build it; store release and every Windows configuration remain unqualified.

See the [desktop guide](../DESKTOP_START_HERE.md), [API guide](../API.md), and [exact packaged-executable smoke result](../desktop/evidence/packaged-results.json).
