# HandNavigate v0.4 - Guided teaching and verified batches

Built 23 October 2026 from the supplied v0.3 source. This is a local engineering release, not a deployed app or native installer. No GitHub changes were made.

## What is new

**Interactive teaching.** The new `/teach` workspace records actual text, dropdown, checkbox and preview-button interactions inside the owned practice form. Start/stop is explicit. Unchanged defaults can be captured explicitly. Private or unsupported actions block compilation instead of disappearing from the sequence.

**Variables and fixed values.** The reviewer chooses typed variables or recorded constants, a maximum row count, and the exact result-verification contract. The compiler does not infer intent or train a model. Imported recipes always require fresh approval; export includes no approval or session state.

**Review the concrete plan.** Recipe approval is separate from reviewing the actual input rows. Changing a value invalidates the plan. The server binds each run to the exact recipe, adapter, ordered rows and plan checksum.

**Bounded replay.** A batch can contain at most 20 rows. Each runs in a fresh owned page. The runner uses actual Chromium actions and checks all three output values. Verified rows produce hash-checked JSON receipts. A wrong result, ambiguous control or unexpected effect halts later work.

**Operational safeguards.** The scheduler and teaching service share one execution slot. Duplicate request IDs return the existing execution instead of creating another. Cancellation preserves completed rows. Interrupted or uncertain work requires review and is never retried automatically. Guided-batch scheduling and resume are not implemented.

**Three-stage interface.** Demonstrate, Bind & review, and Rehearse have separate screens. Variable controls, explicit review checkboxes, plan previews, verified receipts and failure history are wired to the local API. The separate HTML preview is read-only.

## Evidence

- Combined regression suite: **172 passed, 0 failures, 0 errors, 2 explicit skips** across 174 test methods.
- New v0.4 tests: **41** contract, recorder, browser, persistence and API methods.
- Separate rendered-interface checks: **83 passed, 0 failed**; no recorded JavaScript runtime errors.
- The included demonstration records four actual browser events, compiles explicit bindings, and verifies three rows with 12 actions and nine output checks. A separate deliberate wrong-topic run halts and stays visible in history.
- A separate automated test verifies 20 rows, 80 browser actions and 60 output checks with zero model calls. This is not a multi-day reliability study.
- The existing image demo still produces ten verified PNG files. Its scheduling clock is injected, not an overnight trial.

The doctor status is **COMPONENTS_PASS_BROWSER_BLOCKED**. Browser HTTP navigation remains blocked by administrator policy here; no policy was changed. Actual HTTP-client component checks and actual local API requests are not browser-HTTP qualification.

## Run it

After installing the pinned dependencies and Chromium as described in README:

```sh
python -m handnavigate studio
```

Open `http://127.0.0.1:4177/teach` on the same computer. Recording is limited to the owned form. No API key is needed for the current runner.

## Not implemented or not qualified

Arbitrary website recording, Pinterest automation, real customer accounts, automatic intent/loop inference, irreversible remote actions, guided-batch scheduling/resume, authenticated unattended jobs, native installers, native mobile control and cloud execution remain outside this release. Windows/macOS execution has not been tested here. The supplied cross-platform CI configuration has not run on GitHub.

The next external-site gate remains a fully qualified, explicitly authorized browser workflow. The teaching improvements do not waive that requirement.
