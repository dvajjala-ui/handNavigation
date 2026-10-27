# HandNavigate Desktop 0.6.1: measured test report

Date: 27–28 October 2026. This is a Windows Electron app with a persistent local browser. These tests use owned HTTP sources and destinations; Pinterest, Reddit, and arbitrary websites remain separately unqualified.

## Measured results

| Check | Result | Evidence |
| --- | --- | --- |
| Core contracts, recovery, image identity, transport and local API | 34 passed, 0 failed | [unit console](../analysis/desktop-v061-unit-console.txt) |
| Existing real Electron acceptance suite | 16 passed, 0 failed | [results](../desktop/evidence/e2e-results.json) |
| Extended browser, pagination, API and script workflows | 12 passed, 0 failed | [results](../desktop/evidence/workflow-results.json), [final console](../analysis/desktop-v061-desktop-console.txt) |
| Slow uploads, temporary HTTP failures, asynchronous search, minimized input and sign-in deferral | 10 passed, 0 failed | [results](../desktop/evidence/reliability-results.json), [console](../analysis/desktop-v061-reliability-console.txt) |
| Combined desktop regression | 38 passed, 0 failed | [final console](../analysis/desktop-v061-desktop-console.txt) |
| Production dependency audit | 0 reported vulnerabilities | [audit](../analysis/desktop-v061-production-audit.json) |
| Exact portable EXE smoke | 3 decoded images, real API execution, idempotency, bundled script client and slow upload passed | [packaged result](../desktop/evidence/packaged-results.json), [console](../analysis/desktop-v061-packaged-console.txt) |

The portable file is `dist/HandNavigate-0.6.1-Windows.exe` (116,437,404 bytes), SHA-256 `ED6DB2B4A1360A6ED2D7C92903F64696234326039217FA7B72DE7C9A8B7B4402`. [Build log](../analysis/desktop-v061-package-console.txt).

The existing suite covers two 20-image topics, actual teaching and variable replay, persistent login across restart, image decoding, real uploads, remote-byte verification, duplicate upload prevention, a real scheduled execution with an injected future clock, and failure handling.

The extended suite operates the real image and Next-control pickers, saves 20 images across four pages, then scans past those pages and saves 20 different images. It verifies history across partial runs and workflows, preservation of multiple named variable columns during UI edits, and reuse of pending local files when a partial transfer resumes.

The receiving site loads its gallery asynchronously and exposes a paginated view. The app finds originals on later pages without resending files, stops before upload when the gallery exceeds its limit, and rechecks a late upload without another submission. The recheck result is checked through the app interface and in the persisted database.

The API tests cover authentication, rejected website origins and Host headers, approved rows, invalid requests and persistent request IDs. A repeated request starts only one job, including after restart. The supplied PowerShell client starts an actual download and waits for its verified result. Unit tests also check that receipt-write failure releases the browser and runner.

The 0.6.1 reliability tests reproduce two HTTP 503 image-read failures and confirm recovery on the third read. Persistent failure stops after three attempts. Transport checks also cover a reset during response-body reading, access denial, server retry delays, stopping during backoff, and origin validation after retries. Only image reads are retried; upload writes are not automatically repeated.

The receiving fixture takes 3.2 seconds to finish an upload and discards it if the response connection closes early. Both submitted and file-selection uploads finish and are confirmed against persisted image bytes, with zero aborted uploads. Repetition creates no additional upload. Stopping a pending upload produces `NEEDS_REVIEW` and blocks resubmission. A taught search with a delayed HTTP response saves the new topic's image instead of the old results.

A real sign-in popup keeps a due daily job pending without consuming its occurrence or disabling its schedule. Closing it allows one verified execution. Unit coverage also checks browser availability between two due workflows. Teaching, image selection and an active run use the same availability guard.

Atomic state saves retry temporary `EPERM`, `EACCES` and `EBUSY` file locks with a bounded backoff. Fault-injected tests cover a verified upload journal, opening the temporary file and creating the backup. Persistent locks stop after seven attempts, and other I/O errors stop immediately; both preserve the prior primary file. The packaged upload check also verifies that the final result is durably saved.

Replay uses [Chromium's input commands](https://chromedevtools.github.io/devtools-protocol/tot/Input/) in place of [Electron's focus-dependent input method](https://www.electronjs.org/docs/latest/api/web-contents#contentssendinputeventinputevent). The owned background tests minimize the native app window, replay text, selection, checkbox, click, Space and Enter actions, and require trusted text/click/key events. A separate minimized transfer submits one actual file and confirms the persisted original. Both assert that the app remains minimized.

Some cases create workflows through a test-only main-process hook and then execute the production runner. Image/Next picking, teaching, manual execution, API enablement and upload rechecking use the real interface. This does not establish that every setup control has been exercised solely with mouse input.

## Qualification limits

- Duplicate history includes saved images from incomplete runs. Exact bytes, normalized decoded pixels and source identities are checked. Optional visual matching is approximate; older entries without visual metadata retain byte/source checks. Every crop or edit is not guaranteed to match.
- Pagination supports scrolling, a reviewed Next/Load-more control and bounds. Platform-specific content API cursors and complete social-post extraction remain separate work.
- Upload verification requires persisted original bytes. Destinations exposing only recompressed thumbnails need another explicit verifier.
- The API and daily queue require the Windows app to remain open and the computer awake. No overnight endurance run or unattended Linux-server deployment has been performed.
- Sign-in, MFA and CAPTCHA require the person. The app's profile is separate from Codex/Chrome. The earlier assisted Pinterest download does not qualify this executable.
- This is an unsigned local Windows build. CI is configured to repeat tests and build it; store release and every Windows configuration remain unqualified.

See the [desktop guide](../DESKTOP_START_HERE.md), [API guide](../API.md), and [exact packaged-executable smoke result](../desktop/evidence/packaged-results.json).
