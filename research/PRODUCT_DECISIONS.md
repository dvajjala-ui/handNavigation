# Product-owner decisions after v0.2

**Date: 23 October 2026**

## Keep the first promise narrow

A user can rehearse an owned local browser task, inspect the resulting evidence and schedule deterministic repetition. That does not mean the system can learn any website from one demonstration. Keep the supported task and execution environment visible in the UI.

## Trust comes from outcomes and boundaries

The main metric remains verified task completion, not clicks or a guessed confidence score. Preserve distinct VERIFIED, REPLAYED, PARTIAL, HALTED and NEEDS_REVIEW outcomes. A safe stop is better than a false success, but is not completion.

## Make authoring separate from execution

The current teaching path imports narrow recorded actions and requires explicit variable binding. The collection loop and effect verifier are selected templates, not learned intent. A future model may propose drafts, but a reviewed, constrained representation remains the execution boundary. This build intentionally has no model integration.

## Schedule only rehearsed work

Require a matching verified recipe and fixed inputs before a daily schedule is saved. Pin the recipe snapshot. Do not silently update live schedules when the user changes the workflow. New versions pause schedules and require a fresh rehearsal before reuse.

## Prefer a missed run over duplicate uncertain action

Do not replay a backlog after downtime. Do not automatically retry an interrupted attempt whose outcome is unknown. Make reconciliation a visible operator action. Preserve proof, pause the schedule and explain what is uncertain. Never claim that reverting code undoes a remote effect.

## Use local-first honestly

The computer is the runner. The studio must remain open and the machine awake. A phone-sized controller interface is not a phone automation engine. Cloud and native OS scheduling are separate products/gates, not hidden assumptions behind a daily schedule UI.

## The next gate remains a permitted real site

The build environment still blocks ordinary browser HTTP navigation. The prototype therefore cannot establish real-site reliability. Select one authorized retrieval/export workflow with a clear result contract and validate it in an appropriately permitted environment. Do not broaden into unrestricted website automation, account engagement, payments or arbitrary device control before proving this gate.

## What the latest evidence justifies

The package demonstrates persistent scheduling machinery, exact recipe review, conservative recovery and real offline browser downloads. It does not establish an unattended multi-day success rate, human usability, business retention, willingness to pay, generalized recording or production security. The release report distinguishes every test layer.

The original v0.1 product decisions are retained under archive-v01 for historical context; they are not the current implementation inventory.
