"""Manual sign-in only. No recording, credential inspection, screenshots or model calls."""
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from handnavigate.live.browser import open_driver
from handnavigate.live.contracts import Scope, save_json
from handnavigate.transfer.profiles import checked_profile

out = ROOT/'runtime'/'pinterest-download'
scope = Scope(('https://www.pinterest.com', 'https://in.pinterest.com', 'https://s.pinimg.com', 'https://i.pinimg.com',
               'https://www.recaptcha.net', 'https://www.gstatic.com'), ('GET', 'HEAD', 'OPTIONS', 'POST'), 200)
profile = checked_profile(out/'profile', scope)
with open_driver(scope, out/'login-browser', headless=False, profile=profile) as driver:
    driver.goto('https://www.pinterest.com/search/pins/?q=nature%20landscape')
    print('Pinterest window open. Sign in manually; no credentials are recorded.', flush=True)
    until = time.monotonic()+900
    while not driver.page.is_closed() and time.monotonic() < until:
        if (out/'finish-login').exists():
            break
        driver.page.wait_for_timeout(500)
    save_json(out/'login-window-status.json', {'closed':driver.page.is_closed(), 'profile_saved':True})
