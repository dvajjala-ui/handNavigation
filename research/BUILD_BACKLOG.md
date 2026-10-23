# v0.4 status and next acceptance gates

Completed in v0.4: owned-form interactive recording; typed variable/constant binding; explicitly selected output checks; immutable reviewed recipes; plan-bound input batches; per-row evidence; single-runner coordination; request deduplication; interrupted-work review; recipe import/export; desktop/mobile-width teaching workspace.

Not completed: arbitrary-site teaching, automatic intent/loop inference, guided-batch scheduling/resume, authenticated browser qualification, unattended secret lifecycle, native packaging and real-user usability validation.

**Next acceptance gate:** run the strict qualification suite on a policy-permitted machine, qualify one explicitly authorized site and objective task, and only then generalize the guided recorder to that site's reviewed controls. Keep the model-free runner and explicit result checks. Do not treat an owned practice-page success as proof of real-site support.

**Teaching validation:** observe a real person teaching and correcting the supported task; measure teaching time, corrections, comprehension of variables and safe-halt recovery. Automated traces are not evidence for usability.

**Operational work:** add a hard watchdog and safe worker termination, defined retention/deletion, OS-backed credential lifecycle, authenticated sessions and external-outcome reconciliation before recurring site jobs.

---

## Retained detailed backlog from v0.3

# Next acceptance gates after v0.3

## P0: qualify the implemented browser path

Run the supplied full browser sign-in/capture/separate-context export test on a machine whose ordinary browser policy permits localhost navigation. The strict CI flag must fail rather than skip when that gate cannot run. Preserve traces only for the owned synthetic portal; never enable session-bearing debug artifacts by default for real users.

Acceptance: actual browser login, restored session in a new context, exact account match, search, genuine HTTP download, verified CSV, account mismatch rejection, server expiry rejection, redirect rejection and no unauthorized write. Neither API-only checks nor mocks satisfy this gate. The GitHub workflow is configured but was not executed in this delivery.

## P0: one explicitly authorized real-site adapter

Choose one recurring read/export task with an objectively testable result and permission to automate. Document the account scope, route inventory, login resources, download semantics and success contract. Do not assume a site's manual button or a user's checkbox grants automation rights.

Acceptance: supervised trial with real HTTP/browser interaction, output validation against known expected records, explicit session expiry recovery, data minimization and maintainable supported selectors. No universal-site marketing claim.

## P0: strengthen runtime containment

Add OS-level network restrictions, download transfer limits and a hard process-lifetime watchdog. Account for DNS resolution, redirects, popup/worker behavior and every download route. Implement native secret-store integration; do not place an unlock key next to ciphertext merely to enable unattended execution.

Acceptance: unauthorized destinations cannot receive traffic outside application callbacks; oversized or stalled transfers are stopped within a tested resource budget; receipts never include session secrets.

## P1: authenticated recurring jobs

Integrate the experimental lane with the scheduler only after browser qualification, OS key storage and interruption handling. Include account identity in the execution contract, require matching rehearsals, stop on session expiry and invalidate queued work on changed permissions. Distinguish local forget, future-run revocation, active-run cancellation and remote logout.

Acceptance: no hidden unlock prompt in an unattended worker, no plaintext credential files, no retry of uncertain remote actions, and clear operator intervention.

## P1: teaching generalization

Move beyond imported fill/click traces toward interactive recording on the single supported site. Ask which values vary, what establishes item identity, what permits a loop to stop, and how a person knows the result is right. Keep the output program inspectable and versioned.

Acceptance: a design partner can teach the supported task without a developer editing every recipe. An explicit plan/verification contract is produced; unrecognized steps are rejected, not omitted.

## P1: desktop packaging and operation

After platform tests run, package a local desktop shell/runner with clear startup, sleep/wake and pause behavior. Add signed distribution and update handling before claiming a Windows/macOS application. Preserve a mobile controller without implying arbitrary phone-app automation.

## P2: optional AI authoring and reviewed repair

Model calls may help author or diagnose a draft; they must not expand execution permissions. Keep a technically enforced no-model replay mode, reviewed repairs and measured cost per verified result. Do not train a model merely to reproduce already-defined clicks.

## Measurements

Track verified task completion, silent incorrect outcomes, interventions per hundred runs, maintenance time, teaching time, zero-model-run share and cost per verified outcome. Unit-test counts, component checks and safely halted runs must not be presented as a production success percentage.
