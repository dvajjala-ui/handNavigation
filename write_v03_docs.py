"""Generate release documentation from completed evidence, never guessed counts."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parent
OUT=Path('/mnt/data') if Path('/mnt/data').is_dir() else ROOT/'deliverables'
OUT.mkdir(exist_ok=True)

def write(path, text):
    target=ROOT/path
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(text.strip()+'\n')

def main():
    tests=json.loads((ROOT/'evidence/test-results.json').read_text())
    ui=json.loads((ROOT/'evidence/v03-ui-checks.json').read_text())
    doctor=json.loads((ROOT/'evidence/v03-qualification/qualification.json').read_text())
    passed=tests['test_methods']-tests['failures']-tests['errors']-tests['skipped']
    new_passed=passed-85
    stats=f"{passed} passed, {tests['failures']} failed, {tests['errors']} errors, {tests['skipped']} explicitly skipped"
    status={'version':'0.3.0','generated_at':datetime.now(timezone.utc).isoformat(),
            'delivery':'downloadable local source; not deployed; not pushed to GitHub',
            'tests':{'methods':tests['test_methods'],'passed':passed,'failed':tests['failures'],'errors':tests['errors'],'skipped':tests['skipped']},
            'ui':{'passed':ui['passed'],'failed':ui['failed']},'owned_qualification':doctor['status'],
            'browser_http_qualified':doctor.get('browser_workflow',{}).get('status')=='VERIFIED_EXPORT',
            'production_ready':False,'third_party_sites_tested':0,'native_installers_built':0,
            'github_ci':'configured but not pushed or executed', 'live_sessions_or_vault_keys_distributed':False,
            'primary_new_capabilities':['reviewed connection registry','passphrase-encrypted scoped sessions',
                'owned authenticated HTTP portal','experimental browser CSV adapter','layered doctor command','Connections UI'],
            'scheduled_authenticated_exports':False}
    write('DELIVERY_STATUS.json',json.dumps(status,indent=2))
    write('README.md',f'''# HandNavigate Lab v0.3

**Teach and review a local workflow. Repeat it without model calls. Qualify a site connection before granting broader access.**

Built on the supplied v0.2 source on 23 October 2026. This is a local source release, not a deployed service, native installer, or GitHub push.

## What changed

The existing image-collection recorder, deterministic runner, daily scheduler and recovery system remain intact. This release adds a **separate experimental connection path**: fixed site/account contracts, checksum-bound review, encrypted browser sessions, an owned authenticated report portal, CSV output verification, and a Connections workspace.

The first authenticated example exports five generated CSV rows rather than downloading third-party images. That gives authentication and data correctness an owned, objectively testable target. It does not claim Pinterest access or universal website support.

| Area | Current status |
|---|---|
| Original synthetic image workflow | Real Chromium clicks, Blob downloads, PNG verification; still the only schedulable adapter |
| Connection import/review | Working local API, UI and transactional SQLite registry; import never navigates or signs in |
| Session vault | Tested authenticated encryption, passphrase unlock, scope binding, expiry and local forget |
| Owned portal | Actual localhost HTTP login, cookie reuse, search, CSV download and expired-session rejection checked |
| Browser authenticated export | Implemented; full browser HTTP test blocked by administrator policy in this environment |
| Remote HTTPS connections | Strict contract format and experimental adapter; no third-party website qualified |
| Authenticated recurring jobs | Not connected to the scheduler; requires an unattended secret lifecycle and further qualification |
| Native desktop/mobile/cloud | Not implemented or newly qualified by this release |

## Evidence first

The combined suite reports **{stats}**. Rendered interface checks report **{ui['passed']} passed, {ui['failed']} failed** with no recorded JavaScript runtime errors.

The doctor report is `{doctor['status']}`. Its actual HTTP-client checks pass; ordinary browser navigation returns `ERR_BLOCKED_BY_ADMINISTRATOR`. No browser policy, proxy, or alternate engine was used to bypass it. HTTP-client checks are **not** a fallback browser automation or proof that the browser adapter works.

Read `research/TEST_REPORT.md` and the raw JSON under `evidence/`. Passing test methods are not customer task-success percentages.

## Install and start

Python 3.10+ is the source target; this build was checked with Python {tests['environment']['python']} on {tests['environment']['system']}. Windows/macOS qualification has not been performed here.

```sh
cd handnavigate-lab
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows PowerShell instead:
# .venv\\Scripts\\Activate.ps1
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

## Reproduce the checks

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
''')
    write('research/RELEASE_NOTES_V03.md',f'''# HandNavigate v0.3 release notes

Date: 23 October 2026. Deliverable: local source package, not production deployment or native installer.

## The product increment

The v0.2 recorder, verified image collection, scheduler and recovery logic remain separate from the new experimental site connection path. This separation prevents an unqualified authenticated adapter from becoming a recurring job merely because the original fixture passed its tests.

### Reviewed site profiles

A connection specifies one origin, expected account indicator, entry/login paths, allowed request paths, methods and query keys, semantic controls, and an explicit CSV content contract. Unknown fields, scripts, credentials, broad wildcard paths and unsupported output types are rejected. Fixed asset paths can be reviewed individually. Importing does not perform network access.

SQLite persists version-bound review information for the current profile. Approval requires an exact checksum and a true permission acknowledgement. Compare-and-swap prevents stale updates; a new revision removes approval. This is local acknowledgement, not an authenticated signature or legal authorization.

### Encrypted session capture

The new visible-browser capture flow lets the person sign in without recording credential inputs. It checks the exact configured account label before saving supported cookies/localStorage. Session state is encrypted with Fernet using a passphrase-derived scrypt key and a fresh salt. The passphrase is neither stored nor accepted as a command-line argument.

Tests cover missing sessions, wrong passphrases, ciphertext tampering, TTL expiry, expired cookies, scope changes, unsupported state and local forgetting. A session file's presence is displayed as **validity not checked**. A working account is never inferred merely from the presence of a file.

The vault is not an OS keychain. It does not unlock unattended schedules or protect a process compromised while the secret is in memory. Remote session revocation is not implemented.

### Owned portal and export pilot

A new owned HTTP site supplies a synthetic sign-in form, HttpOnly cookie session, account marker, topic search and generated CSV export. It supports failure cases for expiry, wrong data, duplicate records, formula-like cells, login HTML and redirects.

The browser export code checks the account before and after actions, scopes requests, rejects unapproved destinations, and validates actual CSV bytes. Export receipts avoid cookies, raw page data and unsanitized browser errors. It does not run arbitrary generated code, infer a new website, repair itself or retry uncertain outcomes.

The HTTP-client demonstration downloaded one real CSV containing five generated rows and verified it. This **was not a browser download**. The established image fixture separately produced ten verified PNGs in actual Chromium, as before.

### Connections interface

The studio now includes profile import, exact-contract review, separate session-presence status, local revocation, a supervised command-line path, and evidence cards that distinguish HTTP components from browser workflows. Desktop and phone-width layouts were rendered and checked. The portable preview cannot start jobs or change local data.

### Qualification tooling

`doctor` writes a machine-readable report, probes ordinary browser navigation and never bypasses administrator policy. It attempts full browser sign-in and export only when preflight passes. The supplied CI workflow requires the full browser HTTP gate and is configured for three desktop operating systems, but has not run on GitHub.

## Measured results

- Combined automated suite: **{stats}**, {tests['test_methods']} total methods.
- New v0.3 checks included in that suite: **{new_passed} passed and one browser HTTP test skipped**.
- Separate rendered UI checks: **{ui['passed']} passed, {ui['failed']} failed**, no recorded JavaScript runtime errors.
- Owned HTTP doctor: seven component checks passed; browser probe blocked by administrator policy.
- Model calls: zero in the implemented execution paths; no model client/provider is integrated.

Counts include expected safe halts, mocked policy tests and storage tests. They are not independent customer runs or production reliability metrics.

## Still not delivered

No permitted third-party site has been browser-qualified. No real customer account, Pinterest integration, native installer, cloud runner, phone execution engine, autonomous repair or learned general intent is included. Authenticated exports are deliberately not connected to schedules. File-transfer ingress caps, OS egress isolation, OS keychain integration, crash-tolerant export reconciliation and a real deployment soak remain work.

Nothing was pushed to GitHub. No live session or passphrase is distributed.
''')
    skipped='\n'.join(f"- `{x['test']}`: {x['reason']}" for x in tests['skipped_tests'])
    write('research/TEST_REPORT.md',f'''# HandNavigate v0.3 test and qualification report

Generated from completed evidence on {tests['generated_at']}. This report distinguishes execution layers. A mock, an owned HTTP service and a real browser workflow are not interchangeable evidence.

## Combined suite

| Measure | Result |
|---|---:|
| Test methods executed | {tests['test_methods']} |
| Passed | {passed} |
| Failures | {tests['failures']} |
| Errors | {tests['errors']} |
| Explicit skips | {tests['skipped']} |

Command: `python run_tests.py`.

Environment: {tests['environment']['system']}, Python {tests['environment']['python']}, Playwright {tests['environment']['playwright']}, cryptography {tests['environment']['cryptography']}. Dependency pins reflect this environment, not a current security audit.

The supplied v0.2 baseline was rerun first: 85 passed, one skipped. The final suite contains the original and v0.2 regressions plus v0.3 connection tests. No tests were removed to obtain a passing result.

### Skipped methods

{skipped}

The full browser-HTTP test requires an actual owned login, interactive browser actions, encrypted capture, a second browser context, a verified CSV download and rejection after server expiry. An observed administrator block causes a documented skip here. Setting `HANDNAVIGATE_REQUIRE_BROWSER_HTTP=1` makes that condition fail, as configured in the supplied but unexecuted CI workflow.

## What each layer demonstrates

| Layer | Actual execution | Does not demonstrate |
|---|---|---|
| Contract/registry/vault tests | Python validation, SQLite transactions, encrypted files, wrong-key/tamper/expiry checks | Browser login, production key management, remote site authorization |
| Browser semantic components | Real Chromium DOM checks using directly loaded owned HTML | HTTP navigation, browser session reuse, internet sites |
| Owned HTTP component tests | Real localhost server, real cookie jar, login requests, CSV bytes, expired-session rejection | Browser clicks or browser download integration |
| Application request-policy tests | Mock request/response callbacks verifying no follow/fulfill on disallowed routes | OS egress isolation or behavior of all browser protocols |
| Existing image workflow | Real Chromium interactions on in-memory owned HTML and generated Blob downloads | A third-party website or actual HTTP downloads |
| Studio API | Actual localhost HTTP requests, CSRF checks, connection persistence, approved fixture runner integration | End-to-end rendered UI over browser HTTP |
| Editable UI controls | Real DOM and clicks against an explicitly in-memory fetch stub | Browser-to-server HTTP integration |

## Owned portal doctor

Report: `evidence/v03-qualification/qualification.json`.

Observed status: **{doctor['status']}**.

Seven component checks passed: unauthenticated access denied; synthetic sign-in issued an HttpOnly cookie; session reuse displayed the expected account; authenticated search returned the export link; a real HTTP CSV matched the content contract; session encryption round-tripped; and server-side expiry rejected subsequent access.

The artifact `evidence/v03-qualification/owned-http-component-export.csv` contains five actual generated rows downloaded by a Python HTTP client. Its SHA-256 is `{doctor['component_artifact']['sha256']}` and its size is {doctor['component_artifact']['bytes']} bytes. It is not represented as a browser download.

Ordinary browser navigation to the owned portal returned **ERR_BLOCKED_BY_ADMINISTRATOR**. The full authenticated browser flow was **not run** in that doctor invocation. No policy was disabled, no browser engine was substituted to evade the policy, and HTTP-client success was not used to claim browser qualification.

## New checks of particular importance

Review scopes reject credentials, scripts, wildcards, unsafe origins and unknown paths/query keys. Concurrent edits preserve only one valid next revision. Profile changes invalidate approval and encrypted session binding. Unapproved or missing-session execution stops before launching a browser.

Encrypted files were checked for absence of the synthetic cookie plaintext and passphrase. Wrong passphrases and tampered tokens fail closed. TTL expiry, expired cookies, cross-origin storage, parent-domain cookies, non-Secure remote cookies and unsupported auth storage are rejected. Local forget reports that remote logout was not performed.

The CSV verifier rejects wrong topics, duplicate IDs, schema changes, formula-like cells, malformed UTF-8, login HTML, row-count violations and excessive file size. The file-size check is after transfer; it does not prove bounded ingress or disk consumption during a hostile download.

Actual Chromium component tests verify exact account labels, login-required sentinels, ambiguous-target halts and hidden-control exclusion. They load owned HTML directly and do not replace the skipped HTTP integration.

## Rendered interface checks

Command: `python check_ui.py`.

Results: **{ui['passed']} passed, {ui['failed']} failed**; {len(ui['javascript_errors'])} JavaScript runtime errors recorded. The read-only preview made no external browser requests. Checks include desktop/phone-width overflow, navigation, disabled execution, exact recipe consent, scheduling payloads, teaching draft payloads, connection approval consent, checksum binding, credential-free import and distinct HTTP/browser verdicts.

Desktop and phone-width screenshots were visually inspected. Phone width is emulation, not a native phone app or physical-device test. Editable controls use a declared in-memory API stub; the test suite separately exercises the real API via an HTTP client.

## Retained recurring image demonstration

`evidence/v03-demonstration.json` records a real offline browser rehearsal and a real scheduled ten-file collection. The scheduler clock is injected. The copied PNG outputs and manifest are in `evidence/v03-sample-files/`. This is not an overnight or multi-day deployment. No enabled runtime database is distributed.

## Unestablished claims

No third-party site, real customer account, authenticated unattended schedule, Windows/macOS installation, native phone execution, OS credential store, complete network sandbox, all-crash reconciliation, or production reliability rate was validated. The new CI configuration has not been executed. Tests of safe stopping are counted as passing methods, not successful task completion.

## Raw evidence

`evidence/test-results.json`, `evidence/v03-full-console.txt`, `evidence/v03-focused-console.txt`, `evidence/v03-ui-checks.json`, `evidence/v03-ui-console.txt`, `evidence/v03-qualification/qualification.json`, and `evidence/v03-demonstration.json` are included. Earlier release evidence is retained and labeled separately.
''')
    write('research/SECURITY_MODEL_V03.md','''# v0.3 security model and boundaries

This is an engineering pilot, not a security certification. There is no assertion that a hostile website can be safely contained by the application alone.

## Protected boundaries

**Connection contract.** One canonical origin, explicit paths/methods/query keys, exact expected account indicator, semantic controls and a CSV contract. No JavaScript recipe, arbitrary shell command, discovered permission or wildcard route is accepted. Approval binds to the complete profile checksum. A revision change needs new review and invalidates old session binding.

**Action phase.** Browser replay permits GET requests only. Explicit POST routes are available only during visible human sign-in. This does not prove that every site uses GET safely; the actual approved site must be assessed. Redirects are not followed by the application's route fetch. Unexpected popups, dialogs and WebSockets halt; service workers are blocked in the new contexts.

**Session capture.** The human uses an isolated visible browser. The automation does not record credential keystrokes or ask the studio webpage to collect a password. Capture checks the exact configured account label before persisting supported state. An account label is a site-provided signal, not an independent cryptographic attestation of account ownership.

**At-rest state.** A random salt and fixed scrypt parameters derive a Fernet key from the operator's passphrase. The ciphertext contains the reviewed profile hash, origin, expected account, creation/expiry time and browser state. The passphrase is not written to disk, logs, recipe files, API responses or command-line arguments. Atomic replacement and restrictive file modes are used on supported filesystems. POSIX file mode is tested; equivalent Windows ACL hardening is not established.

**Scoped reuse.** Only host-specific root-path cookies and one exact origin's localStorage are accepted. Parent-domain cookies, other origins, IndexedDB, sessionStorage and additional storage fields are rejected rather than silently stripped. Wrong passphrases, corrupted ciphertext, TTL expiry and changed bindings prevent reuse. Server expiry is checked again through the page's signed-in/account state. Local TTL never guarantees the remote session remains valid.

**Receipts.** Authenticated-path receipts avoid cookie values, raw browser exceptions, request query values, page dumps and screenshots. Errors are mapped to safe codes. Studio metadata reports only whether an encrypted file is present, with validity explicitly unchecked. The owned HTTP audit records method, path and status only.

**File output.** A browser-suggested filename is ignored. The runner uses generated filenames, parses actual UTF-8 CSV bytes, verifies exact columns, row bounds, nonempty unique IDs and exact topic binding, and rejects formula-like prefixes and control characters. This conservative CSV profile is not a universal spreadsheet sanitizer or proof that the data has the intended business meaning.

## Important limitations

Application interception is **not** an OS-level firewall. DNS rebinding, network access by every browser subsystem, subresources outside the adapter's support, process compromise and browser vulnerabilities need independent containment. Same-origin approval is not a complete network sandbox.

`route.fetch` is used with redirects disabled to inspect approved responses. It participates in browser-context request handling but is not a universal proof of original browser networking behavior. The complete owned browser flow is a separate, currently blocked integration gate.

File byte limits are checked after a download is saved. They do not cap network transfer or temporary disk consumption while the browser receives an unexpectedly large response. There is no hard-kill watchdog. Individual operations have timeouts; a worker/process could still require operator termination.

The vault is not a keychain or hardware-backed secret store. A strong passphrase matters. A process or machine compromised while unlocked can access the session and passphrase in memory. Python does not provide a guarantee of securely wiping all copies. Encrypted file theft permits offline guessing; the minimum length check is not a strength proof.

The studio is a local development server, not an authenticated multi-user control plane. Origin, Host and CSRF checks do not protect against all malicious local processes, browser extensions or same-user compromise. Do not bind it to a network or share its runtime directory.

Approval records are checksums and local acknowledgements, not signatures. They can be modified by a sufficiently privileged local actor. Permission must actually exist; clicking a checkbox does not confer a website's authorization.

Forgetting removes the local encrypted copy and local approval. It neither revokes a remote cookie nor stops an export already holding a reviewed snapshot/session. Remote revocation belongs in site-specific sign-out or session controls. There is no authenticated recurring scheduling or automatic credential renewal.

The experimental export path does not yet have the original image runner's checkpoint/reconciliation machinery. It uses a new output name for each manual attempt, no automatic retry, and explicit receipts. Exactly-once remote effects and all crash scenarios are not guaranteed. Review partial local outputs after an interrupted process.

## Sources informing the implementation

Primary documentation checked on 23 October 2026; implementation is pinned and tested separately.

- Playwright authentication: https://playwright.dev/python/docs/auth — saved browser state can impersonate an account; state must not be committed or distributed.
- Playwright network handling: https://playwright.dev/python/docs/network — route interception and browser network APIs, including service-worker considerations.
- Cryptography Fernet: https://cryptography.io/en/latest/fernet/ — authenticated symmetric encryption and the importance of keeping the key secret. The latest documentation is not a claim that the installed package is the latest release.

## Before a real customer pilot

Qualify browser HTTP on a permitted machine; obtain a genuinely authorized target; implement per-site session/account checks; decide output semantics; constrain network and filesystem access outside the browser; integrate an OS credential store; enforce download ingress and process lifetime budgets; add export interruption reconciliation; then run a supervised repeated-use pilot and independent security review.
''')
    write('research/ARCHITECTURE.md','''# HandNavigate v0.3 architecture

## Two separate execution lanes

**Established synthetic lane:** recorder -> reviewed recipe -> fixture runner -> verified PNG files -> persistent schedule/attempt store. The existing controller owns one local worker, fixed-input rehearsals, due occurrences and uncertain-run reconciliation.

**Experimental connection lane:** authored profile -> transactional review registry -> visible human sign-in -> encrypted session state -> manually unlocked browser export -> content-verification receipt. This lane is not inserted into the recurring scheduler and is not marked qualified by profile approval.

The separate status vocabulary is intentional. `APPROVED_NOT_QUALIFIED` describes a contract; `VERIFIED_EXPORT` describes one output from the experimental runner; `COMPONENTS_PASS_BROWSER_BLOCKED` describes a layered environment check. None means production ready.

## Components

`connectors.py` validates a constrained profile and implements a separate SQLite registry. Compare-and-swap binds edits to the reviewed predecessor. The route predicate distinguishes login from run phase, canonical origin/path and allowed query keys.

`vault.py` persists only authenticated ciphertext, using a passphrase-derived key. The secret is provided by a terminal prompt, never a frontend field. State is bound to the full profile hash; an updated connection needs fresh capture. The UI can observe file presence but cannot unlock or return its contents.

`portal.py` is the owned reference server. It creates synthetic sessions and exports generated report data. `qualification.py` deliberately has a real HTTP-client harness and a separate ordinary browser probe. No HTTP-client result is promoted to browser evidence.

`portal_runner.py` supplies shared semantic lookup/account checks, the application request guard, interactive capture and supervised CSV export. Every target must be uniquely visible. File verification is explicit, deterministic and independent of whether a success message appeared.

`studio.py` exposes local connection import/approve/forget and extends its status response with nonsecret metadata and a local doctor report. Existing schedule APIs are unchanged. `ui/index.html` provides a Connections view; the preview is a data snapshot with mutations disabled.

## Persistent data

The runtime holds `studio.db` for established workflow state, `connections.db` for site contracts, `sessions/<id>.session.enc` for encrypted sessions, `connection-reports/` for sanitized receipts and `exports/` for verified CSV files. `qualification.json` describes checks on the current runtime's machine. No populated runtime is shipped.

Exact database filenames for legacy engine components remain defined in their source modules; the separate image checkpoint journal is `journal.db`. A recipe/profile and its sensitive session state are never bundled together as a shareable workflow.

## Deliberate limits

There is no model router, custom-trained model, browser-agent exploration or automatic repair. Ordinary deterministic logic still uses no model calls. Authenticated daily scheduling awaits an unattended secret lifecycle, full browser qualification and interruption reconciliation. A future OS runner may unlock through an approved native credential store, but it is not implemented here.

The browser guard is application-level, not an OS sandbox. Cross-domain login, dynamic third-party asset dependencies, broad cookie domains, indexed authentication storage and complex pages need reviewed adapters and stronger containment. The shipped connector is an owned proof target, not a universal recorder.
''')
    write('research/BUILD_BACKLOG.md','''# Next acceptance gates after v0.3

## P0: qualify the implemented browser path

Run the supplied full browser sign-in/capture/separate-context export test on a machine whose ordinary browser policy permits localhost navigation. The strict CI flag must fail rather than skip when that gate cannot run. Preserve traces only for the owned synthetic portal; never enable session-bearing debug artifacts by default for real users.

Acceptance: actual browser login, restored session in a new context, exact account match, search, genuine HTTP download, verified CSV, account mismatch rejection, server expiry rejection, redirect rejection and no unauthorized write. Neither API-only checks nor mocks satisfy this gate. The GitHub workflow is configured but was not executed in this delivery.

## P0: one explicitly authorized real-site adapter

Choose one recurring read/export task with an objectively testable result and permission to automate. Document the account scope, route inventory, login resources, download semantics and success contract. Do not assume a site's manual button or a user's checkbox grants automation rights.

Acceptance: supervised trial with real HTTP/browser interaction, output validation against known expected records, explicit session expiry recovery, data minimization and maintainable supported selectors. No universal-site marketing claim.

## P0: strengthen runtime containment

Add OS-level network restrictions, download transfer limits and a hard process-lifetime watchdog. Account for DNS resolution, redirects, popup/worker behavior and every download route. Implement native secret-store integration; do not place an unlock key next to ciphertext merely to enable unattended execution.

Acceptance: unauthorized destinations cannot receive traffic outside application callbacks; oversized or stalled transfers are stopped within a tested resource budget; receipts never include session secrets.

## P1: authenticated recurring jobs

Integrate the experimental lane with the scheduler only after browser qualification, OS key storage and interruption handling. Include account identity in the execution contract, require matching rehearsals, stop on session expiry and invalidate queued work on changed permissions. Distinguish local forget, future-run revocation, active-run cancellation and remote logout.

Acceptance: no hidden unlock prompt in an unattended worker, no plaintext credential files, no retry of uncertain remote actions, and clear operator intervention.

## P1: teaching generalization

Move beyond imported fill/click traces toward interactive recording on the single supported site. Ask which values vary, what establishes item identity, what permits a loop to stop, and how a person knows the result is right. Keep the output program inspectable and versioned.

Acceptance: a design partner can teach the supported task without a developer editing every recipe. An explicit plan/verification contract is produced; unrecognized steps are rejected, not omitted.

## P1: desktop packaging and operation

After platform tests run, package a local desktop shell/runner with clear startup, sleep/wake and pause behavior. Add signed distribution and update handling before claiming a Windows/macOS application. Preserve a mobile controller without implying arbitrary phone-app automation.

## P2: optional AI authoring and reviewed repair

Model calls may help author or diagnose a draft; they must not expand execution permissions. Keep a technically enforced no-model replay mode, reviewed repairs and measured cost per verified result. Do not train a model merely to reproduce already-defined clicks.

## Measurements

Track verified task completion, silent incorrect outcomes, interventions per hundred runs, maintenance time, teaching time, zero-model-run share and cost per verified outcome. Unit-test counts, component checks and safely halted runs must not be presented as a production success percentage.
''')
    write('evidence/README.md','''# Evidence index

Current release: **v0.3**. `test-results.json` and `v03-full-console.txt` are the final combined suite. `v03-focused-console.txt` is an earlier focused development run, not the final aggregate. `v03-ui-checks.json` contains separate rendered checks. `v03-qualification/qualification.json` explicitly distinguishes real HTTP-client results from the blocked browser flow.

`v03-qualification/owned-http-component-export.csv` was actually downloaded from the owned HTTP service by Python's HTTP client. It is not a browser result. `v03-sample-files/` contains actual Chromium Blob downloads from the established owned in-memory fixture. `v03-demonstration.json` states that scheduling uses an injected test clock.

`v03-preview-state.json` is a non-executing snapshot. It includes a draft profile and measured reports, no encrypted session or active runtime. Earlier v01/v02 reports and screenshots remain for history and must not be substituted for current evidence.

No real customer account, passphrase, live cookie, key, enabled scheduler database or native installation proof is included.
''')
    changelog=(ROOT/'CHANGELOG.md').read_text()
    heading='''# Changelog

## 0.3.0 - 2026-10-23

Reviewed site contracts, encrypted session storage, owned authenticated HTTP portal, experimental CSV browser adapter, layered doctor report, Connections workspace, strict future CI gate, and retained original workflow regressions. Browser HTTP remains blocked/unqualified in this build environment. No authenticated scheduling or GitHub push.

'''
    if '## 0.3.0' not in changelog:
        write('CHANGELOG.md',heading+changelog.removeprefix('# Changelog').lstrip())
    for source,target in [('research/RELEASE_NOTES_V03.md','HandNavigate_v0.3_Release_Notes.md'),
                          ('research/TEST_REPORT.md','HandNavigate_v0.3_Test_Report.md'),
                          ('research/SECURITY_MODEL_V03.md','HandNavigate_v0.3_Security_Model.md'),
                          ('evidence/v03-qualification/owned-http-component-export.csv','HandNavigate_v0.3_Verified_HTTP_Sample.csv')]:
        shutil.copy2(ROOT/source,OUT/target)
    print(json.dumps(status,indent=2))

if __name__=='__main__':
    main()
