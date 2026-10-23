# HandNavigate Lab v0.2

**Teach a constrained local browser workflow, review its exact recipe, verify a rehearsal, and schedule repeat execution without a model.**

Built on the supplied v0.1 prototype on **23 October 2026**. This is a downloadable local source package, not a deployed service, production installer or GitHub commit. Nothing has been pushed to `dvajjala-ui/handNavigation`.

## Start with these boundaries

The application operates on an **owned synthetic media-library fixture**. It does not automate Pinterest, Instagram, other external websites, arbitrary desktop applications or mobile apps. The browser makes real clicks and downloads real generated PNG files, but the validated adapter loads an in-memory page and uses Blob links rather than navigating an HTTP website.

An ordinary localhost browser-navigation probe on October 23 was blocked with `net::ERR_BLOCKED_BY_ADMINISTRATOR`. No browser policy was changed. The studio's HTTP API is separately tested with a localhost HTTP client. UI rendering tests load the HTML directly; editable UI tests use an in-memory API stub, not a workaround for browser policy.

**Scheduling is local and process-bound:** the studio must stay open and the computer must stay awake. Schedules, drafts, history and audit records persist across restarts, but closing the process stops execution. There is no cloud runner, OS startup service, sleep/wake integration or phone execution engine.

The read-only HTML preview contains real reports from an injected-clock demonstration. Opening it starts no jobs. No runtime database or enabled live schedule is included in this package.

## What's new

| Capability | Implemented behavior |
|---|---|
| Persistent studio | SQLite queue, terminal run receipts, schedule definitions, drafts and audit events |
| Daily schedules | IANA timezone, fixed local time, next-run preview, fixed topic/count, pause/resume |
| Missed runs | Run the latest missed occurrence once, or skip beyond a configured grace period; no backlog replay |
| Daylight saving | Skip nonexistent wall times; use only the first occurrence of repeated times |
| Queue correctness | Unique scheduled occurrences, transactional claims, one active worker, stale queued-day replacement and expiry rechecks |
| Recovery | Interrupted RUNNING attempts become NEEDS_REVIEW; no automatic replay; explicit reconciliation leaves schedules paused |
| Teaching review | Import recorded fill/click events, explicitly bind the example topic, optionally select the authored fixture collection contract |
| Recipe changes | Immutable drafts, checksum-bound approval, revision checking, stale-draft rejection and paused schedules on activation |
| Safer verification | Changed files are not served as verified artifacts; private recorded steps stop compilation rather than being silently omitted |
| Studio interface | Responsive workspace, teaching review, schedules, persistent activity, audit history and evidence/limitations views |

The compiler still does **not** infer user intent, loops, conditions, alternatives or verification rules. Selecting the collection template is an explicit human authoring decision, not a learned behavior. Approval receipts are local checksums, not authenticated signatures.

## Install and launch

Use Python 3.10 or newer in a virtual environment. The supplied checks ran on Linux with Python 3.13.5 and Playwright 1.57.0. Windows and macOS are not qualified by this package.

```sh
cd handnavigate-lab
python -m venv .venv
# macOS / Linux:
source .venv/bin/activate
# Windows PowerShell instead:
# .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
python -m handnavigate studio
```

Open `http://127.0.0.1:4177` on the same computer. This development server is loopback-only. Do not expose it to a network. It is not a multi-user authenticated service.

`tzdata==2026.2` provides the tested fallback timezone database on systems without IANA data. Dependency versions describe the tested build, not a recommendation to ignore future security updates.

To use a different local port or persistent data directory:

```sh
python -m handnavigate studio --port 4180 --output my-local-runtime
```

The supplied source supports an HTTP fixture adapter via `--transport http`, but browser HTTP integration remains unvalidated in this environment. Do not change managed browser policy to bypass an administrator's restrictions.

## First useful end-to-end path

1. In **Studio**, keep the standard library scenario, enter a topic and count, inspect the active recipe, check the review box and run a rehearsal.
2. Wait for **VERIFIED**. Partial, halted and merely replayed runs do not establish schedule eligibility.
3. In **Schedules**, use the same topic, count, recipe and transport. Choose a timezone and local time, preview the next three occurrences, then explicitly authorize and save.
4. Leave the studio running. Review each attempted execution in **Activity**. A failed or partial scheduled run pauses that schedule.

A schedule is deliberately limited to fixed inputs that have a matching verified rehearsal in the studio's durable history. A standalone CLI run does not populate that studio history. The current product does not choose new topics automatically.

## Teach and review

Record your own actions on the owned fixture in a visible browser:

```sh
python -m handnavigate record --example-topic architecture
```

Fill Topic with that exact example, click Search, then close the browser tab. Do not click a download link in the narrow recorder. Import `runtime/recording/events.json` in **Teach & review**, identify the example value and the ready-state identifier, and create a draft.

For an explicitly labeled automated example instead:

```sh
python -m handnavigate record --automated-example
```

Checking **append the authored collection contract** adds the already-written local collection loop and PNG verifier. Without that contract a search recipe reports REPLAYED, not VERIFIED, and cannot qualify for recurring verified collection.

Inspect the generated steps and JSON. Approval activates exactly that draft checksum, cancels queued work and pauses schedules. A new verified rehearsal is required before resuming a schedule under the changed recipe. An already-running attempt retains its original immutable snapshot.

The advanced JSON editor supports only the existing constrained operation set. It does not execute arbitrary generated code.

## Interruption and cancellation

A normal Stop request is cooperative: the runner checks it between bounded operations. It is not an OS-level hard-kill watchdog.

After an unexpected process exit, the next exclusive studio owner marks unfinished RUNNING attempts NEEDS_REVIEW and pauses schedules. Inspect the saved reports and artifacts. The explicit reconciliation action abandons that uncertain attempt **without retrying it**. It does not undo external effects or prove that an effect never happened.

The older runner's `.execution.lock` may remain after a hard kill. This build deliberately does not delete it automatically. Confirm that no runner or browser worker is active and inspect the stored evidence before manually removing a stale lock. Do not remove a live worker's lock. Reconciliation does not silently remove that lock.

Queued work has not started. A stale queued scheduled day may be superseded by the latest due occurrence, or expire under the configured missed-run policy. Resuming an explicitly paused schedule begins from a future occurrence; paused days are not backfilled.

## Reproduce the checks

```sh
python run_tests.py
python build_v02_evidence.py
python check_ui.py
```

The first command runs the original regression tests plus scheduling, state-store, teaching, recovery and API/browser integration checks. The demonstration builder performs a real local rehearsal and scheduled collection with an **injected test clock**; it is not an overnight deployment. UI checks separately distinguish read-only rendering from editable controls backed by an in-memory stub.

`check_ui.py` writes screenshot/preview deliverables into `/mnt/data` when present, otherwise the repository's `deliverables` folder. `build_v02_evidence.py` uses the same output convention. No active runtime is distributed.

For focused tests:

```sh
python -m unittest discover -s tests -p test_v02.py -v
```

`research/TEST_REPORT.md` and `evidence/test-results.json` contain exact counts and qualification limits. A test can pass by safely halting. Method counts are not a production task-success rate.

## Important files

| Path | Purpose |
|---|---|
| `handnavigate/scheduling.py` | Pure timezone, daily occurrence and DST arithmetic |
| `handnavigate/store.py` | Transactional schedules, attempts, drafts, audit events and reconciliation |
| `handnavigate/controller.py` | Single local worker and startup recovery |
| `handnavigate/ownership.py` | Process-lifetime local ownership lock; not a distributed lease |
| `handnavigate/studio.py` | Loopback API, request checks and verified artifact retrieval |
| `handnavigate/runner.py` | Existing browser execution and checked download/checkpoint engine |
| `handnavigate/recorder.py` | Narrow recording compiler with explicit variable binding |
| `ui/index.html` | Functional local studio; no external frontend dependency |
| `ui/read-only-preview.html` | Portable non-executing snapshot from measured demo results |
| `tests/test_lab.py`, `tests/test_v02.py` | Original regression and v0.2 tests |
| `check_ui.py` | Separate rendered-interface checks and screenshots |
| `evidence/` | Raw reports, probe results, screenshots and actual sample files |
| `research/RELEASE_NOTES_V02.md` | Implemented changes and remaining product gates |
| `research/archive-v01/` | Historical documents, explicitly not current capability claims |

## Remaining product gates

The next gate is one **explicitly permitted real website and task**, with actual HTTP navigation/download qualification, authenticated-session handling and a suitable output verifier. General teaching, inferred loops, pagination, multi-tab/frame workflows, model-assisted authoring/repair, credential vaults, native desktop packaging, OS scheduling, cloud workers and mobile execution remain unimplemented.

The fixture supplies stable item IDs and expected hashes. Verification proves agreement with that synthetic contract, not independent image meaning, copyright permissions or internet search ranking. Cross-day deduplication is not implemented. File size is checked after browser transfer, not by a streaming download quota. Local advisory locks, SQLite transactions and an injected process-exit test do not establish exactly-once remote writes, resilience to arbitrary hardware failure or production security.
