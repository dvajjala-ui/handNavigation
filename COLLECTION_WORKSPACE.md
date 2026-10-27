# StickerDock collection workspace — 28 October 2026

The live flow is **StickerDock Admin → Supabase job queue → HandNavigate on this computer → Pinterest/Reddit/Imgflip → local originals → Supabase images and metadata → Admin library**. HandNavigate performs the source work itself. Codex browser tools and AI calls are not required to repeat it. Desktop0.7.0 now bundles the worker and its controls.

## Verified in production

- A 20-image request completed with **20 Pinterest images**, each stored and fetched back from the production database/private bucket. Reddit initially stopped at a missing reviewed image host; Pinterest filled the request. This is recorded rather than counted as a Reddit success: [20-image evidence](service/evidence/cloud-live-20261028.json).
- After adding Reddit's advertised `external-preview.redd.it` image host, a separate **4-image Reddit request** completed through the same hosted queue, browser worker and Supabase read-back: [Reddit evidence](service/evidence/cloud-live-233e3178-e832-405d-8d15-c5d1f402a925.json).
- Imgflip's free popular-template catalog passed a two-image live collection and a separate full production queue/storage check: [Imgflip storage evidence](service/evidence/cloud-live-0795c1cf-b839-4d91-8f2f-1928694bbc51.json). There are **26 production candidate rows/images**: 20 Pinterest, four Reddit and two Imgflip, all unreviewed and excluded from automatic generation. The earlier local-only qualification is additional historical evidence, not another production upload.
- The real hosted Admin passed topic-plan save, candidate editing, a downloaded-file SHA-256 match against its database digest, archive/restore and desktop/mobile layout: [Admin evidence](service/evidence/admin-live-20261028.json).
- The final functional revisions passed [StickerDock Web/API CI](https://github.com/dvajjala-ui/stickerdock/actions/runs/40581384063), [HandNavigate worker CI](https://github.com/dvajjala-ui/handNavigation/actions/runs/40581869552), and [Windows desktop/build/portable acceptance](https://github.com/dvajjala-ui/handNavigation/actions/runs/40581869494). The [daily workflow passed](https://github.com/dvajjala-ui/stickerdock/actions/runs/40580811653), correctly enqueueing zero new jobs because today's stored-image quota was already fulfilled. The first deployment/migration passed [provisioning](https://github.com/dvajjala-ui/stickerdock/actions/runs/40578536889), and its heartbeat extension passed [provisioning again](https://github.com/dvajjala-ui/stickerdock/actions/runs/40579777213).

## Use it

Open [StickerDock Admin](https://stickerdock.vercel.app/admin) and select **Collect images**.

1. Enter 1–10 topics, select Pinterest and/or Reddit, and choose one total image count.
2. Choose **Collect now** for an immediate request, or name and save a reusable topic plan.
3. Enable **Run saved plan daily** to enqueue that plan at approximately **09:53 Asia/Kolkata**. GitHub Actions may delay a scheduled invocation. The repository's daily-intake flag is enabled.
4. Watch the connected/offline worker indicator, source-specific results and downloaded/stored counts. Resume incomplete jobs or stop active ones.
5. Browse the image library with site/topic/archive filters and 25-image pagination. Preview, download, edit title/topic/tags/review status, archive or restore candidates. Archive preserves the original files and source provenance.

The configured plan **Daily animal reactions** requests 20 total images across `funny cat reaction` and `funny dog reaction`, from both platforms. Multiple daily plans share the worker's global budget; they do not multiply it. The normal limit on this computer is **20 downloaded images per India calendar day**. Test runs deliberately used a larger temporary budget because earlier same-day qualification had already consumed 24 local downloads.

## Current Windows worker

The worker is configured and running on this PC at loopback `127.0.0.1:47832`. Its outbound queue connection needs no public API, tunnel or exposed browser. A desktop shortcut and a Windows Startup shortcut named **HandNavigate StickerDock worker** were installed. This PC must remain awake, connected and signed in. The startup shortcut starts the worker when this Windows user logs in; it cannot wake a powered-off PC.

To start manually from source:

```powershell
.\Start-StickerDock-Worker.ps1
```

To recreate the shortcuts on an already configured Windows checkout:

```powershell
.\Install-StickerDock-Worker.ps1 -StartAtLogin -StartNow
```

The source worker requires Node.js, `npm ci` once and Chrome on this Windows host. Its private configuration is `runtime/service-live/stickerdock.json`; profiles, API keys, originals and logs are ignored by Git. The ingest credential is server-only. Supabase stores only its hash in the private integration configuration. Do not put it in Admin forms, screenshots, Git or browser code.

The portable **0.7.0 EXE embeds the collection service**. Open **Image collections** to start/stop it, download locally, connect the cloud queue or inspect recent results. It can adopt the existing configured background worker, retaining its own saved source profiles. A worker managed by the desktop app stops when that app closes; an independently running worker is left alone. Source checkout startup scripts remain available for server operation.

## Recovery and deployment

Jobs use durable request IDs, a persistent local journal, duplicate history, expiring exclusive cloud leases and progress heartbeats. A lease watchdog stops a browser run if the heartbeat cannot be confirmed before expiry. Interrupted jobs can be resumed without resending already verified image deliveries. Retries preserve original source URLs and digests. Keep the persistent data folder when moving or updating the worker.

For an always-on deployment, retain Vercel for Admin/API and Supabase for rows/files. Move the Node/Chromium worker and persistent data to one Windows/Linux server with an interactive console for occasional source sign-in. Configure that host before retiring this PC's worker. No server was purchased or provisioned in this task. Linux/Docker and a fresh server IP/session are still unqualified.

## Remaining boundaries

- Automated collection is currently qualified for static JPEG/PNG/WebP from Pinterest and Reddit, plus name-matched Imgflip meme templates. Imgflip is a finite popular catalog, not full-catalog search or an unlimited source of fresh daily images. Its paid search/generation endpoints are not used. [Provider research](IMAGE_SOURCES_2026-10-28.md).
- Site challenges or expired sessions can require a human in HandNavigate's own browser. They are reported and never bypassed. A single successful day is not proof of 100% unattended reliability.
- Download/storage verification proves actual pixels and provenance, not topical quality or reuse rights. Candidates remain outside the Factory inbox. Existing Pinterest OAuth reference-only behavior is preserved. Rights/quality admission, caption/render acceptance and publication are separate pending stages.
- Video/GIF intake, automatic retention/purge and source deletion/revocation propagation remain pending. Archive/restore is implemented; permanent deletion is deliberately separate.
- Observe several days of source counts, duplicate skips, challenges and successful storage delivery before increasing the production budget.

## Reproduce checks

```powershell
npm test
npm run test:service
node service/admin-ui-check.cjs "D:\5. GitUploaded\sticker"
# The following uses real hosted Admin data and edits/restores a candidate:
node service/admin-live-check.cjs
```

`service/cloud-live-check.cjs` submits a real production collection and records its final counts and per-item storage receipts. It requires the configured worker and exclusive access to its profile directory; stop the background worker before invoking it.
