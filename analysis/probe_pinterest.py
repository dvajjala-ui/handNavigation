"""Observe Pinterest through the project's actual browser; never use fixture content."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from handnavigate.live.browser import open_driver
from handnavigate.live.contracts import Scope, save_json

out = ROOT/'runtime'/'pinterest-probe'
scope = Scope(('https://www.pinterest.com', 'https://in.pinterest.com', 'https://s.pinimg.com', 'https://i.pinimg.com'),
              ('GET', 'HEAD', 'OPTIONS', 'POST'), 200)
try:
    with open_driver(scope, out, headless=True) as d:
        d.goto('https://www.pinterest.com/search/pins/?q=nature%20landscape')
        d.page.wait_for_timeout(5000)
        data = {'url': d.page.url, 'title': d.page.title(), 'text': d.page.locator('body').inner_text()[:5000],
                'images': d.page.locator('img').evaluate_all('(images) => images.slice(0,35).map(i=>({src:i.currentSrc||i.src,alt:i.alt,srcset:i.srcset,width:i.naturalWidth,height:i.naturalHeight}))'),
                'controls': d.page.locator('button,input').evaluate_all('(els)=>els.slice(0,30).map(e=>({tag:e.tagName,type:e.type,label:e.getAttribute("aria-label"),text:e.innerText}))'),
                'blocked_requests': d.blocked_requests}
        d.page.screenshot(path=str(out/'page.png'))
        save_json(out/'state.json', data)
        print(json.dumps(data, indent=2))
except Exception as exc:
    save_json(out/'failure.json', {'type':type(exc).__name__, 'error':str(exc)[:1200]})
    print(type(exc).__name__+': '+str(exc)[:1200])
    raise SystemExit(2)
