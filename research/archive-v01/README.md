# HandNavigate Lab

**A runnable engineering experiment for teaching a small browser workflow, reviewing its program, and replaying it without a model.**

Prepared on **22 October 2026** as an additive implementation pack for `dvajjala-ui/handNavigation`. This pack has **not** been committed or pushed to that repository.

## Read this boundary first

This is not a production application and it does not automate Pinterest or any other third-party website. It operates only on its own synthetic media-library fixture.

The validated browser mode loads the fixture directly into Chromium and downloads actual local PNG files through Blob download links. It uses real browser controls, clicks, input events, download events, and filesystem verification, but **does not navigate an HTTP website**. Browser navigation in the build environment was blocked by administrator policy. The environment policy was not changed. The HTTP integration attempt and the limitation are preserved under `evidence/`.

A localhost HTTP fixture adapter is also supplied for testing on your own development machine. Its browser-navigation integration is **not validated in the supplied environment**. The local studio HTTP API is tested separately using a direct localhost HTTP client.

## What works in the experiment

- An editable, constrained JSON recipe with exact label/role targets and an explicitly approved alternative label.
- Variable topic and file count, bounded candidate iteration, duplicate-ID and duplicate-content handling.
- Actual file downloads with size, PNG structure, CRC, bounded decompression, and declared SHA-256 checks.
- SQLite checkpoints, explicit controlled pause/resume, changed/missing-file detection, and overlap prevention.
- Distinct verified, partial, halted, paused, cancelled, and replayed-without-an-effect-contract outcomes.
- A narrow fill/click recorder, explicit parameter substitution, and checksum-bound review receipts.
- A local studio with review, run, stop, resume, manifests, and test evidence.
- No model client, provider SDK, API key, model-training step, or AI repair implementation.

**Teaching limitation:** the recorder can capture a local search demonstration. It does not infer a collection loop, download verifier, intent, branches, or permissions. The supplied image-collection recipe and verifier are hand-authored. The automated teaching test is driven by Playwright, not by an observed external human participant.

## Install

Use Python 3.10 or newer in a virtual environment. Python 3.13.5, Playwright 1.57.0 and the environment's Chromium were used for the supplied checks. Windows and macOS have not been validated.

```sh
python -m venv .venv
# macOS / Linux:
source .venv/bin/activate
# Windows PowerShell instead:
# .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
```

The dependency is pinned to the version actually tested, not asserted to be the latest release. Review dependency updates before any production use. The code prefers a Playwright-managed browser, can use an installed system Chromium if that is missing, and accepts `HANDNAVIGATE_CHROMIUM` as an explicit executable path. It does not disable managed browser policies.

## Start the studio

```sh
python -m handnavigate studio
```

Open `http://127.0.0.1:4177` on your computer. This development server binds only to loopback. Do not expose it to the network. It is not a multi-user authenticated service.

Select a scenario, inspect the four steps, check the explicit review box, and run a rehearsal. The default execution adapter is the **offline browser fixture**. The UI itself is served locally over HTTP.

To try the unvalidated browser-HTTP adapter on an unrestricted development machine:

```sh
python -m handnavigate studio --transport http
```

## Run without the studio

Inspect `recipes/collect-images.json` first. Then explicitly approve that owned-fixture example:

```sh
python -m handnavigate run --approve-local-demo --topic architecture --limit 10
python -m handnavigate run --approve-local-demo --case ambiguous
python -m handnavigate run --approve-local-demo --case fake_success
python -m handnavigate run --approve-local-demo --case duplicates
```

A verified or replayed run exits with code 0. Partial, paused, cancelled, and halted runs exit with code 2 so a calling program cannot confuse them with completed work.

To inspect a visible browser, add `--headed` on a machine with a graphical desktop.

### Prove checkpoint reuse

```sh
python -m handnavigate run --approve-local-demo --job-key example-day --pause-after 3
python -m handnavigate run --approve-local-demo --job-key example-day
```

The first command deliberately pauses. The second rechecks the three saved files and downloads the remaining seven. The job key is bound to the recipe, topic, count, scenario, and fixture transport. Changing those inputs requires a new job key.

This is controlled interruption recovery, not a general crash-consistency proof. A hard process kill may leave `.execution.lock`. Do not remove a lock until you have confirmed no worker is active. Exactly-once remote writes are not implemented.

## Record, compile, review, replay

Automated example, explicitly labelled as such:

```sh
python -m handnavigate record --automated-example
# Inspect runtime/recording/events.json and runtime/recording/recipe.json.
python -m handnavigate approve runtime/recording/recipe.json
python -m handnavigate replay runtime/recording/recipe.json --topic flowers
```

For your own local demonstration, omit `--automated-example`. Type the exact `--example-topic` value in the Topic field, click Search, then close the browser tab. Do not click a download link in this narrow recorder; downloads need a separately reviewed effect contract.

The compiler substitutes only the parameter binding explicitly supplied by the reviewer. The compiler rejects unsupported event types present in its trace. Recorder coverage itself is limited; it does not guarantee that every possible user action was captured. A generated search-only recipe reports **REPLAYED**, not **VERIFIED**, because it has no file-effect contract.

The approval file is a checksum receipt. It is not signed, is not tamper-resistant against the local owner, and is not evidence of an authenticated multi-user approval process.

## Reproduce checks

```sh
python run_tests.py
```

The default test suite uses the offline browser fixture. The HTTP redirect browser integration case is explicitly skipped. Its policy branch has a separate mock-based unit test. Results are exported to `evidence/test-results.json`; individual case outcomes and error codes are retained.

To run browser HTTP integration on your development machine:

```sh
# macOS / Linux:
HANDNAVIGATE_TEST_TRANSPORT=http python run_tests.py
# Windows PowerShell:
# $env:HANDNAVIGATE_TEST_TRANSPORT='http'; python run_tests.py
```

Do not interpret a passing fault test as a successfully completed user task. A test can pass because the runner correctly refuses to act. These deliberately constructed cases do not establish a production success rate.

## Files

| Path | Purpose |
|---|---|
| `handnavigate/runner.py` | Deterministic execution, target resolution, verification, checkpoints |
| `handnavigate/contracts.py` | Constrained workflow schema and review checksums |
| `handnavigate/recorder.py` | Narrow event recorder and explicit parameter compiler |
| `handnavigate/fixture.py` | Owned HTTP and in-memory media fixtures, fault scenarios |
| `handnavigate/studio.py` | Loopback-only development API and run control |
| `ui/index.html` | Functional local studio interface |
| `recipes/collect-images.json` | Authored collection recipe |
| `tests/test_lab.py` | Browser-fixture, contract, policy-unit, and API tests |
| `evidence/` | Measured results, sample receipts, captured and compiled demonstration |
| `research/PRODUCT_DECISIONS.md` | Product owner decisions and next validation gate |
| `research/ARCHITECTURE.md` | Proposed production boundaries, not an implementation claim |
| `research/BUILD_BACKLOG.md` | Prioritized engineering tickets and acceptance criteria |
| `research/SOURCES.md` | Primary-source research register |
| `research/TEST_REPORT.md` | Results and qualification boundaries |

## Important gaps before real-site use

No generalized recorder, natural-language intent parser, inferred loops, pagination, infinite-scroll support, cross-frame/multi-tab workflows, credential vault, scheduling daemon, model repair, transactional remote-write verification, cloud runtime, desktop shell, mobile runtime, OS egress sandbox, signed updates, or production installer is included.

The fixture supplies stable item IDs and expected hashes. A real website may supply neither. Its hash proves agreement with fixture metadata, not independent ownership, search ranking, licensing, or semantic image identity. The download byte cap is checked after browser transfer, not enforced by a streaming network quota. The browser operation timeouts and between-step run budget are not a hard process-level watchdog.

The recorder has basic sensitive-field exclusions, not a complete privacy or secret-detection system. Failure screenshots in the lab contain synthetic data; a real deployment needs a consent, redaction, retention, and access-control design.

This pack is intended to validate mechanisms and expose missing work, not to imply a finished universal automation product.
