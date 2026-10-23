# Architecture and trust boundaries

**Status:** The sections labelled implemented describe the supplied prototype. The production design is proposed, not built.

## 1. Implemented lab

The lab uses Python, Playwright, SQLite and a small loopback HTTP server. This is a validation choice based on the available execution environment, not a decision that the final consumer product must be written in Python.

```text
Local studio or CLI
    -> exact recipe review checksum
    -> constrained recipe validator
    -> deterministic runner
        -> exact semantic target resolver
        -> Playwright action or bounded collection
        -> PNG/file-effect verifier
        -> SQLite verified-item checkpoint
    -> outcome receipt + local artifacts
```

Two fixture adapters exist. `memory` loads owned HTML into Chromium and uses locally constructed Blob URLs. `http` navigates the owned localhost server. Adapter selection is explicit and recorded. A failed HTTP run never silently becomes an offline test.

The shipped action vocabulary is `fill`, `click`, `wait`, and one bounded `collect` operation. Recipe JSON cannot supply JavaScript, Python, a model endpoint, or arbitrary network destinations. Exact role/name, exact label, and test-ID strategies are accepted; raw CSS execution is not user-configurable in this format. The collection adapter itself uses fixed, authored structural attributes of the fixture.

## 2. Proposed production split

A TypeScript/Electron desktop client remains a candidate, alongside a browser extension recorder. Keep the workflow representation and artifact contracts language-neutral so the experiment can be ported or wrapped without preserving every prototype implementation choice.

The controller manages teaching, review, admission, schedules and run history. The runner performs admitted work. A phone can be a controller without being the execution environment. Cloud execution should reuse the same contracts but have a separate admission profile for sessions, network access, file handling and tenancy.

A production scheduler needs a durable queue, leases, heartbeat, missed-run policy and a process watchdog. The studio's background worker thread is an in-process development convenience, not a scheduler or durable queue.

## 3. Recording and compilation boundary

Treat recordings as sensitive evidence, not executable authority. A recording contains actions, observations, selected scope and timing. A candidate compiler derives a workflow draft and lists unresolved assumptions.

An AI authoring service, if added, should emit constrained candidate actions and proposed selectors. It must not emit unrestricted code that the trusted runner executes. Validate schema, permissions, origins, parameter types, loop bounds and output destinations before any rehearsal.

Keep inferred behavior distinguishable from observed behavior. A single click cannot establish whether the user intended the first result, the cheapest result, the newest result, or a particular named item.

The current compiler only replaces a reviewer-identified fill value with `{{topic}}` and adds an explicitly supplied result-state check. It does not infer loops, branches, success oracles or permissions.

## 4. Locator resolution

Production resolution should use stable user-facing semantics and scoped identity before geometry. Match within the correct account, record, dialog or item. Re-resolve targets at execution time, but verify that the logical target remains the approved one.

The prototype rejects multiple visible matches instead of selecting the first. An alternative label is a separate preapproved exact strategy. It is not fuzzy self-healing. Identical duplicate collection items are deduplicated only after their IDs, hashes and destinations agree.

Playwright documents role/label locators and recorder-generated locators; it also warns that an immediately enumerated dynamic list can be flaky. See S3-S5 in the source register. The lab waits for an explicit result-ready marker and snapshots a bounded list. Infinite scrolling and pagination are not implemented.

## 5. Verification layers

A control-level postcondition answers whether the expected interface state appeared. A result-level verifier answers whether the requested output exists and is correct under an explicit contract.

For this lab, result verification checks the actual saved file, a byte limit, minimal PNG structure and CRCs, bounded pixel-data decompression, and agreement with a fixture-declared SHA-256. It does not independently identify a real-world subject or prove content rights.

For a future portal export, consider a portal-generated report ID, expected period, schema, account identity and a stable read-back. For a write, use an independently authorized API, a separate read-only session, a database read, or a counterparty receipt where available. A rendered "Saved" banner alone is insufficient for consequential work.

OpenAdapt's published effect-verification documentation explicitly distinguishes screen confirmation from system-of-record checks and states that declared effects/verifiers need deployment-specific authoring. That is a useful boundary to preserve, not a reason to assume verifiers are automatically learned (S2).

## 6. Proposed lifecycle

```text
DRAFT -> REVIEW_REQUIRED -> REHEARSAL -> QUALIFIED -> ADMITTED
                                      -> NEEDS_CORRECTION

RUNNING -> VERIFIED
        -> PARTIAL
        -> HALTED_BEFORE_NEW_EFFECT
        -> PAUSED
        -> CANCELLED
        -> RECONCILIATION_REQUIRED (future remote-write workflows)
```

The implemented lab outcomes are `VERIFIED`, `PARTIAL`, `HALTED`, `PAUSED`, `CANCELLED`, and `REPLAYED`. `REPLAYED` deliberately means that steps ran but no file-effect contract was present. It is not an alias for verified task completion.

Do not automatically retry an uncertain consequential write. An HTTP timeout may occur after the remote system committed the action. Retry only under a supported idempotency/reconciliation contract.

## 7. Storage and replay identity

The prototype stores jobs and verified items in SQLite. A job key is bound to the recipe hash, topic, count, scenario and adapter. Each verified file has a stable internal filename that ignores the server-suggested filename. On resume, files are revalidated before reuse.

This prevents repeated local downloads in the controlled pause/restart tests. It does not provide distributed exactly-once semantics. File rename and SQLite commit do not form one atomic transaction, and a power loss between them needs reconciliation. The lab deliberately stops on stale locks rather than guessing that no worker exists.

Production data should separately represent workflow versions, admissions, schedules, logical jobs, execution attempts, effects, artifacts, approvals, repairs, credentials and retention policies. Do not overload a single "runs" row with all these roles.

## 8. Network and execution security

The prototype only admits an explicit loopback fixture origin, supports a small GET-only path set, disables service workers for interception, and blocks WebSockets and unexpected popups/dialogs. In the HTTP adapter, routed responses are fetched with redirects disabled and redirects are rejected. The offline external-request check and mock-based redirect-policy test are not an OS-level network isolation assessment.

Playwright's routing documentation notes service-worker interception limitations (S6). A production runner still needs OS/container egress controls, process isolation, storage quotas, per-tenant contexts, a hard watchdog, safe downloads, and an explicit dependency/update policy. Browser request interception by itself should not be marketed as a security sandbox.

The local studio binds to loopback, checks Host and Origin, requires a per-process token for mutation, and serves only known run artifacts. These are development guardrails. It has no user authentication, role-based access control, remote deployment hardening or security audit.

## 9. Secrets and observation handling

Use an OS-backed credential store for desktop credentials, scoped references in workflows, and explicit retention for session state. Never include session cookies in shareable workflow packages. Playwright warns that saved authentication state can impersonate an account (S7).

The recorder's password/private-field exclusions are a small demonstration, not comprehensive redaction. Sensitive information can appear in labels, page content, URLs, screenshots, downloads and error logs. A real implementation needs a threat model and consented recording scope, not just a password-input check.

The model authoring/repair path should have a separate observation sanitizer and outbound-data authorization. A webpage is untrusted data and cannot expand the workflow's permissions.

## 10. Repair policy

A future repair service should receive a minimal failure bundle and propose a patch. The patch must preserve or explicitly renegotiate target identity, permissions and result meaning. Run the original qualification cases plus the new failure case before admission.

Use separate budgets for deterministic recovery, model diagnosis, and human intervention. Strict replay must make model invocation impossible at the capability boundary, not merely discourage it in a prompt. The present lab has no repair service.

## 11. Scheduling specification for the next release

A schedule should contain an IANA timezone, explicit local time, next occurrence, missed-run policy, overlap policy, machine availability policy, maximum run duration and notification destination. Use explicit dates in audit records. Store UTC execution timestamps with the schedule timezone retained for interpretation.

A machine being asleep, an expired session and an unavailable network are distinct conditions. A daily trigger is not enough. Reconnection should not produce an unbounded burst of missed runs.

No scheduling code is shipped in this pack.

## 12. Qualification before expansion

Validate HTTP navigation and file transfer on a supported local machine. Then qualify one permitted real website, including login expiration, empty data, changed results, ambiguity, partial output, slow responses, failed downloads and interruption.

Only afterward evaluate an extension recorder, inferred loops, cloud workers, cross-platform installers or visual fallback. These are independent capability increments with independent failure cases, not a single "make it work everywhere" ticket.
