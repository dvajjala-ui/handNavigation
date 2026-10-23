# HandNavigate engineering backlog after v0.2

## Completed in this package

Daily timezone-aware local scheduling; persisted attempts and audit history; missed-run coalescing/skipping; queued-occurrence expiry; transactional single claims; process ownership; interrupted-attempt reconciliation without retry; imported recording review; explicit collection-template selection; immutable recipe drafts; stale-review rejection; changed-artifact rejection; responsive studio views; regression, crash-injection, API and rendered-UI tests.

## Gate A: one permitted HTTP website and task -- still open

Acceptance: actual navigation, controls, authentication boundaries, HTTP downloads and output verification on an authorized source. Record site permission/scope; do not assume that a visible download button authorizes automation. Verify final outputs, shortfall behavior, changed controls and interrupted downloads. The build environment's managed-browser restriction is not to be bypassed. Run this qualification in an appropriately permitted development environment.

## Gate B: authenticated sessions and private data -- not implemented

Acceptance: credential and session material separated from recipes; appropriate OS secret storage; sign-in/MFA handoff; expired-session behavior; screenshot/trace consent and redaction; retention controls. No secrets in Git, telemetry, recordings, previews or shareable workflow files. Do not advertise general account automation before this gate.

## Gate C: teach a useful workflow without developer rewriting -- partial

Acceptance: observed human demonstrations, explicit variable/loop/condition correction, support for the selected site surfaces, and a clear result contract. Measure teaching completion, correction effort and silent wrong outcomes. The current imported fill/click compiler plus authored collection template is a narrow engineering step, not completion of this gate.

## Gate D: dependable desktop operation -- partial

Acceptance: Windows and macOS qualification, native packaging, signed installers, validated cancellation/teardown, process watchdogs, recovery across actual browser crashes and power loss, OS startup integration, documented sleep/wake behavior, schedule editing/deletion and bounded retention. Current scheduling requires an open studio and awake computer.

## Gate E: optional AI authoring and reviewed repair -- not implemented

Acceptance: provider interface outside the deterministic execution path; explicit budget and permission boundaries; schema-constrained output; proposal diffs; reviewed repairs; measurable cost/accuracy; tests proving strict no-model execution does not invoke providers. Do not train a custom foundation model before the narrow workflow and data case justify it.

## Postpone

Universal desktop control, arbitrary mobile-app execution, payments, social engagement bots, automatic CAPTCHA bypass, unlimited cloud compute, a public workflow marketplace and claims of autonomous operation on every website.

## Metrics for a real pilot

Verified task completion; silent incorrect outcomes; interventions per 100 runs; percentage of runs with zero model calls; teaching time; maintenance minutes per workflow; credential/session interruption rate; cost per verified result; time to diagnose and repair a change. Synthetic test counts are not substitutes for these pilot measurements.
