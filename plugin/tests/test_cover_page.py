# -*- coding: utf-8 -*-
"""The export_cover_page option: titlepage skipping and option wiring.

Checked (default) keeps processing titlepage.xhtml; unchecked skips those
spine items while the rest of the book renders normally.
"""

import types

from calibre_plugins.markdown.output.convert_flow import apply_prefs_to_opts
from calibre_plugins.markdown.utils.helpers import is_titlepage_href
from calibre_plugins.markdown.output.output_plugin import MarkdownOutput
from calibre_plugins.markdown.utils.prefs import (
    DEFAULTS,
    EXPORT_OPTION_KEYS,
    serialize_customization,
)


class Log:
    def __init__(self):
        self.infos = []

    def info(self, message):
        self.infos.append(message)


class OEB:
    def __init__(self, hrefs):
        self.spine = [types.SimpleNamespace(href=h) for h in hrefs]


def _mlizer(opts):
    from calibre_plugins.markdown.output.markdownml_enhanced import (
        EnhancedMarkdownMLizer,
    )
    mlizer = EnhancedMarkdownMLizer(Log())
    mlizer.opts = opts
    return mlizer


def test_is_titlepage_href():
    assert is_titlepage_href('titlepage.xhtml')
    assert is_titlepage_href('Text/titlepage.xhtml')
    assert is_titlepage_href('TitlePage.XHTML')
    assert is_titlepage_href('titlepage.html')
    assert not is_titlepage_href('Text/chapter1.xhtml')
    assert not is_titlepage_href('Text/titlepage.xhtml.bak')
    assert not is_titlepage_href(None)
    assert not is_titlepage_href('')


def test_titlepage_processed_by_default():
    mlizer = _mlizer(types.SimpleNamespace(export_cover_page=True))
    oeb = OEB(['Text/titlepage.xhtml', 'Text/c1.xhtml'])
    mlizer.mlize_spine(oeb)
    assert [i.href for i in mlizer.mlize_seen_spine] == [
        'Text/titlepage.xhtml', 'Text/c1.xhtml']
    assert not mlizer.log.infos


def test_missing_option_means_process():
    mlizer = _mlizer(types.SimpleNamespace())
    oeb = OEB(['Text/titlepage.xhtml'])
    mlizer.mlize_spine(oeb)
    assert [i.href for i in mlizer.mlize_seen_spine] == ['Text/titlepage.xhtml']


def test_titlepage_skipped_when_disabled():
    mlizer = _mlizer(types.SimpleNamespace(export_cover_page=False))
    oeb = OEB(['Text/c1.xhtml', 'Text/titlepage.xhtml', 'Text/c2.xhtml'])
    mlizer.mlize_spine(oeb)
    assert [i.href for i in mlizer.mlize_seen_spine] == [
        'Text/c1.xhtml', 'Text/c2.xhtml']
    # The original spine object is restored for later stages (e.g. the
    # cover lookup in _cover_markdown).
    assert [i.href for i in oeb.spine] == [
        'Text/c1.xhtml', 'Text/titlepage.xhtml', 'Text/c2.xhtml']
    assert mlizer.log.infos


class FakeGuide:
    def __init__(self, href):
        self._href = href

    def get(self, key):
        if key == 'cover' and self._href:
            return types.SimpleNamespace(href=self._href)
        return None


def _cover_oeb():
    """Cover reference pointing straight at an image item (not in spine)."""
    return types.SimpleNamespace(
        guide=FakeGuide('cover.jpeg'),
        metadata=types.SimpleNamespace(cover=[]),
        manifest=[types.SimpleNamespace(id='c', href='cover.jpeg')],
        spine=[],
    )


def test_cover_markdown_rendered_when_export_enabled():
    mlizer = _mlizer(types.SimpleNamespace(
        export_cover_page=True, keep_image_references=True))
    mlizer.images = {'cover.jpeg': '000000.jpeg'}
    assert mlizer._cover_markdown(_cover_oeb()) == \
        '![Cover](images/000000.jpeg)\n\n'


def test_cover_markdown_suppressed_when_export_disabled():
    mlizer = _mlizer(types.SimpleNamespace(
        export_cover_page=False, keep_image_references=True))
    mlizer.images = {'cover.jpeg': '000000.jpeg'}
    assert mlizer._cover_markdown(_cover_oeb()) == ''


def test_option_registered():
    option = next(o for o in MarkdownOutput.options
                  if o.option.name == 'export_cover_page')
    assert option.recommended_value is True
    assert 'export_cover_page' in MarkdownOutput.overridable_options
    assert 'export_cover_page' in EXPORT_OPTION_KEYS
    assert DEFAULTS['export_cover_page'] is True


def test_prefs_flow_applies_export_cover_page():
    class Opts:
        pass

    opts = Opts()
    apply_prefs_to_opts(opts, {'export_cover_page': False})
    assert opts.export_cover_page is False
