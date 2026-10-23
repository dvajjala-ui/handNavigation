"""Reviewed single-origin export contracts; no scripts or discovered permissions."""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import parse_qsl, urlsplit

from .contracts import ContractError, digest, validate_target

ID = re.compile(r'[a-z0-9][a-z0-9-]{0,63}')
PATH = re.compile(r'/[A-Za-z0-9/_.-]*')


def valid_path(path):
    return (isinstance(path, str) and PATH.fullmatch(path) is not None and '//' not in path
            and not any(part in ('.', '..') for part in path.split('/')))


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def exact(value, keys, what):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ContractError(f'Invalid {what} fields')


def validate_profile(profile):
    exact(profile, {'schema_version', 'id', 'revision', 'name', 'origin', 'scope',
                    'permission_note', 'login_path', 'entry_path', 'routes', 'account',
                    'controls', 'file_contract'}, 'connection')
    if type(profile['schema_version']) is not int or profile['schema_version'] != 1:
        raise ContractError('Unsupported connection schema')
    if type(profile['revision']) is not int or not 1 <= profile['revision'] <= 100000:
        raise ContractError('Invalid connection revision')
    if not isinstance(profile['id'], str) or not ID.fullmatch(profile['id']):
        raise ContractError('Invalid connection ID')
    for field, maximum in [('name', 100), ('permission_note', 500)]:
        value = profile[field]
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= maximum or any(ord(c) < 32 for c in value):
            raise ContractError(f'Invalid {field}')
    origin = profile['origin']
    if not isinstance(origin, str) or len(origin) > 250:
        raise ContractError('Invalid origin')
    try:
        parsed = urlsplit(origin)
        port = parsed.port
    except ValueError as exc:
        raise ContractError('Invalid origin') from exc
    if (parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment or
            not parsed.hostname or origin != f'{parsed.scheme}://{parsed.netloc}' or
            parsed.netloc.lower() != parsed.netloc or any(c.isspace() for c in origin)):
        raise ContractError('Use one canonical origin, without credentials, paths or query strings')
    if profile['scope'] == 'owned_local':
        if parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or not port:
            raise ContractError('Owned local scope requires http://127.0.0.1:PORT')
    elif profile['scope'] == 'authorized_https':
        import ipaddress
        try:
            ipaddress.ip_address(parsed.hostname)
        except ValueError:
            pass
        else:
            raise ContractError('Remote connections require an explicitly approved DNS name')
        if (parsed.scheme != 'https' or '.' not in parsed.hostname or
                not re.fullmatch(r'[a-z0-9]+(?:[.-][a-z0-9]+)*', parsed.hostname) or
                parsed.hostname.endswith(('.local', '.localhost')) or parsed.hostname.endswith('.')):
            raise ContractError('Remote connections require a canonical HTTPS DNS origin')
    else:
        raise ContractError('Unknown permission scope')
    for key in ['login_path', 'entry_path']:
        if not valid_path(profile[key]):
            raise ContractError('Only explicit simple paths are supported')
    routes = profile['routes']
    if not isinstance(routes, list) or not 1 <= len(routes) <= 20:
        raise ContractError('Specify 1-20 explicit route contracts')
    seen = set()
    for route in routes:
        exact(route, {'path', 'methods', 'query_keys'}, 'route')
        path = route['path']
        if not valid_path(path) or path in seen:
            raise ContractError('Invalid or duplicate route path')
        seen.add(path)
        methods, keys = route['methods'], route['query_keys']
        if (not isinstance(methods, list) or not methods or
                any(m not in ['GET', 'POST'] for m in methods) or len(methods) != len(set(methods))):
            raise ContractError('Only GET and explicit login-only POST routes are supported')
        if (not isinstance(keys, list) or len(keys) > 12 or any(not isinstance(k, str) or not re.fullmatch(r'[a-z_]{1,40}', k) for k in keys)
                or len(keys) != len(set(keys))):
            raise ContractError('Invalid route query keys')
    for path in [profile['entry_path'], profile['login_path']]:
        if not any(r['path'] == path and 'GET' in r['methods'] for r in routes):
            raise ContractError('Login and entry paths need approved GET routes')
    exact(profile['account'], {'target', 'expected'}, 'account')
    validate_target(profile['account']['target'])
    expected = profile['account']['expected']
    if not isinstance(expected, str) or not 1 <= len(expected) <= 150 or expected != expected.strip() or any(ord(c) < 32 for c in expected):
        raise ContractError('Specify the exact expected account label')
    exact(profile['controls'], {'topic', 'submit', 'ready', 'download', 'auth_required'}, 'controls')
    for target in profile['controls'].values():
        validate_target(target)
    c = profile['file_contract']
    exact(c, {'format', 'columns', 'unique_column', 'topic_column', 'min_rows', 'max_rows', 'max_bytes'}, 'file contract')
    columns = c['columns']
    if c['format'] != 'csv' or not isinstance(columns, list) or not 2 <= len(columns) <= 20:
        raise ContractError('This adapter supports only an explicit CSV schema')
    if any(not isinstance(s, str) or not re.fullmatch(r'[a-z_]{1,40}', s) for s in columns) or len(set(columns)) != len(columns):
        raise ContractError('Invalid or duplicated CSV column')
    if c['unique_column'] not in columns or c['topic_column'] not in columns or c['unique_column'] == c['topic_column']:
        raise ContractError('Specify distinct identity and topic columns')
    if (type(c['min_rows']) is not int or type(c['max_rows']) is not int or
            not 1 <= c['min_rows'] <= c['max_rows'] <= 1000 or type(c['max_bytes']) is not int or not 128 <= c['max_bytes'] <= 1048576):
        raise ContractError('Invalid CSV verification budgets')


def request_allowed(profile, url, method, phase='run'):
    """Application-layer policy, not a DNS-aware network sandbox."""
    try:
        p = urlsplit(url)
        if p.username or p.password or p.fragment or f'{p.scheme}://{p.netloc}' != profile['origin']:
            return False
        if method != 'GET' and not (phase == 'login' and method == 'POST'):
            return False
        pairs = parse_qsl(p.query, keep_blank_values=True, max_num_fields=20)
        if len({k for k, _ in pairs}) != len(pairs):
            return False
        return any(p.path == r['path'] and method in r['methods'] and
                   all(k in r['query_keys'] and len(v) <= 200 for k, v in pairs)
                   for r in profile['routes'])
    except (TypeError, ValueError):
        return False


def demo_profile(origin='http://127.0.0.1:4181'):
    t = lambda value: [{'by': 'testid', 'value': value}]
    return {'schema_version': 1, 'id': 'owned-report-portal', 'revision': 1,
            'name': 'Owned report portal', 'origin': origin, 'scope': 'owned_local',
            'permission_note': 'Owned synthetic portal. No third-party account or website.',
            'login_path': '/login', 'entry_path': '/reports',
            'routes': [{'path': path, 'methods': methods, 'query_keys': keys} for path, methods, keys in [
                ('/login', ['GET'], []), ('/session', ['POST'], []), ('/reports', ['GET'], []),
                ('/api/reports', ['GET'], ['topic']), ('/download', ['GET'], ['topic']), ('/favicon', ['GET'], [])]],
            'account': {'target': t('account-id'), 'expected': 'demo@handnavigate.local'},
            'controls': {'topic': [{'by': 'label', 'value': 'Report topic'}],
                         'submit': [{'by': 'role', 'role': 'button', 'name': 'Find reports'}],
                         'ready': t('report-ready'), 'download': [{'by': 'role', 'role': 'link', 'name': 'Download CSV'}],
                         'auth_required': t('login-required')},
            'file_contract': {'format': 'csv', 'columns': ['item_id', 'topic', 'label'],
                              'unique_column': 'item_id', 'topic_column': 'topic',
                              'min_rows': 5, 'max_rows': 5, 'max_bytes': 131072}}


class ConnectionRegistry:
    """Transactional compare-and-swap approvals; separate from existing schedules."""
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / 'connections.db'
        with self.db() as c:
            c.execute('''CREATE TABLE IF NOT EXISTS connections(
                id TEXT PRIMARY KEY, profile TEXT NOT NULL, sha256 TEXT NOT NULL,
                approved_sha256 TEXT, approved_at TEXT, updated_at TEXT NOT NULL)''')

    @contextmanager
    def db(self):
        c = sqlite3.connect(self.path, timeout=10)
        c.row_factory = sqlite3.Row
        try:
            with c:
                yield c
        finally:
            c.close()

    def list(self):
        with self.db() as c:
            rows = c.execute('SELECT * FROM connections ORDER BY updated_at DESC').fetchall()
        return [self._public(row) for row in rows]

    def _public(self, row):
        value = dict(row)
        value['profile'] = json.loads(value['profile'])
        value['status'] = 'APPROVED_NOT_QUALIFIED' if value['approved_sha256'] == value['sha256'] else 'DRAFT'
        value['scheduled_execution'] = False
        return value

    def get(self, id):
        if not isinstance(id, str) or not ID.fullmatch(id):
            raise ContractError('Invalid connection ID')
        with self.db() as c:
            row = c.execute('SELECT * FROM connections WHERE id=?', (id,)).fetchone()
        if row is None:
            raise ContractError('Connection not found')
        return self._public(row)

    def put(self, profile, base_sha256=None):
        validate_profile(profile)
        key = digest(profile)
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            old = c.execute('SELECT * FROM connections WHERE id=?', (profile['id'],)).fetchone()
            if old:
                if base_sha256 != old['sha256'] or profile['revision'] != json.loads(old['profile'])['revision'] + 1:
                    raise ContractError('Connection changed or revision is stale; reload and review')
            elif base_sha256 is not None or profile['revision'] != 1:
                raise ContractError('A new connection starts at revision one without a base checksum')
            c.execute('INSERT OR REPLACE INTO connections VALUES(?,?,?,NULL,NULL,?)',
                      (profile['id'], json.dumps(profile), key, timestamp()))
        return self.get(profile['id'])

    def approve(self, id, reviewed_sha256, permission_confirmed):
        if not isinstance(id, str) or not ID.fullmatch(id):
            raise ContractError('Invalid connection ID')
        if permission_confirmed is not True:
            raise ContractError('Explicit site permission acknowledgement is required')
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            row = c.execute('SELECT * FROM connections WHERE id=?', (id,)).fetchone()
            if row is None or reviewed_sha256 != row['sha256']:
                raise ContractError('Review this exact current connection before approval')
            c.execute('UPDATE connections SET approved_sha256=sha256,approved_at=? WHERE id=?', (timestamp(), id))
        return self.get(id)

    def revoke(self, id):
        self.get(id)
        with self.db() as c:
            c.execute('UPDATE connections SET approved_sha256=NULL,approved_at=NULL WHERE id=?', (id,))
        return self.get(id)
