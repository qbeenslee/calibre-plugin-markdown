# -*- coding: utf-8 -*-
"""The heading_anchors option: {#slug} suffix on exported headings.

On (default) each heading keeps its auto-generated anchor; off exports
plain headings like `### 第1章`.
"""

import types

from calibre_plugins.markdown.output.convert_flow import apply_prefs_to_opts
from calibre_plugins.markdown.output.output_plugin import MarkdownOutput
from calibre_plugins.markdown.utils.prefs import (
    DEFAULTS,
    EXPORT_OPTION_KEYS,
    serialize_customization,
)


class Log:
    def info(self, message):
        pass


class FakeHeading:
    def __init__(self, text):
        self.text = text
        self.tail = None
        self.attrib = {}

    def __iter__(self):
        return iter([])


def _heading_mlizer(opts):
    from calibre_plugins.markdown.output.markdownml_enhanced import (
        EnhancedMarkdownMLizer,
    )
    mlizer = EnhancedMarkdownMLizer(Log())
    mlizer.opts = opts
    mlizer.blockquotes = 0
    mlizer.in_pre = False
    mlizer.in_code = False
    mlizer._heading_slugs = set()
    return mlizer


def test_heading_anchor_appended_by_default():
    mlizer = _heading_mlizer(types.SimpleNamespace(heading_anchors=True))
    out = ''.join(mlizer._dump_heading(FakeHeading('第1章'), None, 'h3'))
    assert out == '\n### 第1章 {#第1章}\n'


def test_heading_anchor_omitted_when_disabled():
    mlizer = _heading_mlizer(types.SimpleNamespace(heading_anchors=False))
    out = ''.join(mlizer._dump_heading(FakeHeading('第1章'), None, 'h3'))
    assert out == '\n### 第1章\n'
    assert '{#' not in out


def test_heading_anchor_default_when_option_missing():
    mlizer = _heading_mlizer(types.SimpleNamespace())
    out = ''.join(mlizer._dump_heading(FakeHeading('第1章'), None, 'h3'))
    assert '{#第1章}' in out


def test_option_registered():
    option = next(o for o in MarkdownOutput.options
                  if o.option.name == 'heading_anchors')
    assert option.recommended_value is True
    assert 'heading_anchors' in MarkdownOutput.overridable_options
    assert 'heading_anchors' in EXPORT_OPTION_KEYS
    assert DEFAULTS['heading_anchors'] is True


def test_prefs_flow_applies_heading_anchors():
    class Opts:
        pass

    opts = Opts()
    apply_prefs_to_opts(opts, {'heading_anchors': False})
    assert opts.heading_anchors is False
