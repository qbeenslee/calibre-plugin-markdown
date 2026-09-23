# -*- coding: utf-8 -*-
"""Remote image download for the Markdown output (pure stdlib).

The input side passes http(s) image URLs through untouched, so an
``<img src="https://...">`` in the book reaches the output Markdown as
``![alt](https://...)`` - or, for a sized image, as the raw-HTML form.
When "Export image files" is on, these helpers download such images into
the folder the local images use and point the references at the copies.
Failures never block the conversion: the caller keeps the URL references
and reports them in the conversion report.
"""

import os
import re
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from calibre_plugins.markdown.utils.helpers import DEFAULT_IMAGE_DIR, _data_uri

#: URL schemes worth downloading; anything else (data:, file:, ftp:, ...)
#: stays exactly as written.
REMOTE_SCHEMES = frozenset(('http', 'https'))

#: Per-request timeout and response size cap: a stalled or huge host must
#: not hang a conversion or bloat the library folder.
REQUEST_TIMEOUT = 10.0
MAX_IMAGE_BYTES = 50 * 1024 * 1024

#: Some CDNs reject the bare python user agent with 403.
USER_AGENT = 'Mozilla/5.0 (compatible; calibre-markdown-plugin)'

#: ![alt](url). The URL is whatever sits between the parentheses - the same
#: slice rewrite_remote_image_refs matches - so a URL with whitespace is
#: captured whole and rejected by the guard instead of being truncated.
_MARKDOWN_IMAGE_RE = re.compile(r'(!\[[^\]]*\]\()([^)]+)(\))')

#: <img src="url"> / <img src='url'>, the raw-HTML form sized images produce.
_HTML_IMAGE_RE = re.compile(
    r'<img\b[^>]*?\bsrc=(?:"([^"]*)"|\'([^\']*)\')', re.I)

#: Content types a URL without a usable extension may declare.
_CONTENT_TYPE_EXTS = {
    'image/jpeg': '.jpg', 'image/jpg': '.jpg', 'image/pjpeg': '.jpg',
    'image/png': '.png',
    'image/gif': '.gif',
    'image/webp': '.webp',
    'image/svg+xml': '.svg',
    'image/bmp': '.bmp', 'image/x-ms-bmp': '.bmp',
    'image/tiff': '.tif',
    'image/avif': '.avif',
    'image/x-icon': '.ico', 'image/vnd.microsoft.icon': '.ico',
}


def _is_downloadable(url):
    """True for a whitespace-free http(s) URL; anything else stays a URL."""
    if not url or url != url.strip() or re.search(r'\s', url):
        return False
    try:
        scheme = urlparse(url).scheme.lower()
    except ValueError:
        return False
    return scheme in REMOTE_SCHEMES


def collect_remote_image_urls(text):
    """The http(s) image URLs the Markdown references, in first-seen order.

    Both spellings count - ![alt](url) and <img src="url"> - and a URL
    appearing in both (or many times) is collected once.
    """
    if not text or '://' not in text:
        return []
    urls = {}
    for match in _MARKDOWN_IMAGE_RE.finditer(text):
        url = match.group(2)
        if _is_downloadable(url):
            urls.setdefault(url, None)
    for match in _HTML_IMAGE_RE.finditer(text):
        url = match.group(1) if match.group(1) is not None else match.group(2)
        if _is_downloadable(url):
            urls.setdefault(url, None)
    return list(urls)


def _extension_for(url, content_type):
    """The extension to store the image under ('.img' as the fallback)."""
    ext = os.path.splitext(urlparse(url).path)[1].lower()
    if re.fullmatch(r'\.[a-z0-9]{1,5}', ext):
        return ext
    return _CONTENT_TYPE_EXTS.get(content_type, '.img')


def fetch_remote_image(url, timeout=REQUEST_TIMEOUT, max_bytes=MAX_IMAGE_BYTES):
    """Download one image. Returns (data, extension) or None on any failure."""
    try:
        request = Request(url, headers={'User-Agent': USER_AGENT})
        with urlopen(request, timeout=timeout) as response:
            content_type = (response.headers.get('Content-Type') or '').split(
                ';', 1)[0].strip().lower()
            data = response.read(max_bytes + 1)
    except Exception:
        return None
    if not data or len(data) > max_bytes:
        return None
    return data, _extension_for(url, content_type)


def rewrite_remote_image_refs(text, replacements):
    """Point every reference at each URL to its replacement src.

    Both spellings are rewritten everywhere they occur and only the src
    changes - alt/width/height attributes stay untouched. Returns
    (new_text, number_of_references_replaced).
    """
    if not text or not replacements:
        return text, 0
    count = 0
    for url, target in replacements.items():
        pattern = re.compile(r'(!\[[^\]]*\]\()' + re.escape(url) + r'\)')
        text, replaced = pattern.subn(
            lambda match: match.group(1) + target + ')', text)
        count += replaced
        pattern = re.compile(
            r'(<img\b[^>]*?\bsrc=["\'])' + re.escape(url) + r'(["\'])', re.I)
        text, replaced = pattern.subn(
            lambda match: match.group(1) + target + match.group(2), text)
        count += replaced
    return text, count


def download_remote_images(text, urls, dest_dir, start_index):
    """Download the urls into dest_dir; point the references at the copies.

    File names continue the %06d sequence the manifest images use, so a
    downloaded image can never collide with a local one. The folder is
    created only when at least one image is saved. Returns
    (new_text, saved_count, failed_urls).
    """
    replacements = {}
    failed = []
    index = start_index
    for url in urls:
        fetched = fetch_remote_image(url)
        if fetched is None:
            failed.append(url)
            continue
        data, ext = fetched
        fname = '%06d%s' % (index, ext)
        index += 1
        try:
            os.makedirs(dest_dir, exist_ok=True)
            with open(os.path.join(dest_dir, fname), 'wb') as handle:
                handle.write(data)
        except OSError:
            failed.append(url)
            continue
        replacements[url] = '%s/%s' % (DEFAULT_IMAGE_DIR, fname)
    text, _count = rewrite_remote_image_refs(text, replacements)
    return text, len(replacements), failed


def inline_remote_images(text, urls):
    """Replace the url references with inline data URIs (nothing on disk).

    Returns (new_text, inlined_reference_count, failed_urls); a URL
    referenced more than once counts once per reference.
    """
    replacements = {}
    failed = []
    for url in urls:
        fetched = fetch_remote_image(url)
        if fetched is None:
            failed.append(url)
            continue
        data, ext = fetched
        replacements[url] = _data_uri('image%s' % ext, data)
    text, count = rewrite_remote_image_refs(text, replacements)
    return text, count, failed


def _name_stem(url):
    """The sanitized file-name stem for the image at url."""
    stem = os.path.basename(urlparse(url).path)
    stem = os.path.splitext(stem)[0]
    stem = re.sub(r'[^\w.\-]', '_', stem, flags=re.UNICODE).strip('._-')
    return stem or 'image'


def save_remote_image(url, dest_dir, reserved):
    """Fetch url and write it into dest_dir under a URL-derived name.

    reserved is the set of taken base names (updated with the new one), so
    a second URL with the same basename - or a name an already staged or
    local file uses - is never overwritten: the later image gains a -2/-3
    suffix. Returns the file name, or None on any failure, in which case
    the caller keeps the URL reference.
    """
    fetched = fetch_remote_image(url)
    if fetched is None:
        return None
    data, ext = fetched
    stem = _name_stem(url)
    name = '%s%s' % (stem, ext)
    counter = 1
    while name in reserved:
        counter += 1
        name = '%s-%d%s' % (stem, counter, ext)
    try:
        os.makedirs(dest_dir, exist_ok=True)
        with open(os.path.join(dest_dir, name), 'wb') as handle:
            handle.write(data)
    except OSError:
        return None
    reserved.add(name)
    return name
