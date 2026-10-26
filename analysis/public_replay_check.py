"""Audit-only public demo check; temporary contexts, no credentials or model calls."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from handnavigate.live.browser import open_driver
from handnavigate.live.contracts import Scope, approval, save_json
from handnavigate.live.workflows import replay

workflow = json.loads((ROOT / 'examples/live-todomvc.workflow.json').read_text())
results = []
for index in (1, 2):
    inputs = {'todo_text': f'HandNavigate audit example {index}'}
    receipt = approval(workflow, inputs)
    scope = Scope(tuple(workflow['scope']['origins']), tuple(workflow['scope']['methods']), workflow['scope']['max_actions'])
    out = ROOT / 'analysis' / f'public-replay-{index}'
    with open_driver(scope, out, headless=True) as driver:
        driver.goto(workflow['start_url'])
        result = replay(driver, workflow, inputs, receipt)
    results.append({'run': index, 'inputs': inputs, 'result': result})
summary = {'scope': 'Public TodoMVC demo only; temporary browser contexts; receipts issued by audit harness, not an interactive operator review', 'runs': results}
save_json(ROOT / 'analysis' / 'public-replay-summary.json', summary)
print(json.dumps(summary, indent=2))
raise SystemExit(0 if all(r['result']['status'] == 'VERIFIED' for r in results) else 1)
