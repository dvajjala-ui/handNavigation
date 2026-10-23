# Primary-source research register

Checked on **22 October 2026**. Documentation and repositories may change. A publisher's documented capability is not an independently reproduced result.

| ID | Source | What it supports | Qualification |
|---|---|---|---|
| S0 | https://github.com/dvajjala-ui/handNavigation | The referenced repository currently contains the original request and product research documents. | This implementation pack was not pushed to it. |
| S1 | https://github.com/browser-use/workflow-use | Demonstration/workflow generation, parameterized reuse, a documented no-AI execution path. | README explicitly warns of early development and does not recommend production use. Repository identifies AGPL-3.0 licensing; review before adoption. |
| S2 | https://docs.openadapt.ai/concepts/effect-verification/ | Distinction between screen success and verified persisted effects; deployment-specific effect/verifier declarations. | A primary-source search result exposed the substantive page; direct open returned a redirect. Read the current destination and linked implementation before adoption. |
| S3 | https://playwright.dev/docs/locators | Semantic roles, labels and explicit locator contracts. | These mechanisms do not prove the logical correctness of a chosen target. |
| S4 | https://playwright.dev/python/docs/codegen | Generating browser actions/locators from interaction and recording explicit assertions. | A recorder is not a general intent or loop-inference system. |
| S5 | https://playwright.dev/python/docs/api/class-locator | Dynamic list enumeration and readiness considerations. | The lab waits for its own explicit results-ready state. |
| S6 | https://playwright.dev/python/docs/api/class-browsercontext | Isolated contexts, routing, service-worker interception limits and WebSocket routing. | Context/request controls are not OS-level egress isolation. |
| S7 | https://playwright.dev/docs/auth | Saved session state may contain account-impersonation secrets. | Authentication lifecycle and an OS credential store are not implemented here. |
| S8 | https://playwright.dev/python/docs/downloads | Browser download events, waiting for the download and persisting files. | A download event alone does not establish correct output. |
| S9 | https://docs.openadapt.ai/reference/capabilities/ | Published demonstration compiler, verification and execution capability boundaries. | Published statuses and named qualification evidence are not broad production reliability measurements. |
| S10 | https://playwright.dev/python/docs/api/class-route | Redirect-controlled request fetching and route fulfillment/abortion. | The lab redirect branch is unit-tested with a fake route; browser HTTP redirect integration is skipped in the supplied environment. |
| S11 | https://github.com/OpenAdaptAI/OpenAdapt | A close comparison for a demonstration-to-local-program approach and MIT-labelled repository. | No competitor implementation was independently benchmarked in this work. |

## Competitive implication

The basic idea of teaching a workflow and replaying it without constant inference already has substantial prior art. The product should differentiate on a defined user's teaching effort, verifiable results, maintenance burden, privacy and exception handling, not on a claim to have invented AI-assisted browser automation.

OpenAdapt is particularly close in its published framing. Workflow Use is another useful architectural reference, with a different stated maturity and licensing profile. The next useful competitive work is a matched-task evaluation, not another feature-list comparison.

## Sources not used as evidence

No Reddit anecdote, unverified benchmark, vendor price comparison, or claimed user-demand metric is used in this pack. No book, paper or competitor is claimed to have been fully reproduced. Prior conversation research is not treated as independent experimental evidence.

## Evidence produced in this work

`evidence/test-results.json` records test methods, skips and browser-fixture observations. `evidence/sample-run.json` records an actual local fixture run. `evidence/recorded-demonstration.json` and `evidence/compiled-demonstration.json` expose what the narrow teaching experiment captured and emitted. The test report explicitly separates those observations from the proposed product.

## v0.2 implementation references checked 23 October 2026

- Python `zoneinfo`: https://docs.python.org/3/library/zoneinfo.html — IANA timezone support, fold behavior and the tzdata fallback. The implementation is exercised on Python 3.13.5, not claimed to use the newest interpreter shown by the documentation site.
- Python `sqlite3`: https://docs.python.org/3/library/sqlite3.html — local transactions and database access. This does not by itself establish exactly-once effects outside SQLite.
- Playwright Python locators: https://playwright.dev/python/docs/locators — semantic locators and action-time resolution. Existing 1.57.0 is the version actually tested in this package.

These references inform design. Capability and test-result claims are supported by the supplied source and raw execution evidence, not by vendor documentation alone.


## v0.3 implementation references - checked 23 October 2026

- Playwright authentication: https://playwright.dev/python/docs/auth
- Playwright network handling: https://playwright.dev/python/docs/network
- Cryptography Fernet: https://cryptography.io/en/latest/fernet/

These sources informed state handling and request interception. They do not qualify our browser workflow or certify the supplied package. See SECURITY_MODEL_V03.md and TEST_REPORT.md for measured limits.
