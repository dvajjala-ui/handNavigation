# HandNavigate Windows core

A new, isolated implementation of the Windows local-agent direction. The existing desktop app, worker and Python lanes remain intact.

**Instruction → local Ollama plan → validated tools → durable run → checked result.**

This is a development core, not a fully qualified end-to-end product. [Validation status](VALIDATION.md) separates measured file/image/scheduler behavior from real-site and multi-day acceptance. The current acceptance target is **20 Pinterest images in a folder on a remote host, without login**; Instagram and uploads are skipped for that target. [Remote deployment and free-host research](../deploy/free-vm/README.md).

## Current functionality

- Local Ollama planning with JSON-schema output and validation; default recommendation `qwen3.5:4b`.
- Setup once for allowed folders, exact website/image origins, uploads, browser interactions and own-profile Instagram likes. Permissions survive restart; tasks do not repeatedly request the same grant.
- Daily local-time schedules, a persisted SQLite journal, request-ID deduplication, one active runner, Stop, crash recovery and explicit uncertain-effect resolution.
- Delete matching files by moving them to the Windows Recycle Bin. Exact folder, nonrecursive filename pattern, minimum age and maximum file count; links/junctions and system folders are excluded.
- Download decoded JPEG/PNG/WebP images; optionally upload through a normal file input and read back byte-identical originals from a configured gallery. Saved pending files and effect receipts support reconciliation.
- A local-model browser loop using current DOM control references. Fresh scoped output checks can verify a task; a model's completion claim alone is `OBSERVED`.
- An initial own-profile Instagram adapter: checks the configured username against the signed-in navigation Profile link, checks each post's author, skips an already visible Unlike state, and verifies state after a like. **Not live Instagram-qualified.** English labels and compatible desktop markup are required.

This core does not yet control arbitrary native Windows applications. Filesystem and browser operations implement the requested first task families. Administrator actions, UAC, site login, MFA and human challenges cannot be permanently preapproved by this app.

## Start from source

Requires Windows 10/11, Python 3.12+ and installed Google Chrome. A Windows server can run it under its own user; visible browsing/manual sign-in needs an interactive desktop session. No public server port is needed; use the server's local UI through its desktop.

```powershell
cd F:\dwarkesh\handNavigate\windows-agent
.\Setup.ps1 -InstallOllama
.\Start.ps1
```

Open [the local interface](http://127.0.0.1:47841). Save your permissions in **Setup once**, write an instruction, create a plan, fill any missing details, save it and run it. You can also edit/paste a structured plan without a model. After one verified run, enable its daily schedule.

Setup installs dependencies and, with `-InstallOllama`, installs the local runtime and downloads the model through `Install-LocalModel.ps1`. That helper completed installation of Ollama and `qwen3.5:4b` on 5 November. If WinGet's default downloader stalls, `Setup.ps1 -InstallOllama -RepairDownloader` temporarily uses WinGet's documented alternate downloader and restores the original settings. No local inference or local Pinterest task was run after the remote-only request; real-model acceptance runs on a temporary remote test VM.

Ollama's existing running server retains its own model-directory setting. Setup/Start respect a configured model directory; a new installation defaults to this folder's `runtime\models`. They cannot relocate an already running server's files. The launcher also detects a runtime installed inside `runtime\ollama`.

For manual sign-in, stop the runner first so there is one owner of its profile:

```powershell
.\.venv\Scripts\python.exe agent.py login https://www.instagram.com/
```

Sign in yourself and close the browser; restart the core. Its dedicated browser profile is separate from your usual Chrome and the earlier HandNavigate app. The source Start script can also use the parent repository's existing `.venv` in development.

## Example tasks

Cleanup instruction:

> Every day at 18:00 Asia/Kolkata, recycle *.tmp files older than 7 days from D:\MyTemporaryFiles, at most 20 files. Do not enter subfolders.

Save `D:\MyTemporaryFiles` in cleanup permissions once. A complete structured plan can be pasted directly:

```json
{
  "name": "Daily temporary files",
  "instruction": "Recycle old temporary files from my chosen folder daily",
  "kind": "cleanup",
  "folder": "D:\\MyTemporaryFiles",
  "pattern": "*.tmp",
  "older_than_days": 7,
  "max_items": 20,
  "schedule": {"time": "18:00", "timezone": "Asia/Kolkata"}
}
```

Images require an actual source URL and matching image selector. Add image CDN origins to Setup. Transfers also need an upload form URL, exact account text visible on the destination, a normal file-input selector, an optional submit button name, and a gallery URL that exposes saved originals. The default selector is `img`; narrow it when the page also contains unrelated images. The current gallery verifier checks one bounded page, not arbitrary pagination. Sites that recompress originals need a separate verifier and will not be falsely reported verified.

Own-profile Instagram instruction:

> Daily at 20:00 Asia/Kolkata, check my own profile https://www.instagram.com/MY_USERNAME/ and like up to 10 currently visible posts that are not already liked. My username is MY_USERNAME.

Enable own-profile likes and the exact origins required by the site. This is a bounded scan of profile posts, not an infinite backfill or a guarantee of every new post. Login, a missing signed-in Profile identity, localization, changed markup or a challenge stops the task. No live account was accessed during development.

For a general browser task, include the URL, goal and exact visible account/owned-page marker. For unattended verified schedules, configure a real `result_selector` and `expected_result`. The exact text must be absent initially and newly present at that one visible element after execution. A preexisting success message does not qualify. A task without an independent verifier ends `OBSERVED` and cannot enable an unattended schedule.

## Scheduling and operation

- Keep the process running, the PC awake and the required user session available. The core cannot wake a powered-off PC or bypass a locked desktop.
- Optional current-user login startup: `Install-Startup.ps1`; remove with `Install-Startup.ps1 -Remove`. These scripts were authored, but no startup entry was installed on the developer PC.
- Downtime produces at most one catch-up run, not a backlog of repeated effects. A failed, partial or uncertain run pauses its schedule.
- A crash leaves an interrupted effect as `NEEDS_REVIEW`. Inspect the destination, then choose the explicit completed/absent resolution in History. Resolution is recorded as a human assertion; it is not retroactively counted as independent verification.
- Reusing a request ID returns the original run. State is local to this runner's data folder. OS locks prevent two processes using the same folder. Separate machines do not share exactly-once guarantees.
- Source state is in `runtime/data`; packaged state defaults to `%LOCALAPPDATA%\HandNavigateAgent`. These folders contain sensitive browser sessions, task inputs, logs and downloaded files. They are not source artifacts to share.
- Browser observations go only to a loopback Ollama endpoint. No cloud provider fallback or model-generated shell execution is implemented. The initial setup page is loopback-only with Host, Origin and session-token checks.

## Build and validate

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\Build.ps1
```

Build creates `dist\HandNavigateAgent\HandNavigateAgent.exe`. Keep the whole directory together. It includes Python and Playwright's driver, but requires installed Chrome and a separately installed Ollama/model. It is an unsigned development package, not a signed installer.

See [PLAN.md](PLAN.md) for implementation choices and acceptance boundaries, [VALIDATION.md](VALIDATION.md) for current measured checks, and [ORIGINAL_REQUEST.md](ORIGINAL_REQUEST.md) for the preserved user request.
