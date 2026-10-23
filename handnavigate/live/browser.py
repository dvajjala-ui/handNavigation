"""Real Playwright observations/actions. The CLI never loads a fixture as fallback."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
import time
from uuid import uuid4

from playwright.sync_api import Error as BrowserError, expect, sync_playwright
from ..runner import chromium_options, launch_browser
from .contracts import LiveError, Scope, TARGET_OPS, public_url, save_json, validate_action, validate_locator

DESCRIBE = Path(__file__).with_name('describe.js').read_text(encoding='utf-8')
INTERACTIVE = 'button,a[href],input:not([type=hidden]),textarea,select,[role=button],[role=tab],[role=menuitem],[role=checkbox],[contenteditable=true]'
PRIVATE = 'input[name*=token i],input[name*=secret i],input[name*=password i],input[name*=key i],input[type=password],input[autocomplete*=password],input[autocomplete*=cc-],input[autocomplete=one-time-code],[data-private],[data-sensitive]'
READ_TEXT = r'''() => {
  const out=[]; let size=0;
  const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
  while(walker.nextNode() && size < 10000){
    const n=walker.currentNode,p=n.parentElement;
    if(!p || p.closest('script,style,noscript,input,textarea,[data-private],[data-sensitive]')) continue;
    const s=getComputedStyle(p); if(s.display==='none'||s.visibility==='hidden'||!p.getClientRects().length)continue;
    const t=n.textContent.replace(/\s+/g,' ').trim(); if(t){out.push(t);size+=t.length;}
  }
  return out.join('\n').slice(0,10000);
}'''


def locator_for(page, spec: dict):
    validate_locator(spec)
    k = spec['kind']
    if k == 'role':
        return page.get_by_role(spec['role'], name=spec['name'], exact=True)
    if k == 'label':
        return page.get_by_label(spec['value'], exact=True)
    if k == 'placeholder':
        return page.get_by_placeholder(spec['value'], exact=True)
    if k == 'testid':
        return page.get_by_test_id(spec['value'])
    if k == 'text':
        return page.get_by_text(spec['value'], exact=True)
    return page.locator(spec['value'])


class Driver:
    def __init__(self, page, scope: Scope, output: Path, *, test_document: bool = False):
        self.page, self.scope, self.output = page, scope, Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        self.test_document = test_document  # Used only by explicitly labeled offline tests, never CLI.
        self.elements: dict = {}
        self.latest: dict | None = None
        self.events: list[dict] = []
        self.downloads: list[dict] = []
        self.blocked_requests: list[dict] = []
        self.network_events: list[dict] = []
        self.steps: list[dict] = []
        self.action_count = 0
        self.started = time.monotonic()
        self.pending_download = False
        self.observed_url = None
        self.observed_text = None
        self.unexpected_effect: str | None = None

    def install_guard(self):
        def route_request(route):
            r = route.request
            if self.scope.permits_request(r.url, r.method):
                route.continue_()
            else:
                if len(self.blocked_requests) < 100:
                    self.blocked_requests.append({'method': r.method, 'url': public_url(r.url)})
                route.abort('blockedbyclient')
        self.page.context.route('**/*', route_request)
        if hasattr(self.page.context, 'route_web_socket'):
            self.page.context.route_web_socket('**/*', lambda ws: ws.close())
        def response(response):
            if len(self.network_events) < 200:
                self.network_events.append({'method': response.request.method, 'url': public_url(response.url),
                                            'status': response.status, 'at': time.time()})
        self.page.context.on('response', response)
        def popup(p):
            if p != self.page:
                self.unexpected_effect = 'New tabs/popups require manual handling in this development build'
                p.close()
        self.page.context.on('page', popup)
        def dialog(d):
            self.unexpected_effect = 'A browser dialog requires manual handling'
            d.dismiss()
        self.page.on('dialog', dialog)
        def download(d):
            if not self.pending_download:
                d.cancel()
                self.unexpected_effect = 'Unexpected download; use an explicitly approved download action'
        self.page.on('download', download)

    def check_page(self):
        if self.page.is_closed():
            raise LiveError('Browser page was closed')
        if self.unexpected_effect:
            raise LiveError(self.unexpected_effect)
        if self.page.url == 'about:blank' and self.test_document:
            return
        self.scope.check(self.page.url)

    def goto(self, url: str):
        self.scope.check(url)
        self.page.goto(url, wait_until='domcontentloaded', timeout=25000)
        self.check_page()

    def observe(self, label: str = 'observation') -> dict:
        self.check_page()
        for item in self.elements.values():
            try:
                item['handle'].dispose()
            except BrowserError:
                pass
        self.elements = {}
        descriptors = []
        handles = self.page.locator(INTERACTIVE).element_handles()
        try:
            for handle in handles[:250]:
                if not handle.is_visible():
                    handle.dispose()
                    continue
                meta = handle.evaluate(DESCRIBE)
                if meta['sensitive']:
                    handle.dispose()
                    continue
                element_id = f'e{len(descriptors)}'
                spec = self.find_replay_locator(handle, meta['candidates'])
                public = {k: v for k, v in meta.items() if k not in {'fingerprint', 'candidates', 'connected'}}
                if public.get('href'):
                    public['href'] = public_url(public['href'])
                public.update({'id': element_id, 'locator': spec})
                descriptors.append(public)
                self.elements[element_id] = {'handle': handle, 'meta': meta, 'locator': spec}
        finally:
            for h in handles[250:]:
                h.dispose()
        snapshot = uuid4().hex
        shot = f'{snapshot}.png'
        self.page.screenshot(path=str(self.output / shot), full_page=False, animations='disabled',
                             mask=[self.page.locator(PRIVATE)], timeout=10000)
        for path in [self.output / shot]:
            try: path.chmod(0o600)
            except OSError: pass
        self.observed_url = self.page.url
        self.observed_text = self.page.evaluate(READ_TEXT)
        self.latest = {'snapshot': snapshot, 'at': datetime.now(timezone.utc).isoformat(),
                       'url': public_url(self.page.url), 'title': self.page.title(), 'label': label,
                       'text': self.observed_text, 'elements': descriptors,
                       'screenshot': shot, 'truncated': len(handles) > 250,
                       'frame_count': len(self.page.frames), 'network': self.network_events[-15:],
                       'blocked_requests': self.blocked_requests[-10:],
                       'limitations': ['Main-frame semantic controls only; no iframe/canvas/popup automation',
                                       'Text and screenshots may contain private information; redaction is heuristic']}
        save_json(self.output / f'{snapshot}.json', self.latest)
        return self.latest

    def find_replay_locator(self, handle, candidates: list) -> dict | None:
        for spec in candidates:
            try:
                loc = locator_for(self.page, spec)
                if loc.count() != 1:
                    continue
                candidate = loc.element_handle(timeout=1000)
                same = candidate is not None and handle.evaluate('(el, other) => el === other', candidate)
                if candidate is not None:
                    candidate.dispose()
                if same:
                    return spec
            except (BrowserError, LiveError):
                continue
        return None

    def bind_locator(self, spec: dict) -> str:
        """Bind a reviewed replay locator to the latest observed node, never .first()."""
        loc = locator_for(self.page, spec)
        if loc.count() != 1 or not loc.is_visible():
            raise LiveError('Replay target is missing, hidden, or ambiguous')
        handle = loc.element_handle(timeout=2500)
        meta = handle.evaluate(DESCRIBE)
        if meta['sensitive']:
            handle.dispose()
            raise LiveError('Sensitive controls require manual handling')
        key = f'e{len(self.elements)}'
        self.elements[key] = {'handle': handle, 'meta': meta, 'locator': spec}
        return key

    def execute(self, action: dict, approve) -> dict:
        validate_action(action)
        if action['op'] == 'finish':
            raise LiveError('Completion is handled by the verifier, not the executor')
        self.check_page()
        if self.action_count >= self.scope.max_actions or time.monotonic() - self.started > 900:
            raise LiveError('Action or runtime budget exhausted')
        if not self.latest or action.get('snapshot') != self.latest['snapshot']:
            raise LiveError('Stale observation; observe again before acting')
        op = action['op']
        target = self.elements.get(action.get('target'))
        if op in TARGET_OPS and target is None:
            raise LiveError('Target does not exist in the current observation')
        proposed = {k: v for k, v in action.items() if k not in {'snapshot', 'target'}}
        if target:
            proposed['target_description'] = {k: target['meta'][k] for k in ['role', 'name', 'tag']}
        if op == 'navigate':
            self.scope.check(action['value'])
        if not approve(proposed):
            raise LiveError('Operator declined the action')
        # Recheck AFTER human approval; do not act on an old node or changed account view.
        self.check_page()
        if self.observed_url != self.page.url or self.observed_text != self.page.evaluate(READ_TEXT):
            raise LiveError('Page content or URL changed while awaiting approval; observe again')
        if target:
            current = target['handle'].evaluate(DESCRIBE)
            if not current['connected'] or current['sensitive'] or current['fingerprint'] != target['meta']['fingerprint']:
                raise LiveError('Target changed while awaiting approval')
            if current['disabled']:
                raise LiveError('Target is disabled')
        before = self.latest
        step = {k: v for k, v in action.items() if k not in {'target', 'snapshot', 'reason'}}
        if target:
            step['locator'] = target['locator']
        event = {'index': self.action_count, 'before': before['snapshot'], 'action': proposed,
                 'status': 'STARTED', 'network_start': len(self.network_events)}
        self.events.append(event)
        self.action_count += 1
        save_json(self.output / 'actions.json', self.events)
        try:
            h = target['handle'] if target else None
            if op == 'click': h.click(timeout=8000)
            elif op == 'fill': h.fill(action['value'], timeout=8000)
            elif op == 'select': h.select_option(value=action['value'], timeout=8000)
            elif op == 'check': h.set_checked(action['checked'], timeout=8000)
            elif op == 'press': h.press(action['value'], timeout=8000)
            elif op == 'navigate': self.goto(action['value'])
            elif op == 'scroll': self.page.mouse.wheel(0, action['amount'])
            elif op == 'wait': self.page.wait_for_timeout(action['amount'])
            elif op == 'download':
                self.pending_download = True
                try:
                    with self.page.expect_download(timeout=15000) as info:
                        h.click(timeout=8000)
                    download = info.value
                    if download.failure():
                        raise LiveError('Browser reported a failed download')
                    filename = f'download-{uuid4().hex}.bin'
                    file = self.output / filename
                    download.save_as(str(file))
                    if not 1 <= file.stat().st_size <= 25 * 1024 * 1024:
                        file.unlink(missing_ok=True)
                        raise LiveError('Downloaded file is empty or exceeds the 25 MiB post-download limit')
                    item = {'file': filename, 'bytes': file.stat().st_size,
                            'sha256': sha256(file.read_bytes()).hexdigest(), 'url': public_url(download.url)}
                    self.downloads.append(item)
                finally:
                    self.pending_download = False
            # A bounded observation delay is NOT a business-completion assertion.
            self.page.wait_for_timeout(200)
            after = self.observe('after-' + op)
            event.update({'status': 'EXECUTED', 'after': after['snapshot'],
                          'network': self.network_events[event['network_start']:]})
            if not target or target['locator']:
                self.steps.append(step)
            else:
                event['replay_blocker'] = 'No unique stable locator was available'
            save_json(self.output / 'actions.json', self.events)
            return after
        except Exception:
            event['status'] = 'UNCERTAIN_OR_FAILED'
            save_json(self.output / 'actions.json', self.events)
            raise

    def verify(self, checks: list[dict], inputs: dict | None = None) -> list[dict]:
        from .contracts import resolve_value
        self.check_page()
        results = []
        for check in checks:
            kind = check['kind']
            value = resolve_value(check['expected'], inputs or {})
            if kind == 'url_equals':
                expect(self.page).to_have_url(value, timeout=8000)
            elif kind == 'text_visible':
                loc = self.page.get_by_text(value, exact=True)
                expect(loc).to_be_visible(timeout=8000)
            elif kind == 'input_value':
                loc = locator_for(self.page, check['locator'])
                expect(loc).to_have_value(value, timeout=8000)
            elif kind in {'download_count', 'download_sha256'}:
                for item in self.downloads:
                    file = self.output / item['file']
                    if not file.is_file() or sha256(file.read_bytes()).hexdigest() != item['sha256']:
                        raise LiveError('Downloaded artifact is missing or changed')
                if kind == 'download_count' and len(self.downloads) != value:
                    raise LiveError('Download count did not match')
                if kind == 'download_sha256' and not any(x['sha256'] == value for x in self.downloads):
                    raise LiveError('Expected download hash was not found')
            else:
                raise LiveError('Unknown verifier')
            results.append({'kind': kind, 'passed': True})
        return results


@contextmanager
def open_driver(scope: Scope, output: Path, *, headless: bool = False, profile: Path | None = None):
    """Uses installed browser policy as-is; never switches engine to bypass a URL block."""
    with sync_playwright() as p:
        browser = None
        if profile:
            profile = profile.resolve()
            profile.mkdir(parents=True, exist_ok=True)
            try: profile.chmod(0o700)
            except OSError: pass
            options = chromium_options()
            if not options and not Path(p.chromium.executable_path).exists():
                executable = shutil.which('chromium') or shutil.which('chromium-browser')
                if executable:
                    options = {'executable_path': executable}
            context = p.chromium.launch_persistent_context(str(profile), headless=headless,
                         service_workers='block', accept_downloads=True, viewport={'width':1280,'height':850}, **options)
        else:
            browser = launch_browser(p, headless=headless)
            context = browser.new_context(service_workers='block', accept_downloads=True,
                                          viewport={'width':1280,'height':850})
        page = context.pages[0] if context.pages else context.new_page()
        page.set_default_timeout(8000)
        driver = Driver(page, scope, output)
        driver.install_guard()
        try:
            yield driver
        finally:
            save_json(Path(output) / 'network-metadata.json', {'responses':driver.network_events,'blocked':driver.blocked_requests})
            context.close()
            if browser:
                browser.close()
