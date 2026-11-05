"""Remote Reddit collector using the VM's saved browser session.

Writes the same verified manifest shape as the Pinterest collector so one import
path can store either source. A network block or sign-in wall is reported as
ACCESS_REQUIRED and the run stops: no credential is typed, no challenge is
answered, and no other source is substituted.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT.parent)]

from collect_pinterest import verified_inventory
from core.browser import Browser
from core.models import Permissions, Plan
from core.policy import Policy, checked_path
from core.runtime import ProcessLock
from core.sources import source_config

CONFIG = source_config('reddit')
HOSTS = ('www.reddit.com', 'old.reddit.com', 'reddit.com')
NAME = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.')


def page_url(subreddit, explicit=''):
    """Only an exact public HTTPS Reddit page is allowed."""
    if explicit:
        parsed = urlsplit(explicit)
        if (parsed.scheme != 'https' or parsed.hostname not in HOSTS or parsed.username
                or parsed.password or parsed.port or parsed.fragment):
            raise ValueError('Choose an exact public HTTPS Reddit page without credentials, ports or fragments.')
        return explicit
    if not subreddit or len(subreddit) > 21 or any(character not in NAME for character in subreddit):
        raise ValueError('Use a plain subreddit name of at most 21 letters, digits, dot, dash or underscore.')
    return 'https://www.reddit.com/r/' + subreddit + '/top/?t=month'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--subreddit', default='')
    parser.add_argument('--page-url', default='')
    parser.add_argument('--count', type=int, default=20, choices=range(1, 21))
    parser.add_argument('--output', required=True)
    parser.add_argument('--profile-data', default='', help='VM data folder holding the signed-in browser profile')
    parser.add_argument('--channel', default='chrome')
    args = parser.parse_args()

    if os.environ.get('HANDNAVIGATE_REMOTE_RUNNER') != '1':
        parser.error('Reddit collection runs only on the chosen Linux VM, where the user signed in.')
    try:
        url = page_url(args.subreddit, args.page_url)
    except ValueError as error:
        parser.error(str(error))
    runtime = checked_path(args.profile_data) if args.profile_data else None
    if runtime and not (runtime / 'browser-profile').is_dir():
        parser.error('The chosen VM profile does not exist. Complete manual login first.')
    output = checked_path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        parser.error('Choose a new empty output folder for this run.')
    images = output / 'pictures'
    images.mkdir()

    report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'executor': platform.platform(),
              'remote': True, 'requested': args.count, 'source': 'Reddit browser', 'source_url': url,
              'session_mode': 'saved_profile' if runtime else 'none', 'upload_used': False,
              'status': 'RUNNING', 'items': []}
    report_file = output / 'result.json'

    def save():
        report_file.write_text(json.dumps(report, indent=2), encoding='utf-8')

    save()
    cancel = threading.Event()
    timer = threading.Timer(240, cancel.set)
    timer.start()
    started = time.monotonic()
    try:
        policy = Policy(Permissions(browser_origins=list(CONFIG['browser_origins']),
                                    image_origins=list(CONFIG['image_origins'])))
        plan = Plan(name='Reddit image collection',
                    instruction='Collect the visible images on this public subreddit page',
                    kind='images', start_url=url, image_selector=CONFIG['image_selector'],
                    max_items=args.count)
        holder = runtime or output / 'private-runtime'
        with ProcessLock(holder), Browser(holder, policy, cancel, headless=True,
                                          channel=args.channel) as browser:
            def record(item):
                report['items'].append(item)
                save()

            try:
                browser.collect(plan, images, set(), record)
            finally:
                try:
                    observed = browser.observe()
                    report['page'] = {'url': observed['url'], 'title': observed['title'],
                                      'image_matches': len(browser.candidates(CONFIG['image_selector'])),
                                      'text': observed['text'][:1800]}
                    browser.page.screenshot(path=str(output / 'page.png'), timeout=5000)
                except Exception as error:
                    report['observation_error'] = str(error)[:300]
        complete = verified_inventory(images, report['items'], args.count)
        report['status'] = 'VERIFIED' if complete else 'PARTIAL'
        text = report.get('page', {}).get('text', '').lower()
        walls = [marker for marker in CONFIG['wall_markers'] if marker in text]
        if not report['items'] and walls:
            report['status'] = 'ACCESS_REQUIRED'
            report['wall_markers'] = walls
    except Exception as error:
        report['status'] = 'CANCELLED' if cancel.is_set() else 'FAILED'
        report['error'] = str(error)[:1000]
    finally:
        timer.cancel()
        report['downloaded'] = len(report['items'])
        report['seconds'] = round(time.monotonic() - started, 2)
        for item in report['items']:
            item['file'] = 'pictures/' + Path(item['file']).name
        save()

    print(json.dumps({key: value for key, value in report.items() if key != 'items'}, indent=2), flush=True)
    raise SystemExit(0 if report['status'] == 'VERIFIED' else 2)


if __name__ == '__main__':
    main()
