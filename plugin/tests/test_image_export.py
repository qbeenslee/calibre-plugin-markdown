# -*- coding: utf-8 -*-
"""Image export: into an explicit folder, into the sidecar, or inlined."""

import base64

from calibre_plugins.markdown.utils.helpers import (
    DEFAULT_IMAGE_DIR,
    export_mapped_images,
    inline_image_references,
    referenced_image_map,
)

JPEG = b'\xff\xd8\xff\xe0JPEG'


class FakeItem:
    def __init__(self, data, href='images/cover.jpeg'):
        self.data = data
        self.href = href


class FakeOEB:
    def __init__(self, items=None):
        self.manifest = [FakeItem(JPEG)] if items is None else items


def test_referenced_image_map_keeps_the_referenced_ones():
    text = 'body\n\n![cover](%s/000000.jpeg)\n' % DEFAULT_IMAGE_DIR
    mapping = {'images/cover.jpeg': '000000.jpeg', 'images/logo.png': '000001.png'}
    assert referenced_image_map(text, mapping) == {
        'images/cover.jpeg': '000000.jpeg'}


def test_referenced_image_map_drops_the_unreferenced_cover():
    # export_cover_page unchecked: the cover page is skipped, so nothing in
    # the Markdown points at the cover image.
    assert referenced_image_map(
        'body\n', {'images/cover.jpeg': '000000.jpeg'}) == {}


def test_referenced_image_map_handles_empty_inputs():
    assert referenced_image_map('', {'images/a.png': 'a.png'}) == {}
    assert referenced_image_map('body\n', {}) == {}
    assert referenced_image_map('body\n', {'images/a.png': ''}) == {}


def test_export_into_explicit_dir(tmp_path):
    dest = tmp_path / 'images'
    written = export_mapped_images(
        FakeOEB(), {'images/cover.jpeg': 'cover.jpeg'},
        str(tmp_path / 'x.md'), dest_dir=str(dest))
    assert written == 1
    assert (dest / 'cover.jpeg').read_bytes() == JPEG


def test_export_defaults_to_sidecar(tmp_path):
    md = tmp_path / 'x.md'
    assert export_mapped_images(
        FakeOEB(), {'images/cover.jpeg': 'cover.jpeg'}, str(md)) == 1
    assert (tmp_path / 'x.images' / 'cover.jpeg').read_bytes() == JPEG


def test_no_images_creates_nothing(tmp_path):
    md = tmp_path / 'x.md'
    assert export_mapped_images(FakeOEB(), {}, str(md)) == 0
    assert not (tmp_path / 'x.images').exists()


def test_existing_empty_dir_is_left_alone(tmp_path):
    # A caller-owned folder must survive a conversion that writes no images.
    dest = tmp_path / 'images'
    dest.mkdir()
    oeb = FakeOEB(items=[])
    assert export_mapped_images(
        oeb, {'images/cover.jpeg': 'cover.jpeg'}, str(tmp_path / 'x.md'),
        dest_dir=str(dest)) == 0
    assert dest.is_dir()
    assert list(dest.iterdir()) == []


def test_mapped_name_cannot_escape_the_folder(tmp_path):
    md = tmp_path / 'x.md'
    assert export_mapped_images(
        FakeOEB(), {'images/cover.jpeg': '../../escape.jpeg'}, str(md)) == 1
    assert (tmp_path / 'x.images' / 'escape.jpeg').exists()
    assert not (tmp_path / 'escape.jpeg').exists()


def test_inline_replaces_reference_with_data_uri():
    text = 'cover:\n\n![cover](%s/cover.jpeg)\n' % DEFAULT_IMAGE_DIR
    out, count = inline_image_references(
        text, FakeOEB(), {'images/cover.jpeg': 'cover.jpeg'})
    assert count == 1
    assert '![cover](data:image/jpeg;base64,' in out
    assert '%s/cover.jpeg' % DEFAULT_IMAGE_DIR not in out


def test_inline_payload_is_the_image_bytes():
    text = '![cover](%s/cover.jpeg)' % DEFAULT_IMAGE_DIR
    out, count = inline_image_references(
        text, FakeOEB(), {'images/cover.jpeg': 'cover.jpeg'})
    payload = out.split('base64,')[1].split(')')[0]
    assert base64.b64decode(payload) == JPEG


def test_unmapped_reference_is_left_alone():
    text = '![x](%s/a.png)' % DEFAULT_IMAGE_DIR
    out, count = inline_image_references(
        text, FakeOEB(), {'images/other.png': 'other.png'})
    assert count == 0 and out == text


def test_inline_without_images_is_noop():
    text = '![x](%s/a.png)' % DEFAULT_IMAGE_DIR
    out, count = inline_image_references(text, FakeOEB(), {})
    assert count == 0 and out == text
