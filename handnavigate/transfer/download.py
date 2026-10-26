"""Download a real site's image listing directly to local Downloads; no upload target."""
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import quote, urlsplit

from playwright.sync_api import Error as BrowserError, TimeoutError as BrowserTimeout, sync_playwright

from ..live.browser import open_driver
from ..live.contracts import LiveError, Scope, public_url, save_json
from ..ownership import RuntimeOwnership
from ..runner import chromium_options
from .files import image_metadata, read_url
from .profiles import checked_profile

PINTEREST_SCOPE = Scope(('https://www.pinterest.com', 'https://in.pinterest.com', 'https://s.pinimg.com',
                         'https://i.pinimg.com', 'https://www.recaptcha.net', 'https://www.gstatic.com'),
                        ('GET', 'HEAD', 'OPTIONS', 'POST'), 200)

LIMITS = {'max_bytes': 25*1024*1024, 'max_pixels': 40_000_000, 'min_width': 128, 'min_height': 128}


def manual_pinterest_signin(profile, url, timeout_seconds=1800):
    """Direct human sign-in, including normal SSO tabs; no recorder or agent actions.

    Only this human phase permits ordinary popup navigation. The normal reviewed
    request guard is installed again for image collection after the browser closes.
    """
    if profile is None:
        raise LiveError('Manual sign-in needs a dedicated saved browser profile')
    confirmed = False
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(str(profile), headless=False, accept_downloads=False,
                                                      **chromium_options())
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(url, wait_until='domcontentloaded')
            print('Complete sign-in in the Pinterest window. Downloading starts automatically when Pinterest confirms the session.', flush=True)
            until = time.monotonic()+timeout_seconds
            while context.pages and time.monotonic() < until:
                cookies = context.cookies(['https://www.pinterest.com'])
                if any(c['name']=='_auth' and c['value']=='1' for c in cookies):
                    confirmed = True
                    context.pages[0].wait_for_timeout(500)
                    break
                context.pages[0].wait_for_timeout(500)
        except BrowserError:
            confirmed = False
        finally:
            try:
                context.close()
            except BrowserError:
                pass  # A human may have closed the login window already.
    if not confirmed:
        raise LiveError('PINTEREST_LOGIN_REQUIRED: manual sign-in was not completed')


def downloads_folder():
    if os.name == 'nt':
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r'Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders') as key:
                value, _ = winreg.QueryValueEx(key, '{374DE290-123F-4565-9164-39C4925E467B}')
                return Path(os.path.expandvars(value)).resolve()
        except OSError:
            pass
    return Path.home()/'Downloads'


def image_urls(item):
    """Use only the resolutions actually advertised by the page; never invent URLs."""
    choices = []
    for option in item.get('srcset', '').split(','):
        fields = option.strip().split()
        if not fields:
            continue
        score = 1.0
        if len(fields) > 1 and re.fullmatch(r'[\d.]+[wx]', fields[-1]):
            try: score = float(fields[-1][:-1])
            except ValueError: continue
        choices.append((score, fields[0]))
    choices.sort(key=lambda c: c[0], reverse=True)
    urls = [url for _, url in choices]
    if item.get('src'):
        urls.append(item['src'])
    return list(dict.fromkeys(urls))


PIN_IMAGES = r'''els => els.map(i => {
  const pin=i.closest('a[href*="/pin/"]') || i.closest('[data-test-id="pin"]')?.querySelector('a[href*="/pin/"]');
  return {pin:pin?.href || null,src:i.currentSrc||i.src,srcset:i.srcset||'',alt:i.alt||'',
          gated:!!i.closest('[data-test-id="gated-pin-image"]')};
})'''


class LocalDownload:
    def __init__(self, *, url, scope, count, folder, root, selector='img', pinterest=False,
                 profile=None, headless=True, timeout_seconds=300):
        if type(count) is not int or not 1 <= count <= 100:
            raise LiveError('Image count must be an integer from 1 to 100')
        scope.check(url)
        self.url, self.scope, self.count = url, scope, count
        self.folder, self.root = Path(folder).resolve(), Path(root).resolve()
        self.selector, self.pinterest, self.headless = selector, pinterest, headless
        self.profile = checked_profile(profile, scope) if profile else None
        self.timeout_seconds = timeout_seconds
        self.deadline = time.monotonic()+timeout_seconds
        self.report = {'schema': 'handnavigate.local-download.v1', 'status': 'HALTED', 'source': public_url(url),
                       'request_sha256': sha256(url.encode()).hexdigest(), 'requested':count, 'downloaded':0,
                       'folder':str(self.folder), 'model_calls':0, 'items':[], 'error':None}
        self.manifest = self.folder/'handnavigate-manifest.json'
        self.owns_manifest = not self.manifest.exists()
        self.manual_login = False

    def check(self):
        if time.monotonic() >= self.deadline:
            raise LiveError('Download time budget exhausted; validated files are preserved')

    def verify_local(self, item):
        name = item['file']
        path = (self.folder/name).resolve()
        if Path(name).name != name or not path.is_relative_to(self.folder) or not path.is_file():
            raise LiveError('A previously downloaded image is missing or has an unsafe path')
        with path.open('rb') as file:
            meta = image_metadata(file.read(LIMITS['max_bytes']+1), LIMITS)
        if any(item.get(key) != value for key, value in meta.items()):
            raise LiveError('A previously downloaded image changed; it will not be silently overwritten')

    def save(self):
        self.report['downloaded'] = len(self.report['items'])
        if self.owns_manifest:
            save_json(self.manifest, self.report)
        save_json(self.root/'download-result.json', self.report)

    def blocked(self, page):
        if not self.pinterest:
            return False
        # Do not extract gated previews, remove overlays, or bypass sign-in/challenges.
        return (page.locator('[data-test-id="gated-pin-image"]').count() > 0 or
                page.locator('input[type=password]:visible').count() > 0 or
                '/login' in urlsplit(page.url).path)

    def run(self):
        self.root.mkdir(parents=True, exist_ok=True)
        self.folder.mkdir(parents=True, exist_ok=True)
        owner = RuntimeOwnership(self.root)
        try:
            if self.manifest.exists():
                prior = json.loads(self.manifest.read_text(encoding='utf-8'))
                if prior.get('schema') != self.report['schema'] or prior.get('request_sha256') != self.report['request_sha256']:
                    raise LiveError('This folder belongs to a different download; choose another folder')
                items = prior.get('items', [])
                if not isinstance(items, list) or len(items) > self.count:
                    raise LiveError('The existing download has more files than this request; choose another folder')
                self.report['items'] = items
                for item in items:
                    self.verify_local(item)
                self.owns_manifest = True
            if len(self.report['items']) < self.count:
                if self.manual_login:
                    manual_pinterest_signin(self.profile, self.url)
                    self.deadline = time.monotonic()+self.timeout_seconds
                with open_driver(self.scope, self.root/'browser', headless=self.headless, profile=self.profile) as driver:
                    driver.goto(self.url)
                    if self.pinterest and any(c['name']=='_auth' and c['value']=='1'
                                              for c in driver.page.context.cookies(['https://www.pinterest.com'])):
                        # A signed-in page may initially hydrate guest markup. Wait
                        # for that UI to settle; do not delete or evade its login gate.
                        try:
                            driver.page.locator('[data-test-id="gated-pin-image"]').first.wait_for(state='detached', timeout=15000)
                        except BrowserTimeout:
                            raise LiveError('PINTEREST_LOGIN_REQUIRED: Pinterest did not accept the saved session') from None
                    try:
                        driver.page.locator(self.selector).first.wait_for(state='attached', timeout=15000)
                    except BrowserTimeout:
                        if self.blocked(driver.page):
                            raise LiveError('PINTEREST_LOGIN_REQUIRED: sign in in the dedicated Pinterest window first')
                        raise LiveError('No matching images appeared in the actual page') from None
                    seen = {i['source_id'] for i in self.report['items']}
                    hashes = {i['sha256'] for i in self.report['items']}
                    for _ in range(25):
                        self.check()
                        driver.check_page()
                        if self.blocked(driver.page):
                            raise LiveError('PINTEREST_LOGIN_REQUIRED: search images are gated; sign in manually to continue')
                        candidates = driver.page.locator(self.selector).evaluate_all(PIN_IMAGES)
                        for item in candidates[:500]:
                            self.check()
                            if len(self.report['items']) >= self.count:
                                break
                            if item['gated']:
                                continue
                            if self.pinterest:
                                pin = item.get('pin')
                                if not pin or not re.match(r'^/pin/\d+/?$', urlsplit(pin).path):
                                    continue
                                self.scope.check(pin)
                                source_id = pin
                            else:
                                source_id = item.get('src')
                            if not source_id or source_id in seen:
                                continue
                            seen.add(source_id)
                            data = None
                            for url in image_urls(item):
                                if self.pinterest and urlsplit(url).hostname != 'i.pinimg.com':
                                    continue
                                try:
                                    data = read_url(driver.page.context, self.scope, url, LIMITS['max_bytes'], self.deadline)
                                    break
                                except LiveError as exc:
                                    if 'Image HTTP 404' not in str(exc):
                                        raise
                            if data is None:
                                continue
                            meta = image_metadata(data, LIMITS)
                            if meta['sha256'] in hashes:
                                continue
                            name = f"pinterest-{len(self.report['items'])+1:02d}-{meta['sha256'][:16]}{meta['extension']}" if self.pinterest else f"image-{meta['sha256']}{meta['extension']}"
                            target = self.folder/name
                            if target.exists():
                                raise LiveError('An untracked file already has this output name; refusing to overwrite it')
                            temporary = self.folder/(name+'.part')
                            temporary.write_bytes(data)
                            temporary.replace(target)
                            self.report['items'].append({**meta, 'file':name, 'source_id':public_url(source_id), 'image_url':public_url(url)})
                            hashes.add(meta['sha256'])
                            self.save()
                            print(f"Downloaded {len(self.report['items'])}/{self.count}: {name}", flush=True)
                        if len(self.report['items']) >= self.count:
                            break
                        signature = driver.page.locator(self.selector).evaluate_all('els=>els.map(i=>i.src).join("\\n")')
                        driver.page.mouse.wheel(0, 2000)
                        try:
                            driver.page.wait_for_function('c=>Array.from(document.querySelectorAll(c.selector)).map(i=>i.src).join("\\n")!==c.before',
                                                          arg={'selector':self.selector, 'before':signature}, timeout=8000)
                        except BrowserTimeout:
                            break
            for item in self.report['items']:
                self.verify_local(item)
            self.report['status'] = 'VERIFIED' if len(self.report['items']) == self.count else 'PARTIAL'
            if self.report['status'] == 'PARTIAL':
                self.report['error'] = 'The actual page did not provide enough distinct eligible images'
        except Exception as exc:
            self.report['status'] = 'AUTH_REQUIRED' if isinstance(exc, LiveError) and 'PINTEREST_LOGIN_REQUIRED' in str(exc) else 'HALTED'
            self.report['error'] = str(exc)[:700] if isinstance(exc, LiveError) else f'{type(exc).__name__}: download failed; saved files were preserved'
        finally:
            try:
                self.save()
            finally:
                owner.close()
        return self.report


def download_pinterest(query='nature landscape', count=20, folder=None, root=Path('runtime/pinterest-download'), *, headless=True, manual_login=False):
    if not isinstance(query, str) or not query.strip() or len(query) > 200:
        raise LiveError('Use a topic of 1-200 characters')
    query = query.strip()
    label = re.sub(r'[^a-zA-Z0-9]+', '-', query).strip('-')[:70] or 'images'
    folder = Path(folder) if folder else downloads_folder()/('Pinterest-'+label)
    runner = LocalDownload(url='https://www.pinterest.com/search/pins/?q='+quote(query), scope=PINTEREST_SCOPE,
                         count=count, folder=folder, root=root, selector='img[srcset], a[href*="/pin/"] img',
                         pinterest=True, profile=Path(root)/'profile', headless=headless and not manual_login)
    runner.manual_login = manual_login
    return runner.run()
