# Bounded Railway daily collector

This container runs the existing outbound queue worker and exits after the queue
has been idle for 90 seconds. A 25-minute application limit stops active work;
an independent 28-minute process-group limit kills a stuck shutdown after 30 more
seconds. Partial collections, queue errors and interruptions fail the run.

Configure one replica, 1 vCPU / 2 GB RAM, a 5 GB volume mounted at `/data`, restart
policy `NEVER`, Dockerfile `deploy/railway/Dockerfile` and one daily cron schedule.
Set only `STICKERDOCK_BASE_URL` and the existing `STICKERDOCK_INGEST_TOKEN` as
server variables. No public domain, HTTP health check or database admin key is
needed. The volume retains profiles, originals, duplicate history and request IDs.
Its size is fixed; review storage use before it fills rather than deleting data
or enabling automatic paid expansion.

At full 2 GB RAM / 1 vCPU for 30 minutes daily, 30 runs use about $0.42 RAM + $0.42
CPU monthly at the October 28 prices, plus up to $0.75 for 5 GB storage and egress.
Allow $1–$3 of metered usage monthly for the collector, subject to actual runs and
pricing. The Hobby subscription includes $5 usage across the workspace. Existing
projects, manual extra runs, taxes and agent services affect the account's bill.
Do not apply a workspace-wide shutdown cap without checking other projects.

Qualify guest access on the exact Railway host before enabling daily collection.
True source challenges remain attention-required; this cron image has no public
graphical console. For human interaction use the separate private VM deployment.
Each batch refreshes duplicate hashes and source links through the authenticated
intake endpoint before claiming work. It never receives a database admin key.
Set `HANDNAVIGATE_ENQUEUE_DAILY=1` when activating the daily cron: the host enqueues
the saved Admin plans itself, using the server's India date and existing SQL daily
quota/idempotency. Disable the old GitHub browser worker only after qualification;
there is no timing dependency on GitHub's separate scheduler. Reconcile unfinished
work before migration; do not copy live browser locks.
