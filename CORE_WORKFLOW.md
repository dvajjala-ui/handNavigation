# Core workflow: teach once, transfer images without AI

## Download 20 Pinterest images to this computer

```powershell
.\handnavigate.cmd download --query "nature landscape" --count 20
```

Files go to your Windows Downloads folder in `Pinterest-nature-landscape`, with a manifest of the actual files, source URLs, dimensions and SHA-256 hashes. The command verifies every image, skips duplicate bytes and safely reuses its existing output on repeat runs. No AI or upload destination is involved.

If Pinterest requires sign-in, use `handnavigate.cmd download --query "nature landscape" --count 20 --login` once. Sign in yourself in the dedicated browser; ordinary Google sign-in tabs are supported during this manual phase. The download starts automatically when Pinterest confirms the session, and later runs reuse it. The downloader stops at gated previews or login pages. It does not remove login overlays or collect gated preview URLs. It uses only image resolutions advertised by the actual Pin page and does not guess original-image addresses. `--folder` chooses another local output folder.

The original brief in `research/ORIGINAL_PRODUCT_REQUEST.md` asks for a demonstrated browser task that repeats without needing AI to think through every click. The new transfer engine implements that repeatable path: discover images, download and decode them, upload through the destination's real form, check the persisted destination files, and journal each confirmed result.

## Try the complete core now

On this Windows checkout, the Python environment and Chromium are already installed:

```powershell
.\handnavigate.cmd demo
```

This explicitly starts two owned HTTP sites, collects 10 images across result pages, uploads through a real multipart browser form on the second site, downloads the saved files back and compares their hashes. It accepts real PNG, JPEG and WebP files. Results and files go to `runtime/transfer-demo`. This demonstration is never substituted for a failed run against your sites.

## Set up your two sites once

```powershell
.\handnavigate.cmd init --source "https://YOUR-SOURCE.example/images" --target "https://YOUR-TARGET.example/gallery" --submit "Upload"
.\handnavigate.cmd teach image-transfer.json
.\handnavigate.cmd run image-transfer.json
```

`init` writes a reviewable site-pair recipe. `teach` opens a dedicated browser for each site. Sign in yourself before recording, demonstrate the search/folder/open-form setup, and stop before downloading or uploading. Select an example source image and the destination gallery in the browser. The recipe keeps the recorded setup and selected image group. Source and destination sessions are retained separately in `runtime/transfer/profiles`. Credentials are never demonstrated to the recorder.

The first `run` prints the recipe and asks for its one-time exact approval. Later runs of that same setup and inputs do not prompt. A changed selector, action, site scope or input requires a new review. Teaching is a draft workflow: it does not magically infer which images you own, original-image URLs, hidden APIs or task meaning.

For straightforward sites, skip `teach` and set the selectors directly at creation:

```powershell
.\handnavigate.cmd init --source "https://YOUR-SOURCE.example/images" --target "https://YOUR-TARGET.example/gallery" --source-images ".photo-card img.original" --target-images "#gallery img" --submit "Upload image"
.\handnavigate.cmd login image-transfer.json
.\handnavigate.cmd run image-transfer.json
```

Omit `--submit` only if file selection itself uploads the file. `--source-attribute href` can select original download links instead of thumbnails. The default selector `img` is a starting draft: narrow it to the images you intend to copy. A default cannot distinguish avatars, adverts and originals on an arbitrary site.

Recorded live workflows can also supply setup through `init --source-setup recording/workflow.draft.json --target-setup other/workflow.draft.json`. Their steps and scopes are imported, and unresolved recording blockers are rejected. Variable bindings work through existing live parameter references and `run --inputs inputs.json`.

## Repeat or resume

```powershell
.\handnavigate.cmd run image-transfer.json
```

The default job identity is the recipe/input hash plus today's date in `Asia/Kolkata`. Repeating the command on the same day resumes/rechecks that job rather than uploading another copy. Use `--job my-trial-2` for a deliberately distinct run. With `new_only: true`, future jobs skip previously confirmed image bytes and collect new items. If fewer than 10 eligible images exist, the result is `PARTIAL`, files are preserved and the engine starts no new uploads for that incomplete selection.

Uploads use verified image bytes from memory, never page-supplied local filenames. PNG/JPEG/WebP decoding, dimensions, pixel count and transfer bytes are bounded. Every image redirect must stay inside the recipe's exact allowed origins. During execution the page's automatic image/media loads are blocked; image retrieval uses the streaming reader, with cookies selected from the browser for each URL. Teaching still displays images normally. Pages that require successful image-onload events to reveal controls need an adapter. This transport is used for all image reads, not as a navigation-policy fallback. A browser navigation failure stops the task. Browser request guards are application-level checks, not an OS network sandbox.

## Daily runs

After one complete verified run of the exact recipe and inputs:

```powershell
.\handnavigate.cmd schedule image-transfer.json --at 09:00 --timezone Asia/Kolkata
.\handnavigate.cmd worker
```

Keep that worker process running and the computer awake. Schedules pin the recipe, inputs, approval and dedicated profile paths. Occurrences are persisted and deduplicated. On wake after downtime the worker runs at most the latest occurrence; it does not replay a backlog of missed days. A partial, failed or uncertain run pauses its schedule. `schedules` lists IDs; `pause ID` and `pause ID --resume` control them.

The worker starts each transfer in a separate process with a hard lifetime. On timeout it terminates that process tree; its next explicit retry checks the item journal. This does not install a Windows startup service, keep a sleeping PC awake, or run on a phone.

## What success actually means

`VERIFIED` requires exactly the requested number of selected local images and matching byte hashes from the destination's persisted image URLs, fetched after gallery reload. A toast, click or model statement cannot substitute for those checks. `latest-result.json` and per-job receipts include source identity, file hashes, formats, sizes, dimensions and destination IDs.

The destination verifier is deliberately byte-exact. Set its image URL attribute/selector to the stored original, not a resized thumbnail. Sites that recompress images need a separate explicit verifier; this build halts for review rather than falsely claiming an exact copy. Add `target.verify.ready` as a live locator for the gallery's loaded indicator on asynchronous sites, and `target.verify.setup` for any separate gallery-opening steps. `source.next` can be a bounded scroll, a reviewed click locator, or null. Source and target `identity` checks can require exact visible account text.

## Interruptions and login expiry

An item is marked `UPLOADING` before file selection, because a site's change event may start a network request. After interruption, the engine reads the destination first. A matching persisted image reconciles the receipt without resending the file. An unknown effect becomes `NEEDS_REVIEW`; it is never retried blindly. If you inspect the destination and confirm an item was not uploaded, record that decision explicitly:

```powershell
.\handnavigate.cmd resolve --job THE_JOB --sha256 THE_IMAGE_HASH --confirmed-not-uploaded
```

Then repeat the same job. `login image-transfer.json` renews expired sessions manually. MFA/CAPTCHA and unsupported surfaces require human intervention. Main-frame semantic controls and normal file inputs are supported; iframe upload widgets, new-tab flows, cross-domain login resources and WebSocket-dependent sites need additional adapters/scopes. Add only the exact required origins and request methods. This is a reusable execution core, not a promise that every website accepts the same teaching selectors.

## Install on another computer

Python 3.11+:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m playwright install chromium
```

On macOS/Linux use `.venv/bin/python -m handnavigate live transfer` instead of the Windows launcher. Those platforms still need their own qualification; do not assume this Windows run proves them.

## Verify the build

```powershell
.\.venv\Scripts\python.exe run_tests.py
```

That command now includes the legacy suite, the live-browser suite, source-to-destination HTTP transfer tests and scheduler tests. CI installs the development dependencies and invokes the same complete gate. The owned integration tests cover two-site uploads, pagination/deduplication, mixed image formats, fewer-than-required items, corrupt data, wrong account, tampered local files, fake success, crash recovery, authenticated image reads, rejected redirects and the real subprocess CLI. Scheduling tests separately cover pinned rehearsals, daily deduplication, missed days, interruption and pause-on-failure.

API references used for the implementation: [Playwright file uploads](https://playwright.dev/python/docs/api/class-locator#locator-set-input-files), [Pillow image verification](https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.verify).
