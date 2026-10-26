"""Inspect login state without printing cookies, account details, or credentials."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from handnavigate.live.browser import open_driver, PRIVATE
from handnavigate.live.contracts import save_json
from handnavigate.transfer.download import PINTEREST_SCOPE
from handnavigate.transfer.profiles import checked_profile

out = ROOT/'runtime'/'pinterest-download'
profile = checked_profile(out/'profile', PINTEREST_SCOPE)
with open_driver(PINTEREST_SCOPE, out/'session-check', headless=True, profile=profile) as driver:
    driver.goto('https://www.pinterest.com/search/pins/?q=nature%20landscape')
    driver.page.wait_for_timeout(6000)
    cookies = driver.page.context.cookies(['https://www.pinterest.com'])
    result = {'url': driver.page.url.split('?')[0], 'gated_images': driver.page.locator('[data-test-id="gated-pin-image"]').count(),
              'pin_link_images': driver.page.locator('a[href*="/pin/"] img').count(),
              'visible_password_controls': driver.page.locator('input[type=password]:visible').count(),
              'pinterest_auth_flag': any(c['name']=='_auth' and c['value']=='1' for c in cookies),
              'has_session_cookie': any(c['name']=='_pinterest_sess' for c in cookies),
              'cookie_count':len(cookies), 'blocked_origins':list({r['url'].split('/')[2] for r in driver.blocked_requests})}
    save_json(out/'session-check.json', result)
    driver.page.screenshot(path=str(out/'session-check.png'), mask=[driver.page.locator(PRIVATE)])
    print(json.dumps(result, indent=2))
