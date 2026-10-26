"""Reviewable site adapters. A recorded setup sequence is reused without a model."""
from copy import deepcopy
import re

from ..live.contracts import LiveError, Scope, digest, origin, resolve_value, validate_locator, validate_workflow


def bounded(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        raise LiveError(f'{name} must be an integer from {low} to {high}')


def selector(value):
    if not isinstance(value, str) or not value or len(value) > 500:
        raise LiveError('A nonempty CSS selector of at most 500 characters is required')
    validate_locator({'kind': 'css', 'value': value})


def exact(obj, required, optional=()):
    if not isinstance(obj, dict) or set(obj) - set(required) - set(optional) or set(required) - set(obj):
        raise LiveError('Missing or unknown transfer contract fields')


def scope_for(site):
    s = site['scope']
    exact(s, ('origins', 'methods', 'max_actions'))
    return Scope(tuple(s['origins']), tuple(s['methods']), s['max_actions'])


def validate(recipe, inputs=None):
    inputs = inputs or {}
    exact(recipe, ('schema', 'name', 'count', 'source', 'target', 'limits', 'new_only'))
    if recipe['schema'] != 'handnavigate.transfer.v1':
        raise LiveError('Not an image transfer recipe')
    if not isinstance(recipe['name'], str) or not 1 <= len(recipe['name']) <= 150:
        raise LiveError('Give the transfer a short name')
    bounded(recipe['count'], 1, 100, 'count')
    if type(recipe['new_only']) is not bool:
        raise LiveError('new_only must be boolean')
    limits = recipe['limits']
    exact(limits, ('max_bytes', 'max_pixels', 'min_width', 'min_height', 'max_pages', 'max_candidates', 'timeout_seconds', 'verify_seconds'))
    for key, lo, hi in [('max_bytes', 1024, 25*1024*1024), ('max_pixels', 1, 40_000_000),
                        ('min_width', 1, 10000), ('min_height', 1, 10000), ('max_pages', 1, 100),
                        ('max_candidates', 1, 1000), ('timeout_seconds', 5, 3600), ('verify_seconds', 1, 120)]:
        bounded(limits[key], lo, hi, key)
    scopes = []
    for side in ('source', 'target'):
        site = recipe[side]
        common = ('url', 'scope', 'setup')
        exact(site, common + (('items', 'image_selector', 'image_attribute', 'next') if side == 'source'
                            else ('file_input', 'submit', 'verify')), ('identity',))
        scope = scope_for(site)
        scope.check(resolve_value(site['url'], inputs))
        setup = site['setup']
        if not isinstance(setup, list):
            raise LiveError('setup must be recorded workflow steps')
        if setup:
            validate_workflow({'schema': 'handnavigate.live.v1', 'start_url': resolve_value(site['url'], inputs),
                               'scope': scope.as_dict(), 'steps': setup, 'checks': []}, inputs, require_checks=False)
            if any(s['op'] in {'download'} for s in setup):
                raise LiveError('Setup cannot download files')
        if site.get('identity'):
            exact(site['identity'], ('locator', 'text'))
            validate_locator(site['identity']['locator'])
            text = resolve_value(site['identity']['text'], inputs)
            if not isinstance(text, str) or not text or len(text) > 500:
                raise LiveError('Identity requires exact expected account text')
        scopes.append(scope)
    src, dst = recipe['source'], recipe['target']
    selector(src['items'])
    if src['image_selector']:
        selector(src['image_selector'])
    if src['image_attribute'] not in {'src', 'href', 'data-src', 'data-original', 'data-full', 'data-download-url'}:
        raise LiveError('Use an explicit image URL attribute, not page scripts')
    if src['next'] is not None:
        exact(src['next'], ('kind',), ('locator',))
        if src['next']['kind'] == 'click':
            validate_locator(src['next'].get('locator'))
        elif src['next'] != {'kind': 'scroll'}:
            raise LiveError('Pagination must be a reviewed click or bounded scroll')
    validate_locator(dst['file_input'])
    if dst['submit'] is not None:
        validate_locator(dst['submit'])
    check = dst['verify']
    exact(check, ('url', 'items', 'image_selector', 'image_attribute', 'id_attribute'), ('setup', 'ready'))
    scopes[1].check(resolve_value(check['url'], inputs))
    if check.get('setup'):
        validate_workflow({'schema': 'handnavigate.live.v1', 'start_url': resolve_value(check['url'], inputs),
                           'scope': scopes[1].as_dict(), 'steps': check['setup'], 'checks': []}, inputs, require_checks=False)
    if check.get('ready'):
        validate_locator(check['ready'])
    selector(check['items'])
    if check['image_selector']:
        selector(check['image_selector'])
    if check['image_attribute'] not in {'src', 'href', 'data-src', 'data-original', 'data-full'}:
        raise LiveError('Destination verification requires a downloadable image URL')
    if not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_-]{0,79}', check['id_attribute']):
        raise LiveError('Destination needs a stable item identity attribute')
    return tuple(scopes)


def approve(recipe, inputs):
    validate(recipe, inputs)
    return {'schema': 'handnavigate.transfer.approval.v1', 'sha256': digest({'recipe': recipe, 'inputs': inputs})}


def require_approval(recipe, inputs, receipt):
    scopes = validate(recipe, inputs)
    if receipt != approve(recipe, inputs):
        raise LiveError('Transfer approval differs from this exact recipe and inputs')
    return scopes


def template(source_url, target_url, count=10):
    source_origin, target_origin = origin(source_url), origin(target_url)
    recipe = {'schema': 'handnavigate.transfer.v1', 'name': 'Daily image transfer', 'count': count, 'new_only': True,
              'source': {'url': source_url, 'scope': Scope((source_origin,), max_actions=200).as_dict(), 'setup': [],
                         'items': 'img', 'image_selector': '', 'image_attribute': 'src', 'next': {'kind': 'scroll'}},
              'target': {'url': target_url, 'scope': Scope((target_origin,), ('GET', 'HEAD', 'OPTIONS', 'POST'), 200).as_dict(),
                         'setup': [], 'file_input': {'kind': 'css', 'value': 'input[type=file]'}, 'submit': None,
                         'verify': {'url': target_url, 'items': 'img', 'image_selector': '', 'image_attribute': 'src', 'id_attribute': 'src'}},
              'limits': {'max_bytes': 25*1024*1024, 'max_pixels': 40_000_000, 'min_width': 1, 'min_height': 1,
                         'max_pages': 20, 'max_candidates': 500, 'timeout_seconds': 900, 'verify_seconds': 20}}
    validate(recipe)
    return deepcopy(recipe)
