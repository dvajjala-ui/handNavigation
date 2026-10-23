# v0.2 architecture: implemented, local and constrained

Date: 23 October 2026. The v0.1 design proposal is retained under `archive-v01/`.

## Actual runtime

```text
Local studio HTML
    | loopback JSON API; host/origin/session-token checks
    v
StudioServer
    | explicit recipe review / input validation
    v
SQLite studio.db
    | immutable recipe snapshot + request
    | daily schedule -> unique queued occurrence
    v
Controller: one worker, one active attempt
    | exact local-only recipe, no model dependency
    v
Playwright Runner -> owned in-memory fixture -> generated PNG downloads
    | PNG structure / CRC / SHA-256 / count checks
    v
journal.db checkpoints + artifacts + atomic report JSON
    | terminal outcome persisted by controller
    v
studio.db attempts and audit trail -> studio evidence views
```

Two databases have different responsibilities. `journal.db` is the existing runner's file/checkpoint store. `studio.db` is the new queue, recipe, schedule and operational-history store. The two are not a distributed transaction. A crash between the runner's file/report persistence and studio completion remains uncertain and requires reconciliation.

## Scheduling contract

A schedule captures an immutable recipe, fixed topic/count, fixture transport, IANA timezone, daily wall-clock time, grace period and missed-run policy. Eligibility requires a prior VERIFIED studio rehearsal of the same recipe and inputs. Search-only REPLAYED output does not qualify.

The daily-time engine constructs wall-clock candidates, round-trips through UTC to reject nonexistent local times, and chooses the earliest UTC instant for repeated wall times. Next occurrences are strictly future-facing. The default UI zone is Asia/Kolkata; the engine accepts installed IANA zones.

`enqueue_due` runs inside a SQLite immediate transaction. It chooses the latest due occurrence rather than expanding a backlog. An unstarted older day can be superseded. A running occurrence cannot be replaced. The `(schedule_id, due_at)` unique constraint suppresses duplicate materialization. `claim` rechecks lateness before executing, including queue delays that exceed a skip policy's grace period.

A partial, paused, cancelled or halted scheduled execution pauses its schedule. Explicitly resuming a paused schedule starts at its next future occurrence, not at every date missed while paused.

## States and ownership

```text
QUEUED -> RUNNING -> VERIFIED | REPLAYED | PARTIAL | HALTED | PAUSED | CANCELLED
QUEUED -> SUPERSEDED | MISSED | CANCELLED
RUNNING --process interrupted--> NEEDS_REVIEW --explicit acknowledgement--> ABANDONED
```

`RuntimeOwnership` holds an advisory OS lock on the local runtime while the controller owns it. POSIX and Windows code paths exist; only the Linux path was exercised here. A unique partial SQLite index permits one RUNNING attempt. Queue claims use transactions.

These controls prevent ordinary duplicate local claims in the tested design. They are not a distributed fencing service, an OS egress sandbox, or a proof of exactly-once remote effects. The existing runner also uses `.execution.lock`; a hard-kill stale file remains subject to deliberate operator review rather than automatic deletion.

The controller holds ownership until its worker has stopped. A persistence error after a possible effect stops the worker; it does not trigger a hidden retry. Startup recovery is performed only after obtaining ownership. Unknown attempts block new claims and schedule creation until reconciliation.

## Teaching and version changes

The narrow recorder captures fill/click actions. Compilation substitutes only an explicitly supplied example-topic binding. Unsupported events, private steps and malformed inputs fail validation. The application never assumes an omitted sensitive step was unnecessary.

An operator may explicitly append the authored collection contract. That loop and verifier are not inferred. A checksum-reviewed draft activates as the next revision, cancels queued work and pauses schedules; in-flight attempts keep their original immutable snapshot. Stale parallel drafts cannot overwrite a later revision. Review receipts are not digital signatures or multi-user approvals.

## UI and API boundaries

The UI has studio, teaching, scheduling, activity and evidence views. Polling avoids re-rendering unchanged history/draft panels so expanded details and focus are not continually destroyed. Strings rendered into HTML are escaped. Recipe and recording editing remain constrained by server-side validation.

The loopback API checks Host, Origin and a per-process session token for writes, bounds JSON bodies, and serves artifacts only from recorded artifact paths. Download retrieval rechecks the file hash before presenting it as verified. It is a development server and must not be exposed to a network. Screenshots and raw reports are synthetic; a real data-retention/redaction design is still required.

## Explicitly absent

No external website adapter, browser extension, generalized intent model, model author/repair tool, credential vault, authenticated account lifecycle, cloud queue, native installer, mobile execution engine, startup service, infinite scrolling, remote-write verifier, signed update mechanism or production incident-monitoring system is present.
