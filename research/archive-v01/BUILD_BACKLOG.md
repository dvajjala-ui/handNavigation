# Build backlog and acceptance gates

Prepared 22 October 2026. "Implemented" means present in this lab, not production-qualified.

## Completed experimental scope

| ID | Work | Evidence or boundary |
|---|---|---|
| LAB-01 | Constrained recipe interpreter | Source and contract tests; no arbitrary-code opcode |
| LAB-02 | Exact semantic target resolution | Layout variation, alternative label, ambiguity, unknown-label cases |
| LAB-03 | Bounded collection and deduplication | Distinct duplicate-ID and duplicate-content checks |
| LAB-04 | Download effect verification | Real offline Blob downloads; size, PNG and hash fault checks |
| LAB-05 | Checkpointing and controlled resume | No repeated download clicks for the three reused files |
| LAB-06 | Narrow teaching pipeline | Actual browser fill/click recording; explicit parameter binding; review; replay |
| LAB-07 | Local studio | Source UI and loopback API; review/run/stop/resume paths |
| LAB-08 | Evidence package | Reproducible tests, receipts, teaching trace and transparent exclusions |

## P0 - Before representing this as real-site automation

### ENG-01 - Validate the HTTP adapter on a supported machine
**Acceptance:** All expected localhost HTTP cases execute in Chromium on a documented OS/browser combination. Verify actual HTTP downloads, redirects, content-disposition behavior, unavailable servers and response timeouts. Preserve failures. Do not reuse offline success as evidence for this gate.

### ENG-02 - Establish one permitted real task
**Acceptance:** Written scope identifies the site, account role, operator authority, allowed actions, prohibited actions, and desired artifact. Define the manual result oracle before automation. The task must not depend on bypassing a site's access controls or protections.

### ENG-03 - Build the real-site adapter
**Acceptance:** Stable record identity, input mapping, list readiness, candidate ordering, download/source association and shortfall rules are explicitly documented. No fixture-specific `data-asset-id` or provided hash is assumed to exist on the real site.

### ENG-04 - Replace demonstration-only file verification
**Acceptance:** Supported file formats are identified safely; source and task metadata are associated with the artifact. Invalid, incorrect, truncated, oversized and duplicate files are distinguishable. Network transfer quotas and parser resource limits are enforced, not just checked after transfer.

### ENG-05 - Hard watchdog and crash reconciliation
**Acceptance:** Kill the browser and worker at defined points before/after file rename and database commit. A restarted worker either reuses a verified artifact, safely reconciles it, or asks for intervention. No stale lock is deleted automatically without a supported ownership/lease policy.

### ENG-06 - Runtime containment and privacy review
**Acceptance:** OS/container network egress policy, output-directory confinement, credential isolation, log redaction, screenshot retention, dependency provenance and update strategy are documented and tested. Do not treat browser interception as an OS sandbox.

## P1 - Make teaching the differentiated experience

### TEACH-01 - Explicit scope and recording controls
**Acceptance:** A user can start/pause/discard one-tab recording and see its boundaries. Selected text, credentials, screenshots and URLs have a documented collection policy. No background all-desktop capture by default.

### TEACH-02 - Rich action capture
**Acceptance:** Navigation, fill, click, select, keyboard submit, downloads and tab changes have typed event representations with source context. Unsupported actions cause a visible warning instead of being omitted.

### TEACH-03 - Structured ambiguity resolution
**Acceptance:** The product distinguishes example values, dynamic variables, ordering, fixed items, loops and stopping criteria. Unresolved choices are surfaced in plain language. The user can correct them without editing code.

### TEACH-04 - Candidate workflow compiler
**Acceptance:** On held-out tasks, compiler drafts can be evaluated against an engineer-authored reference. All generated actions pass the same schema and policy checks. Inferred behavior is labelled; no direct execution of arbitrary model-written code.

### TEACH-05 - Review and admission
**Acceptance:** The review screen names allowed origins, accounts, output locations, consequential actions, variables, loops, result checks and uncertainty policies. Approval binds an exact version. Production approval is authenticated; a local checksum is insufficient.

### TEACH-06 - Corrections become explicit branches
**Acceptance:** A correction demonstrates a trigger condition and alternative path. Regression cases for the original branch still pass. Repeated blind fallback clicking is not accepted as learning.

## P1 - Recurring operations

### OPS-01 - Durable local scheduler
**Acceptance:** Timezone, missed-run policy, sleeping/offline runner behavior, overlap, maximum duration and notification are explicit. Restarting the app does not lose or duplicate admitted logical jobs.

### OPS-02 - Authentication lifecycle
**Acceptance:** Session expiry pauses before unauthorized action; credentials remain outside workflow exports; the user can reauthenticate and resume appropriately. MFA and CAPTCHA are human handoff conditions, not bypass targets.

### OPS-03 - Run center and exception inbox
**Acceptance:** Completed, partial, halted, uncertain and cancelled outcomes remain separate. Show the evidence and next required human action. The operator can distinguish a safe stop from a completed task.

### OPS-04 - Local output and optional sync
**Acceptance:** Files are available offline after download. Sync status is separate from collection status. A cloud collection is not reported as available on a phone until the phone has actually received it.

### OPS-05 - Versioned deployment and rollback
**Acceptance:** The deployed recipe, adapter, verifier, runtime and policy versions are recorded. A version rollback affects future execution; it must not be described as undoing prior external actions.

## P2 - Controlled intelligence

### AI-01 - Authoring assistance
**Acceptance:** Compare stronger and cheaper models on the same draft-generation tasks. Measure valid plans, review effort, variable accuracy and cost. Do not select a model solely by token price.

### AI-02 - Repair proposals
**Acceptance:** Failure evidence is sanitized; proposed changes are reviewable; permissions do not expand silently; regression tests run before readmission. Strict mode cannot invoke a provider.

### AI-03 - Usage accounting
**Acceptance:** Distinguish zero-model execution, authoring inference, failed repair attempts and approved repair inference. Enforce both call and spend limits. The lab's constant zero field is replaced by real accounting if models are added.

## P2 - Distribution and expansion

### DIST-01 - Supported desktop package
**Acceptance:** Clean install/uninstall, signed updates, browser dependency management, OS permissions, wake/sleep behavior and secrets storage are validated independently on each supported OS.

### DIST-02 - Mobile controller
**Acceptance:** Inspect outcomes, approve scoped actions and access synced artifacts from a phone. Do not advertise arbitrary on-device control of other apps.

### DIST-03 - Optional cloud runner
**Acceptance:** Tenant isolation, egress control, browser leases, encrypted session state, artifact access, usage caps and worker recovery have production tests. Local admission is not automatically valid in the cloud environment.

## Explicitly out of the first release

Universal desktop/remote-desktop automation, unrestricted social engagement, autonomous payments, a public workflow marketplace, foundation-model training, arbitrary browser profiles, undocumented API replay, and anti-detection features.

## Architecture evaluation rather than premature commitment

Before choosing a production engine, run the same permitted tasks through (a) a thin custom Playwright interpreter, (b) an evaluated OpenAdapt integration, and (c) another suitable workflow framework. Use the same output oracle, fault cases and cost accounting. Published capability lists are discovery evidence, not substitutes for this comparison.

The current lab is an original, minimal mechanism experiment. It does not embed either competitor's source code. A legal/dependency review is still required before bringing any third-party project into a distributed commercial product.
