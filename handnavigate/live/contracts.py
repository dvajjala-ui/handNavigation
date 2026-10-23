"""Small, closed contracts: model output is data, never executable code."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


class LiveError(ValueError):
    pass


SECRET = re.compile(r'password|passwd|secret|token|api[-_ ]?key|credential|one[-_ ]?time|credit.?card|cvv', re.I)
OPS = {'click', 'fill', 'select', 'check', 'press', 'navigate', 'scroll', 'wait', 'download', 'finish'}
TARGET_OPS = {'click', 'fill', 'select', 'check', 'press', 'download'}
KEYS = {'Enter', 'Tab', 'Escape', 'ArrowDown', 'ArrowUp', 'ArrowLeft', 'ArrowRight', 'Space'}


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(',', ':'), allow_nan=False)


def digest(value: object) -> str:
    return sha256(canonical(value).encode()).hexdigest()


def origin(url: str) -> str:
    try:
        p = urlsplit(url)
        if p.scheme not in {'http', 'https'} or not p.hostname or p.username or p.password:
            raise LiveError('Only HTTP(S) URLs without embedded credentials are supported')
        host = p.hostname.lower()
        if ':' in host:
            host = '[' + host + ']'
        port = p.port
        suffix = '' if port is None or (p.scheme, port) in {('http', 80), ('https', 443)} else f':{port}'
        return f'{p.scheme}://{host}{suffix}'
    except (TypeError, ValueError) as exc:
        raise LiveError('Invalid HTTP(S) URL') from exc


def public_url(url: str) -> str:
    """Evidence keeps paths and parameter names; it does not log query values."""
    try:
        p = urlsplit(url)
        return urlunsplit((p.scheme, p.netloc.split('@')[-1], p.path,
                           urlencode([(k, '[REDACTED]') for k, _ in parse_qsl(p.query)]), ''))
    except ValueError:
        return '[invalid URL]'


@dataclass(frozen=True)
class Scope:
    origins: tuple[str, ...]
    methods: tuple[str, ...] = ('GET', 'HEAD', 'OPTIONS')
    max_actions: int = 30

    def __post_init__(self):
        if not 1 <= len(self.origins) <= 20:
            raise LiveError('Specify 1-20 exact origins')
        if any(origin(o) != o or urlsplit(o).path for o in self.origins):
            raise LiveError('Origins must be canonical: https://host[:port], without paths')
        if set(self.methods) - {'GET', 'HEAD', 'OPTIONS', 'POST', 'PUT', 'PATCH', 'DELETE'}:
            raise LiveError('Unsupported request method')
        if type(self.max_actions) is not int or not 1 <= self.max_actions <= 200:
            raise LiveError('max_actions must be an integer from 1 to 200')

    def check(self, url: str) -> None:
        if origin(url) not in self.origins:
            raise LiveError('URL is outside the explicitly allowed origins')
        if any(SECRET.search(k) or k.lower() in {'code', 'authorization'} for k, _ in parse_qsl(urlsplit(url).query)):
            raise LiveError('Credential-bearing navigation URL is not supported; sign in manually')

    def permits_request(self, url: str, method: str) -> bool:
        try:
            return origin(url) in self.origins and method.upper() in self.methods
        except LiveError:
            return False

    def as_dict(self) -> dict:
        return {'origins': list(self.origins), 'methods': list(self.methods), 'max_actions': self.max_actions}


def validate_action(action: object) -> dict:
    if not isinstance(action, dict) or action.get('op') not in OPS:
        raise LiveError('Unknown browser action')
    op = action['op']
    allowed = {'op', 'reason', 'snapshot'}
    if op in TARGET_OPS:
        allowed.add('target')
    if op in {'fill', 'select', 'press', 'navigate'}:
        allowed.add('value')
    if op == 'check':
        allowed.add('checked')
    if op in {'scroll', 'wait'}:
        allowed.add('amount')
    if set(action) - allowed:
        raise LiveError('Unexpected action fields; scripts and arbitrary tool arguments are not accepted')
    if not isinstance(action.get('reason', ''), str) or len(action.get('reason', '')) > 600:
        raise LiveError('Action reason must be a short string')
    if op in TARGET_OPS and (not isinstance(action.get('target'), str) or not re.fullmatch(r'e\d+', action['target'])):
        raise LiveError('Target must be an element ID from the latest observation')
    if op in {'fill', 'select', 'press', 'navigate'}:
        if not isinstance(action.get('value'), str) or len(action['value']) > 4000:
            raise LiveError('Action value must be a bounded string')
        if re.search(r'(?:gsk_|sk-proj-)[A-Za-z0-9_-]{16,}', action['value']):
            raise LiveError('Credential-like action value rejected')
    if op == 'press' and action['value'] not in KEYS:
        raise LiveError('Only bounded single-key presses are supported')
    if op == 'check' and type(action.get('checked')) is not bool:
        raise LiveError('checked must be a boolean, not a string')
    if op in {'wait', 'scroll'}:
        amount = action.get('amount')
        limit = 3000 if op == 'wait' else 2000
        if type(amount) is not int or abs(amount) > limit or (op == 'wait' and amount < 0):
            raise LiveError('Wait/scroll amount is outside its budget')
    return action


def validate_locator(locator: object) -> dict:
    if not isinstance(locator, dict):
        raise LiveError('A locator must be an object')
    kind = locator.get('kind')
    fields = {'role': {'kind', 'role', 'name'}, 'label': {'kind', 'value'},
              'placeholder': {'kind', 'value'}, 'testid': {'kind', 'value'},
              'text': {'kind', 'value'}, 'css': {'kind', 'value'}}
    if kind not in fields or set(locator) != fields[kind]:
        raise LiveError('Invalid locator contract')
    if any(not isinstance(v, str) or len(v) > 500 for v in locator.values()):
        raise LiveError('Locator values must be bounded strings')
    if kind == 'css' and (not locator['value'] or locator['value'].startswith(('xpath=', '//'))):
        raise LiveError('Only CSS syntax is accepted for CSS locators')
    return locator


def resolve_value(value: object, inputs: dict) -> object:
    if isinstance(value, dict):
        if set(value) != {'parameter'} or not isinstance(value['parameter'], str):
            raise LiveError('Only explicit parameter references are supported')
        name = value['parameter']
        if name not in inputs or type(inputs[name]) not in {str, bool, int}:
            raise LiveError(f'Missing or invalid input parameter: {name}')
        return inputs[name]
    return value


def validate_workflow(workflow: object, inputs: dict | None = None, require_checks: bool = True) -> Scope:
    if not isinstance(workflow, dict) or workflow.get('schema') != 'handnavigate.live.v1':
        raise LiveError('Not a live-browser workflow')
    if workflow.get('provenance', {}).get('blockers', 0):
        raise LiveError('Workflow has unresolved import or capture blockers')
    scope = Scope(**{k: tuple(workflow['scope'][k]) if k in {'origins', 'methods'} else workflow['scope'][k]
                     for k in ('origins', 'methods', 'max_actions')})
    scope.check(workflow['start_url'])
    steps = workflow.get('steps')
    if not isinstance(steps, list) or not 1 <= len(steps) <= scope.max_actions:
        raise LiveError('Workflow must contain a bounded, nonempty action sequence')
    inputs = inputs or {}
    for step in steps:
        if not isinstance(step, dict) or step.get('op') not in OPS - {'finish'}:
            raise LiveError('Unsupported workflow step')
        if set(step) - {'op', 'locator', 'value', 'checked', 'amount', 'source_action'}:
            raise LiveError('Unexpected workflow step fields')
        action = {k: resolve_value(v, inputs) for k, v in step.items() if k not in {'locator', 'source_action'}}
        if step['op'] in TARGET_OPS:
            validate_locator(step.get('locator'))
            action['target'] = 'e0'
        validate_action(action)
        if step['op'] == 'navigate':
            scope.check(action['value'])
    checks = workflow.get('checks', [])
    if not isinstance(checks, list) or len(checks) > 30 or (require_checks and not checks):
        raise LiveError('Define at least one explicit completion check before approving a workflow')
    for check in checks:
        if not isinstance(check, dict) or check.get('kind') not in {'text_visible', 'url_equals', 'input_value', 'download_count', 'download_sha256'}:
            raise LiveError('Unknown completion check')
        kind = check['kind']
        fields = {'kind', 'expected'} | ({'locator'} if kind == 'input_value' else set())
        if set(check) != fields:
            raise LiveError('Unexpected completion check fields')
        val = resolve_value(check['expected'], inputs)
        if kind == 'download_count':
            if type(val) is not int or not 1 <= val <= 100:
                raise LiveError('download_count must be a positive bounded integer')
        elif not isinstance(val, str) or (not val and kind != 'input_value') or len(val) > 4000:
            raise LiveError('Completion check requires a nonempty string')
        if kind == 'input_value':
            validate_locator(check['locator'])
        if kind == 'download_sha256' and not re.fullmatch('[0-9a-f]{64}', val):
            raise LiveError('Invalid expected SHA-256')
        if kind == 'url_equals':
            scope.check(val)
    return scope


def approval(workflow: dict, inputs: dict) -> dict:
    validate_workflow(workflow, inputs)
    return {'schema': 'handnavigate.live.approval.v1', 'sha256': digest({'workflow': workflow, 'inputs': inputs}),
            'notice': 'Local review receipt, not a cryptographic identity or website authorization.'}


def require_approval(workflow: dict, inputs: dict, receipt: dict) -> Scope:
    scope = validate_workflow(workflow, inputs)
    if receipt.get('schema') != 'handnavigate.live.approval.v1' or receipt.get('sha256') != digest({'workflow': workflow, 'inputs': inputs}):
        raise LiveError('Approval does not match this exact workflow and these inputs')
    return scope


def save_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding='utf-8')
    tmp.replace(path)
    try:
        path.chmod(0o600)
    except OSError:
        pass
