"""A narrow demonstration recorder and transparent, deterministic compiler.

It records local top-level fill/click interactions. It does NOT infer intent,
loops, verifiers, fallbacks, authentication, or arbitrary website behavior.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from .contracts import ContractError, validate_recipe

RECORDER_SCRIPT = r'''
(() => {
 if(window.top!==window || window.__handnavigateRecorder) return;
 window.__handnavigateRecorder=true;
 const sensitive = el => el.type==='password' || el.hasAttribute('data-private') ||
   /password|one-time-code|cc-|credit/i.test(el.autocomplete||'');
 const label = el => (el.getAttribute('aria-label') ||
   (el.labels && [...el.labels].map(x=>x.textContent.trim()).join(' ')) || '').trim();
 document.addEventListener('change',e=>{
   const el=e.target;
   if(!(el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement))return;
   if(sensitive(el)){window.__hnCapture({op:'redacted',reason:'sensitive_field'});return;}
   const name=label(el);
   if(name) window.__hnCapture({op:'fill',target:[{by:'label',value:name}],value:el.value});
 },true);
 document.addEventListener('click',e=>{
   const el=e.target.closest('button,a,[role="button"]');
   if(!el || sensitive(el))return;
   const name=(el.getAttribute('aria-label')||el.textContent||'').trim();
   if(!name)return;
   if(el.matches('a[download]')){
     window.__hnCapture({op:'unsupported',reason:'download_requires_explicit_effect_contract'});return;
   }
   window.__hnCapture({op:'click',target:[{by:'role',role:el.tagName==='A'?'link':'button',name}]});
 },true);
})();
'''


class Recorder:
    def __init__(self):
        self.events: list[dict] = []

    def attach(self, page) -> None:
        def capture(_source, event):
            if isinstance(event, dict):
                self.events.append(event)
        page.expose_binding("__hnCapture", capture)
        page.add_init_script(RECORDER_SCRIPT)
        page.evaluate(RECORDER_SCRIPT)

    def save(self, path: Path | str) -> None:
        Path(path).write_text(json.dumps({"schema_version": 1, "events": self.events}, indent=2))


def compile_recording(events: list[dict], *, example_topic: str,
                      ready_test_id: str | None = None) -> dict:
    """Parameter binding is explicitly supplied by the reviewer, not guessed."""
    if not isinstance(events, list) or not isinstance(example_topic, str) or not example_topic or len(example_topic) > 80 or len(events) > 100:
        raise ContractError("Missing example topic or recording too large")
    steps: list[dict] = []
    for event in events:
        if not isinstance(event, dict):
            raise ContractError("Every recorded event must be an object")
        if event.get("op") == "redacted":
            raise ContractError("Recording includes a private step; this compiler cannot safely omit it")
        if event.get("op") not in ("fill", "click"):
            raise ContractError("Recording includes an unsupported action; review it rather than dropping it")
        action = deepcopy(event)
        if action["op"] == "fill":
            if action.get("value") != example_topic:
                raise ContractError("Every captured fill needs an explicit parameter binding")
            action["value"] = "{{topic}}"
            if steps and steps[-1]["op"] == "fill" and steps[-1]["target"] == action["target"]:
                steps.pop()
        action["id"] = f"recorded-{len(steps) + 1}"
        steps.append(action)
    if not steps:
        raise ContractError("No supported actions were recorded")
    if ready_test_id is not None and (not isinstance(ready_test_id, str) or not ready_test_id or len(ready_test_id) > 150):
        raise ContractError("Invalid explicitly reviewed ready-state identifier")
    if ready_test_id:
        steps.append({"id": "reviewed-postcondition", "op": "wait",
                      "target": [{"by": "testid", "value": ready_test_id}]})
    recipe = {"schema_version": 1, "id": "recorded-search", "revision": 1,
              "name": "Recorded search - explicit review required",
              "parameters": {"topic": "string", "limit": "integer"}, "steps": steps}
    validate_recipe(recipe)
    return recipe
