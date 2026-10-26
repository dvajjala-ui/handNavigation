# HandNavigate live-browser core: local run guide

For the implemented image download/upload core, start with [CORE_WORKFLOW.md](CORE_WORKFLOW.md). Windows: `handnavigate.cmd demo` runs a complete owned two-site transfer. `live transfer init/teach/run` configures real site pairs; `schedule/worker` repeats verified recipes without AI. The older experimental browser guide below remains relevant for individual actions and recordings.

**Status: experimental development module, not a qualified release.** The code accepts real URLs and has no synthetic-site fallback. External browser navigation and live-model operation could not be validated in this environment. The old studio UI still opens its practice workflow; use the `live` CLI below for the new browser core.

## Setup

Use the included `handnavigate-lab` folder and Python 3.11 or newer. Prefer a virtual environment.

```text
python -m venv .venv
```

Activate `.venv` in your shell, then:

```text
python -m pip install -r requirements.txt
python -m playwright install chromium
python -m handnavigate live --help
```

The new provider adapter uses the Python standard library; it does not require another AI SDK. Browser policies remain in force. Do not disable organizational browser protections to make a test pass.

## First check: observe an actual public test page

Playwright publishes the following TodoMVC demonstration specifically for testing. The example below is an authored acceptance check, NOT a result that passed here.

```text
python -m handnavigate live inspect --url https://demo.playwright.dev/todomvc/ --authorized-site --out live-runs/inspect
```

This should open a visible browser, navigate to the URL, and save a bounded control/text snapshot and screenshot. `OBSERVED` only means navigation and observation succeeded; it does not mean a task completed.

For a headless diagnostic:

```text
python -m handnavigate live doctor --url https://demo.playwright.dev/todomvc/ --authorized-site --out live-runs/doctor
```

A blocked navigation returns a nonzero exit status. There is no localhost simulation fallback.

## AI-free real-site replay acceptance example

Review `examples/live-todomvc.workflow.json`. It fills the public demo's task input, presses Enter, checks the displayed task, and checks that the input cleared. `examples/live-todomvc.inputs.json` holds the explicit task variable.

Approve the exact recipe and inputs:

```text
python -m handnavigate live approve examples/live-todomvc.workflow.json --inputs examples/live-todomvc.inputs.json --out live-runs/todo.approval.json
```

The command prints the actual recipe and requires typing `APPROVE` locally. Then run:

```text
python -m handnavigate live replay examples/live-todomvc.workflow.json --inputs examples/live-todomvc.inputs.json --approval live-runs/todo.approval.json --authorized-site --out live-runs/todo-replay
```

No AI provider is called by replay. Changing a parameter, selector, action or check invalidates the receipt and requires renewed approval. No approval receipt is pre-bundled for this public-site example.

The default session is temporary. Using a persistent profile can retain prior state, so repeating a non-idempotent action can create duplicates. This runner does not guarantee exactly-once external effects.

## Teach by demonstration

```text
python -m handnavigate live record --url https://demo.playwright.dev/todomvc/ --authorized-site --expect-text "HandNavigate browser core check" --out live-runs/recorded
```

In the opened browser, enter the exact task text and press Enter. Return to the terminal and press Enter to end recording. Inspect `recording.json`, `recording-report.json` and `workflow.draft.json`.

Recordings are drafts. Private controls and unsupported interactions block compilation. Review the sequence and locators, add meaningful completion checks, and parameterize values explicitly. Example:

```json
{"op":"fill","locator":{"kind":"label","value":"Topic"},"value":{"parameter":"topic"}}
```

Supply `{"topic":"architecture"}` in an inputs file. The compiler does not infer loops, variables, alternative routes or task meaning from one demonstration. A missing output check cannot be replaced by the model saying "done".

## Let AI choose supervised browser actions

Rotate the key contained in the uploaded capture ZIP. Set a fresh `GROQ_API_KEY` in your local process environment. Do not paste it into chat, put it in the source archive, or send it through a webpage.

Example using a tool-capable Groq model documented at the time of review:

```text
python -m handnavigate live agent --url https://demo.playwright.dev/todomvc/ --authorized-site --allow-ai --model openai/gpt-oss-120b --goal "Add one todo named HandNavigate browser core check, then stop." --expect-text "HandNavigate browser core check" --out live-runs/agent
```

The runtime sends bounded page text/control observations to Groq, requests one tool call, prints the proposed action, and asks `Execute this action? Type y:`. After execution, it sends a fresh observation. This can incur provider charges. The provided key was not used to test this path.

A successful supervised run writes `workflow.draft.json`; it is not automatically approved. Review and approve it, then replay through the same no-AI path above.

Screenshots are local by default. `--send-screenshots` explicitly includes images in model requests, only for a model that supports both image input and the necessary tool calling. That compatibility and live vision operation are unqualified here. The example GPT-OSS command is the text/control path, not a claim of vision support.

## Login and website dependencies

A separate dedicated profile can retain the site's login state:

```text
python -m handnavigate live record --url https://YOUR-AUTHORIZED-SITE.example --authorized-site --allow-method POST --profile live-profiles/my-site --manual-login --out live-runs/my-site-recording
```

Replace the placeholder with the actual authorized site. The person signs in manually before recording or sending content to AI. A new profile is created only in a dedicated directory; regular browser profile directories are rejected. Profile directories are sensitive and must not be included in exports. This development build does not integrate these profiles with the previous encrypted vault or provide an unattended credential service.

Only the starting origin and GET/HEAD/OPTIONS requests are allowed by default. Modern sites may need explicitly listed API/CDN/login origins and POST requests. Add exact origins with repeated `--allow-origin https://host` flags and permitted methods with `--allow-method POST`. Review blocked request metadata instead of granting a wildcard. A changed profile origin scope requires a separate profile.

These are application-level constraints, not an OS-level security boundary or an authorization grant from the website. WebSockets and service workers are blocked; sites requiring them may not work. Main-frame controls only: no iframe, popup, canvas, drag-and-drop or upload support in this module.

## Reuse your TruStudio capture

Your ZIP contains the capture tool, not a completed capture session. After using that tool on an authorized site, import its generated `capture.json`:

```text
python -m handnavigate live import-trustudio PATH-TO-CAPTURE/capture.json --flow F001 --out live-runs/imported
```

The importer never reads `.env`, HAR files, session cookies or source maps. It imports captured actions and marks missing/private/ambiguous information as blockers. It does not call AI or automatically run the imported actions.

Important: the original tool truncates values and does not reliably preserve checkbox state. A captured `on` value cannot become a guessed `checked=true`. Review report warnings and recapture such interactions. Captured redacted URLs and incomplete long text need human correction. Change a click that intentionally starts a download into the explicit `download` action and define the expected result.

## Evidence and limits

`result.json` reports `VERIFIED` only when the configured checks pass. That is not proof of all business semantics. A file count check proves a count; a hash check proves matching bytes. Neither automatically establishes licensing, visual relevance, or permission to download.

The runner writes action intent before execution. Failures become halted or uncertain work; there is no automatic replay of a failed external action. A website can change state before a timeout, so inspect the real site before retrying.

Local snapshots/screenshots/recordings may contain private data despite heuristic masking. No HAR, complete DOM dump, JS bundle download, cookies or authorization headers are intentionally sent to the model. This does not make all visible page text safe to share. Use `--allow-ai` only with data you are authorized to send.

## Reproduce component tests

```text
python -m pip install -r requirements-dev.txt
python -m pytest tests/live -q
python build_live_evidence.py
```

These use explicit offline owned documents and a scripted provider to verify the protocol. They do not qualify a remote site or a live LLM. The sample output labels that distinction.

The old `python run_tests.py` remains the previous suite. Its current full rerun timed out; do not interpret historical v0.4 reports as a current complete regression pass.
