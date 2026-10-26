"""Actual browser/HTTP source-to-destination transfers, not set_content or stubbed uploads."""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO

from PIL import Image
import pytest

from handnavigate.live.contracts import LiveError
from handnavigate.transfer.contracts import approve, template, validate
from handnavigate.transfer.engine import Transfer
from handnavigate.transfer.files import image_metadata


from handnavigate.transfer.demo import running_demo as sites


def run(recipe, root, job='day-1', **kwargs):
    return Transfer(recipe, {}, approve(recipe, {}), root, job, **kwargs).run()


def test_ten_real_images_cross_site_upload_and_idempotent_rerun(tmp_path):
    with sites() as (recipe, uploads, images, state):
        result = run(recipe, tmp_path)
        assert result['status'] == 'VERIFIED', result
        assert result['confirmed'] == 10
        assert result['model_calls'] == 0
        assert len(uploads) == state['post_count'] == 10
        assert {sha256(x).hexdigest() for x in uploads} == {r['sha256'] for r in result['items']}
        assert {r['format'] for r in result['items']} == {'PNG', 'JPEG', 'WEBP'}
        repeated = run(recipe, tmp_path)
        assert repeated['status'] == 'VERIFIED', repeated
        assert repeated['uploaded'] == 0
        assert len(uploads) == state['post_count'] == 10


def test_second_day_selects_ten_new_images(tmp_path):
    with sites() as (recipe, uploads, _, state):
        first = run(recipe, tmp_path)
        second = run(recipe, tmp_path, 'day-2')
        assert first['status'] == second['status'] == 'VERIFIED', (first, second)
        assert len(uploads) == state['post_count'] == 20
        assert len({sha256(x).hexdigest() for x in uploads}) == 20


def test_fewer_than_requested_never_claims_success_or_starts_uploads(tmp_path):
    with sites(count=3) as (recipe, uploads, _, state):
        result = run(recipe, tmp_path)
        assert result['status'] == 'PARTIAL', result
        assert result['downloaded'] == 3
        assert not uploads and not state['post_count']


def test_invalid_image_halts_before_any_upload(tmp_path):
    with sites(corrupt=True) as (recipe, uploads, _, state):
        result = run(recipe, tmp_path)
        assert result['status'] == 'HALTED', result
        assert not uploads and not state['post_count']


def test_fake_success_requires_review_and_never_blindly_retries(tmp_path):
    with sites(upload_mode='fake_success') as (recipe, uploads, _, state):
        recipe['count'] = 1
        result = run(recipe, tmp_path)
        assert result['status'] == 'NEEDS_REVIEW', result
        again = run(recipe, tmp_path)
        assert again['status'] == 'NEEDS_REVIEW', again
        assert state['post_count'] == 1


def test_crash_after_server_acceptance_reconciles_without_duplicate(tmp_path):
    with sites() as (recipe, uploads, _, state):
        recipe['count'] = 2
        def crash(kind, item):
            if kind == 'AFTER_UPLOAD': raise RuntimeError('simulated process interruption')
        first = run(recipe, tmp_path, on_event=crash)
        assert first['status'] == 'NEEDS_REVIEW', first
        assert len(uploads) == 1
        recovered = run(recipe, tmp_path)
        assert recovered['status'] == 'VERIFIED', recovered
        assert recovered['reconciled'] == 1
        assert len(uploads) == state['post_count'] == 2


def test_wrong_account_prevents_upload(tmp_path):
    with sites() as (recipe, uploads, _, state):
        recipe['target']['identity']['text'] = 'Different account'
        result = run(recipe, tmp_path)
        assert result['status'] == 'HALTED'
        assert not uploads and not state['post_count']


def test_tampered_artifact_never_reaches_upload(tmp_path):
    with sites() as (recipe, uploads, _, state):
        recipe['count'] = 1
        def tamper(kind, item):
            if kind == 'DOWNLOADED':
                for path in (tmp_path/'artifacts').iterdir(): path.write_bytes(b'wrong file')
        result = run(recipe, tmp_path, on_event=tamper)
        assert result['status'] == 'HALTED', result
        assert not uploads and not state['post_count']


def test_changed_approval_and_job_contract_rejected(tmp_path):
    with sites(count=1) as (recipe, uploads, _, state):
        recipe['count'] = 1
        receipt = approve(recipe, {})
        changed = deepcopy(recipe); changed['count'] = 2
        with pytest.raises(LiveError): Transfer(changed, {}, receipt, tmp_path, 'day-1')
        assert run(recipe, tmp_path)['status'] == 'VERIFIED'
        before = (tmp_path/'latest-result.json').read_text()
        with pytest.raises(LiveError): run(changed, tmp_path)
        assert (tmp_path/'latest-result.json').read_text() == before


@pytest.mark.parametrize('field,value', [('count', True), ('new_only', 'true'), ('count', 101)])
def test_invalid_transfer_contracts_rejected(field, value):
    recipe = template('https://source.example', 'https://target.example')
    recipe[field] = value
    with pytest.raises(LiveError): validate(recipe)


def test_image_dimensions_and_size_are_enforced():
    recipe = template('https://source.example', 'https://target.example')
    data = BytesIO(); Image.new('RGB', (50, 50)).save(data, format='PNG')
    recipe['limits']['max_pixels'] = 100
    with pytest.raises(LiveError): image_metadata(data.getvalue(), recipe['limits'])


def test_cross_origin_image_redirect_is_blocked_before_request(tmp_path):
    with sites(count=1) as (recipe, uploads, _, state):
        recipe['count'] = 1
        state['image_redirect'] = recipe['target']['url'].replace('/target', '/forbidden')
        result = run(recipe, tmp_path)
        assert result['status'] == 'HALTED', result
        assert not state['blocked_hits'] and not uploads


def test_browser_cookies_are_used_for_authenticated_image_download(tmp_path):
    with sites(count=1, auth=True) as (recipe, uploads, _, state):
        recipe['count'] = 1
        for side, path in [('source', '/source'), ('target', '/target')]:
            base = recipe[side]['scope']['origins'][0]
            recipe[side]['url'] = base+'/login'
            recipe[side]['setup'] = [{'op':'navigate', 'value':base+path}]
        recipe['target']['verify']['url'] = recipe['target']['url']
        recipe['target']['verify']['setup'] = recipe['target']['setup']
        result = run(recipe, tmp_path)
        assert result['status'] == 'VERIFIED', result
        assert len(uploads) == state['post_count'] == 1


def test_async_gallery_pagination_and_upload_on_file_selection(tmp_path):
    with sites(count=3, page_size=1, async_gallery=True, auto_upload=True, async_pagination=True) as (recipe, uploads, _, state):
        recipe['count'] = 2
        recipe['target']['submit'] = None
        result = run(recipe, tmp_path)
        assert result['status'] == 'VERIFIED', result
        assert len(uploads) == state['post_count'] == 2
        again = run(recipe, tmp_path)
        assert again['status'] == 'VERIFIED', again
        assert state['post_count'] == 2


def test_reusing_same_images_confirms_existing_remote_files_without_duplicates(tmp_path):
    with sites(count=1) as (recipe, uploads, _, state):
        recipe['count'] = 1
        recipe['new_only'] = False
        first = run(recipe, tmp_path)
        second = run(recipe, tmp_path, 'day-2')
        assert first['status'] == second['status'] == 'VERIFIED', (first, second)
        assert second['uploaded'] == 0
        assert len(uploads) == state['post_count'] == 1


def test_empty_source_returns_partial_without_uploading(tmp_path):
    with sites(count=0) as (recipe, uploads, _, state):
        result = run(recipe, tmp_path)
        assert result['status'] == 'PARTIAL', result
        assert result['downloaded'] == 0
        assert not uploads and not state['post_count']
