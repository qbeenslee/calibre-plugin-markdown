# -*- coding: utf-8 -*-
"""One image, one file: the shifted files the builtin handling asks for.

TXT Input calls shift_file() once per <img> element and numbers every copy
('x.png', 'x-1.png', ...) because the copy it wrote before is already there,
so a Markdown file that uses one image 110 times used to ship 110 copies of
it. MarkdownInput.shift_file() writes identical bytes once instead and hands
every reference the same file name.
"""

import os

from calibre_plugins.markdown.input.input_plugin import (
    MarkdownInput,
    _content_digest,
)

PNG = b'\x89PNG\r\n\x1a\nfake-png'
OTHER_PNG = b'\x89PNG\r\n\x1a\nanother-png'
JPEG = b'\xff\xd8\xff\xe0JPEG'


def _plugin(output_dir):
    plugin = MarkdownInput()
    plugin.output_dir = str(output_dir)
    return plugin


def _builtin_embed(plugin, base_dir, srcs):
    """TXT Input's fix_resources loop (html5_parser is unavailable here)."""
    hrefs = []
    for src in srcs:
        with open(os.path.join(base_dir, src), 'rb') as f:
            data = f.read()
        hrefs.append(os.path.basename(
            plugin.shift_file(os.path.basename(src), data)))
    return hrefs


def test_one_image_many_references_ships_one_file(tmp_path):
    # The book references the same file three times: every reference has to
    # point at the one copy that was written.
    base = tmp_path / 'in'
    (base / 'images').mkdir(parents=True)
    (base / 'images' / '000001.png').write_bytes(PNG)
    out = tmp_path / 'out'
    out.mkdir()
    plugin = _plugin(out)

    hrefs = _builtin_embed(plugin, str(base), ['images/000001.png'] * 3)

    assert hrefs == ['000001.png'] * 3
    assert sorted(os.listdir(out)) == ['000001.png']
    assert (out / '000001.png').read_bytes() == PNG


def test_different_images_keep_their_own_file(tmp_path):
    # Two images written under the same name: the -1 numbering the builtin
    # uses for a collision still applies, deduplication does not eat one.
    out = tmp_path / 'out'
    out.mkdir()
    plugin = _plugin(out)

    first = os.path.basename(plugin.shift_file('000001.png', PNG))
    second = os.path.basename(plugin.shift_file('000001.png', OTHER_PNG))

    assert first == '000001.png'
    assert second == '000001-1.png'
    assert (out / first).read_bytes() == PNG
    assert (out / second).read_bytes() == OTHER_PNG


def test_same_bytes_under_another_extension_are_not_merged(tmp_path):
    # The extension is part of the key: it decides the media type, so one
    # image shipped as both .png and .jpg stays two files.
    out = tmp_path / 'out'
    out.mkdir()
    plugin = _plugin(out)

    plugin.shift_file('000001.png', PNG)
    plugin.shift_file('000001.jpg', PNG)

    assert sorted(os.listdir(out)) == ['000001.jpg', '000001.png']


def test_a_vanished_cached_file_is_written_again(tmp_path):
    # A cache entry from an earlier conversion points into a directory that
    # is gone: the file is written again instead of being handed out as a
    # reference to nothing.
    out = tmp_path / 'out'
    out.mkdir()
    plugin = _plugin(out)
    plugin._shifted_by_content = {
        ('.png', _content_digest(PNG)): str(tmp_path / 'gone' / '000001.png')}

    path = plugin.shift_file('000001.png', PNG)

    assert path == str(out / '000001.png')
    assert (out / '000001.png').read_bytes() == PNG


def test_content_that_is_not_bytes_has_no_digest():
    # Anything that is not bytes is shifted the builtin way (no comparison,
    # no caching); TXT Input only ever hands over bytes.
    assert _content_digest('<p>x</p>') == ''
    assert _content_digest(PNG) == _content_digest(bytearray(PNG))
    assert _content_digest(PNG) != _content_digest(JPEG)
