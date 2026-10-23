# v0.3 security model and boundaries

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
