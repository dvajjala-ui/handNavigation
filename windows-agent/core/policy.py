from __future__ import annotations
import os
from pathlib import Path
from .models import Permissions, Plan, origin


def checked_path(value: str) -> Path:
    raw=Path(value)
    if not raw.is_absolute() or '..' in raw.parts or str(raw).startswith(('\\\\','//')):
        raise PermissionError('Use an absolute local folder, without traversal or network shares.')
    if os.name=='nt' and (':' in str(raw)[2:] or str(raw).startswith('\\\\')):
        raise PermissionError('Alternate streams and device paths are not supported.')
    # Reject junctions/reparse points as well as symbolic links in every component.
    for parent in [raw,*raw.parents]:
        if parent.is_symlink() or getattr(parent,'is_junction',lambda:False)():
            raise PermissionError('Links and junctions are not allowed in file task paths.')
    return raw.resolve()


class Policy:
    def __init__(self,permissions: Permissions):
        self.permissions=permissions

    def folder(self,value):
        target=checked_path(value)
        if not any(target.is_relative_to(checked_path(root)) for root in self.permissions.cleanup_roots):
            raise PermissionError('Folder is outside saved cleanup permissions. Add it once in Setup.')
        if target==Path(target.anchor):
            raise PermissionError('A whole drive cannot be a cleanup folder.')
        if os.name=='nt':
            protected=[os.environ.get(k,'') for k in ('WINDIR','PROGRAMFILES','PROGRAMFILES(X86)')]
            if any(p and (target.is_relative_to(Path(p).resolve()) or Path(p).resolve().is_relative_to(target)) for p in protected):
                raise PermissionError('System and installed-program folders are excluded from cleanup.')
        return target

    def url(self,url,images=False):
        allowed=self.permissions.browser_origins+(self.permissions.image_origins if images else [])
        if origin(url) not in allowed:
            raise PermissionError('Website is outside saved permissions: '+origin(url))
        return url

    def plan(self,plan: Plan):
        if plan.missing_information:
            raise ValueError('Missing: '+'; '.join(plan.missing_information))
        if plan.kind=='cleanup':
            self.folder(plan.folder)
        else:
            self.url(plan.start_url)
        if plan.upload_url:
            if not self.permissions.allow_upload:
                raise PermissionError('File uploads are not enabled in Setup.')
            self.url(plan.upload_url);self.url(plan.gallery_url)
        if plan.kind=='instagram_like_own' and not self.permissions.allow_instagram_likes:
            raise PermissionError('Own-profile Instagram likes are not enabled in Setup.')
        if plan.kind=='browser' and not self.permissions.allow_browser_changes:
            raise PermissionError('Agent browser interaction is not enabled in Setup.')
