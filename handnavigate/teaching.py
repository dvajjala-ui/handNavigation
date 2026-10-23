"""Explicit demonstration-to-recipe compilation for one owned form adapter.

This is not model training or universal site inference. Each variable mapping,
output contract and repeat bound is supplied by the reviewer. Recipes contain
no executable JavaScript, arbitrary selectors, URLs, secrets or remote writes.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import re
from typing import Any

from .contracts import ContractError, digest

ADAPTER = {
    'id': 'owned-form-v1',
    'scope': 'Owned in-memory practice form only; no network or external writes',
    'fields': {
        'topic': {'op': 'fill', 'label': 'Topic', 'type': 'string', 'max_length': 80},
        'layout': {'op': 'select', 'label': 'Layout', 'type': 'enum', 'choices': ['compact', 'detailed']},
        'captions': {'op': 'check', 'label': 'Include captions', 'type': 'boolean'},
    },
    'controls': {'prepare': {'role': 'button', 'name': 'Prepare preview'}},
    'outputs': {'topic': 'result-topic', 'layout': 'result-layout', 'captions': 'result-captions'},
    'verifier': 'inputs_match_preview_v1',
}
ADAPTER_SHA = digest(ADAPTER)
MAX_EVENTS = 48
MAX_ROWS = 20
RESERVED_NAMES = {'__proto__', 'constructor', 'prototype', 'row_id'}


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def exact(value: Any, keys: set[str], what: str) -> None:
    if not isinstance(value, dict) or set(value) != keys:
        raise ContractError(f'{what}: unknown or missing fields')


def validate_value(field: str, value: Any) -> None:
    spec = ADAPTER['fields'][field]
    if spec['type'] == 'boolean':
        if type(value) is not bool:
            raise ContractError(f'{field} must be a boolean, not a truthy string')
    elif spec['type'] == 'enum':
        if not isinstance(value, str) or value not in spec['choices']:
            raise ContractError(f'{field} must be one of the reviewed options')
    elif (not isinstance(value, str) or not value.strip() or len(value) > spec['max_length']
          or any(ord(c) < 32 or 0x7f <= ord(c) < 0xa0 for c in value)):
        raise ContractError(f'{field} must be 1-{spec["max_length"]} printable characters')


def validate_events(events: Any) -> None:
    if not isinstance(events, list) or not 4 <= len(events) <= MAX_EVENTS:
        raise ContractError(f'Record all three fields and one preview action, at most {MAX_EVENTS} events')
    seen = set()
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            raise ContractError('Every event must be an object')
        if event.get('op') == 'blocked':
            raise ContractError('Recording contains a private or unsupported action; it cannot be silently omitted')
        op = event.get('op')
        if op == 'click':
            exact(event, {'op', 'control'}, 'Click event')
            if event['control'] != 'prepare' or index != len(events) - 1:
                raise ContractError('Exactly one Prepare preview action must end this lesson')
        elif isinstance(op, str) and op in ('fill', 'select', 'check'):
            exact(event, {'op', 'field', 'value'}, 'Field event')
            field = event['field']
            if not isinstance(field, str) or field not in ADAPTER['fields'] or ADAPTER['fields'][field]['op'] != op:
                raise ContractError('Unreviewed field or mismatched action')
            validate_value(field, event['value'])
            seen.add(field)
        else:
            raise ContractError('Unsupported recorded operation')
    if seen != set(ADAPTER['fields']) or events[-1].get('op') != 'click':
        raise ContractError('All three fields and the final Prepare preview click must be explicitly captured')


def parameter_spec(field: str) -> dict:
    return {k: deepcopy(v) for k, v in ADAPTER['fields'][field].items() if k not in ('op', 'label')}


def compile_lesson(events: list[dict], bindings: dict, *, name: str,
                   verification_contract: str, max_rows: int = 10) -> dict:
    validate_events(events)
    exact(bindings, set(ADAPTER['fields']), 'Bindings')
    if verification_contract != ADAPTER['verifier']:
        raise ContractError('Explicitly select the reviewed input-to-preview verification contract')
    params, sources = {}, {}
    for field, binding in bindings.items():
        if not isinstance(binding, dict):
            raise ContractError('Each binding must be an object')
        mode = binding.get('mode')
        if mode == 'variable':
            exact(binding, {'mode', 'name'}, 'Variable binding')
            key = binding['name']
            if (not isinstance(key, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,31}', key)
                    or key in RESERVED_NAMES or key in params):
                raise ContractError('Use unique variable names, starting with a letter')
            params[key] = parameter_spec(field)
            sources[field] = {'parameter': key}
        elif mode == 'constant':
            exact(binding, {'mode'}, 'Constant binding')
        else:
            raise ContractError('Choose a variable or a recorded constant for every field')
    steps, final = [], {}
    for index, event in enumerate(events):
        step = {'id': f'step-{index + 1}', 'op': event['op']}
        if event['op'] == 'click':
            step['control'] = event['control']
        else:
            field = event['field']
            source = deepcopy(sources.get(field, {'literal': event['value']}))
            step.update(field=field, value=source)
            final[field] = source
        steps.append(step)
    recipe = {'schema_version': 2, 'kind': 'guided-form', 'name': name,
              'adapter_id': ADAPTER['id'], 'adapter_sha256': ADAPTER_SHA,
              'parameters': params, 'steps': steps,
              'verification': {'contract': verification_contract, 'expected': final},
              'repeat': {'max_rows': max_rows, 'stop_on_error': True}}
    validate_lesson(recipe)
    return recipe


def validate_source(field: str, source: Any, parameters: dict) -> None:
    if not isinstance(source, dict) or len(source) != 1:
        raise ContractError('A value must be one explicit variable or literal')
    if 'literal' in source:
        validate_value(field, source['literal'])
    elif 'parameter' in source:
        name = source['parameter']
        if not isinstance(name, str) or name not in parameters or digest(parameters[name]) != digest(parameter_spec(field)):
            raise ContractError('Variable type does not match the field')
    else:
        raise ContractError('Expressions and generated code are not supported')


def validate_lesson(recipe: Any) -> None:
    exact(recipe, {'schema_version', 'kind', 'name', 'adapter_id', 'adapter_sha256',
                   'parameters', 'steps', 'verification', 'repeat'}, 'Lesson')
    if type(recipe['schema_version']) is not int or recipe['schema_version'] != 2 or recipe['kind'] != 'guided-form':
        raise ContractError('Unsupported lesson schema')
    if recipe['adapter_id'] != ADAPTER['id'] or recipe['adapter_sha256'] != ADAPTER_SHA:
        raise ContractError('This recipe is bound to a different adapter; review is required')
    if not isinstance(recipe['name'], str) or not recipe['name'].strip() or len(recipe['name']) > 100 or any(ord(c) < 32 for c in recipe['name']):
        raise ContractError('Lesson name must be 1-100 printable characters')
    params = recipe['parameters']
    if not isinstance(params, dict) or len(params) > 3:
        raise ContractError('At most three variables are supported')
    for key in params:
        if not isinstance(key, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,31}', key) or key in RESERVED_NAMES:
            raise ContractError('Invalid variable name')
    steps = recipe['steps']
    if not isinstance(steps, list) or not 4 <= len(steps) <= MAX_EVENTS:
        raise ContractError('Invalid step count')
    seen, used, final = set(), set(), {}
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            raise ContractError('Every step must be an object')
        op = step.get('op')
        if op == 'click':
            exact(step, {'id', 'op', 'control'}, 'Click step')
            if index != len(steps) - 1 or step['control'] != 'prepare':
                raise ContractError('Exactly one owned preview action must end the recipe')
        elif isinstance(op, str) and op in ('fill', 'select', 'check'):
            exact(step, {'id', 'op', 'field', 'value'}, 'Field step')
            field = step['field']
            if not isinstance(field, str) or field not in ADAPTER['fields'] or ADAPTER['fields'][field]['op'] != op:
                raise ContractError('Unreviewed field or action')
            validate_source(field, step['value'], params)
            if 'parameter' in step['value']:
                used.add(step['value']['parameter'])
            final[field] = step['value']
        else:
            raise ContractError('Unsupported step')
        sid = step['id']
        if not isinstance(sid, str) or not re.fullmatch(r'[a-z0-9-]{1,64}', sid) or sid in seen:
            raise ContractError('Step IDs must be valid and unique')
        seen.add(sid)
    if used != set(params) or set(final) != set(ADAPTER['fields']) or steps[-1]['op'] != 'click':
        raise ContractError('Every field and variable must be used; end with the preview action')
    exact(recipe['verification'], {'contract', 'expected'}, 'Verification')
    if recipe['verification']['contract'] != ADAPTER['verifier'] or digest(recipe['verification']['expected']) != digest(final):
        raise ContractError('Verification must match the final explicitly defined field values')
    exact(recipe['repeat'], {'max_rows', 'stop_on_error'}, 'Repeat policy')
    if type(recipe['repeat']['max_rows']) is not int or not 1 <= recipe['repeat']['max_rows'] <= MAX_ROWS or recipe['repeat']['stop_on_error'] is not True:
        raise ContractError('Repeats require a 1-20 row bound and stop-on-error')


def resolve(source: dict, values: dict) -> Any:
    return values[source['parameter']] if 'parameter' in source else source['literal']


def validate_rows(recipe: dict, rows: Any) -> None:
    validate_lesson(recipe)
    if not isinstance(rows, list) or not 1 <= len(rows) <= recipe['repeat']['max_rows']:
        raise ContractError('Input row count exceeds the reviewed repeat limit')
    identities = set()
    for row in rows:
        exact(row, {'row_id', 'values'}, 'Input row')
        rid = row['row_id']
        if not isinstance(rid, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', rid) or rid in identities:
            raise ContractError('Each row needs a unique, safe row_id')
        identities.add(rid)
        exact(row['values'], set(recipe['parameters']), 'Row variables')
        for step in recipe['steps']:
            if 'value' in step:
                validate_value(step['field'], resolve(step['value'], row['values']))


def make_plan(recipe: dict, rows: list[dict]) -> dict:
    validate_rows(recipe, rows)
    expanded = []
    for row in rows:
        expected = {field: resolve(source, row['values']) for field, source in recipe['verification']['expected'].items()}
        expanded.append({'row_id': row['row_id'], 'expected': expected,
                         'actions': [{**step, **({'value': resolve(step['value'], row['values'])} if 'value' in step else {})}
                                     for step in recipe['steps']]})
    body = {'recipe_sha256': digest(recipe), 'inputs_sha256': digest(rows), 'adapter_sha256': ADAPTER_SHA,
            'row_count': len(rows), 'action_count': len(rows) * len(recipe['steps']),
            'assertion_count': 3 * len(rows), 'rows': expanded, 'scope': ADAPTER['scope'],
            'model_calls': 0, 'external_writes': False}
    return {**body, 'plan_sha256': digest(body)}


def example_events() -> list[dict]:
    return [{'op': 'fill', 'field': 'topic', 'value': 'architecture'},
            {'op': 'select', 'field': 'layout', 'value': 'detailed'},
            {'op': 'check', 'field': 'captions', 'value': True},
            {'op': 'click', 'control': 'prepare'}]


def example_bindings() -> dict:
    return {field: {'mode': 'variable', 'name': field} for field in ADAPTER['fields']}


def example_recipe() -> dict:
    return compile_lesson(example_events(), example_bindings(), name='Daily topic previews',
                          verification_contract=ADAPTER['verifier'], max_rows=10)


def example_rows() -> list[dict]:
    return [{'row_id': 'architecture', 'values': {'topic': 'architecture', 'layout': 'detailed', 'captions': True}},
            {'row_id': 'gardens', 'values': {'topic': 'city gardens', 'layout': 'compact', 'captions': False}},
            {'row_id': 'interiors', 'values': {'topic': 'quiet interiors', 'layout': 'detailed', 'captions': True}}]
