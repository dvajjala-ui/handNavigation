"""Passphrase-encrypted, profile-bound session state. Never persist the passphrase.

This is not an OS keychain, hardware isolation, or protection against a compromised
process. Only host-specific cookies and same-origin localStorage are supported.
"""
from __future__ import annotations
import base64
from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import secrets
from urllib.parse import urlsplit

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from .contracts import ContractError, digest
from .connectors import validate_profile

MAX_VAULT_BYTES = 2097152


class SessionError(ContractError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def validate_state(profile, state):
    if not isinstance(state, dict) or set(state) != {'cookies', 'origins'}:
        raise ContractError('Only cookies and same-origin localStorage are supported')
    host = urlsplit(profile['origin']).hostname
    if not isinstance(state['cookies'], list) or len(state['cookies']) > 100:
        raise ContractError('Invalid session cookies')
    cookie_keys = set()
    for cookie in state['cookies']:
        fields = {'name', 'value', 'domain', 'path', 'expires', 'httpOnly', 'secure', 'sameSite'}
        if not isinstance(cookie, dict) or set(cookie) != fields:
            raise ContractError('Unsupported cookie fields')
        if cookie['domain'] != host or cookie['path'] != '/':
            raise ContractError('Only host-specific root-path cookies are supported')
        if not isinstance(cookie['name'], str) or not cookie['name'] or len(cookie['name']) > 256:
            raise ContractError('Invalid cookie name')
        if cookie['name'] in cookie_keys:
            raise ContractError('Duplicate cookie names are ambiguous in this restricted profile')
        cookie_keys.add(cookie['name'])
        if any(ord(c) < 32 for c in cookie['name']):
            raise ContractError('Invalid cookie name')
        if not isinstance(cookie['value'], str) or len(cookie['value']) > 16384:
            raise ContractError('Invalid cookie value')
        if cookie['sameSite'] not in ['Strict', 'Lax', 'None'] or type(cookie['httpOnly']) is not bool or type(cookie['secure']) is not bool:
            raise ContractError('Invalid cookie flags')
        if profile['scope'] == 'authorized_https' and cookie['secure'] is not True:
            raise ContractError('HTTPS sessions require Secure cookies')
        if type(cookie['expires']) not in (int, float) or not math.isfinite(cookie['expires']) or cookie['expires'] < -1:
            raise ContractError('Invalid cookie expiry')
    if not isinstance(state['origins'], list) or len(state['origins']) > 1:
        raise ContractError('Only one storage origin is supported')
    for origin in state['origins']:
        if not isinstance(origin, dict) or set(origin) != {'origin', 'localStorage'} or origin['origin'] != profile['origin']:
            raise ContractError('Storage origin does not match the connection')
        if not isinstance(origin['localStorage'], list) or len(origin['localStorage']) > 100:
            raise ContractError('Invalid localStorage')
        storage_keys = set()
        for pair in origin['localStorage']:
            if not isinstance(pair, dict) or set(pair) != {'name', 'value'} or any(not isinstance(v, str) or len(v) > 16384 for v in pair.values()):
                raise ContractError('Invalid storage entry')
            if pair['name'] in storage_keys:
                raise ContractError('Duplicate localStorage keys are ambiguous')
            storage_keys.add(pair['name'])
    if not state['cookies'] and not any(o['localStorage'] for o in state['origins']):
        raise ContractError('No reusable authentication state was captured')


def _fernet(passphrase, salt):
    if not isinstance(passphrase, str) or not 12 <= len(passphrase) <= 1024:
        raise SessionError('PASSPHRASE_REQUIRED', 'Use a passphrase of 12-1024 characters')
    kdf = Scrypt(salt=salt, length=32, n=32768, r=8, p=1)
    return Fernet(base64.urlsafe_b64encode(kdf.derive(passphrase.encode())))


class SessionVault:
    def __init__(self, root):
        self.root = Path(root)
        if self.root.is_symlink():
            raise ContractError('Vault root may not be a symbolic link')
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def path(self, profile):
        validate_profile(profile)
        return self.root / (profile['id'] + '.session.enc')

    def save(self, profile, state, passphrase, *, ttl_hours=8, now=None):
        validate_profile(profile)
        validate_state(profile, state)
        if type(ttl_hours) is not int or not 1 <= ttl_hours <= 24:
            raise ContractError('Session TTL must be 1-24 hours')
        at = now or datetime.now(timezone.utc)
        if at.tzinfo is None:
            raise ContractError('Session clock must be timezone aware')
        payload = {'schema': 1, 'profile_sha256': digest(profile), 'origin': profile['origin'],
                   'account': profile['account']['expected'], 'created_at': at.isoformat(),
                   'expires_at': (at + timedelta(hours=ttl_hours)).isoformat(), 'state': state}
        salt = secrets.token_bytes(16)
        token = _fernet(passphrase, salt).encrypt(json.dumps(payload).encode()).decode()
        envelope = {'schema': 1, 'kdf': 'scrypt-n32768-r8-p1', 'salt': base64.b64encode(salt).decode(), 'ciphertext': token}
        data = json.dumps(envelope).encode()
        if len(data) > MAX_VAULT_BYTES:
            raise ContractError('Session exceeds encrypted storage budget')
        path = self.path(profile)
        temporary = self.root / ('.' + secrets.token_hex(16) + '.tmp')
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        return {'stored_encrypted': True, 'profile_sha256': digest(profile), 'expires_at': payload['expires_at']}

    def load(self, profile, passphrase, *, now=None):
        path = self.path(profile)
        if not path.is_file() or path.is_symlink():
            raise SessionError('AUTH_REQUIRED', 'No stored session. Sign in interactively first')
        if path.stat().st_size > MAX_VAULT_BYTES:
            raise SessionError('SESSION_LOCKED', 'Session envelope is invalid')
        try:
            e = json.loads(path.read_bytes())
            if set(e) != {'schema', 'kdf', 'salt', 'ciphertext'} or e['schema'] != 1 or e['kdf'] != 'scrypt-n32768-r8-p1':
                raise ValueError()
            salt = base64.b64decode(e['salt'], validate=True)
            if len(salt) != 16:
                raise ValueError()
            raw = _fernet(passphrase, salt).decrypt(e['ciphertext'].encode())
            payload = json.loads(raw)
        except SessionError:
            raise
        except (ValueError, KeyError, TypeError, AttributeError, InvalidToken) as exc:
            raise SessionError('SESSION_LOCKED', 'Cannot unlock session: incorrect passphrase or damaged envelope') from exc
        if payload.get('profile_sha256') != digest(profile) or payload.get('origin') != profile['origin'] or payload.get('account') != profile['account']['expected']:
            raise SessionError('SESSION_SCOPE_CHANGED', 'Session belongs to a different reviewed connection version; sign in again')
        at = now or datetime.now(timezone.utc)
        expires = datetime.fromisoformat(payload['expires_at'])
        if at.tzinfo is None or expires.tzinfo is None:
            raise ContractError('Session clock must be timezone aware')
        if at >= expires:
            raise SessionError('AUTH_REQUIRED', 'Stored session TTL has expired; sign in again')
        validate_state(profile, payload['state'])
        cookies = payload['state']['cookies']
        if cookies and not payload['state']['origins'] and all(c['expires'] != -1 and c['expires'] <= at.timestamp() for c in cookies):
            raise SessionError('AUTH_REQUIRED', 'All stored cookies expired; sign in again')
        return payload['state']

    def forget(self, profile):
        self.path(profile).unlink(missing_ok=True)
        return {'local_copy_removed': True, 'remote_session_revoked': False}
