# Core workflow implementation status

25 October 2026. Based on the original teach-once/repeat-without-AI brief in ORIGINAL_PRODUCT_REQUEST.md.

## Delivered

The new handnavigate/transfer package executes a complete source-to-destination image transfer. It discovers a bounded set of images with scroll or click pagination, downloads authenticated image bytes with per-hop origin checks, validates decoded PNG/JPEG/WebP content, submits verified bytes through the destination's browser file input, reloads its gallery and fetches persisted images independently to check their SHA-256 hashes. It does not substitute the owned demo for a failed real-site run.

SQLite records READY, UPLOADING, NEEDS_REVIEW and CONFIRMED states. An interruption after acceptance is reconciled from the remote files before retrying. Repeated jobs do not duplicate already-confirmed outputs. New daily jobs can either select unseen images or confirm existing copies, according to the reviewed new_only setting. Fewer eligible images produce PARTIAL without starting a new incomplete batch of uploads.

The teaching command records real setup actions and selects the source image group and destination gallery. Login uses separate dedicated browser profiles. This is explicit recipe authoring from demonstration, not automatic intent or arbitrary-loop inference. Routine execution makes no model calls.

Daily scheduling pins recipes/inputs/approvals and requires a verified rehearsal. Occurrences are deduplicated, missed days produce at most the latest job, non-verified jobs pause the schedule, and workers have a hard process lifetime. The Windows launcher provides one command for normal execution after setup.

## Measured verification

- Complete regression: 238 passed, 1 skipped, plus 91 passing unittest subtests.
- Two later edge regressions: 2 passed. These cover confirming an existing remote image without resending it, and an empty source producing PARTIAL with no upload.
- Total distinct automated cases across the two recorded runs: 240 passed, 1 skipped, 0 failures/errors.
- The skipped legacy redirect integration case cannot represent HTTP redirects in its offline Blob fixture. The new real-HTTP cross-origin image redirect test passed; this is separate evidence, not a relabeling of the old skip.
- Actual explicit demo: 10 downloaded, 10 browser upload requests, 10 independently confirmed remote images, 0 AI calls. Both sites ran over real local HTTP, on separate origins, using real multipart uploads and mixed image formats.
- The Playwright-driven teaching picker smoke check passed on actual owned HTTP pages. No real-person teaching study was performed.
- Authenticated image reads, delayed pagination/gallery loading, upload-on-file-selection, wrong account, local tampering, fake success, interrupted upload, same-day replay, second-day new selection, real subprocess execution and worker termination are covered.
- Dependency consistency, Python compilation and git whitespace checks passed.

## Scope still requiring user site trials

The user chose to test their own sites. No third-party site pair has been qualified by this change. Selectors must identify original image URLs, the intended upload form/account and persisted destination originals. Byte-changing recompression/resizing cannot pass the exact-byte verifier and needs a different reviewed site contract. Main-frame controls and standard file inputs are supported; iframe/new-tab/custom upload widgets, image-onload-dependent pages and additional API/CDN/login origins may need an adapter. Sessions remain sensitive dedicated browser profiles rather than an OS credential service. No overnight reliability or other-platform qualification is claimed.

## Run

Windows: `handnavigate.cmd demo` for the explicit owned acceptance demonstration. For actual sites use `init`, `teach`, then `run image-transfer.json`. See ../CORE_WORKFLOW.md for commands and limits.

Evidence: ../evidence/transfer-core/qualification.json, full-suite.xml, final-edge-cases.xml, demo-result.json and teaching-picker-smoke.json. `python run_tests.py` now includes legacy, live and transfer suites; CI uses that complete entry point. No Git commit, push or deployment was performed.
