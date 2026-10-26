"""The core source -> validated files -> browser upload -> remote-byte verification loop.

The adapters are data, not generated code. There is no model call or fixture fallback.
"""
from contextlib import ExitStack
from hashlib import sha256
import json
import os
from pathlib import Path
import time
from urllib.parse import urljoin

from playwright.sync_api import TimeoutError as BrowserTimeout, expect, sync_playwright

from ..live.browser import locator_for, open_driver
from ..live.contracts import LiveError, TARGET_OPS, digest, public_url, resolve_value, save_json
from ..ownership import RuntimeOwnership
from .contracts import require_approval
from .files import image_metadata, read_url
from .store import Journal
from .profiles import checked_profile


class NeedsReview(LiveError):
    pass


def unique(page, spec, *, visible=True):
    locator = locator_for(page, spec)
    if locator.count() != 1:
        raise LiveError('A configured control is missing or ambiguous; teach that locator again')
    if visible and not locator.is_visible():
        raise LiveError('A configured control is hidden')
    return locator


def check_identity(driver, site, inputs):
    driver.check_page()
    if site.get('identity'):
        identity = site['identity']
        expect(unique(driver.page, identity['locator'])).to_have_text(resolve_value(identity['text'], inputs), timeout=5000)
    if driver.page.locator('input[type=password]:visible').count():
        raise LiveError('Sign-in is required; use the login command before running')


def prepare(driver, site, inputs, url=None):
    driver.goto(url or resolve_value(site['url'], inputs))
    for step in site['setup']:
        driver.observe('setup')
        action = {k: resolve_value(v, inputs) for k, v in step.items() if k not in {'locator', 'source_action'}}
        action['snapshot'] = driver.latest['snapshot']
        if action['op'] in TARGET_OPS:
            action['target'] = driver.bind_locator(step['locator'])
        driver.execute(action, lambda _: True)
    check_identity(driver, site, inputs)


class Transfer:
    def __init__(self, recipe, inputs, receipt, root, job, *, headless=True, source_profile=None, target_profile=None,
                 cancel=None, on_event=None):
        self.scopes = require_approval(recipe, inputs, receipt)
        if not isinstance(job, str) or not 1 <= len(job) <= 150:
            raise LiveError('job must be a nonempty identifier of at most 150 characters')
        self.recipe, self.inputs, self.root, self.job = recipe, inputs, Path(root).resolve(), job
        self.headless, self.profiles = headless, (source_profile, target_profile)
        self.profiles = tuple(checked_profile(p, self.scopes[i]) if p else None for i, p in enumerate(self.profiles))
        if self.profiles[0] is not None and self.profiles[0] == self.profiles[1]:
            raise LiveError('Source and destination must have separate dedicated profiles')
        self.cancel, self.on_event = cancel, on_event
        self.deadline = time.monotonic()+recipe['limits']['timeout_seconds']
        self.namespace = digest({'source': recipe['source'], 'target': recipe['target'], 'inputs': inputs})
        self.report = {'schema': 'handnavigate.transfer.result.v1', 'job': job, 'status': 'HALTED',
                       'contract_sha256': digest({'recipe': recipe, 'inputs': inputs}),
                       'execution_id': os.environ.get('HANDNAVIGATE_TRANSFER_EXECUTION_ID'),
                       'requested': recipe['count'], 'downloaded': 0, 'confirmed': 0, 'uploaded': 0,
                       'reconciled': 0, 'model_calls': 0, 'items': [], 'skipped': [], 'error': None}
        self.transfer_count = 0

    def check(self):
        if self.cancel and self.cancel.is_set():
            raise LiveError('Transfer cancelled; completed receipts are preserved')
        if time.monotonic() >= self.deadline:
            raise LiveError('Transfer runtime budget exhausted')

    def event(self, kind, item=None):
        self.check()
        if self.on_event:
            self.on_event(kind, item)

    def fetch(self, driver, url):
        self.check()
        return read_url(driver.page.context, driver.scope, url, self.recipe['limits']['max_bytes'], self.deadline)

    def artifact(self, row):
        path = (self.root/row['artifact']).resolve()
        if not path.is_relative_to((self.root/'artifacts').resolve()) or not path.is_file() or path.is_symlink():
            raise LiveError('A journaled image is missing or outside the artifact directory')
        if path.stat().st_size > self.recipe['limits']['max_bytes']:
            raise LiveError('A journaled image was replaced by an oversized file')
        with path.open('rb') as file:
            data = file.read(self.recipe['limits']['max_bytes']+1)
        meta = image_metadata(data, self.recipe['limits'])
        if meta != json.loads(row['metadata']) or meta['sha256'] != row['sha256']:
            raise LiveError('A journaled image changed; refusing to upload it')
        return path, data, meta

    def target_inventory(self, target):
        """Reload the remote gallery, then download its persisted images independently."""
        self.check()
        side = self.recipe['target']
        config = side['verify']
        verification_site = {**side, 'setup': config.get('setup', [])}
        prepare(target, verification_site, self.inputs, resolve_value(config['url'], self.inputs))
        target.page.wait_for_load_state('domcontentloaded')
        if config.get('ready'):
            locator_for(target.page, config['ready']).wait_for(state='visible', timeout=10000)
        else:
            # Normal async galleries must finish their listing request before an
            # empty DOM is treated as an empty destination. Busy apps can provide
            # an explicit loaded indicator instead of waiting for network quiet.
            target.page.wait_for_load_state('networkidle', timeout=10000)
        items = target.page.locator(config['items'])
        total = items.count()
        if total > self.recipe['limits']['max_candidates']:
            raise LiveError('Destination gallery exceeds the reviewed verification bound; use a narrower folder selector')
        inventory = {}
        seen_ids = set()
        for index in range(total):
            self.check()
            item = items.nth(index)
            id_ = item.get_attribute(config['id_attribute'])
            image = item.locator(config['image_selector']) if config['image_selector'] else item
            if image.count() != 1 or not id_ or id_ in seen_ids:
                raise LiveError('Destination item identities or image URLs are missing/ambiguous')
            seen_ids.add(id_)
            value = image.get_attribute(config['image_attribute'])
            if not value:
                raise LiveError('Destination image has no verification URL')
            url = urljoin(target.page.url, value)
            data = self.fetch(target, url)
            meta = image_metadata(data, self.recipe['limits'])
            hash_ = meta['sha256']
            if hash_ in inventory:
                raise NeedsReview('Destination already contains duplicate image bytes; review before adding files')
            inventory[hash_] = id_
        return inventory

    def collect(self, source, journal, existing):
        src, limits = self.recipe['source'], self.recipe['limits']
        prepare(source, src, self.inputs)
        selected = {r['sha256'] for r in journal.items(self.job)}
        known = journal.known(self.namespace) if self.recipe['new_only'] else set()
        known -= selected
        seen_urls = set()
        pages_without_growth = 0
        candidates = 0
        for page_no in range(limits['max_pages']):
            self.check()
            check_identity(source, src, self.inputs)
            # Give a genuine asynchronous listing a bounded chance to render.
            if not selected and page_no == 0:
                try:
                    source.page.locator(src['items']).first.wait_for(state='attached', timeout=8000)
                except BrowserTimeout:
                    return False
            cards = source.page.locator(src['items'])
            before = len(seen_urls)
            for index in range(min(cards.count(), limits['max_candidates'])):
                if len(selected) >= self.recipe['count']:
                    return True
                self.check()
                image = cards.nth(index).locator(src['image_selector']) if src['image_selector'] else cards.nth(index)
                if image.count() != 1:
                    raise LiveError('A source item has ambiguous image controls')
                value = image.get_attribute(src['image_attribute'])
                if not value:
                    continue
                url = urljoin(source.page.url, value)
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                candidates += 1
                if candidates > limits['max_candidates']:
                    return False
                # Scope/network/invalid-content failures stop the run instead of silently
                # replacing a requested top image with a different one.
                data = self.fetch(source, url)
                meta = image_metadata(data, limits)
                hash_ = meta['sha256']
                if hash_ in selected or hash_ in known or (self.recipe['new_only'] and hash_ in existing):
                    if len(self.report['skipped']) < 100:
                        self.report['skipped'].append({'source': public_url(url), 'reason': 'duplicate_or_already_transferred'})
                    continue
                path = self.root/'artifacts'/(hash_+meta['extension'])
                path.parent.mkdir(parents=True, exist_ok=True)
                temp = path.with_suffix(path.suffix+'.part')
                temp.write_bytes(data)
                temp.replace(path)
                journal.add(self.job, public_url(url), meta, path.relative_to(self.root).as_posix())
                if hash_ in existing:
                    journal.state(self.job, hash_, 'CONFIRMED', existing[hash_])
                selected.add(hash_)
                self.event('DOWNLOADED', hash_)
            if len(selected) >= self.recipe['count']:
                return True
            pages_without_growth = pages_without_growth+1 if len(seen_urls) == before else 0
            next_ = src['next']
            if next_ is None or pages_without_growth >= 2:
                break
            signature = cards.evaluate_all("(nodes, c) => nodes.map(n => (c.child ? n.querySelector(c.child) : n)?.getAttribute(c.attribute) || '').join('\\n')",
                                           {'child': src['image_selector'], 'attribute': src['image_attribute']})
            if next_['kind'] == 'click':
                control = locator_for(source.page, next_['locator'])
                if control.count() == 0 or (control.count() == 1 and control.is_disabled()):
                    break
                unique(source.page, next_['locator']).click(timeout=8000)
            else:
                source.page.mouse.wheel(0, 1800)
            try:
                source.page.wait_for_function("c => Array.from(document.querySelectorAll(c.selector)).map(n => (c.child ? n.querySelector(c.child) : n)?.getAttribute(c.attribute) || '').join('\\n') !== c.before",
                                              arg={'selector': src['items'], 'child': src['image_selector'],
                                                   'attribute': src['image_attribute'], 'before': signature}, timeout=5000)
            except BrowserTimeout:
                break
        return len(selected) >= self.recipe['count']

    def upload(self, target, row, journal):
        self.check()
        _, data, meta = self.artifact(row)
        side = self.recipe['target']
        prepare(target, side, self.inputs)
        control = unique(target.page, side['file_input'], visible=False)
        if control.evaluate("el => el.tagName !== 'INPUT' || el.type !== 'file' || !!el.webkitdirectory"):
            raise LiveError('The upload target must be a unique file input, not a directory or another control')
        submit = unique(target.page, side['submit']) if side['submit'] else None
        check_identity(target, side, self.inputs)
        self.check()
        # Persist BEFORE selecting files: onchange itself may transmit them.
        journal.state(self.job, row['sha256'], 'UPLOADING')
        self.event('BEFORE_UPLOAD', row['sha256'])
        # Use verified in-memory bytes; a local file replaced after verification cannot be exfiltrated.
        control.set_input_files({'name': meta['sha256']+meta['extension'], 'mimeType': meta['mime'], 'buffer': data}, timeout=10000)
        if submit:
            submit.click(timeout=10000)
        # Do not navigate away while an onchange/fetch upload is still transmitting.
        # Quiet network is a transport wait only; remote bytes below establish success.
        target.page.wait_for_load_state('networkidle', timeout=15000)
        self.report['uploaded'] += 1
        self.event('AFTER_UPLOAD', row['sha256'])
        until = min(self.deadline, time.monotonic()+self.recipe['limits']['verify_seconds'])
        while True:
            inventory = self.target_inventory(target)
            if row['sha256'] in inventory:
                journal.state(self.job, row['sha256'], 'CONFIRMED', inventory[row['sha256']])
                self.event('CONFIRMED', row['sha256'])
                return
            if time.monotonic() >= until:
                journal.state(self.job, row['sha256'], 'NEEDS_REVIEW')
                raise NeedsReview('Upload outcome is uncertain: no matching persisted destination image. No automatic resubmission.')
            target.page.wait_for_timeout(350)

    def run(self):
        self.root.mkdir(parents=True, exist_ok=True)
        # A lifetime OS lock is automatically released after a process crash.
        owner = RuntimeOwnership(self.root)
        try:
            journal = Journal(self.root)
        except BaseException:
            owner.close()
            raise
        begun = False
        report_path = self.root/'runs'/(sha256(self.job.encode()).hexdigest()+'.json')
        try:
            journal.begin(self.job, digest({'recipe': self.recipe, 'inputs': self.inputs}), self.namespace)
            begun = True
            with ExitStack() as stack:
                playwright = stack.enter_context(sync_playwright())
                drivers = [stack.enter_context(open_driver(scope, self.root/'browser'/side, headless=self.headless,
                                                          profile=self.profiles[i], playwright=playwright))
                           for i, (side, scope) in enumerate(zip(('source','target'), self.scopes))]
                source, target = drivers
                # The page supplies listing/controls; validated image bytes travel only
                # through the streaming reader. This also prevents the browser from
                # autonomously following image redirects before our per-hop checks.
                for driver in drivers:
                    def media_route(route):
                        if route.request.resource_type in {'image', 'media'}:
                            route.abort('blockedbyclient')
                        else:
                            route.fallback()
                    driver.page.context.route('**/*', media_route)
                inventory = self.target_inventory(target)
                for pending in journal.uncertain(self.namespace):
                    if pending['sha256'] not in inventory:
                        raise NeedsReview('An earlier upload has an unknown outcome. Inspect the destination before explicitly resolving it as not uploaded.')
                    journal.state(pending['job'], pending['sha256'], 'CONFIRMED', inventory[pending['sha256']])
                    self.report['reconciled'] += 1
                for row in journal.items(self.job):
                    self.artifact(row)
                    if row['state'] == 'CONFIRMED' and row['sha256'] not in inventory:
                        raise NeedsReview('A previously confirmed destination image is now missing or modified')
                    if row['sha256'] in inventory:
                        journal.state(self.job, row['sha256'], 'CONFIRMED', inventory[row['sha256']])
                complete = self.collect(source, journal, inventory) if len(journal.items(self.job)) < self.recipe['count'] else True
                if not complete:
                    self.report.update(status='PARTIAL', error='Fewer eligible images than requested. Files preserved; no new uploads were started.')
                else:
                    for row in journal.items(self.job):
                        self.check()
                        if row['state'] != 'CONFIRMED':
                            self.upload(target, row, journal)
                    # Re-read all remote outputs, including earlier items, before success.
                    final = self.target_inventory(target)
                    if not all(r['sha256'] in final for r in journal.items(self.job)):
                        raise NeedsReview('Destination changed before final verification')
                    self.report['status'] = 'VERIFIED'
        except (Exception, KeyboardInterrupt) as exc:
            if not begun:
                raise
            uncertain = journal.uncertain(self.namespace)
            self.report['status'] = 'NEEDS_REVIEW' if isinstance(exc, NeedsReview) or uncertain else 'HALTED'
            self.report['error'] = str(exc)[:700] if isinstance(exc, LiveError) else f'{type(exc).__name__}: browser or transfer failed; no uncertain upload was retried'
        finally:
            try:
                if begun:
                    self.report['items'] = [{**json.loads(r['metadata']), 'source': r['source_id'], 'file': r['artifact'],
                                     'state': r['state'], 'target_id': r['target_id']} for r in journal.items(self.job)]
                    self.report['downloaded'] = len(self.report['items'])
                    self.report['confirmed'] = sum(r['state']=='CONFIRMED' for r in self.report['items'])
                    journal.finish(self.job, self.report)
                    save_json(report_path, self.report)
                    save_json(self.root/'latest-result.json', self.report)
            finally:
                try:
                    journal.close()
                finally:
                    owner.close()
        return self.report
