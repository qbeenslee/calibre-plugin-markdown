# -*- coding: utf-8 -*-
"""The "Keep image sizes" option, on the output and the input side.

Output: sized images export as raw <img> HTML when on (see test_image_size.py),
plain ![](path) references when off.

Input: the Markdown's own width/height reach the book when on; when off the
sizes are stripped before calibre's resource handling sees the HTML.
"""

import calibre_plugins.markdown.input.input_plugin as input_mod
from calibre_plugins.markdown.input.input_plugin import MarkdownInput
from calibre_plugins.markdown.output.output_plugin import MarkdownOutput
from calibre_plugins.markdown.utils.helpers import strip_image_sizes
from calibre_plugins.markdown.utils.prefs import (
    DEFAULTS,
    EXPORT_OPTION_KEYS,
    INPUT_OPTION_KEYS,
)


# ----------------------------------------------------------- output side

def test_output_option_registered():
    option = next(o for o in MarkdownOutput.options
                  if o.option.name == 'keep_image_sizes')
    assert option.recommended_value is True
    assert 'keep_image_sizes' in MarkdownOutput.overridable_options
    assert 'keep_image_sizes' in EXPORT_OPTION_KEYS
    assert DEFAULTS['keep_image_sizes'] is True


def test_output_pane_shows_the_option():
    # The customization dialog's BOOL_OPTIONS row and the pane row itself need
    # a widget toolkit; scripts/verify_keep_image_sizes.py covers them on the
    # real thing.
    from calibre_plugins.markdown.output.conversion_ui import option

    assert 'keep_image_sizes' in option


# ------------------------------------------------------------ input side

def test_input_option_registered():
    option = next(o for o in MarkdownInput.options
                  if o.option.name == 'keep_image_sizes')
    assert option.recommended_value is True
    assert 'keep_image_sizes' in INPUT_OPTION_KEYS
    assert DEFAULTS['keep_image_sizes'] is True


def test_input_pane_shows_the_option():
    # The customization dialog's rows are covered on the real thing by
    # scripts/verify_keep_image_sizes.py (Qt at module level).
    from calibre_plugins.markdown.input.conversion_ui import OPTION

    assert 'keep_image_sizes' in OPTION


def _plugin(keep, monkeypatch):
    plugin = MarkdownInput()
    plugin._keep_image_sizes = keep
    plugin._book_dir = None
    monkeypatch.setattr(MarkdownInput, '_image_refs',
                        lambda self, html: [])
    return plugin


def test_fix_resources_drops_the_sizes_when_off(tmp_path, monkeypatch):
    plugin = _plugin(False, monkeypatch)
    html = '<p>text</p><img src="images/1.jpg" width="800" height="auto">'

    out = plugin.fix_resources(html, str(tmp_path))

    assert out == '<p>text</p><img src="images/1.jpg">'
    # The builtin resource handling sees the size-free HTML.
    assert plugin.fix_resources_seen == (out, str(tmp_path))


def test_fix_resources_keeps_the_sizes_when_on(tmp_path, monkeypatch):
    plugin = _plugin(True, monkeypatch)
    html = '<img src="images/1.jpg" width="800">'

    assert plugin.fix_resources(html, str(tmp_path)) == html


def test_sizes_are_kept_when_the_option_was_never_set(tmp_path, monkeypatch):
    # convert() sets the flag; anything reaching fix_resources beforehand
    # keeps calibre's default behaviour (sizes kept).
    plugin = MarkdownInput()
    plugin._book_dir = None
    monkeypatch.setattr(MarkdownInput, '_image_refs', lambda self, html: [])
    html = '<img src="images/1.jpg" width="800">'

    assert plugin.fix_resources(html, str(tmp_path)) == html


# ------------------------------------------------------- size stripping

def test_strip_removes_quoted_attributes():
    assert strip_image_sizes(
        '<img src="a.jpg" width="800" height="600" alt="x">') == \
        '<img src="a.jpg" alt="x">'


def test_strip_removes_single_quoted_and_bare_attributes():
    assert strip_image_sizes("<img src='a.jpg' width='50%' height=200>") == \
        "<img src='a.jpg'>"


def test_strip_removes_style_declarations():
    assert strip_image_sizes(
        '<img src="a.jpg" style="width:50%; margin:0">') == \
        '<img src="a.jpg" style="margin:0">'
    # A style attribute left empty goes away with it.
    assert strip_image_sizes('<img src="a.jpg" style="height:auto">') == \
        '<img src="a.jpg">'


def test_strip_leaves_other_size_names_alone():
    for html in ('<img src="a.jpg" max-width="100%">',
                 '<img src="a.jpg" data-width="5">',
                 '<img src="a.jpg" style="max-width:100%">'):
        assert strip_image_sizes(html) == html


def test_strip_only_touches_img_tags():
    assert strip_image_sizes(
        '<div style="width:50%">x</div><img width="1">') == \
        '<div style="width:50%">x</div><img>'


def test_strip_without_images_is_identity():
    assert strip_image_sizes('plain text') == 'plain text'
    assert strip_image_sizes('') == ''
