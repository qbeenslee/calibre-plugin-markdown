# -*- coding: utf-8 -*-
"""Baseline checks that the test scaffolding itself works.

These cover existing helpers so a broken conftest.py is obvious immediately.
"""

from calibre_plugins.markdown.utils.helpers import (
    DEFAULT_IMAGE_DIR,
    image_sidecar_path,
    rewrite_markdown_image_dir,
)


def test_image_sidecar_path_is_sibling_folder():
    assert image_sidecar_path('/a/b.md') == '/a/b.images'
    assert DEFAULT_IMAGE_DIR == 'images'


def test_rewrite_replaces_default_image_dir():
    src = 'text ![alt](images/cover.jpeg)\n'
    out = rewrite_markdown_image_dir(src, 'book.images')
    assert '(book.images/cover.jpeg)' in out
    assert '(images/cover.jpeg)' not in out
