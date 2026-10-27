# HandNavigate Desktop

Open **dist/HandNavigate-0.7.0-Windows.exe**. It includes the app, embedded teaching browser, image decoder, script client and collection worker. You do not need Python, Node, a terminal or an AI key for local downloads. Pinterest/Reddit collection uses an installed Chrome or Edge browser; Imgflip's popular-template catalog needs no browser login.

## Collect images without teaching a workflow

1. Open **Image collections** in the sidebar. Enter topics, choose sites, set one total count and select local Downloads or the connected StickerDock library.
2. Choose **Collect images**. The worker starts automatically. The panel shows downloaded/stored counts and the verified result, with Stop/Resume for incomplete work.
3. Open **Connection & worker settings** to connect StickerDock once, choose a persistent data folder, or change the local daily image budget. The saved credential is never sent back to the UI. Existing configured background workers are adopted without starting a second process against their profiles.
4. Use **Open Admin** for saved daily plans, fresh planner topics and the downloaded-image gallery. Keep this app open when it owns the worker. An independently running worker keeps running when this window closes.

Local collections appear under **Downloads/HandNavigate Collections**. Chrome/Edge sign-in requests open a separate window; these sessions are separate from the embedded teaching browser. The existing background-worker shortcut is still supported.

## Your first workflow

1. Click **New workflow**, enter a website, and choose **Download images** or **Repeat a taught task**. The Pinterest template is a convenient starting point, not the only supported site.
2. Open the website in the app's browser and sign in manually if needed. That browser session is shared by teaching and execution and is retained locally according to the website's cookie lifetime.
3. For image downloads, navigate to the actual image results and click **Choose images**, then one image from the intended group. The app proposes the matching group and image hosts for review. For a repeated form task, click **Start teaching**, demonstrate its supported controls, then **Stop teaching**.
4. In **Review**, check the recorded actions and output checks. Change a demonstrated input to `{{topic}}` to bind it to your values. For a repeated task, add the visible result text or exact final URL that proves completion. Click **Approve & run**.

Files appear in your chosen Downloads location, grouped by workflow and run. **History** shows verified image hashes, dimensions, source URLs, result checks and failures. Open the output folder directly from the app.

Temporary image-read failures get up to three read attempts within the 30-second request budget. Short server retry delays are respected; a longer rate limit stops the run for a later attempt. Access denial and invalid site scopes are not retried. History records the retries.

Choose **More results** according to the site: scroll, Next page / Load more, or only this page. For Next, click **Choose Next control** and point to the actual button or link in the browser. A page limit bounds the search. The app stops on missing/disabled Next controls or repeated pages and reports a partial result when fewer images are available.

**Collect new images each time** remembers saved files even from partial runs. **Duplicate history** can cover this workflow or every workflow in the app. Exact file bytes, normalized decoded pixels and previously saved source identities prevent repeat downloads. **Also skip similar images** adds approximate visual matching for many resized or recompressed copies. It can exclude similar-looking images and does not guarantee recognition of every crop or edit. Older history without visual fingerprints retains its file/source checks.

## Different values and daily runs

Enter one topic or prompt value per line in **Values to repeat**. `{{topic}}` can appear in a starting search URL or in a taught input. A direct search URL encodes the value safely. **Advanced** accepts named variable rows when you need several changing fields.

Run each configured value once and inspect the result. In **Daily**, choose the time and timezone and turn on the schedule. It rotates through the configured rows, deduplicates each daily occurrence and collects new image bytes when that option is selected. It runs locally while the app is open and the computer is awake. After downtime it executes at most the latest occurrence rather than replaying every missed day. Failed or partial jobs pause the schedule.

A due daily job waits while another job, teaching, control selection or a sign-in popup uses the browser. It keeps its due occurrence until the browser is available.

You can minimize the app while supported workflows execute. Text, clicks and bounded keys target the embedded browser without needing the desktop window to hold focus. The computer must stay awake. Closing the app still stops its worker.

Editing executable steps, variables, websites, image count or result checks invalidates the earlier approval and rehearsal. This prevents a changed draft from silently altering an active daily workflow.

For a script or another local program, enable the local API in **Daily**, copy the workflow ID and use **Save script client**. [API.md](API.md) contains commands and endpoints. Repeating an API request ID returns the original run, so a network retry does not silently start another download/upload job.

## Uploading images to another site

Choose **Download and upload images**. Set up the source as above, then open the destination's upload form in the same browser and click **Use this upload form**. Navigate to its saved-image gallery and click **Choose saved gallery**. Review both sites and the selected file input before running.

Only validated files from this run can be submitted. The app reloads the saved gallery and downloads its persisted images to verify byte-identical originals. An interrupted or unverifiable upload is marked **Needs review** and is not blindly repeated. Repeating a successful transfer confirms matching remote files without creating another copy.

Before opening the gallery, the runner waits up to 45 seconds for observed upload requests to finish. This also covers forms that upload when a file is selected. Slow or uncertain writes are never automatically resubmitted. A site's delayed background jobs can still require a later **Recheck uploaded originals**.

Configure **Saved gallery pages** when persisted images span several pages. Verification stops before uploading if the destination exceeds the reviewed page limit. A partial source transfer reuses its validated pending files when the same approved row runs again. **Recheck uploaded originals** resolves a late upload by reading the destination without submitting it again. If an upload is absent, the explicit missing-upload confirmation allows a later retry. A recheck preserves the original run's review status and does not automatically enable a schedule.

## Supported boundaries

The core supports ordinary main-frame text inputs, clicks, selection controls, checkboxes, bounded key presses, navigation, image groups, scrolling and normal file inputs. A site can require a specific selector, reviewed CDN/API host, output rule or adapter. Iframes, canvas-only controls, drag-and-drop-only widgets and browser/device apps outside this browser are not generic supported targets. Sign-in, MFA and CAPTCHA require the person; the app does not bypass challenges. Popup-based sign-in is available before recording or running. A popup during execution stops the task for attention.

The app does not infer a complete arbitrary workflow from a natural-language prompt. A person demonstrates the steps once, binds the changing values and defines a result check. No AI model is called by repeat execution.

Image downloads require actual advertised image URLs and bounded JPEG/PNG/WebP content. Invalid placeholders are skipped while the app searches for valid candidates. Uploaded image verification currently requires access to the destination's persisted original bytes. Recompression or resized-only galleries need an explicit alternative verifier. New image discovery is bounded; a source with fewer eligible new images gives **Partial**, not false success.

The app's site browser has a separate session from ChatGPT's in-app browser, Chrome and the earlier Python runner. Its first sign-in is therefore necessary. Passwords are not recorded in taught actions. The local browser profile remains sensitive; its files should not be shared. Session-only cookies may require sign-in after closing the app, while persistent cookies survive within the website's expiration rules.

Closing the app stops the local worker; minimizing keeps it available. Reopening preserves workflows, approvals, schedules and history. Work interrupted during a remote task requires outcome review. This build has been tested on Windows; it does not establish every-site reliability, a multi-day production success rate or 100% absence of bugs.

## Development and verification

Source: `desktop/`. Existing Python engines remain available for their earlier CLI workflows.

```powershell
npm install
npm test
npm run test:desktop
npm run dist
npm run test:packaged
```

`npm test` verifies contracts, approvals, durable recovery, daily occurrence handling, timezone/DST and image decoding. The Electron acceptance tests operate the real desktop UI and embedded browser against owned HTTP sites: two topics with 20 downloads each, actual teaching and parameter replay, shared-session reuse across restart, browser uploads, remote-byte checks, duplicate prevention and failure handling. Those sites are explicit test targets and are never substituted for a failed third-party run.

The supplied Windows executable is a local build, without a publisher signing certificate. It is not an app-store release or a security certification. See `research/DESKTOP_TEST_REPORT.md` for the measured build results and limitations.
