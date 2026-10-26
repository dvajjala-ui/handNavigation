"""Owned HTTP smoke check for the actual in-page teaching picker (not a human study)."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from handnavigate.live.browser import open_driver
from handnavigate.live.contracts import save_json
from handnavigate.transfer.contracts import validate
from handnavigate.transfer.demo import running_demo
from handnavigate.transfer.teaching import PICKER

choices = {}
with running_demo(count=4) as (recipe, _, _, _):
    scopes = validate(recipe)
    for side, scope in zip(('source', 'target'), scopes):
        with open_driver(scope, ROOT/'runtime'/'teaching-picker-check'/side, headless=True) as driver:
            driver.goto(recipe[side]['url'])
            if side == 'target':
                driver.page.locator('#gallery').evaluate("el => el.style.minHeight='100px'")
            driver.page.evaluate(PICKER, {'kind': side})
            driver.page.locator('article img' if side == 'source' else '#gallery').first.click()
            choices[side] = driver.page.evaluate('window.__hnPicked')
assert choices['source']['matches'] == 4, choices
assert choices['target']['selector'] == '#gallery img', choices
result = {'status': 'PASS', 'scope': 'Playwright-driven picker on real owned HTTP pages; not observed human teaching', 'choices': choices}
save_json(ROOT/'evidence'/'transfer-core'/'teaching-picker-smoke.json', result)
print(json.dumps(result, indent=2))
