"""One reviewed setup, one repeatable run command. No model service is required."""
import argparse
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import sys
import time
from zoneinfo import ZoneInfo

from ..live.contracts import LiveError, digest, resolve_value, save_json
from ..live.cli import read_json
from .contracts import approve, require_approval, template, validate


def run_args(parser):
    parser.add_argument('recipe', type=Path)
    parser.add_argument('--inputs', type=Path)
    parser.add_argument('--approval', type=Path)
    parser.add_argument('--root', type=Path, default=Path('runtime/transfer'))
    parser.add_argument('--source-profile', type=Path)
    parser.add_argument('--target-profile', type=Path)


def receipt_for(args, recipe, inputs):
    expected = approve(recipe, inputs)
    path = args.approval or args.root/'approvals'/(expected['sha256']+'.json')
    if path.exists():
        receipt = read_json(path)
        require_approval(recipe, inputs, receipt)
        return receipt
    if args.approval:
        raise LiveError('The specified approval file does not exist')
    print(json.dumps({'recipe': recipe, 'inputs': inputs}, indent=2))
    if not sys.stdin.isatty():
        raise LiveError('First run needs review in an interactive terminal; scheduled workers never prompt')
    if input('Review the two sites, actions and image rules. Type APPROVE once to save this setup: ').strip() != 'APPROVE':
        raise LiveError('Transfer was not approved')
    save_json(path, expected)
    return expected


def main(argv=None):
    parser = argparse.ArgumentParser(description='Core image transfer: teach once, repeat without AI')
    sub = parser.add_subparsers(dest='command', required=True)
    download = sub.add_parser('download', help='Download Pinterest images directly to your local Downloads folder')
    download.add_argument('--site', choices=['pinterest'], default='pinterest')
    download.add_argument('--query', default='nature landscape')
    download.add_argument('--count', type=int, default=20)
    download.add_argument('--folder', type=Path)
    download.add_argument('--root', type=Path, default=Path('runtime/pinterest-download'))
    download.add_argument('--headed', action='store_true')
    download.add_argument('--login', action='store_true', help='Open the dedicated browser for manual sign-in before downloading')
    init = sub.add_parser('init', help='Create a reusable site-pair recipe')
    init.add_argument('--source', required=True)
    init.add_argument('--target', required=True)
    init.add_argument('--count', type=int, default=10)
    init.add_argument('--out', type=Path, default=Path('image-transfer.json'))
    init.add_argument('--source-images', default='img', help='CSS selector matching original image elements or download links')
    init.add_argument('--source-attribute', default='src')
    init.add_argument('--file-input', default='input[type=file]')
    init.add_argument('--submit', help='Exact label of the final upload button; omit for upload-on-file-selection sites')
    init.add_argument('--target-images', default='img', help='CSS selector matching persisted uploaded images')
    init.add_argument('--source-setup', type=Path, help='Reviewed live-recorded setup workflow; imports its steps')
    init.add_argument('--target-setup', type=Path)
    for name in ('run', 'login', 'teach', 'schedule'):
        cmd = sub.add_parser(name)
        run_args(cmd)
        if name == 'run':
            cmd.add_argument('--job', help='Stable retry identity; default is today in the chosen timezone')
            cmd.add_argument('--timezone', default='Asia/Kolkata')
            visibility = cmd.add_mutually_exclusive_group()
            visibility.add_argument('--headless', action='store_true')
            visibility.add_argument('--headed', action='store_true')
            cmd.add_argument('--inside-worker', action='store_true', help=argparse.SUPPRESS)
        if name == 'schedule':
            cmd.add_argument('--at', required=True, help='Daily HH:MM')
            cmd.add_argument('--timezone', default='Asia/Kolkata')
    worker = sub.add_parser('worker', help='Run the daily queue; keep this process and machine awake')
    worker.add_argument('--root', type=Path, default=Path('runtime/transfer'))
    worker.add_argument('--once', action='store_true')
    listing = sub.add_parser('schedules')
    listing.add_argument('--root', type=Path, default=Path('runtime/transfer'))
    toggle = sub.add_parser('pause')
    toggle.add_argument('id')
    toggle.add_argument('--root', type=Path, default=Path('runtime/transfer'))
    toggle.add_argument('--resume', action='store_true')
    resolve = sub.add_parser('resolve', help='Explicitly resolve a reviewed uncertain upload')
    resolve.add_argument('--root', type=Path, default=Path('runtime/transfer'))
    resolve.add_argument('--job', required=True)
    resolve.add_argument('--sha256', required=True)
    resolve.add_argument('--confirmed-not-uploaded', action='store_true', required=True)
    demo = sub.add_parser('demo', help='Explicit owned HTTP demonstration: transfer 10 real images between two local sites')
    demo.add_argument('--root', type=Path, default=Path('runtime/transfer-demo'))
    args = parser.parse_args(argv)
    try:
        if args.command == 'download':
            from .download import download_pinterest
            result = download_pinterest(args.query, args.count, args.folder, args.root, headless=not args.headed, manual_login=args.login)
            print(json.dumps(result, indent=2))
            return 0 if result['status'] == 'VERIFIED' else 2
        if args.command == 'init':
            if args.out.exists():
                raise LiveError('Recipe already exists; choose a different output or edit that file')
            recipe = template(args.source, args.target, args.count)
            recipe['source'].update(items=args.source_images, image_attribute=args.source_attribute)
            recipe['target']['file_input'] = {'kind': 'css', 'value': args.file_input}
            recipe['target']['verify']['items'] = args.target_images
            if args.submit:
                recipe['target']['submit'] = {'kind': 'role', 'role': 'button', 'name': args.submit}
            for side in ('source', 'target'):
                file = getattr(args, side+'_setup')
                if file:
                    workflow = read_json(file)
                    if workflow.get('provenance', {}).get('blockers'):
                        raise LiveError('Resolve the recorded setup blockers first')
                    recipe[side]['setup'] = workflow['steps']
                    recipe[side]['scope'] = workflow['scope']
            validate(recipe)
            save_json(args.out, recipe)
            print(f'Created {args.out}. Review the original-image selector, upload button and persisted-gallery selector once, then run it.')
            return 0
        if args.command in {'worker', 'schedules', 'pause'}:
            from .scheduler import Scheduler
            scheduler = Scheduler(args.root)
            try:
                if args.command == 'schedules':
                    print(json.dumps(scheduler.list(), indent=2))
                elif args.command == 'pause':
                    scheduler.enable(args.id, args.resume)
                    print('Resumed' if args.resume else 'Paused')
                else:
                    while True:
                        for result in scheduler.tick():
                            print(json.dumps(result, indent=2), flush=True)
                        if args.once:
                            break
                        time.sleep(5)
            finally:
                scheduler.close()
            return 0
        if args.command == 'resolve':
            from .store import Journal
            journal = Journal(args.root)
            try:
                journal.resolve_not_uploaded(args.job, args.sha256)
            finally:
                journal.close()
            print('Recorded operator resolution. Rerun the same job to continue.')
            return 0
        if args.command == 'demo':
            from .demo import running_demo
            from .engine import Transfer
            with running_demo() as (recipe, uploads, _, state):
                # This is explicitly an owned test, never a substitute for the requested sites.
                job = 'owned-demo-'+datetime.now().strftime('%Y%m%dT%H%M%S%f')
                result = Transfer(recipe, {}, approve(recipe, {}), args.root, job).run()
                result['demo_http_upload_requests'] = state['post_count']
                result['demo_persisted_images'] = len(uploads)
                print(json.dumps(result, indent=2))
                save_json(args.root/'demo-result.json', result)
                return 0 if result['status'] == 'VERIFIED' else 2
        recipe = read_json(args.recipe)
        inputs = read_json(args.inputs) if args.inputs else {}
        scopes = validate(recipe, inputs)
        source_profile = args.source_profile or args.root/'profiles'/'source'
        target_profile = args.target_profile or args.root/'profiles'/'target'
        if args.command == 'teach':
            from .teaching import teach
            taught = teach(deepcopy(recipe), inputs, args.root, source_profile, target_profile)
            # Preserve the prior draft so teaching remains reversible.
            save_json(args.recipe.with_suffix('.before-teaching.json'), recipe)
            save_json(args.recipe, taught)
            print(f'Saved the demonstrated setup and selected image controls to {args.recipe}. Run this recipe to rehearse it.')
            return 0
        if args.command == 'login':
            from ..live.browser import open_driver
            from ..live.recording import wait_for_operator
            from .profiles import checked_profile
            from .engine import check_identity
            for side, profile, scope in zip(('source', 'target'), (source_profile, target_profile), scopes):
                profile = checked_profile(profile, scope)
                with open_driver(scope, args.root/'login'/side, profile=profile) as driver:
                    driver.goto(resolve_value(recipe[side]['url'], inputs))
                    wait_for_operator(driver.page, f'Sign in to {side} manually. Press ENTER here when finished: ')
                    check_identity(driver, recipe[side], inputs)
            print('Dedicated site sessions saved locally. Repeat runs do not ask for login until a session expires.')
            return 0
        receipt = receipt_for(args, recipe, inputs)
        if args.command == 'schedule':
            from .scheduler import Scheduler
            spec = {'name': recipe['name'], 'time': args.at, 'timezone': args.timezone, 'misfire': 'run_once', 'grace_seconds': 3600}
            scheduler = Scheduler(args.root)
            try:
                identifier = scheduler.add(recipe, inputs, receipt, spec, source_profile, target_profile)
            finally:
                scheduler.close()
            print(f'Daily schedule saved: {identifier}. Start: python -m handnavigate live transfer worker --root "{args.root}"')
            return 0
        job = args.job or 'daily-'+digest({'recipe': recipe, 'inputs': inputs})[:16]+'-'+datetime.now(ZoneInfo(args.timezone)).date().isoformat()
        if args.inside_worker:
            from .engine import Transfer
            result = Transfer(recipe, inputs, receipt, args.root, job, headless=not args.headed,
                              source_profile=source_profile, target_profile=target_profile).run()
        else:
            from .scheduler import execute_worker
            result = execute_worker(recipe, inputs, receipt, args.root, job, source_profile, target_profile, headless=not args.headed)
        print(json.dumps(result, indent=2))
        return 0 if result['status'] == 'VERIFIED' else 2
    except KeyboardInterrupt:
        print('Stopped. Saved files and transfer receipts are preserved for the next run.', file=sys.stderr)
        return 130
    except Exception as exc:
        print(json.dumps({'status': 'HALTED', 'error': str(exc)[:700] if isinstance(exc, LiveError) else
                          f'{type(exc).__name__}: setup or execution failed; no upload was retried'}), file=sys.stderr)
        return 2
