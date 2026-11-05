# Core validation — 5 November 2026

This is a working development core, not a 100% qualified unattended product. The current target is twenty Pinterest images in a folder on a remote host. Instagram and uploads are skipped for that target; a one-time manual Pinterest login is now authorized.

## Source and rebuilt Windows executable

**30 checks: 29 passed, one skipped, zero failures/errors, 46.986 seconds.** [Actual console](evidence/windows-tests.txt). The executable was rebuilt from the committed Python core at `b5f72c5`. The only skip is a user-created Windows symlink fixture, unavailable on this PC.

Checks cover real disposable Recycle Bin cleanup, filename/age/count limits, saved permissions and revocation, path boundaries, durable request IDs, process locking, restart/review behavior, controlled-clock daily scheduling, actual owned image download/upload/read-back, local API access checks, and the actual packaged setup UI and transfer flow. Browser checks reject outside redirects and WebSockets, changed records, old success text, hidden/gated image elements, and multiple srcset resolutions counted as separate pictures. A fresh independent result now stops the model before another click, including at the last allowed action.

These are controlled fixtures and real local OS/package operations. They do not prove arbitrary websites, multi-day reliability, clean-machine setup, Windows Server acceptance or signing. No user D-drive files were removed. The scheduler was not enabled for a real task.

## Real Ollama model

Ollama and `qwen3.5:4b` were installed successfully during authorized setup. The earlier WinGet downloader stall was resolved through its documented alternate downloader; original settings were restored. Local inference and Pinterest collection were kept off the user's PC after the remote-only request.

The latest [remote CPU inference run](https://github.com/dvajjala-ui/handNavigation/actions/runs/42013128808) passed **4/5** cases. [Exact plans, actions and results](evidence/remote-local-model.json):

| Case | Actual result |
| --- | --- |
| Instruction to cleanup plan and disposable cleanup | VERIFIED; 53.32 seconds |
| Missing task details | Returned missing information; 32.86 seconds |
| Instruction to two decoded image downloads | VERIFIED; 45.42 seconds |
| Instruction to upload and original-image verification | FAILED validation: account text assigned to the wrong field; no transfer executed |
| Instruction to a browser click and fresh exact result | VERIFIED after one click; 52.84 seconds total |

This establishes real inference for the named tasks, not general model accuracy or a performance guarantee. Small models still need plan review. Validation failures remain blocked before execution. Failed-output evidence now retains the current raw response instead of accidentally showing the previous successful plan. Upload planning remains an open core limitation even though uploads are outside the current target.

## Remote Pinterest and hosting

The GitHub Windows acceptance VM loaded Pinterest search and a public travel board but received a login form and gated images: **ACCESS_REQUIRED, 0/20**. [Observed board report](evidence/remote-pinterest.json), [remote run](https://github.com/dvajjala-ui/handNavigation/actions/runs/42011610291). No login gate was removed and no alternate source was silently substituted.

The user then authorized one-time manual Pinterest login. An Oracle Free Tier Mumbai A1 request (2 OCPU / 12 GB) failed for lack of capacity. After explicit user selection, a free E2.1.Micro browser VM (1 GB, Ubuntu 24.04 Minimal) was created and accepted SSH. The user signed in on the VM through a temporary loopback screen tunneled over SSH. The core collector then returned **VERIFIED, 20/20 in 103.19 seconds**. An independent VM-side read fully decoded all files, compared the exact folder to the manifest and verified twenty distinct hashes. These are 236-pixel-wide previews, not original-resolution images. [Sanitized measured result](evidence/oracle-pinterest.json).

The temporary login processes were closed. The core application runs as a persistent unprivileged systemd user service with saved setup/profile and a loopback-only UI. The small VM does not host the recommended 4B model. [Deployment and reconnect guide](../deploy/free-vm/README.md).

## Private Supabase image library and the live daily schedule

The `stickerly` project now holds the collected images. [001_collections.sql](migrations/001_collections.sql) creates four tables (`collection_topics`, `collection_jobs`, `collection_runs`, `collected_images`), turns on row-level security for all four, and revokes every anonymous and authenticated grant, so only the worker's Postgres role can read them. Bytes go to a private `handnavigate-images` bucket (JPEG/PNG/WebP only, 25 MiB ceiling); the code refuses to reuse the bucket if it is ever public. The database row stores the path plus hash, size and pixel dimensions, never the image.

Measured on 5 November with [tools/verify_library.py](tools/verify_library.py) — see [the sanitized report](evidence/supabase-library.json): **149 images across six topics, all 149 re-downloaded through authenticated Storage and matched to their recorded SHA-256 and byte count**. No row is claimed without the object existing in the bucket. Travel 20, Nature 30, Animals 39, Art 20, Food 20, Architecture 20. The first Animals batch verified twenty distinct files but inserted nineteen rows because one wildlife pin was byte-identical to an image already in the library, and `sha256` is unique.

The control page stays loopback-only, so the library is published a different way: [tools/make_gallery.py](tools/make_gallery.py) asks Storage for a signed link per row, fetches every one of those links back **with no `apikey` and no `Authorization` header** and hash-compares it, and only then writes a single self-contained HTML file. Measured on 5 November, 149 of 149 rows produced a link that opened on its own and matched its recorded SHA-256, so the published page carries no key, no token and no credential — only links that stop working at their expiry (72 hours in the published build). The page is unlisted, marked `noindex,nofollow,noarchive`, states that the pictures are reference-only previews of material belonging to the pages they came from, and is served behind the site's own private access mode. Refreshing it is re-running the tool and re-publishing; nothing about the worker, its profile or its secret key travels with the file.

A topic only becomes collectable on a source after a real signed-in run passes on that source's exact configured URL; [tools/import_collection.py](tools/import_collection.py) calls `mark_verified` only for a `VERIFIED` batch whose source URL equals the stored one, and the migrations seed both source columns as unverified. All six topics earned it that way on Pinterest on 5 November, four of them in one pass through [earn-topics.sh](../deploy/free-vm/earn-topics.sh). An unearned topic is still listed in the UI, marked as needing a verified batch for the chosen source, and the runner refuses it — so nothing is claimed for a source that has not been read.

The daily job **Daily Pinterest rotation** is live on the VM: random verified topic, 20 images, `09:00` `Asia/Kolkata`, `enabled=true`. Occurrences ran unattended through the worker's own scheduler tick — one triggered by the driver and the catch-up occurrence claimed for the local date, `VERIFIED, 20/20` and `VERIFIED, 5/5` stored with per-image read-back. `enabled` is only settable after that job's own run reaches `VERIFIED`, and a `PARTIAL`, `HALTED` or crashed run pauses it instead of retrying in a loop.

Reddit runs through the same saved browser profile instead of an API key, because that is the route the user chose. [tools/collect_reddit.py](tools/collect_reddit.py) and [earn-reddit.sh](../deploy/free-vm/earn-reddit.sh) are wired and measured: a 20-image batch on `https://www.reddit.com/r/travel/top/?t=month` from the VM ended in `ACCESS_REQUIRED` with 0 images in 11.1 seconds, and the page text it recorded is Reddit's own block — "You've been blocked by network security. To continue, log in to your Reddit account or use your developer token". The run stops there. No credential is typed, no challenge is answered, no other source is substituted, and `reddit_verified` stays false, so no Reddit job can be scheduled. What is still missing is one thing only the user can do: sign in to Reddit once on the VM through [tools/remote_login.py](tools/remote_login.py) `--source reddit` over the noVNC tunnel. After that sign-in the same script can earn topics for real; whether Reddit lifts a network-level block for a logged-in datacenter session is measured, not assumed.

The suite is now 39 tests, all passing locally (2 skipped). [test_collection_rules.py](tests/test_collection_rules.py) covers the parts that must fail before anything is written: the plain-.env rules, the exact project endpoint, a source with no earned topic being refused for create, edit and enable, job bounds, an unknown source refusing to store, Reddit page allow-listing, the pages the manual-login helper will open for each source, and a check that every source config names columns the migrations really create. Each of those tests runs against a connection that raises on use, so a pass proves no SQL was reached.

The separate [x64 and Arm container checks](https://github.com/dvajjala-ui/handNavigation/actions/runs/42009765486) built the Linux image and started Chromium as an unprivileged user. Those checks establish browser/container startup, not real Pinterest access or Oracle performance. GitHub Actions is used only for bounded software tests, not a production personal automation service.

## Development package and remaining acceptance

`dist/HandNavigateAgent/HandNavigateAgent.exe` is an unsigned development package. Keep its entire sibling `_internal` directory. Installed Chrome and a separately configured Ollama model remain prerequisites. [Build and source hashes](evidence/build.json); [actual packaged setup UI](evidence/packaged-ui.png). Managed-runtime TLS policy files are preserved when present; certificate verification is not disabled.

Still unqualified: original-resolution Pinterest downloads, natural multi-day scheduling, full model plus browser operation on the chosen persistent host, clean-machine installation, Windows Server, signing, and arbitrary native Windows applications. The Instagram adapter has synthetic evidence only and is outside the current target. Startup scripts were parsed and integrated with the installer; no local login-startup entry was installed.

Run the measured checks after building with `HANDNAVIGATE_TEST_PACKAGE=1` and `.venv/Scripts/python.exe -m unittest discover -s windows-agent/tests -v`.

The [hosted Windows rebuild and checks at b5f72c5](https://github.com/dvajjala-ui/handNavigation/actions/runs/42015207534) passed all 30 tests, including the symlink case, in 57.474 seconds. The [matching x64 and Arm image checks](https://github.com/dvajjala-ui/handNavigation/actions/runs/42015207580) also passed. These CI results and the measured local suite are distinct from live-site and model results. Original application lanes and untracked research files were preserved.
