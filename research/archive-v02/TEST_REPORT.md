# HandNavigate v0.2: test and qualification report

**Build date:** 23 October 2026  
**Suite execution:** 2026-10-23T05:42:16.208859+00:00  
**Scope:** Owned synthetic fixture, local state and local API only.

## Results

**85 passed, 0 failed, 0 errors, 1 explicitly skipped out of 86 automated test methods.**

**28 separate rendered-UI checks passed; 0 failed; no JavaScript runtime errors were recorded.**

These are test counts, not 85 successful customer workflows and not a production reliability percentage. Fault tests pass when the system correctly refuses or pauses. The original 50-method suite was rerun before changes: 49 passed and one was skipped. The current combined suite retains those regressions and adds the v0.2 tests.

## Evidence by layer

| Layer | What actually ran | What this does not establish |
|---|---|---|
| Original browser runner | Real Chromium clicks, semantic targets, local Blob downloads, file checks, controlled resume and fault scenarios | HTTP site navigation or public-site reliability |
| Daily-time arithmetic | India time conversion, invalid specs, strict future calculation, DST gap/fold handling | Multi-year operational uptime or all global calendar behavior |
| Queue and storage | Durable history, matching-rehearsal gate, unique occurrences, concurrent claims, overlap handling, missed-run coalescing/skipping, stale-queue expiry and replacement | Distributed exactly-once remote effects |
| Scheduled browser integration | Actual controller worker thread; clock advanced to a daily due time; two actual files downloaded and verified; duplicate tick did not repeat work; history survived reopening | An overnight or multi-day wall-clock soak |
| Interruption recovery | Child process wrote a simulated local effect then exited via os._exit before recording completion; restart marked NEEDS_REVIEW and did not repeat the effect | A real remote transaction crash, physical power failure, disk-controller durability or every browser-crash point |
| Teaching/API integration | HTTP request imported fill/click events, bound a topic, explicitly selected the authored collection contract, approved the checksum, performed a VERIFIED browser rehearsal and saved a schedule | Human usability, inferred intent, learned loops or arbitrary-site support |
| Artifact integrity | Changing a previously verified file made the API reject it instead of serving it as verified | Independent semantic identity, rights or safety of third-party content |
| Rendered interface | Actual HTML/JS rendered in Chromium at desktop and 390-pixel phone widths; navigation, overflow, read-only controls and error checks | Native phone execution or real hardware qualification |
| Editable UI controls | In-memory fetch stub checked consent gates and request payloads for run, schedule, compile and draft actions | Browser-to-server HTTP integration; actual API integration is tested separately |

## Recorded demonstration

`evidence/v02-demonstration.json` records one real offline rehearsal and one scheduled invocation. Both produced **10 verified PNG files**. The collection uses the owned synthetic fixture and an **injected clock**, deliberately advanced to trigger the schedule. `evidence/v02-sample-files/` contains the actual files and a manifest with hashes.

The preview's verified counters come from these reports. Its scheduled time is an example saved by the demonstration. Opening the preview does not schedule work, and the source ZIP contains no active runtime database.

The zero-model result is structural: there is no model client, provider SDK, API key integration, training operation or model-repair path in this runner. The report field is not a general-purpose provider-billing meter.

## HTTP browser restriction remains

A fresh ordinary browser navigation on **2026-10-23T05:37:48.642027+00:00** to the owned localhost fixture failed with `net::ERR_BLOCKED_BY_ADMINISTRATOR`. Browser version: **144.0.7559.96**. No administrator policy was changed and no browser-network bypass was installed.

The existing HTTP redirect browser integration test remains explicitly skipped under the in-memory adapter. Its separate fake-route unit test checks policy logic, not an observed browser HTTP redirect. Direct localhost API requests are not equivalent to browser navigation.

The web UI was rendered from HTML directly. Editable UI checks used an in-memory API stub. This distinction is preserved in `evidence/v02-ui-checks.json` and is not presented as a live-site test.

## Environment

Python 3.13.5; Playwright 1.57.0; Linux; Chromium 144.0.7559.96; tested tzdata fallback 2026.2. Generated PNG fixtures are 24 by 24 pixels. Timing and throughput are not representative of ordinary internet images.

The code includes a Windows ownership-lock path and IANA timezone fallback, but Windows/macOS runtime behavior and native installers were not tested. A phone-sized browser viewport is not a mobile automation engine.

## Operational limits

The studio must remain open and the computer awake. The worker does not wake a sleeping device or run after application exit. Schedule definitions and history survive restarts. A non-verified scheduled run pauses its schedule. Unknown interrupted attempts block further work until explicitly acknowledged, and acknowledgement does not automatically resume schedules.

The existing runner can leave `.execution.lock` after a hard kill. It is not automatically removed. Operators must confirm no live worker remains and inspect evidence before manual stale-lock recovery. Cancellation is cooperative, not a hard process watchdog.

SQLite queue state and runner file checkpoints are separate stores. A crash between their writes is deliberately treated as uncertain rather than claimed to be exactly-once. No production security audit, OS-level egress sandbox, remote-write verifier, authenticated session lifecycle, general privacy/redaction guarantee or cloud operational qualification is provided.

## Reproduction and raw records

```sh
python run_tests.py
python build_v02_evidence.py
python check_ui.py
```

Raw files: `evidence/test-results.json`, `evidence/test-console.txt`, `evidence/v01-baseline-recheck-console.txt`, `evidence/v02-ui-checks.json`, `evidence/v02-http-browser-probe.json`, `evidence/v02-demonstration.json` and `evidence/v02-sample-files/manifest.json`.
