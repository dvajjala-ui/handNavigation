from __future__ import annotations
import hashlib
import json
from typing import Literal
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Schedule(Strict):
    time: str = Field(pattern=r'^([01]\d|2[0-3]):[0-5]\d$')
    timezone: str = 'Asia/Kolkata'

    @field_validator('timezone')
    @classmethod
    def zone(cls, value):
        ZoneInfo(value)
        return value


def origin(url: str) -> str:
    u = urlsplit(url)
    if u.scheme not in ('http', 'https') or not u.hostname or u.username or u.password:
        raise ValueError('Use an HTTP(S) URL without credentials.')
    # Exact origins, including explicit non-default ports.
    port = u.port
    host = '[' + u.hostname + ']' if ':' in u.hostname else u.hostname
    return f'{u.scheme}://{host}' + (f':{port}' if port and port != {'http':80,'https':443}[u.scheme] else '')


class Plan(Strict):
    name: str = Field(min_length=1, max_length=120)
    instruction: str = Field(min_length=1, max_length=8000)
    kind: Literal['cleanup', 'images', 'instagram_like_own', 'browser']
    schedule: Schedule | None = None
    folder: str = Field(default='',max_length=2000)
    pattern: str = Field(default='*',max_length=200)
    older_than_days: int = Field(default=0, ge=0, le=36500)
    start_url: str = Field(default='',max_length=3000)
    goal: str = Field(default='',max_length=8000)
    account_marker: str = Field(default='',max_length=200)
    result_selector: str = Field(default='',max_length=500)
    expected_result: str = Field(default='',max_length=2000)
    image_selector: str = Field(default='img',max_length=500)
    upload_url: str = Field(default='',max_length=3000)
    gallery_url: str = Field(default='',max_length=3000)
    file_selector: str = Field(default='input[type=file]',max_length=500)
    submit_name: str = Field(default='',max_length=200)
    max_items: int = Field(default=10, ge=1, le=100)
    max_steps: int = Field(default=25, ge=1, le=60)
    missing_information: list[str] = Field(default_factory=list, max_length=10)

    @model_validator(mode='after')
    def check(self):
        for url in (self.start_url, self.upload_url, self.gallery_url):
            if url:
                origin(url)
        if not self.missing_information:
            if self.kind == 'cleanup' and not self.folder:
                raise ValueError('Cleanup needs an exact folder.')
            if self.kind != 'cleanup' and not self.start_url:
                raise ValueError('Browser tasks need an exact starting URL.')
            if self.upload_url and (not self.gallery_url or not self.account_marker):
                raise ValueError('Uploads need a saved-original gallery URL and expected account text.')
            if self.kind == 'browser' and (not self.goal or not self.account_marker):
                raise ValueError('Browser tasks need a goal and expected account/owned-page text.')
        if not self.pattern or any(c in self.pattern for c in '/\\:') or self.pattern in ('.','..'):
            raise ValueError('Use a filename pattern, without folder paths.')
        if bool(self.result_selector) != bool(self.expected_result):
            raise ValueError('A browser result check needs both an exact selector and expected result text.')
        return self

    def digest(self):
        return hashlib.sha256(json.dumps(self.model_dump(),sort_keys=True).encode()).hexdigest()


class Permissions(Strict):
    cleanup_roots: list[str] = Field(default_factory=list, max_length=30)
    browser_origins: list[str] = Field(default_factory=list, max_length=50)
    image_origins: list[str] = Field(default_factory=list, max_length=50)
    allow_upload: bool = False
    allow_browser_changes: bool = False
    allow_instagram_likes: bool = False

    @model_validator(mode='after')
    def combined_bound(self):
        if len(set(self.browser_origins+self.image_origins))>20:
            raise ValueError('This core supports at most 20 distinct website/image origins.')
        return self

    @field_validator('browser_origins', 'image_origins')
    @classmethod
    def origins(cls, values):
        for value in values:
            if origin(value) != value or urlsplit(value).path:
                raise ValueError('Enter exact origins, for example https://www.instagram.com.')
        return sorted(set(values))


class Action(Strict):
    action: Literal['observe','navigate','click','fill','scroll','wait','finish']
    ref: str = ''
    value: str = Field(default='', max_length=4000)
    url: str = ''
    evidence: str = Field(default='', max_length=2000)
