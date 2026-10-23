# TruStudio capture review and HandNavigate course correction

## Direct answer

The previously delivered HandNavigate v0.4 was not a completed general real-website automation product. Its main run/record/replay paths and teaching UI were tied to owned fixtures. It had an experimental authenticated export adapter, but no completed general live-site AI control loop. The build sequence put too much supporting infrastructure ahead of the core feature.

The supplied `trustudio_capture.zip` is directly relevant. It contains a real Playwright browser capture tool, not merely a website mockup. The archive contains the source tool and configuration, but no saved `capture.json`, screenshots, or completed site-session evidence. This review is a source inspection, not a claim that its live capture was executed here.

## Immediate credential issue

The archive's `.env` contains a nonempty credential-like `GROQ_API_KEY`. Validity was not checked. The key was not used, printed, sent to a provider, or copied into the deliverable. Rotate/revoke it and use a fresh local key. `.gitignore` does not remove secrets from a ZIP that already contains them.

Raw HAR files, authenticated profiles, screenshots and captured HTML also need to be treated as private, even when derived JSON logs redact common secrets.

## What the supplied tool actually does

The source package is `trustudio-capture-core-v4`, using Node.js and Playwright plus a Groq HTTP adapter.

1. `login` opens a visible persistent Chromium profile and lets the person sign in.
2. `capture` opens the supplied real URL in that browser profile.
3. Injected listeners capture clicks, input/change events and feature/checkpoint hotkeys.
4. State collection saves viewport and full-page screenshots, rendered HTML and computed styles/control summaries.
5. Request listeners collect network evidence and downloadable frontend assets, including exposed source maps.
6. Deterministic analysis builds flow/state/API summaries and a local report.
7. Groq analyzes compact per-feature evidence and produces an application/implementation map.

Screenshots are collected at states, including interactions and manual checkpoints. This is not a fixed-rate video recorder. The distinction between observed, inferred and unknown behavior is useful and should survive integration.

### What it does not do

The model is a post-capture analyst, not an online browser operator. `groqStructured` receives messages and a JSON output schema, but no browser tools. The analyzer calls it after capture. There is no model-request -> browser-action -> new-observation loop in this source.

The current analyzer sends compact text/JSON evidence. It does not attach the saved screenshots as image inputs. Keeping a screenshot on disk is not the same as the model seeing it.

It does not compile an approved parameterized executable recipe, define dependable task-level success checks, or replay a demonstration autonomously. Inspecting frontend JS/source maps does not reveal unavailable server-side source code.

## Code-grounded findings

All locations below refer to the uploaded tool, not the new HandNavigate module.

| Finding | Source | Consequence / recommended change |
| --- | --- | --- |
| Real URL and persistent browser profile | `src/index.mjs`, lines 95-107 and 493-500 | Reuse this approach for a dedicated, user-visible browser session. It already demonstrates the right connection mechanism in code. |
| One global input debounce timer | `src/index.mjs`, lines 175-186 | Editing another field can cancel the pending event for the previous field. Use per-element timers and flush before clicks/navigation. |
| Input values truncated to 220 characters | `src/index.mjs`, line 181 | Useful for reports, but not a lossless replay format. Preserve bounded full values or mark truncation as an import blocker. |
| Checkbox/radio value is not checked state | `src/index.mjs`, lines 176-186 | A value such as `on` cannot tell whether the user checked or unchecked a control. Record a boolean. |
| Before-state is a cached latest state | `src/index.mjs`, lines 502, 521, 538-540 | Rapid events can be correlated with stale state. `latestState` is also global across pages. Treat it as a previous checkpoint, not guaranteed immediate pre-action evidence. |
| Queue-processing time replaces event time | `src/index.mjs`, line 539 | API timing correlation can drift behind the human event. Keep event and processing timestamps separate; timing is not proof of causality. |
| Screenshot failures are swallowed | `src/index.mjs`, lines 516-521 | The state can name a screenshot that was not saved. Record explicit missing-evidence status. |
| Wrong test-attribute name in design selector fallback | `src/index.mjs`, line 239 | A `data-test` or `data-cy` value is emitted as a `data-testid` selector. Preserve the original attribute name. The separate interaction selector routine does this differently. |
| Full embedded HAR recording | `src/index.mjs`, line 500 | Derived redaction does not sanitize the raw HAR. Keep it opt-in and local; do not send it by default to AI. |
| No image input in AI analysis | `src/ai/analyzer.mjs`, lines 28-105, 185-188 and 245-248 | The model sees structured summaries, not the saved screenshots. Add explicitly consented vision only where useful and supported. |
| Local review server uses a string prefix path check | `src/index.mjs`, line 601 | `file.startsWith(root)` does not enforce directory ancestry for sibling names sharing the prefix. Use a resolved relative-path boundary check, reject symlink escapes, and serve captured HTML as inert content rather than trusted executable application code. |

The path-check issue above was identified statically. No private sibling files were accessed and no exploit was run.

## What should be reused

Reuse the explicit flow boundaries, interaction/state IDs, dedicated login profile, state snapshots, event/network timeline, per-feature evidence compaction, and observed/inferred/unknown discipline. These support explaining a workflow and diagnosing failures.

Do not make downloading every JS bundle and stylesheet a prerequisite for automation. Those assets can help diagnose a difficult site or understand a UI, but a browser can operate the rendered application using its current controls and state. Playwright's semantic locators and accessibility-oriented tools are a more direct operational interface.

## Correct product architecture

```
User instruction or demonstration
              |
Real browser session + bounded observation
              |
AI proposes ONE action, or a reviewed recipe supplies it
              |
Runtime checks scope, target, budget and approval
              |
Playwright executes on the real page
              |
Fresh observation + explicit outcome checks
              |
Evidence-linked draft -> human review -> deterministic replay
```

The model cannot grant itself new websites, change success criteria, or execute arbitrary generated JavaScript. A website's content is data, not an authority over the user's task.

We should reuse Playwright (or its MCP/CLI interface where suitable) as browser infrastructure. HandNavigate's product layer is demonstration-to-workflow conversion, variable/branch review, verification, controlled recovery and recurring operations. Reimplementing a browser or reverse-engineering the entire website is not the product.

## What was added in this development build

`handnavigate/live/` is integrated through `python -m handnavigate live ...`.

- `browser.py`: real-URL launch, dedicated optional browser profiles, semantic control snapshots, local screenshots, bounded action execution, network metadata and result checks.
- `agent.py`: explicit-opt-in Groq local-tool loop; optional screenshot sending for a compatible vision model; one supervised action per model turn; actual actions exported as a draft.
- `recording.py`: main-frame human recording, per-field debounce, explicit checkbox states, and password-control rejection. Human-action observations are honestly labeled checkpoints.
- `workflows.py`: conservative TruStudio `capture.json` import and model-free deterministic replay.
- `contracts.py`: origin/method/action constraints, typed parameter references, completion checks, exact workflow/input review receipts.
- `cli.py`: inspect, record, agent, import-trustudio, approve, replay and environment-doctor commands.

There is no fixture fallback in the live CLI. The existing studio UI is still the earlier practice interface; the new core has not been wired into that UI or its scheduler.

## Capability and evidence boundaries

The new code includes the missing real-site execution path. That is a code delivery, not a claim of proven end-to-end real-site automation.

The new component suite passed 42 tests. It exercised real Chromium against explicitly offline test documents, including a scripted provider that tested the tool protocol. Real Groq requests: zero. A normal live-URL probe was blocked by administrator policy and returned `ENVIRONMENT_BLOCKED`; no browser policy was changed and no alternate transport substituted.

A complete rerun of the older regression suite did not finish within the execution limit. The log has 19 passed tests and one skipped test before termination during the next test. No full-app regression pass is claimed.

## What is still missing before the core can be called delivered

The acceptance gate is not another UI screen. It is a supervised, authorized external-site task that completes with real browser navigation and a real model when needed, produces evidence and a reviewed recipe, then repeats with changed inputs and zero provider calls.

The current development module is deliberately limited to main-frame semantic controls. It does not support general iframe control, canvas coordinate interaction, multiple tabs, drag-and-drop, arbitrary uploads, automatic branch/loop synthesis, safe autonomous login, OS keychain integration, cloud execution, or live-workflow scheduling. Screenshot sending is wired but has not been tested with a live vision model. It is not hardened for malicious websites or unattended consequential actions.

The uploaded capture tool is a useful foundation for this direction. It is not, by itself, an automation agent; the missing component is an executable, observable control loop and its workflow compiler.

## Primary documentation checked

- Playwright locators: https://playwright.dev/docs/locators
- Playwright MCP: https://playwright.dev/mcp/introduction
- Playwright CLI: https://playwright.dev/agent-cli/quick-start
- Playwright trace snapshots: https://playwright.dev/python/docs/trace-viewer
- Groq local tool calling: https://console.groq.com/docs/tool-use/local-tool-calling
- OpenAI computer use: https://developers.openai.com/api/docs/guides/tools-computer-use

These sources establish the browser/tool mechanisms, not the reliability of this development build.
