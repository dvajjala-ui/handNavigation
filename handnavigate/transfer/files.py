"""Bounded authenticated HTTP reads and independent image decoding."""
from hashlib import sha256
from io import BytesIO
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import warnings

from PIL import Image, UnidentifiedImageError

from ..live.contracts import LiveError


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def read_url(context, scope, url, max_bytes, deadline):
    """Each redirect rechecks scope and selects cookies for that exact destination.

    Only read requests use this transport; uploads always use the actual browser form.
    No browser-policy fallback or alternate browser engine is involved.
    """
    opener = build_opener(NoRedirect)
    for _ in range(6):
        scope.check(url)
        if not scope.permits_request(url, 'GET'):
            raise LiveError('Image GET is outside the reviewed request scope')
        remaining = deadline-time.monotonic()
        if remaining <= 0:
            raise LiveError('Transfer runtime budget exhausted')
        cookies = context.cookies([url])
        headers = {'User-Agent': 'HandNavigate/1.0', 'Accept': 'image/*', 'Accept-Encoding': 'identity'}
        if cookies:
            headers['Cookie'] = '; '.join(c['name']+'='+c['value'] for c in cookies)
        try:
            response = opener.open(Request(url, headers=headers), timeout=min(15, remaining))
        except HTTPError as exc:
            if exc.code in {301, 302, 303, 307, 308}:
                destination = urljoin(url, exc.headers.get('Location', ''))
                exc.close()
                if not destination or destination == url:
                    raise LiveError('Invalid image redirect') from None
                if urlsplit(url).scheme == 'https' and urlsplit(destination).scheme != 'https':
                    raise LiveError('Image redirect would downgrade HTTPS') from None
                url = destination
                continue
            code = exc.code
            exc.close()
            raise LiveError(f'Image HTTP {code}; no write action was retried') from None
        except (URLError, TimeoutError, OSError):
            raise LiveError('Image network read failed; retry this run after checking connectivity') from None
        with response:
            length = response.headers.get('Content-Length')
            if length and (not length.isdigit() or int(length) > max_bytes):
                raise LiveError('Image exceeds the transfer byte limit')
            chunks, size = [], 0
            while True:
                if time.monotonic() >= deadline:
                    raise LiveError('Transfer runtime budget exhausted')
                chunk = response.read(min(65536, max_bytes-size+1))
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise LiveError('Image exceeds the transfer byte limit')
                chunks.append(chunk)
            if length and size != int(length):
                raise LiveError('Image transfer was truncated')
            return b''.join(chunks)
    raise LiveError('Too many image redirects')


def image_metadata(data, limits):
    if not 1 <= len(data) <= limits['max_bytes']:
        raise LiveError('Image bytes are empty or oversized')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                fmt, size = image.format, image.size
                if fmt not in {'PNG', 'JPEG', 'WEBP'}:
                    raise LiveError('Only decoded PNG, JPEG and WebP images are accepted')
                if size[0]*size[1] > limits['max_pixels']:
                    raise LiveError('Image exceeds the decoded pixel limit')
                if size[0] < limits['min_width'] or size[1] < limits['min_height']:
                    raise LiveError('Image does not meet the minimum dimensions')
                if getattr(image, 'n_frames', 1) != 1:
                    raise LiveError('Animated images require a separate reviewed adapter')
                image.verify()
            with Image.open(BytesIO(data)) as image:
                image.load()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise LiveError('Downloaded content is not a valid bounded image') from None
    extension = {'PNG': '.png', 'JPEG': '.jpg', 'WEBP': '.webp'}[fmt]
    return {'sha256': sha256(data).hexdigest(), 'bytes': len(data), 'format': fmt,
            'mime': {'PNG': 'image/png', 'JPEG': 'image/jpeg', 'WEBP': 'image/webp'}[fmt],
            'extension': extension, 'width': size[0], 'height': size[1]}
