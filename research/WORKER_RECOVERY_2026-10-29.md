# Worker recovery — 29 October 2026

HandNavigate 0.9.1 replaces the old PID-only `worker.lock` file with a 30-second filesystem lease renewed every 10 seconds. A second worker cannot use the same browser and journal folder while the lease is current. A crashed worker's lease expires, and the scheduled collector waits up to 35 seconds to acquire it before processing the queue. A termination signal cancels that wait. The worker stops if it loses its lease rather than continuing to write shared state.

An active old-format PID lock remains protected regardless of file age. When its process has exited, the old JSON bytes are copied to a `worker.lock.legacy-*` diagnostic file before the lease directory replaces it. The migration uses a file-only unlink; a concurrent upgrader cannot rename or remove a newly acquired lease directory. An unreadable old lock is preserved and requires inspection. HTTP shutdown releases the lease after collection and browser cleanup, even if unrelated process timers keep the old CLI process alive.

Desktop image collections use the same lease. If its lease is lost, the collection worker closes and the app reports the condition while keeping the teaching browser open. Existing journals, receipts, downloaded images, cookies, and candidate review state remain in their data folders.

Local verification: 37 core tests, 34 worker tests including a real killed process, heartbeat, 30-second recovery, concurrent migration, HTTP shutdown, and desktop-only worker loss; the desktop end-to-end suite passed. The bounded AMD64 and ARM64 container workflow also runs the recovery tests with a mounted data volume. Source-bound CI and portable acceptance must pass before publishing the 0.9.1 executable.

This prevents a stale PID from permanently blocking future daily runs. It does not guarantee that every source has 20 fresh usable images each day, remove website login or human checks, or grant rights to reuse third-party images. Stored source images remain pending review in StickerDock.
