# HandNavigate Desktop

For StickerDock's parameterized server integration, see [SERVICE.md](SERVICE.md). The new worker mode uses HandNavigate's own persistent browsers and download runner. It has saved 20 Pinterest and four Reddit images live; its production deployment and Supabase activation are separately pending.

**Open `dist/HandNavigate-0.6.1-Windows.exe` to use the desktop app and its persistent browser.** No Python, Node or AI key is needed for the packaged build. Version 0.6.1 fixes background input, waits for slow uploads, retries temporary image-read failures and Windows save locks, and defers daily jobs while sign-in is open. It includes Next-page/Load-more controls, durable duplicate history, resumable partial transfers, and a local script API. See [DESKTOP_START_HERE.md](DESKTOP_START_HERE.md) and [API.md](API.md). Source: `desktop/`.

The Python source and historical delivery below remain available. Their Studio screens and browser sessions are separate from the new desktop app.

# Core image transfer implementation

Start with [CORE_WORKFLOW.md](CORE_WORKFLOW.md). The new `live transfer` engine collects and validates real images, uploads through a browser form, verifies persisted destination image bytes, resumes through a durable journal, and runs pinned daily jobs without AI. Windows quick check: `handnavigate.cmd demo`.

The sections below describe the older delivery and its historical qualification boundaries. They do not describe the new transfer implementation; consult the core workflow guide for current behavior and limits.

# Experimental live-browser core patch

This bundle preserves v0.4 and adds `python -m handnavigate live ...`. The old studio is still practice-only.

Start with [LIVE_BROWSER_START_HERE.md](LIVE_BROWSER_START_HERE.md), [the source review](research/TRUSTUDIO_CODE_REVIEW.md), and [the current qualification report](research/LIVE_CORE_TEST_REPORT.md).

42 new component tests pass. Real browser navigation was blocked in this environment; no live model request was made. The older full regression rerun was incomplete. This is not a production or fully qualified release.

---

# Historical v0.4 README (retained below)

# HandNavigate Lab v0.4

**Demonstrate a form. Review its variables and result checks. Repeat the approved task without a model.**

This release adds an interactive **Guided teaching** workspace on top of the supplied v0.3 application. It records actual text, dropdown, checkbox and button interactions inside an owned practice page, compiles explicit bindings, and executes bounded, verified batches. It is a runnable local source build, not a deployed service, native installer, or GitHub push.

## Start here: Guided teaching

```sh
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows PowerShell instead:
# .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
python -m handnavigate studio
```

Open `http://127.0.0.1:4177/teach` on the same computer. The studio home is `http://127.0.0.1:4177/`.

In **Demonstrate**, acknowledge the scope and start recording. Fill Topic, choose Layout, set Include captions, and click Prepare preview. Use Capture current inputs to explicitly include unchanged defaults. Stop recording.

In **Bind & review**, choose variables or fixed values, set the repeat bound, explicitly select the three output checks, compile the draft, and approve its exact version.

In **Rehearse**, enter rows or load the labeled three-row sample. Preview and review the exact input plan, then run. Inspect verified JSON receipts and any halted rows. The source includes a 20-row/80-action automated browser test, not a claim of arbitrary long-task reliability.

**The teaching target is the bundled owned form, not Pinterest or another website.** The loop, bindings and verifier are explicitly selected, not inferred. No model provider is integrated. Guided batches are supervised and are not connected to the daily scheduler.

Read [the teaching guide](research/TEACHING_GUIDE.md), [v0.4 release notes](research/RELEASE_NOTES_V04.md), [the current test report](research/TEST_REPORT.md), and [the security boundaries](research/SECURITY_MODEL_V04.md).

## Reproduce the v0.4 evidence

```sh
python run_tests.py
python -m handnavigate doctor --output evidence/v04-qualification
# Read a nonzero doctor result; do not hide or bypass it.
python build_v04_evidence.py
python check_ui.py
python write_v04_docs.py
```

The doctor requires a working owned browser-HTTP flow for exit code 0. A managed-browser block remains a nonzero result even when separate HTTP-client checks pass. Do not modify policy to turn it green. Evidence generation uses the explicitly scoped in-memory fixture, not an alternative HTTP transport.

UI checks distinguish read-only rendering and in-memory stubbed controls from the separate actual HTTP API integration tests. Windows/macOS CI is supplied but has not been executed here.

The following sections document the retained v0.3 image workflow and experimental connection path. Their qualification boundaries have not been expanded by the new teaching screen.

---

## Install and start

Python 3.10+ is the source target; this build was checked with Python 3.13.5 on Linux. Windows/macOS qualification has not been performed here.

```sh
cd handnavigate-lab
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows PowerShell instead:
# .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
python -m handnavigate studio
```

Open `http://127.0.0.1:4177` on the same computer. The studio is loopback-only and not a multi-user authenticated web service. Do not expose it to your network.

Dependencies are exact versions used for this test build, including `cryptography==46.0.4`; they are not a claim of being the latest or a substitute for a release-time vulnerability review.

## Use the established image workflow

Review the active recipe in Studio, run a rehearsal, and inspect the actual verified files. After a VERIFIED result, create a daily schedule with the same topic, count, recipe and transport. Keep the process running and the computer awake. The phone-width UI is a controller layout, not on-device mobile execution.

Teaching still requires explicit variable binding and selection of the authored collection contract. The compiler does not infer arbitrary intent, loops or verifiers.

## Inspect a new connection

Run an owned test portal in a separate terminal, from the same project directory:

```sh
python -m handnavigate portal
```

This creates an **unapproved** `owned-report-portal` profile in the default `runtime` directory. In the studio, open **Connections**, inspect its origin, exact expected account, routes, control targets and CSV contract, then acknowledge site permission and approve the exact checksum.

No real password is needed for the owned portal. Its demo session is synthetic, lasts 15 minutes on the server, and disappears when that portal process restarts.

On a computer where ordinary browser navigation is permitted, capture the demo session from a private terminal:

```sh
python -m handnavigate connect owned-report-portal
```

Choose a long passphrase at the hidden terminal prompt. Complete sign-in yourself in the visible browser and type `SAVE` in the terminal. The application then checks the expected account and encrypts the supported browser state. It does not record credential typing or keep the passphrase.

Rehearse the experimental export:

```sh
python -m handnavigate export owned-report-portal --topic architecture
```

The command asks for the passphrase again. It rechecks the account, searches, downloads the file, validates the CSV schema, row bounds, IDs, exact topic and conservative cell rules, then writes a receipt. Browser export failures do not retry automatically. No screenshots or raw browser errors are retained from this authenticated path.

**This path was not fully browser-qualified in the build environment.** It may fail or require adapter changes even on a policy-permitted machine. No authenticated export schedule is available.

The default encrypted-state TTL is eight hours, but it never extends a website's real session lifetime. Expired or wrong-account sessions require human sign-in. Changing the connection revision or permissions invalidates the old encrypted state binding.

To remove the local session and approval:

```sh
python -m handnavigate connection-forget owned-report-portal
```

This does not revoke the remote site's session or stop an already-running export. Use the site's own sign-out/session controls for remote revocation.

## Environment and HTTP qualification

```sh
python -m handnavigate doctor
```

This starts a temporary **owned** portal, checks its real HTTP behavior, tests encryption with a synthetic cookie, probes ordinary browser navigation, and attempts browser sign-in/export only when that probe succeeds. It does not test an external site.

Results are written to `runtime/qualification.json`. The studio reads that local report; importing a profile does not set it to qualified. Exit code 0 requires the owned browser flow to pass; code 2 means incomplete or failed qualification. Do not disable an administrator policy to make it pass.

## Reviewable profiles and command-line operations

`profiles/owned-report-portal.json` is a draft contract, not a credential or approval. To import it without running the portal:

```sh
python -m handnavigate connection-import profiles/owned-report-portal.json
python -m handnavigate connections
```

New profiles require revision 1. Changes require the prior checksum with `--base-sha256` and the next revision. The studio offers the same operations. CLI approval requires the exact checksum printed by `connections`:

```sh
python -m handnavigate connection-approve owned-report-portal --reviewed-sha256 YOUR_REVIEWED_CHECKSUM --i-have-permission
```

All commands accept `--output` for a different runtime directory. Use the same directory across studio, portal, connect and export. Approval is local acknowledgement, not a signature or evidence that a website has authorized you.

## Archived v0.3 reproduction commands

```sh
python run_tests.py
python -m handnavigate doctor --output evidence/v03-qualification
python build_v03_evidence.py
python check_ui.py
python write_v03_docs.py
```

The doctor command intentionally returns 2 for an administrator block. Continue to the next command only after reading the report; do not hide the nonzero status in CI. The preview builder runs two real offline browser image workflows with an injected scheduler clock, not an overnight deployment. Editable UI tests use an in-memory API stub; actual localhost API tests are separate.

The supplied `.github/workflows/qualification.yml` is configured for Linux, Windows and macOS. It has **not** been pushed or executed. `HANDNAVIGATE_REQUIRE_BROWSER_HTTP=1` turns an administrator-blocked browser HTTP test into a failure rather than a skip.

## Security and support boundaries

Only one exact origin and explicit paths/query keys are accepted. Browser execution is GET-only; reviewed POST routes are usable only during interactive login. Redirects, unexpected dialogs/popups and WebSockets stop the pilot. This is application-layer defense, **not** DNS-aware egress isolation or an OS sandbox.

The vault supports host-specific root-path cookies and same-origin localStorage only. Cross-domain sign-in, parent-domain cookies, IndexedDB, sessionStorage, passkeys and MFA orchestration are not supported. Human sign-in may use site MFA only when all required resources fit the approved contract; no challenge is bypassed.

See `research/SECURITY_MODEL_V03.md` for limits, including download size validation after transfer, lack of a hard-kill watchdog, and local-machine compromise. No live session, passphrase, key, enabled runtime database, or production account is included.

## Important new files

| Path | Responsibility |
|---|---|
| `handnavigate/connectors.py` | Validated site contracts, request policy and transactional review registry |
| `handnavigate/vault.py` | Passphrase-derived authenticated encryption and scoped session lifecycle |
| `handnavigate/portal.py` | Owned authenticated HTTP test site |
| `handnavigate/portal_runner.py` | Experimental browser session capture, CSV export, identity and result checks |
| `handnavigate/qualification.py` | Separate HTTP-client and browser qualification layers |
| `handnavigate/connection_cli.py` | Explicit local commands and hidden passphrase prompts |
| `tests/test_v03.py` | Connection, vault, HTTP, browser-component and API regression tests |
| `check_ui_v03.py` | Rendered preview and explicitly stubbed editable UI checks |

Nothing has been committed or pushed to `dvajjala-ui/handNavigation`.
