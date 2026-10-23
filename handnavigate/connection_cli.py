"""Explicit operator entry points. Secrets come only from a hidden terminal prompt."""
from __future__ import annotations
import getpass
import json
from pathlib import Path
import time
from .connectors import ConnectionRegistry, demo_profile
from .contracts import ContractError, digest
from .portal import running_portal
from .portal_runner import capture_session, run_export
from .qualification import qualify_owned
from .vault import SessionVault


def add_commands(commands):
    doctor = commands.add_parser('doctor', help='Check owned HTTP components and ordinary browser navigation separately')
    doctor.add_argument('--output', type=Path, default=Path('runtime'))
    portal = commands.add_parser('portal', help='Serve the owned authenticated report fixture; no real credentials')
    portal.add_argument('--port', type=int, default=4181)
    portal.add_argument('--output', type=Path, default=Path('runtime'))
    imp = commands.add_parser('connection-import', help='Validate and save an unapproved connection profile')
    imp.add_argument('profile', type=Path)
    imp.add_argument('--base-sha256')
    approve = commands.add_parser('connection-approve', help='Acknowledge permission for this exact connection checksum')
    approve.add_argument('id')
    approve.add_argument('--reviewed-sha256', required=True)
    approve.add_argument('--i-have-permission', action='store_true')
    listing = commands.add_parser('connections', help='Inspect connection contracts; never returns session contents')
    connect = commands.add_parser('connect', help='Human sign-in in a visible browser, then encrypted session capture')
    connect.add_argument('id')
    connect.add_argument('--ttl-hours', type=int, default=8)
    export = commands.add_parser('export', help='Supervised experimental CSV export; not a scheduled workflow')
    export.add_argument('id')
    export.add_argument('--topic', required=True)
    forget = commands.add_parser('connection-forget', help='Remove local session and revoke local approval; does not log out the remote site')
    forget.add_argument('id')
    for parser in [imp, approve, listing, connect, export, forget]:
        parser.add_argument('--output', type=Path, default=Path('runtime'))


COMMANDS = {'doctor', 'portal', 'connection-import', 'connection-approve', 'connections', 'connect', 'export', 'connection-forget'}


def execute(args):
    if args.command == 'doctor':
        report = qualify_owned(args.output)
        print(json.dumps(report, indent=2))
        return 0 if report['status'] == 'OWNED_BROWSER_QUALIFIED' else 2
    registry = ConnectionRegistry(args.output)
    vault = SessionVault(args.output / 'sessions')
    if args.command == 'portal':
        with running_portal(args.port) as server:
            profile = demo_profile(server.origin)
            existing = {c['id']: c for c in registry.list()}.get(profile['id'])
            if not existing:
                registry.put(profile)
            elif existing['profile'] != profile:
                # Never silently overwrite a user-edited or approved contract.
                profile_path = args.output / 'owned-portal-profile.json'
                profile_path.write_text(json.dumps(profile, indent=2))
                print(f'Existing connection preserved. New server profile: {profile_path}', flush=True)
            print(f'Owned demo portal: {server.origin}/login', flush=True)
            print('No real password. Review and approve the connection separately. Keep this process open.', flush=True)
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                return 0
    if args.command == 'connections':
        result = {'connections': registry.list()}
    elif args.command == 'connection-import':
        if args.profile.stat().st_size > 65536:
            raise ContractError('Connection profile exceeds 64 KiB')
        result = registry.put(json.loads(args.profile.read_text()), args.base_sha256)
    elif args.command == 'connection-approve':
        result = registry.approve(args.id, args.reviewed_sha256, args.i_have_permission)
    elif args.command == 'connection-forget':
        record = registry.revoke(args.id)
        result = vault.forget(record['profile'])
    elif args.command == 'connect':
        record = registry.get(args.id)
        phrase = getpass.getpass('Vault passphrase (12+ characters; never saved): ')
        confirmation = getpass.getpass('Repeat passphrase: ')
        if phrase != confirmation:
            raise ContractError('Passphrases do not match')
        result = capture_session(record, vault, phrase, ttl_hours=args.ttl_hours)
    else:
        record = registry.get(args.id)
        phrase = getpass.getpass('Unlock session passphrase: ')
        result = run_export(record, vault, phrase, topic=args.topic, output=args.output)
    print(json.dumps(result, indent=2))
    return 2 if result.get('status') == 'HALTED' else 0
