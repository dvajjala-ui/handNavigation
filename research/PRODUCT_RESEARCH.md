# HandNavigate product research and proposed first release

Research date: 22 October 2026. This is a feasibility and product proposal, not a working implementation. Vendor capabilities are documented claims, not independently tested results. Costs and policies can change. Roadmap durations and launch targets below are planning assumptions.

**Recommendation: build a product that turns a demonstrated browser task into a reviewed, reusable workflow. Run ordinary steps as code, verify the results, and use AI only when creating or repairing the workflow. Start with one permitted website and a narrow family of download/export tasks.**

The realistic promise is “Teach a task, approve the steps, and let it repeat—with evidence and help when something changes.” A promise to work on every website, phone, and desktop application forever without maintenance would be unsupported.

## What teaching means

The user demonstrates a task and explains its intent. The system saves a program containing variables, targets, loops, conditions, and checks. It does not need to update a foundation model's weights for each user.

For example, typing “architecture” once does not tell the recorder whether that word is permanent or changes daily. Downloading two images does not establish whether the intended loop is two images, ten images, every image, or only previously unseen images. The teaching UI must expose those choices.

There are three different capabilities:

| Capability | What is saved | AI needed on ordinary runs? |
|---|---|---|
| Exact macro | A fixed sequence | No, but little flexibility |
| Parameterized workflow | Steps, variables, loops, explicit branches, result checks | Often no |
| General agent | A goal and tools for discovering a path | Usually yes for novel decisions |

HandNavigate should primarily deliver the middle option. It can offer an agent as an optional assistant for creating and repairing workflows.

This has a long research history under programming by demonstration. [WebRobot, PLDI 2022](https://arxiv.org/abs/2203.09993) describes synthesizing web automation programs interactively from demonstrations and evaluates its approach on 76 benchmarks. This supports technical feasibility, not a guarantee of general live-site reliability.

## How GPT and Claude can operate a browser

A model does not directly possess mouse control. An application gives it observations and a defined set of actions. In a screenshot-based loop, the model receives the screen, requests actions, the application executes permitted actions, and the model receives an updated screen. The host application must still verify completion. This mechanism is described in the official [OpenAI computer-use documentation](https://developers.openai.com/api/docs/guides/tools-computer-use) and [Claude computer-use documentation](https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool). These API descriptions should not be treated as a complete account of every internal ChatGPT or Claude product implementation.

For a known website, we can often use browser structure directly: HTML elements, accessible names, labels, and relationships. [Playwright locators](https://playwright.dev/docs/locators) support this. The proposed execution order is an authorized official API where suitable, then semantic browser locators, then reviewed visual assistance when required. Do not use an undocumented private endpoint simply because browser traffic exposes it.

AI can propose the recipe; a constrained runtime executes it. Simple rules should stay rules. Randomly choosing a topic from a user-provided list, counting ten items, comparing dates, or skipping duplicate files does not require an LLM. Selecting images according to an ambiguous aesthetic preference may require AI on each run unless the user converts that preference into explicit filters.

## The proposed teaching experience

1. **Choose the site and task.** Explain what the automation may read, download, or change and where it will run.
2. **Demonstrate.** Record deliberate actions and relevant page state in a selected session. Pause capture for credentials and sensitive inputs.
3. **Explain the variables.** Turn topic, date, quantity, destination, and similar values into editable inputs.
4. **Show an alternate path.** For example, logged-in versus logged-out, an empty result, or a menu that opens before a download.
5. **Review the recipe.** Show readable steps and what counts as success. Highlight actions that affect other people, money, account settings, or remote data.
6. **Run together.** Let the user watch, pause, take over, and correct one step. Test fresh sessions and changed inputs, not only the original screen.
7. **Enable a schedule.** State the timezone, execution device, offline behavior, missed-run behavior, and limits.
8. **Report the result.** Show verified files or records, partial completion, skipped items, and anything requiring attention.

Corrections should create a versioned workflow update. They should not silently change the meaning of future runs. A few supervised successes are useful onboarding evidence but do not establish that all future branches are covered.

## Accuracy: checks matter more than replaying clicks

Each step needs a precondition, a target, an action, and a postcondition. A download step might require the expected domain, account, selected item, exactly one visible download control, and then a completed file whose content decodes as the expected type. A successful click is not evidence of a successful download.

Store several complementary target descriptions: an accessible role/name, stable attributes where available, the enclosing card or dialog, and an expected destination or relationship. Generated element IDs, absolute XPath, list position, and screen coordinates should not be the sole identity of an important target. Runtime snapshot references are generally temporary and must be resolved against fresh state.

[Playwright's actionability checks](https://playwright.dev/docs/actionability) already help with visibility, stability, enabled state, event reception, and unique matching. They cannot determine whether the selected account or business outcome is correct; HandNavigate must add those checks.

The proposed recovery order is:

1. Reobserve the page and allow a bounded wait for a known loading condition.
2. Try a previously approved equivalent locator or branch only when its preconditions match.
3. If enabled, ask AI to propose a repair using the smallest relevant page context.
4. Validate the proposal against permitted actions and expected results. Require user review for ambiguous or consequential changes.
5. Pause with a clear explanation when the result cannot be established.

Do not cycle through vaguely similar buttons until one works. Do not let a model's self-reported confidence authorize a risky action. A changed page can still contain a button with the same label and a different meaning.

For long workflows, record checkpoints and item identifiers, limit loops and retries, prevent overlapping runs on the same account, and reconcile uncertain results before retrying. A crash after a remote submission but before recording success must not lead automatically to a duplicate submission. Arbitrary browser interactions cannot provide universal exactly-once execution or rollback.

As an illustration, if 50 independent steps each succeeded with probability 0.99, complete-run success would be about 60.5%. Real failures are not independent, but the calculation explains why “usually clicks correctly” is insufficient.

## Applying this to the Pinterest example

The technical workflow is understandable: choose a topic, search, select a defined set of results, download permitted images, skip duplicates, and save an offline collection. The specification should resolve:

- Does “top ten” mean the first ten eligible results shown to this account, a popularity ranking, or the ten best according to taste?
- Are videos, ads, previously saved images, or low-resolution files excluded?
- If only seven eligible results exist, should the result be partial or should the search expand?
- Is the topic randomly chosen from a list or generated by AI?
- Which device must contain the files before the user loses connectivity?

The sensible deterministic definition is “the first ten unique eligible images in the results shown to this account at run time,” with explicit filters and a bounded scan. Do not imply those are a universal top ten. If the ranking criterion requires interpretation, AI costs may remain.

**Pinterest should not be the first production integration without an approved access route.** Its [current terms](https://policy.pinterest.com/en/terms-of-service) restrict unauthorized automated access, including collection and search; its [community guidelines](https://policy.pinterest.com/en/community-guidelines) also restrict unapproved automation. The terms page announces another update effective 12 November 2026, so recheck before integration. A user demonstrating the flow does not grant platform permission.

Pinterest documents a [manual image-download feature](https://help.pinterest.com/en/article/download-an-image). That does not establish permission to automate bulk collection or reuse every image. Content rights and the method of access are separate questions.

Use a user-owned asset library, an internal portal with authorization, or an explicitly permitted source for the proof of concept. Demonstrate the same search-select-download loop there. Verify ten actual files, retain source references, and report shortages accurately.

Downloading new remote images still needs internet at execution time. A cloud job can collect files while the user's phone is offline, but the phone must later connect and finish downloading before those files become available offline. “AI-free” and “internet-free” are different capabilities.

## Device support and execution location

| Experience | Proposed approach | Main limitation |
|---|---|---|
| Windows/macOS browser automation | Dedicated Chromium session with a desktop runner | Computer must be available and connected for web tasks |
| Phone controls a job | Responsive web dashboard controlling a paired runner | Phone is the controller; execution is elsewhere |
| Runs while every personal device is off | Cloud browser worker | Ongoing compute, authentication, storage, and data-transfer costs |
| Automation inside Safari on iPhone | Separate Safari extension/integration work | Background execution and access differ from desktop |
| Android native-app automation | Separate Android implementation and distribution review | Permissions and accessibility policy constrain behavior |
| Windows/macOS native-app automation | Later OS-specific adapters | Browser locators cannot control arbitrary native apps |

[Chrome alarms](https://developer.chrome.com/docs/extensions/reference/api/alarms) do not wake a sleeping device; missed repeating alarms are coalesced when it wakes. An extension is not an always-on scheduler. Apple's [background task documentation](https://developer.apple.com/documentation/BackgroundTasks/choosing-background-strategies-for-your-app) gives the system control over background scheduling, so an iPhone should not be promised as an unrestricted unattended browser worker.

The current [Google Play AccessibilityService policy](https://support.google.com/googleplay/android-developer/answer/10964491?hl=en) explicitly distinguishes deterministic, human-defined automation from prohibited autonomous planning/execution through that API, with a specific accessibility-tool exception. This distinction fits the recipe idea but does not automatically approve an Android app or remove other disclosure requirements.

For “open an app when the PC starts,” the OS already provides much of the machinery. [Microsoft documents configuring startup apps and the Startup folder](https://support.microsoft.com/en-au/windows/experience/startup-boot/configure-startup-applications-in-windows). HandNavigate would add value by helping users express a multi-step routine and inspect its outcome, not by recreating simple app startup.

## Competitors and building blocks

These overlap with different parts of the proposal. Capabilities below come from their documentation or product pages; they have not been tested in this project.

| Product | Relevant capability | Implication |
|---|---|---|
| [Browserflow](https://docs.browserflow.app/guides/building-a-flow) | Records browser actions as editable commands | Recording alone is already established |
| [Automa](https://github.com/AutomaApp/automa/blob/main/README.md) | Browser workflows assembled from blocks | Useful reference for visual editing; inspect licensing before reuse |
| [Ui.Vision](https://ui.vision/rpa) | Browser/visual automation and file-oriented workflows | Established alternative for users comfortable with macros |
| [Power Automate Desktop](https://learn.microsoft.com/en-us/power-automate/desktop-flows/recording-flow) | Desktop and web recording with UI selectors | Strong existing competition for Windows automation |
| [UiPath Task Mining](https://docs.uipath.com/task-mining/automation-cloud/latest/user-guide/assisted-task-mining-introduction) | Captures task variations and exports a task skeleton | Multiple demonstrations and process discovery are established ideas |
| [Skyvern](https://www.skyvern.com/products) | Recording, AI workflow creation, and cached Playwright execution | Very close to the proposed AI-then-code approach |
| [Stagehand / Browserbase](https://www.browserbase.com/templates/basic-caching) | AI browser actions with cached reuse that can avoid repeated model calls | Candidate component to evaluate rather than rebuild |
| [Browser Use](https://browser-use.com/developers) | Hosted agents and browser infrastructure, including scripted/agent handoffs | Another candidate runtime or repair component |
| [Bardeen](https://www.bardeen.ai/pricing) | Automation oriented toward go-to-market work | An example of focusing a broad engine on a specific customer group |

Skyvern explicitly advertises generated-code caching and repeat runs without the LLM. Browserbase provides a caching example with subsequent zero-LLM-call runs. These are evidence that the pattern exists; “show once, run forever” should be treated as marketing, not a reliability contract.

Automa's repository specifies AGPL or commercial licensing. Public source is not equivalent to unrestricted proprietary reuse. Check exact versions, licenses, and dependencies for any component before incorporating it.

The opportunity is therefore not invention of a new automation category. It is making task teaching, verification, correction, and ownership simpler for a particular group of users. A strong competitive comparison uses the same real task, changed inputs, a broken selector, an expired session, and measured support effort across tools.

## What community reports and case studies add

In this [r/Playwright discussion](https://www.reddit.com/r/Playwright/comments/1tuyf33/for_people_using_browser_automation_in_real_work/), practitioners report changed selectors, page-readiness problems, session failures, and manual review after failures. This is qualitative user evidence with a small self-selected sample, not a measured industry failure rate. I would use it to design tests and interviews, not to claim competitors are unreliable.

Browserbase's [Ramp case study](https://www.browserbase.com/blog/case-study-ramp) describes receipt retrieval from merchant portals and procurement research. It is a vendor-authored customer story, not an independent audit. The useful product lesson is the specific recurring business outcome and existing customer workflow; its scale figures should not become our own capacity assumptions.

For further reading, [Mind2Web](https://arxiv.org/abs/2306.06070) studies generalization across websites, while [WebArena](https://webarena.dev/static/paper.pdf) provides realistic multi-step environments and outcome-based evaluation. Their original model scores are historical and should not be presented as the limits of current models. Henry Lieberman's [Your Wish Is My Command: Programming by Example](https://shop.elsevier.com/books/your-wish-is-my-command/lieberman/978-1-55860-688-3) is useful background for designing teaching and correction interfaces; it is not a modern deployment guide.

## Proposed architecture

**First technical prototype:** TypeScript, Playwright, a dedicated headed Chromium profile, a small React interface, and SQLite for local recipes and run history. Package a desktop application only after the task engine works. Electron is a reasonable packaging candidate because it can host the Node-based runner; decide after measuring distribution and resource requirements.

The user logs into the dedicated automation browser directly. Do not copy their everyday browser's cookies into cloud infrastructure. Local and cloud execution should be visibly separate connections, with revocation and expiry handling.

| Component | Responsibility |
|---|---|
| Recorder | Capture deliberate actions and relevant target context; omit secrets |
| Recipe editor | Display inputs, ordered steps, branches, bounded loops, and checks |
| Workflow compiler | Convert demonstrations and explanations into a constrained schema; AI may assist |
| Validator | Reject unsupported actions, missing limits, invalid destinations, and ambiguous targets |
| Runner | Execute approved primitives, persist progress, and verify outcomes |
| Repair assistant | Suggest a bounded change, with evidence and version history |
| Scheduler | Trigger runs, apply timezone/missed-run rules, and enforce account locks |
| Artifact manager | Track completed files, hashes, source identities, and partial results |
| Run review | Explain failures and let users correct, resume, or disable a workflow |

A recipe should include its version, allowed domains, account reference, input schema, execution location, step definitions, expected results, timeout/retry limits, stop conditions, permission scope, and approval requirements. Store actual secrets in a protected vault or OS credential store, not inside the recipe or model prompt.

Start with a small action vocabulary: navigate, fill, choose, click, wait-for-condition, extract, download, bounded loop, explicit branch, assert, request help, and finish. General-purpose model-generated JavaScript should not execute with unrestricted access to the user's computer.

For a cloud pilot, add a responsive dashboard, authenticated API, Postgres, artifact storage, a durable job queue, and isolated browser workers. Supabase is a possible choice for auth/database/storage; the actual browser workers belong in suitable worker processes or managed browser infrastructure, not inside a short-lived database/edge request. Run one job per connected account at a time initially. Use leases, heartbeats, duplicate suppression, cancellation, and a maximum runtime. Keep the runner interface provider-neutral, but implement only one provider initially.

For a small pilot, managed browsers can reduce infrastructure work. Self-hosting becomes worth evaluating only when measured costs, session requirements, or control needs justify the operational burden. A dedicated browser context reduces accidental state sharing; it should not be treated as a complete isolation boundary for hostile executable code.

### Extension distribution constraint

An extension can later help users teach workflows in their existing browser, with narrow site permissions and a packaged recorder. [Chrome native messaging](https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging) can connect it to an installed companion application.

However, [Chrome Web Store policy](https://developer.chrome.com/docs/webstore/program-policies/policies) restricts remotely hosted code and interpreters for complex remotely fetched commands, even when represented as data. Do not assume that converting generated code into JSON makes an extension compliant. Review the exact design early; keep automation execution in the companion or isolated cloud runner when appropriate. This architecture choice is not a promise of store approval.

### Model routing

| Situation | Proposed handling |
|---|---|
| Reviewed workflow with matching checks | No model call |
| Explicit known alternate path | Ordinary conditional code |
| Simple candidate mapping in a constrained repair | Evaluate a lower-cost model against the task benchmark |
| Difficult initial interpretation or complex repair | Stronger model, with bounded tools and review |
| Ambiguous target, expired login, unknown consequences | Ask the user or pause |

Do not purchase GPUs or fine-tune a model for the first release. Gather consented examples of failures and corrections, remove sensitive data, and measure whether a later smaller model offers meaningful savings. Training costs are unnecessary if validated scripts already handle most runs.

Treat website text as data, not as permission to change the workflow. Enforce destination restrictions, action permissions, and resource limits outside the model. For login challenges and CAPTCHA, hand control to the user or pause; bypassing protections should not be a product dependency.

## Proposed UI

The primary interface should be understandable without a node graph. An advanced graph can come later.

| Screen | Main content and action |
|---|---|
| My routines | Task name, site, execution location, next run, last outcome; Teach a task |
| Teaching | Active recording indicator, captured steps, pause and stop; Mark as variable |
| Review | Readable recipe, inputs, result checks, permissions, schedule; Run with me |
| Run | Current step, completed artifacts, exact stopping reason; Pause / Take over |
| Needs attention | Expected state versus observed state; Correct this step / Disable |
| History and connections | Run evidence, workflow versions, connected accounts/devices; Revoke / Delete |

Use honest statuses: Ready, Running, Waiting for device, Waiting for internet, Needs login, Needs review, Completed, and Partially completed. Show local versus cloud storage clearly. An offline collection must show which files are actually downloaded on the current device.

User-selected operation modes could be “Ask before each run,” “Run the approved recipe,” and “Allow limited AI repair.” Consequential actions retain their own permission requirements. A no-AI mode should pause on unfamiliar changes rather than silently switching to a model.

## Economics and product positioning

Zero model calls do not make a cloud run free. Track browser minutes, compute, bandwidth, storage, model usage during teaching/repair, and human support. The useful metric is cost per verified successful run, including retries and failures.

Illustration: 100 users, one two-minute run daily, and 30 days produce 100 browser hours before setup and retries. At the research date, [Browserbase's pricing page](https://www.browserbase.com/pricing) lists a $20/month Developer tier with 100 browser hours and $0.12/hour overage. This is only a browser infrastructure reference, not the total cost of HandNavigate or a quote for an unrestricted agent service.

For the image example, ten 2 MB images daily across those users would produce roughly 60 GB of new image data a month, excluding page traffic. Storage, synchronization, and especially metered proxy traffic can materially exceed model costs. Estimate them separately; do not assume all traffic needs a proxy. Local execution transfers most browser compute to the user's device but adds installer, support, and availability costs.

An illustrative monthly model budget is: teaching sessions multiplied by observed teaching cost, plus failed runs needing repair multiplied by observed repair cost. The repair rate is an unknown to measure. Do not claim a 90% or 99% AI reduction until logs establish it for the selected workflows.

My initial customer hypothesis is people repeatedly collecting reports or assets from the same permitted portal. Interview users before choosing the commercial vertical. Consumer Pinterest downloading may demonstrate a desire, but platform permission and willingness to pay make it a weak foundation for the first business.

Use a subscription with explicit local features and metered cloud usage as a pricing hypothesis. Test willingness to pay before fixing prices. Avoid unlimited cloud execution until costs are measured. Strong differentiation could be a fast teaching experience, accurate result verification, private local execution, easy repair, and exportable recipes.

Prompt sequencing across AI tools is a possible later workflow. Prefer a provider's supported API where available, and preserve budgets, output checks, stop conditions, and context explicitly. Repeatedly opening chats does not by itself preserve context or establish permission to bypass service limits. Automated social engagement is not a recommended launch niche; Instagram's current terms pages returned HTTP 429 during this research, so this brief does not claim that specific Instagram automation is permitted.

## Build order and acceptance criteria

These are proposed milestones, not a delivery commitment. Roughly six to eight weeks for a narrow private pilot may be plausible with an experienced full-time engineer and a cooperative target site. A reliable public product, native mobile execution, and arbitrary-site coverage are substantially larger projects.

| Phase | Work | Evidence required to proceed |
|---|---|---|
| Discovery | Interview about ten prospective users; select one site and recurring task family; verify permitted access | Several users repeat the task often and agree to test it; clear permission path |
| Deterministic core | Implement one parameterized workflow and checks without AI | Changed inputs work; duplicate execution, timeout, and partial download are handled |
| Teaching | Add recording, editable inputs, and AI-assisted recipe drafting | New users can inspect and correct what was inferred |
| Reliability | Add alternate paths, state checks, versioning, checkpoints, and takeover | Deliberate UI/session/network failures stop or recover correctly |
| Private pilot | Add scheduling, run history, device status, limited repair, and optional cloud execution | Repeat use with measured cost and intervention burden |
| Expansion | Add adjacent workflows and another supported site | Existing reliability and support costs remain acceptable |

Suggested pilot targets: at least five users voluntarily retain a weekly routine over four weeks; at least 95% verified completion on eligible supported runs; at least 90% of those runs need no model call; zero observed unintended external changes. These are targets, not current results or safety guarantees. Report all scheduled-run availability separately so sleeping devices and expired sessions do not disappear from the statistics. Track both completion with assistance and completion without intervention.

Build a test matrix covering changed text, duplicate buttons, reordered results, slower loading, account expiry, empty results, missing downloads, duplicated images, interrupted transfers, worker crashes, resume after a side effect, overlapping schedules, timezone changes, malicious page instructions, and unsupported page layouts. Test supported Windows/macOS configurations independently. A finite test suite cannot prove permanent correctness.

Stop expanding scope if users spend more time repairing routines than they save, access depends on fighting platform restrictions, model calls remain necessary for almost every run, or users do not return after the novelty wears off. Revisit the customer segment or task family before building more infrastructure.

**The first concrete engineering experiment should prove that a demonstrated search-and-download task on one permitted site can become a parameterized recipe, pass supervised review, and complete repeated runs with the model disabled while correctly detecting deliberate failures.**
