# Windows core validation — rechecked 5 November 2026

## Measured result

**23 checks executed: 22 passed, one skipped, zero failures/errors.** This includes the real packaged Windows executable, its local setup interface, and an owned image-transfer flow. [Full console](evidence/windows-tests.txt).

Fresh rerun on 5 November: the same 23 checks completed in 42.384 seconds, again with 22 passes and one symlink skip. This verifies the implemented paths under the stated fixtures; it does **not** establish that all requested features work end to end on real services.

| Requested core feature | Evidence available | Remaining gate |
| --- | --- | --- |
| Natural-language instructions using local Ollama/Qwen | Schema/API contract tested with an owned model-server fixture | Install a real model and test planning/action accuracy and performance |
| Delete matching files from a chosen folder | Real disposable Windows Recycle Bin operation; scoped cleanup and bounds checks | Trial with the user's actual folder rules |
| Daily execution | Controlled-clock occurrence, DST, restart and deduplication checks | Natural multi-day run on the target PC/server |
| Like new posts on the user's Instagram profile | Synthetic account/author/control-state checks only | Sign-in and live own-account acceptance |
| Download images and upload them elsewhere | Source and actual EXE verified real bytes between owned HTTP sites | Qualification of the user's real source and destination |
| Saved setup permissions | Persistence, revocation, local API and packaged setup UI tested | Clean-machine installation and Windows Server acceptance |

The dedicated `windows-agent.yml` workflow builds the executable and repeats the core/package checks on Windows for future changes. Adding that workflow is not itself proof of a successful hosted CI run. It does not install a model, log into a real account, or exercise natural multi-day scheduling.

Run from the repository root after building:

```powershell
$env:HANDNAVIGATE_TEST_PACKAGE='1'
.\.venv\Scripts\python.exe -m unittest discover -s windows-agent/tests -v
```

Environment: Windows 10 x64, Python 3.12.14, installed Chrome; dependency versions are in `requirements.txt`. Source and package browser tests run headless against owned sites. The package is produced by PyInstaller 6.16.0. PowerShell launch/setup/build scripts were also parsed successfully, and the UI JavaScript passed its syntax check.

## What passed

- Real Windows Recycle Bin operation on one disposable test file. No user D-drive content was deleted.
- Matching files only, no recursion, age/count limits, no partial deletion when the file-count bound is exceeded, saved permission revocation and outside-folder/traversal rejection.
- Durable request IDs, single-run exclusion, a real process/file lock, persisted setup, restart-to-review, explicit human resolution and a lost-receipt scenario.
- Daily time arithmetic, DST gaps, one catch-up occurrence after downtime, duplicate prevention and verified-rehearsal requirements. These are controlled-clock checks, not natural overnight operation.
- Real owned image bytes downloaded, decoded, uploaded through a file form and independently read back. A repeated request creates no extra upload.
- Redirect to a second unapproved local origin blocked before reaching that server.
- WebSocket interception creates no outside server connection and stops the task.
- An enclosing record changing from A to B blocks the click.
- A fresh configured exact-text output verifies; a preexisting message or a model completion claim alone remains `OBSERVED` and cannot activate a daily schedule.
- Synthetic Instagram markup checks configured/signed-in identity, post author, existing Unlike state, one Like transition and wrong-account/author rejection. This fixture uses request fulfillment; it sends no request to Instagram.
- An owned Ollama-compatible HTTP fixture checks JSON-schema request construction, returned-plan validation and missing-information behavior. This is API-contract evidence, not real-model inference.
- Actual packaged EXE: starts its local server, renders the interface in real Chrome, saves permissions through the actual Setup controls, accepts a task, completes two image uploads/read-backs, reuses its request ID and exits through authenticated shutdown.

The skipped check requires user-created Windows symlinks, disabled on this machine. Symlink/junction rejection exists in the path checker, but that particular OS-level fixture was not executed.

## Package

Path: `dist/HandNavigateAgent/HandNavigateAgent.exe`; the entire sibling `_internal` directory is required. The package contains 1,104 files, approximately 152.3 MB total in the measured build. It is unsigned.

EXE SHA-256:

```text
E675A42E6FEB1BBBD44D1B94F814D9650D074EA0354F136B2ACB0A414B78E8A6
```

[Build/source manifest](evidence/build.json) and [actual packaged setup screenshot](evidence/packaged-ui.png). The manifest labels the repository baseline separately from the new source files, which were uncommitted when the package was built.

The managed Python used here has an extra TLS CA-policy file beside its SSL module. Build preserves that file when present; it does not disable certificate validation to make the package work. Stock Python builds do not need that conditional resource.

## Outstanding acceptance

- **Local model not installed or benchmarked.** The winget download remained stalled and was stopped. The subsequent direct installer command was rejected by automatic approval review with `blocked by policy`. No local inference, memory, latency or instruction-success result is claimed.
- **No live Instagram qualification.** No actual account was signed into or modified. The initial adapter depends on compatible English desktop markup and a visible signed-in Profile link.
- **No real third-party source/destination transfer qualification.** Owned HTTP fixtures prove this implementation's transport and verification mechanics; they do not establish every site's login, selectors, rate limits, gallery or source access.
- **No natural multi-day run**, clean-machine installation, Windows Server acceptance, publisher signing, bounded retention or native Windows-application automation.
- **Setup and startup scripts were not executed as an installation.** Their syntax was checked; no login-startup shortcut or enabled real task was installed on this PC.

Existing HandNavigate implementation files and previously untracked research documents were preserved. New core work is under `windows-agent/`, with a dedicated CI workflow. The initial 4 November build was local; this report was refreshed before the user's requested source-code push on 5 November. No deployment, startup entry or real recurring task was activated by these checks.
