# HandNavigate Desktop

Open **dist/HandNavigate-0.5.0-Windows.exe**. It includes the app, Chromium browser, image decoder and local runner. You do not need Python, Node, a terminal, a separate browser install or an AI key to use the packaged app.

## Your first workflow

1. Click **New workflow**, enter a website, and choose **Download images** or **Repeat a taught task**. The Pinterest template is a convenient starting point, not the only supported site.
2. Open the website in the app's browser and sign in manually if needed. That browser session is shared by teaching and execution and is retained locally according to the website's cookie lifetime.
3. For image downloads, navigate to the actual image results and click **Choose images**, then one image from the intended group. The app proposes the matching group and image hosts for review. For a repeated form task, click **Start teaching**, demonstrate its supported controls, then **Stop teaching**.
4. In **Review**, check the recorded actions and output checks. Change a demonstrated input to `{{topic}}` to bind it to your values. For a repeated task, add the visible result text or exact final URL that proves completion. Click **Approve & run**.

Files appear in your chosen Downloads location, grouped by workflow and run. **History** shows verified image hashes, dimensions, source URLs, result checks and failures. Open the output folder directly from the app.

## Different values and daily runs

Enter one topic or prompt value per line in **Values to repeat**. `{{topic}}` can appear in a starting search URL or in a taught input. A direct search URL encodes the value safely. **Advanced** accepts named variable rows when you need several changing fields.

Run each configured value once and inspect the result. In **Daily**, choose the time and timezone and turn on the schedule. It rotates through the configured rows, deduplicates each daily occurrence and collects new image bytes when that option is selected. It runs locally while the app is open and the computer is awake. After downtime it executes at most the latest occurrence rather than replaying every missed day. Failed or partial jobs pause the schedule.

Editing executable steps, variables, websites, image count or result checks invalidates the earlier approval and rehearsal. This prevents a changed draft from silently altering an active daily workflow.

## Uploading images to another site

Choose **Download and upload images**. Set up the source as above, then open the destination's upload form in the same browser and click **Use this upload form**. Navigate to its saved-image gallery and click **Choose saved gallery**. Review both sites and the selected file input before running.

Only validated files from this run can be submitted. The app reloads the saved gallery and downloads its persisted images to verify byte-identical originals. An interrupted or unverifiable upload is marked **Needs review** and is not blindly repeated. Repeating a successful transfer confirms matching remote files without creating another copy.

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
```

`npm test` verifies contracts, approvals, durable recovery, daily occurrence handling, timezone/DST and image decoding. The Electron acceptance tests operate the real desktop UI and embedded browser against owned HTTP sites: two topics with 20 downloads each, actual teaching and parameter replay, shared-session reuse across restart, browser uploads, remote-byte checks, duplicate prevention and failure handling. Those sites are explicit test targets and are never substituted for a failed third-party run.

The supplied Windows executable is a local build, without a publisher signing certificate. It is not an app-store release or a security certification. See `research/DESKTOP_TEST_REPORT.md` for the measured build results and limitations.
