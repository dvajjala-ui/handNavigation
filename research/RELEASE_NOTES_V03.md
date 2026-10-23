# HandNavigate v0.3 release notes

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

- Combined automated suite: **131 passed, 0 failed, 0 errors, 2 explicitly skipped**, 133 total methods.
- New v0.3 checks included in that suite: **46 passed and one browser HTTP test skipped**.
- Separate rendered UI checks: **41 passed, 0 failed**, no recorded JavaScript runtime errors.
- Owned HTTP doctor: seven component checks passed; browser probe blocked by administrator policy.
- Model calls: zero in the implemented execution paths; no model client/provider is integrated.

Counts include expected safe halts, mocked policy tests and storage tests. They are not independent customer runs or production reliability metrics.

## Still not delivered

No permitted third-party site has been browser-qualified. No real customer account, Pinterest integration, native installer, cloud runner, phone execution engine, autonomous repair or learned general intent is included. Authenticated exports are deliberately not connected to schedules. File-transfer ingress caps, OS egress isolation, OS keychain integration, crash-tolerant export reconciliation and a real deployment soak remain work.

Nothing was pushed to GitHub. No live session or passphrase is distributed.
