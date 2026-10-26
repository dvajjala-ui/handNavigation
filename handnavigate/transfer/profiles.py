"""Dedicated per-site browser profiles, never the person's normal browser profile."""
from pathlib import Path
import json

from ..live.contracts import LiveError, save_json


def checked_profile(path, scope):
    path = Path(path).resolve()
    marker = path/'.handnavigate-profile.json'
    if path.exists() and (not path.is_dir() or (any(path.iterdir()) and not marker.is_file())):
        raise LiveError('Use a dedicated new profile directory, not your regular browser profile')
    if marker.is_file():
        saved = json.loads(marker.read_text(encoding='utf-8'))
        if saved.get('origins') != list(scope.origins):
            raise LiveError('Browser profile origin scope changed; use a separate profile or review the old one')
    save_json(marker, {'origins': list(scope.origins), 'sensitive': True})
    return path
