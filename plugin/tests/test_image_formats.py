# -*- coding: utf-8 -*-
"""Image formats: every image the book declares reaches the export.

calibre's OEB2HTML.map_resources maps only the media types its OEB_IMAGES set
lists (gif/jpeg/png/svg), so a book carrying webp images kept their in-EPUB
hrefs in the Markdown - references the .md cannot resolve - and the files were
never exported (sample: library book 17). EnhancedMarkdownMLizer maps the
remaining image media types after calibre's own pass.
"""

import base64
import os
from operator import attrgetter

from calibre_plugins.markdown.utils.helpers import (
    DEFAULT_IMAGE_DIR,
    export_mapped_images,
    inline_image_references,
    referenced_image_map,
)

WEBP = b'RIFF\x24\x00\x00\x00WEBPVP8 fake-webp-bytes'
JPEG = b'\xff\xd8\xff\xe0JPEG'

#: What calibre's OEB_IMAGES lists; the fake base map_resources maps exactly
#: these, which is what makes the webp assertion below meaningful.
CALIBRE_IMAGE_TYPES = frozenset(
    ('image/gif', 'image/jpeg', 'image/png', 'image/svg+xml'))


class FakeItem:
    def __init__(self, href, media_type, data=JPEG):
        self.href = href
        self.media_type = media_type
        self.data = data


class FakeOEB:
    def __init__(self, items):
        self.manifest = list(items)


class Log:
    def __init__(self):
        self.lines = []

    def info(self, message):
        self.lines.append(message)

    def debug(self, message):
        self.lines.append(message)


def _calibre_map_resources(monkeypatch):
    """Install calibre's own image pass on the stub base class.

    The stub MarkdownMLizer has no map_resources; this mirrors the upstream
    one (sorted hrefs, %06d names, OEB_IMAGES only) so the enhanced override
    is exercised against the behaviour it extends.
    """
    from calibre.ebooks.txt import markdownml

    def map_resources(self, oeb_book):
        self.images = {}
        for item in sorted(oeb_book.manifest, key=attrgetter('href')):
            if item.media_type in CALIBRE_IMAGE_TYPES \
                    and item.href not in self.images:
                self.images[item.href] = '%06d%s' % (
                    len(self.images), os.path.splitext(item.href)[1])

    monkeypatch.setattr(
        markdownml.MarkdownMLizer, 'map_resources', map_resources,
        raising=False)


def _map(monkeypatch, items):
    from calibre_plugins.markdown.output.markdownml_enhanced import (
        EnhancedMarkdownMLizer,
    )

    _calibre_map_resources(monkeypatch)
    mlizer = EnhancedMarkdownMLizer(Log())
    mlizer.map_resources(FakeOEB(items))
    return mlizer


def test_webp_is_mapped_without_moving_calibre_numbers(monkeypatch):
    mlizer = _map(monkeypatch, [
        FakeItem('a.png', 'image/png'),
        FakeItem('b.webp', 'image/webp', WEBP),
        FakeItem('c.jpg', 'image/jpeg'),
    ])
    assert mlizer.images == {
        'a.png': '000000.png',
        'c.jpg': '000001.jpg',
        'b.webp': '000002.webp',
    }


def test_a_webp_only_book_numbers_from_zero(monkeypatch):
    mlizer = _map(monkeypatch, [
        FakeItem('x.webp', 'image/webp', WEBP),
        FakeItem('y.webp', 'image/webp', WEBP),
    ])
    assert mlizer.images == {'x.webp': '000000.webp', 'y.webp': '000001.webp'}


def test_other_image_types_calibre_skips_are_mapped_too(monkeypatch):
    mlizer = _map(monkeypatch, [
        FakeItem('p.avif', 'image/avif'),
        FakeItem('q.bmp', 'image/bmp'),
    ])
    assert mlizer.images == {'p.avif': '000000.avif', 'q.bmp': '000001.bmp'}


def test_non_images_are_left_alone(monkeypatch):
    mlizer = _map(monkeypatch, [
        FakeItem('style.css', 'text/css'),
        FakeItem('book.otf', 'application/vnd.ms-opentype'),
        FakeItem('ch1.xhtml', 'application/xhtml+xml'),
        FakeItem('no-type.webp', None),
        FakeItem('empty-type.webp', ''),
        FakeItem('', 'image/webp'),
    ])
    assert mlizer.images == {}


def test_mapping_is_reported_in_the_log(monkeypatch):
    mlizer = _map(monkeypatch, [
        FakeItem('a.png', 'image/png'),
        FakeItem('b.webp', 'image/webp', WEBP),
    ])
    assert any('webp' in line for line in mlizer.log.lines), mlizer.log.lines


def test_mapped_webp_is_exported_and_referenced(monkeypatch, tmp_path):
    mlizer = _map(monkeypatch, [FakeItem('b.webp', 'image/webp', WEBP)])
    text = ('<img src="%s/000000.webp" width="400px" height="auto">'
            % DEFAULT_IMAGE_DIR)
    image_map = referenced_image_map(text, mlizer.images)
    assert image_map == {'b.webp': '000000.webp'}

    oeb = FakeOEB([FakeItem('b.webp', 'image/webp', WEBP)])
    dest = tmp_path / 'images'
    assert export_mapped_images(
        oeb, image_map, str(tmp_path / 'x.md'), dest_dir=str(dest)) == 1
    assert (dest / '000000.webp').read_bytes() == WEBP


def test_webp_is_inlined_as_its_own_mime_type(monkeypatch):
    items = [FakeItem('b.webp', 'image/webp', WEBP)]
    mlizer = _map(monkeypatch, items)
    text = '![x](%s/000000.webp)' % DEFAULT_IMAGE_DIR
    out, count = inline_image_references(text, FakeOEB(items), mlizer.images)
    assert count == 1
    head, payload = out.split('base64,')
    assert 'data:image/webp;' in head
    assert base64.b64decode(payload.split(')')[0]) == WEBP
