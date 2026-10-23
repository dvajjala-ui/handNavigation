# HandNavigate v0.4 security boundaries

The v0.3 connection/session boundaries remain in `SECURITY_MODEL_V03.md`. This document describes the additional guided-teaching path. Neither document is a security certification.

## Explicitly constrained execution

Guided recipes are bound to the shipped owned-form adapter and its checksum. Their strict schema permits only a fixed set of fill, select, checkbox-state and preview-click operations. No arbitrary URL, selector, JavaScript, shell command, expression evaluator, file upload, credential input, or external write is exposed by this recipe format.

The owned form is loaded into an in-memory browser document. Browser requests and WebSockets are denied at the application layer, and unexpected navigation, popups, dialogs and downloads halt the run. This is not DNS-aware network isolation or an operating-system sandbox. It does not qualify the separate authenticated browser adapter, and it is not a workaround for managed browser policy.

## Recording and data

Recording requires an explicit start and stays inside the practice form. Password controls, private-marked ancestors and recognized credential/payment autocomplete markers produce blocked-event metadata rather than captured values. Unknown controls and unsupported actions are rejected rather than silently omitted.

A normal text field can still contain sensitive information that the app cannot recognize. Do not enter secrets. The persistent lesson database and verified JSON artifacts are not encrypted. The encrypted session vault from v0.3 is separate; it is not connected to this recorder or guided-batch execution. Local-machine compromise is out of scope.

## Approvals, input review and imports

Approval binds the exact recipe checksum. Input plans bind the recipe, adapter and concrete ordered rows. The server revalidates both before starting. Inputs use strict types, safe row identifiers and explicit size/repeat bounds. An import always loses approval. Client controls are convenience gates; the server independently enforces review.

A new request identifier is required for each intentional execution plan. Reusing the same request identifier and unchanged plan returns the existing run. Reusing it with a changed plan is rejected. The interface prevents a second click from generating a new execution for an already accepted plan. Failure to create a secure request identifier keeps execution disabled.

These protections are local acknowledgements and request deduplication, not authenticated human signatures, remote exactly-once guarantees, or website permission.

## Runtime lifecycle

The original scheduler and teaching service share a process-local execution lock. The studio owns the existing runtime-directory process lock. SQLite records the run intent before starting the worker and saves progress after each verified row. Unfinished or uncertain work requires review after restart and is never automatically retried.

A bounded cooperative cancellation path and browser-operation timeouts are implemented. There is no hard watchdog for a stuck browser process. An interrupted guided batch cannot be resumed automatically in this release. Acknowledgement does not undo an effect.

## Output evidence

The runner compares three actual visible output values with independently resolved recipe/input expectations. The owned app's success message is insufficient. Wrong or missing output halts later rows. Artifacts are created without overwriting an existing file and are hash-checked when served.

The evidence establishes correctness only for the owned form and selected contract. It does not establish that a remote service persisted a record, that arbitrary downloaded content is correct, or that an adversarial page is safe. There are no irreversible remote actions in the guided fixture.

## Local service and preview

The service remains loopback-only with host, origin and per-session-token checks on mutations. It is not an authenticated multi-user server and must not be exposed to a LAN or public internet. UI values are escaped before rendering. Strict HTML security headers remain in place on served pages.

The separate evidence preview contains no active session, cookies, passphrase, enabled job database or API connection. Its effect controls are disabled. It issues no network requests in the rendered checks. Mobile screenshots establish responsive layout only, not mobile device control.

## Remaining release gates

Ordinary browser HTTP navigation is still blocked by administrator policy in this build environment. No policy was changed. The owned HTTP-client component checks do not qualify browser HTTP execution. No third-party site, real customer account, native Windows/macOS installer, OS keychain, authenticated schedule, cloud worker, or cross-device session system has been qualified.

The current Linux test results and checked scenarios are engineering evidence, not penetration testing, a production SLA, or cross-platform certification.
