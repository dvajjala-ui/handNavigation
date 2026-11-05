"""Per-source collection settings shared by the scheduler and the batch collectors.

Each entry states the exact origins a run may touch, the selector that counts one
displayed picture as one candidate, and the verification flag a topic must earn
before that source may be scheduled for it. Nothing here bypasses a sign-in wall:
a source that reports a block or a challenge ends its run unresolved.
"""
from __future__ import annotations

from urllib.parse import urlsplit

PINTEREST_BROWSER_ORIGINS = ['https://www.pinterest.com', 'https://in.pinterest.com',
                             'https://s.pinimg.com', 'https://s1.pinimg.com', 'https://s2.pinimg.com']
REDDIT_BROWSER_ORIGINS = ['https://www.reddit.com', 'https://old.reddit.com', 'https://reddit.com']

SOURCES = {
    'pinterest': {
        'label': 'Pinterest',
        'verified_column': 'pinterest_verified',
        'url_column': 'pinterest_url',
        'browser_origins': PINTEREST_BROWSER_ORIGINS,
        'image_origins': ['https://i.pinimg.com'],
        'image_selector': 'a[href*="/pin/"] img:not([data-test-id="gated-pin-image"])',
        'gated_selector': '[data-test-id="gated-pin-image"]',
        'wall_markers': ('log in', 'sign up', 'continue with', 'access denied'),
    },
    'reddit': {
        'label': 'Reddit',
        'verified_column': 'reddit_verified',
        'url_column': 'reddit_url',
        'browser_origins': REDDIT_BROWSER_ORIGINS,
        'image_origins': ['https://i.redd.it', 'https://preview.redd.it',
                          'https://external-preview.redd.it', 'https://styles.reddit.com',
                          'https://emoji.reddit.com'],
        # One displayed post thumbnail contributes one URL; srcset variants of the
        # same picture must not count toward the requested number of images.
        'image_selector': 'a[href*="/comments/"] img',
        'gated_selector': 'faceplate-login-prompt, [data-testid="gateway-bottom-ribbon"]',
        'wall_markers': ("you've been blocked by network security", 'whoa there, pardner',
                         'blocked due to a network policy', 'log in', 'create an account'),
    },
}


def source_config(key):
    if key not in SOURCES:
        raise ValueError('Unknown image source. Choose ' + ' or '.join(sorted(SOURCES)) + '.')
    return SOURCES[key]


# Origins a collection run may load, versus the smaller set a person may be sent
# to by hand when signing in. Static asset hosts are never a sign-in destination.
PAGE_HOSTS = {'pinterest': ('www.pinterest.com', 'in.pinterest.com'),
              'reddit': ('www.reddit.com', 'old.reddit.com', 'reddit.com')}


def login_page_url(key, url):
    """An exact public HTTPS page of this source, for the manual sign-in helper."""
    config = source_config(key)
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.netloc not in PAGE_HOSTS[key]
            or parsed.username or parsed.password or parsed.fragment):
        raise ValueError('Choose an exact public HTTPS ' + config['label']
                         + ' page without credentials, ports or fragments.')
    return url


def reddit_page_url(subreddit):
    return 'https://www.reddit.com/r/' + subreddit + '/top/?t=month'
