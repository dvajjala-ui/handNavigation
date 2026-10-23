# HandNavigate v0.3 architecture

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
