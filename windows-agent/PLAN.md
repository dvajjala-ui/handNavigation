# Windows agent core plan — 4 November 2026

## Intended outcome

Run on the user's Windows PC or Windows server. A locally installed model interprets instructions; the application provides the actual filesystem/browser tools and scheduler. The user chooses permissions during setup; recurring tasks reuse those permissions. New scopes need one setup change. OS and website consent remain controlled by those systems.

The first task families are folder cleanup, own-profile post likes, image downloads and image uploads. The broader direction also supports a bounded local-model browser loop. Native app control, arbitrary shell execution, collaboration, billing, mobile support and StickerDock-specific ingestion are outside this core increment.

## Implementation

- Python 3.12+, Playwright, Pydantic, Pillow, Send2Trash and standard-library SQLite/HTTP/threading.
- Ollama JSON-schema plans; local-only endpoint. The application validates scope and arguments independently of model output. Unknown folders/accounts/times stay missing rather than being invented.
- Dedicated browser profile, exact origin grants, per-hop CDP request checks and WebSocket interception with no server connection. A WebSocket attempt stops the task.
- Reuse `handnavigate/transfer/files.py` for image decoding and bounded manual-redirect image reads; its supporting scope module is bundled. Do not reuse the older live driver's redirect interception as the new browser guard.
- SQLite tasks and runs; immutable saved plans; fresh run IDs and durable external request IDs; effect intent before operation; effects verified afterwards; OS-owned process lock with automatic crash release.
- Separate `VERIFIED`, `OBSERVED`, `PARTIAL`, `HALTED`, `CANCELLED`, `NEEDS_REVIEW` and human `REVIEWED` states.
- Daily schedules require a verified rehearsal, deduplicate due requests, run once after downtime, and pause on incomplete outcomes.
- Small local setup/task/history interface. CLI operations and an unsigned Windows directory package support deployment without redesigning the existing app.

## Model choice

This PC reports about 16 GB RAM and Intel UHD 750 integrated graphics. Start with Ollama `qwen3.5:4b`; it is a candidate baseline, not a proven reliable agent on this hardware. Measure plan accuracy, valid-action rate, peak memory and latency before selecting it for unattended use. A stronger server can try a larger local model without changing the tool contracts.

Qwen's current Ollama page lists tool/vision support and smaller model variants. Local JSON schema is supported by Ollama. The implementation currently uses DOM text observations, not vision. A real model must still pass the task acceptance set; successful loading alone is insufficient.

References checked on 4 November 2026:

- [Ollama structured output](https://docs.ollama.com/capabilities/structured-outputs): schema-constrained JSON, followed here by independent Pydantic validation.
- [Ollama Windows](https://docs.ollama.com/windows): native runtime and installation requirements. Model storage is a separate operational concern.
- [Qwen3.5 model variants](https://ollama.com/library/qwen3.5): candidate local model family; provider capability descriptions are not local benchmarks.
- [Browser Use](https://github.com/browser-use/browser-use): reference for an observation/action browser-agent architecture. Its existing local-model example is at [examples/models/ollama.py](https://github.com/browser-use/browser-use/blob/main/examples/models/ollama.py). No code from that project was copied into this increment.
- [Microsoft UFO](https://github.com/microsoft/UFO): reference for broader Windows UI-agent architecture; general native-application control is deferred.
- [Playwright WebSocket routes](https://playwright.dev/python/docs/api/class-websocketroute): an intercepted socket has no server connection unless the handler explicitly connects it. This core does not connect, sinks messages locally and stops execution.

## Acceptance sequence

1. Owned fixtures prove cleanup boundaries, real decoded image transfer, read-back, identity changes, fresh results, origin boundaries, schedule occurrences, restart recovery and request deduplication.
2. Build the actual Windows executable and smoke its own local UI/API and an owned transfer. Keep source, packaged and real-provider evidence separate.
3. Install the local model and measure real instruction planning plus action selection on owned tasks. No simulated planner result qualifies this stage.
4. With the user's sign-in and exact account/site configuration, qualify one real source/destination and the own-profile adapter. No real Instagram writes or broad D-drive deletions are needed for component tests.
5. Run a natural multi-day schedule on the target host, including expired login, changed page, Stop and a restarted runner. Signing, clean-machine install and long-running retention remain release work.
