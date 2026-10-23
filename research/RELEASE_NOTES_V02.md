# HandNavigate v0.2: release notes

**23 October 2026. Local source package; no GitHub push or external deployment.**

## The product moved from one-off rehearsals to recurring local operation

The studio now stores daily schedules, immutable recipe snapshots, queued attempts, terminal reports, reviewable drafts and audit events in SQLite. A single local worker executes approved tasks. The new scheduling path was exercised with actual browser downloads using an injected test clock.

### Daily schedules

Choose a fixed topic/count, an IANA timezone, a local daily time and a missed-run policy. A matching VERIFIED rehearsal is required first. Missed days are coalesced into one latest occurrence or skipped, not replayed as a backlog. Nonexistent daylight-saving times are skipped; repeated local times run only at the first occurrence. A late queued job is rechecked before execution. An older unstarted queued day can be superseded by the newest due day.

### Conservative recovery

The queue uses transactional claims, a unique scheduled-occurrence key and one active attempt. An advisory process lock prevents two studios owning the same local runtime. If execution is interrupted without a terminal report, the attempt becomes NEEDS_REVIEW. The operator can acknowledge its outcome without retrying it. Schedules remain paused. These are local guarantees within tested cases, not a promise of exactly-once external actions.

### Teaching and reviewed versions

Import recorded fill/click actions, explicitly identify the topic variable and optionally select the existing authored image-collection contract. Drafts are inspectable and checksum-reviewed. Activating a changed recipe pauses schedules and cancels queued work. A stale parallel draft cannot overwrite a newer active revision.

Private recorded steps previously could be silently dropped by compilation; this version rejects such traces. Changed artifacts are also rechecked and rejected before serving them as verified files.

### Studio interface

The redesigned application has a workflow workspace with a side inspector, teaching/review screens, a schedule builder with upcoming-run previews, durable activity history, reconciliation controls, an audit trail and a quality/limitations view. Desktop and phone-width layouts were rendered and checked; there is no native phone automation app.

## Qualification

**85 automated tests passed; 0 failed; 0 errors; 1 explicitly skipped.** Separately, **28 rendered-UI checks passed**. UI checks distinguish actual rendering from editable controls backed by an in-memory API stub.

A recorded demonstration produced **10 actual verified files through the scheduled path**, with no model dependency. The clock was advanced for testing; this is not evidence of overnight uptime.

## What has not changed

The runner still operates only on its owned synthetic fixture. Ordinary browser HTTP navigation remains blocked in the build environment and was not bypassed. Pinterest, Instagram, authenticated websites, general desktop control, model-assisted repair, custom training, cloud execution, native installers and mobile execution are not implemented or qualified.

The studio must remain open and the computer awake. The preview is read-only. The ZIP includes no active runtime database or automatically enabled job.

## Run it

```sh
cd handnavigate-lab
python -m pip install -r requirements.txt
python -m playwright install chromium
python -m handnavigate studio
```

Use a Python virtual environment as described in README.md. Open `http://127.0.0.1:4177` on the same computer. Start with a reviewed normal-scenario rehearsal, then save a schedule using exactly the same verified inputs.

## Next product gate

Validate one explicitly permitted real HTTP website and task, including its authentication boundary and actual output contract, in an appropriately permitted environment. The detailed follow-on backlog covers credential handling, observed human teaching, native platform qualification and optional reviewed AI authoring/repair.
