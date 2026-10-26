from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from handnavigate.live.browser import open_driver
from handnavigate.live.contracts import Scope, save_json

scope = Scope(('https://www.pinterest.com', 'https://in.pinterest.com', 'https://s.pinimg.com', 'https://i.pinimg.com'),
              ('GET', 'HEAD', 'OPTIONS', 'POST'), 200)
out = ROOT/'runtime'/'pinterest-pin-inspection'
with open_driver(scope, out, headless=True) as d:
    d.goto('https://www.pinterest.com/search/pins/?q=nature%20landscape')
    d.page.locator('img[srcset]').first.wait_for(state='attached', timeout=15000)
    pins = d.page.locator('img[srcset]').evaluate_all('els=>els.map(i=>({pin:i.closest("a")?.href,src:i.currentSrc||i.src,srcset:i.srcset,alt:i.alt,parents:Array.from((function*(e){for(let n=0;e&&n<5;n++,e=e.parentElement)yield e})(i.parentElement)).map(e=>({tag:e.tagName,id:e.id,testid:e.getAttribute("data-test-id"),role:e.getAttribute("role"),text:e.innerText?.slice(0,100)}))}))')
    result = {'count':len(pins), 'pins':pins}
    save_json(out/'pins.json', result)
    print(json.dumps(result, indent=2))
