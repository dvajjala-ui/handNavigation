# Guided teaching: user and developer guide

## What this release actually teaches

HandNavigate v0.4 records interactions in its **owned practice form**: a Topic text field, a Layout dropdown, an Include captions checkbox, and a Prepare preview button. It compiles these actions into a typed, reviewable recipe. You decide which values are variables and which remain fixed. You explicitly select the result checks and maximum number of input rows.

This is demonstration-to-program compilation, not foundation-model training. It is not yet an arbitrary-website recorder, browser extension, desktop accessibility recorder, or an authenticated-site workflow. It neither learns an unobserved intent nor silently invents recovery branches.

## Start the local app

From the extracted `handnavigate-lab` directory, create and activate a virtual environment as described in the README, then:

```sh
python -m pip install -r requirements.txt
python -m playwright install chromium
python -m handnavigate studio
```

Open the same-computer address:

```text
http://127.0.0.1:4177/teach
```

The main studio also links to Guided teaching. The HTML preview distributed separately is read-only: it cannot record, approve, sign in, schedule, or start a runner.

## 1. Demonstrate

Acknowledge the recording scope and choose **Start recording**. Enter a topic, select a layout, set the checkbox, and click **Prepare preview**. Stop recording.

Only events inside the practice form are captured. The app's own navigation, approvals and input-plan editor are outside that recording root. Text-input events are coalesced only while they are adjacent edits to the same control; a click is a sequence boundary.

A control that keeps its initial value may emit no change event. Use **Capture current inputs** before Prepare preview to explicitly include unchanged defaults. This also records an unchecked checkbox as `false`, rather than guessing from its omission.

A recording must contain all three fields and end with one Prepare preview click. Private controls, unknown controls and unsupported actions invalidate compilation; they are not dropped from an otherwise plausible recipe. This is an intentionally narrow safe subset.

**Load sample trace** loads a labeled synthetic example. It is not represented as your own demonstration. Automated tests also drive the recorder; their evidence is not a human usability study.

## 2. Bind and review

For each field, select **Variable** or **Keep fixed**. Variable names must be distinct and match the permitted identifier format. Fixed values retain the recorded constants. There is no executable expression syntax.

Choose a maximum batch size from 1 to 20. Select the explicit verification contract: displayed topic, layout and captions must match the final reviewed inputs for each row. Stop-on-error is mandatory.

Compile a draft. Inspect its ordered actions, variable definitions, expected outputs, repeat bound and checksum before approving it. Approval covers that exact recipe; it is a local checksum acknowledgement, not a signature or evidence of permission from a website.

Recipes are immutable records. Compile or import a new recipe rather than modifying an approved object in place. Imports always create an unapproved draft. Export includes the recipe, including any recorded constants, but no approval, cookies, session state, or vault keys. Never put secrets in a topic or exported constant; field redaction is not general data-loss prevention.

## 3. Review the actual execution plan

Choose or enter input rows. Each row needs a unique `row_id`; values must match the reviewed string, enum and boolean types. `false` is not interchangeable with the string `"false"`.

**Use 3 demo rows** inserts labeled demonstration values. Review those inputs before execution. A recipe with fixed fields does not need corresponding variables in each row.

Preview the plan. It shows row count, action count, result-check count, and every expected output. Its checksum binds the recipe, adapter, input values and ordering. Changing an input invalidates the visible plan review; the server also rejects an outdated plan.

After acknowledging the plan, choose **Run verified rehearsal**. A request identifier prevents the same accepted HTTP request from creating a second batch. A newly reviewed plan may intentionally start a new batch. This is local request deduplication, not exactly-once execution on arbitrary remote systems.

## 4. Inspect evidence

The runner opens a fresh owned form per row, uses actual Chromium interactions, and checks the three displayed output values. It does not accept a success banner as evidence that the requested values were used.

A verified row produces a local JSON artifact containing the expected and observed values, recipe checksum, run and row identities, timestamp, and scope. The API rechecks the artifact hash before serving it. Tampered files are not silently shown as verified.

The batch stops on wrong or missing output, ambiguous controls, an unexpected dialog/effect, a time-budget failure, or cancellation. Already verified rows remain available. A halted batch is not a completed task.

The local scheduler and teaching rehearsal share one execution slot. Guided lessons are not connected to daily scheduling. Existing image schedules remain available and run only while the process is open and the computer is awake.

## Stop, interruption and recovery

Stop is cooperative at step boundaries, not an operating-system hard kill. Individual browser operations have timeouts, and the owned batch has a 90-second budget checked between operations. There is no hard-kill watchdog for a wedged browser process.

Unfinished work found after a restart is marked `NEEDS_REVIEW`. Review the saved evidence and acknowledge it without retry. Acknowledgement does not undo effects and does not automatically restart unfinished rows. This release does not implement resume for guided batches; the established image runner's checkpoint mechanism is separate.

## Files and architecture

| File | Responsibility |
|---|---|
| `handnavigate/teaching.py` | Strict recording, binding, recipe, row and plan contracts |
| `handnavigate/assets/teaching_recorder.js` | Explicitly started, root-scoped browser event capture |
| `handnavigate/assets/owned_form.*` | Owned practice app, separate from the expected-output logic |
| `handnavigate/teaching_runner.py` | Actual browser replay, result checking and per-row evidence |
| `handnavigate/teaching_service.py` | Persistent drafts, approvals, run intents, deduplication and recovery |
| `ui/teach.html`, `ui/teach.js` | Three-stage recording, review and rehearsal workspace |
| `tests/test_v04.py` | Contract, browser, storage and actual localhost API checks |
| `check_ui_v04.py` | Rendered previews and explicitly stubbed interactive UI checks |

The existing schema-1 image workflow is unchanged. Guided lessons use a separate schema-2 format and cannot be silently substituted into image schedules.

## Sources consulted for the implementation

Checked 23 October 2026. Documentation informed action and assertion usage; it is not evidence that this product works on an external site.

- Playwright Python actions: https://playwright.dev/python/docs/input
- Playwright Python locators: https://playwright.dev/python/docs/locators
- Playwright Python assertions: https://playwright.dev/python/docs/test-assertions

Actual version and platform measurements are in `evidence/test-results.json`. Dependencies remain pinned to the supplied build versions; they are not represented as the latest releases.
