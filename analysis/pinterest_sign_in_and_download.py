"""A human signs in in a normal dedicated browser; then the real downloader runs.

No credential recording, cookie export, stealth flags or challenge automation.
"""
from pathlib import Path
import json
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from playwright.sync_api import sync_playwright
from handnavigate.runner import chromium_options
from handnavigate.live.contracts import save_json
from handnavigate.transfer.download import PINTEREST_SCOPE, download_pinterest
from handnavigate.transfer.profiles import checked_profile

out = ROOT/'runtime'/'pinterest-download'
profile = checked_profile(out/'profile', PINTEREST_SCOPE)
status = out/'active-login-status.json'
ready = False
save_json(status, {'status':'WAITING_FOR_MANUAL_LOGIN'})
with sync_playwright() as p:
    # This phase is direct human browser use, including ordinary SSO popups.
    # The execution request scope is installed only by the downloader afterward.
    context = p.chromium.launch_persistent_context(str(profile), headless=False,
                                                  accept_downloads=False, **chromium_options())
    try:
        page = context.pages[0] if context.pages else context.new_page()
        page.goto('https://www.pinterest.com/search/pins/?q=nature%20landscape', wait_until='domcontentloaded')
        print('Sign in in the Pinterest window. The download starts automatically after Pinterest confirms login.', flush=True)
        until = time.monotonic()+1800
        while context.pages and time.monotonic() < until:
            cookies = context.cookies(['https://www.pinterest.com'])
            if any(c['name']=='_auth' and c['value']=='1' for c in cookies):
                ready = True
                save_json(status, {'status':'LOGIN_CONFIRMED'})
                break
            page.wait_for_timeout(1000)
    finally:
        context.close()
if not ready:
    save_json(status, {'status':'LOGIN_NOT_COMPLETED'})
    raise SystemExit(2)
print('Pinterest confirmed login. Downloading 20 images.', flush=True)
result = download_pinterest('nature landscape', 20, root=out)
save_json(status, {'status':result['status'], 'downloaded':result['downloaded'], 'folder':result['folder']})
print(json.dumps(result, indent=2), flush=True)
raise SystemExit(0 if result['status']=='VERIFIED' else 2)
