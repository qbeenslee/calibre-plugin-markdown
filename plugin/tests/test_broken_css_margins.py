# -*- coding: utf-8 -*-
"""A book's unreadable CSS margin must not take the conversion down.

calibre expands the `margin` shorthand itself, so a typo like
`margin: -2em 0 olid #20F2f0` reaches the renderer as `margin-bottom: olid`.
unit_convert() hands values it does not understand back as the same string, and
upstream's soft-scene-break code then calls float() on it: the ValueError aborts
the whole conversion, so the book never exports at all.

The renderer resets such a value to 0 before anything reads it. The declaration
is the book's own typo and "no margin" is the honest reading of it - upstream
then computes a negative em count and writes no scene-break blank line.
"""

import types

XHTML = 'http://www.w3.org/1999/xhtml'


class Log:
    def __init__(self):
        self.messages = []

    def info(self, message):
        self.messages.append(message)

    def debug(self, message):
        pass


class FakeStyle:
    """Matches the slices of calibre's Style this renderer reads."""

    def __init__(self, declared=None):
        self._declared = dict(declared or {})
        self._base = {'display': 'block', 'visibility': 'visible',
                      'font-style': 'normal', 'font-weight': 'normal'}

    def get(self, name, default=None):
        return self._declared.get(name, default)

    def set(self, name, value):
        self._declared[name] = value

    def cssdict(self):
        return dict(self._declared)

    def __getitem__(self, name):
        return self._base[name]

    def __contains__(self, name):
        return name in self._base


class FakeStylizer:
    def __init__(self, style):
        self._style = style

    def style(self, elem):
        return self._style


def _mlizer(**opt_values):
    from calibre_plugins.markdown.output.markdownml_enhanced import (
        EnhancedMarkdownMLizer,
    )
    options = {'keep_image_references': True}
    options.update(opt_values)
    mlizer = EnhancedMarkdownMLizer(Log())
    mlizer.opts = types.SimpleNamespace(**options)
    mlizer.in_pre = False
    mlizer.in_code = False
    mlizer._in_table_cell = False
    mlizer._in_figure = False
    mlizer._repaired_margins = []
    return mlizer


def _elem(**attribs):
    tail = attribs.pop('tail', None)
    return types.SimpleNamespace(
        tag='{%s}img' % XHTML, attrib=dict(attribs), tail=tail)


# ------------------------------------------------------------- the repair

def test_unreadable_margin_is_reset_to_zero():
    from calibre_plugins.markdown.output.renderers.primitives import (
        repair_margin_lengths,
    )
    style = FakeStyle({'margin-bottom': 'olid'})

    assert repair_margin_lengths(style) == [('margin-bottom', 'olid')]
    assert style.get('margin-bottom') == '0'


def test_readable_lengths_and_keywords_are_left_alone():
    from calibre_plugins.markdown.output.renderers.primitives import (
        repair_margin_lengths,
    )
    for value in ('2em', '1.5em', '-2em', '50%', '0', '0%', '15px', '1pt',
                  'auto', 'inherit', 'initial', 'unset', 12, 2.5):
        style = FakeStyle({'margin-top': value, 'margin-bottom': value})
        assert repair_margin_lengths(style) == [], value
        assert style.get('margin-top') == value


def test_unreadable_unit_suffix_is_reset():
    # 老人修仙记 declares `margin: 1em 1em 1em 1emem`.
    from calibre_plugins.markdown.output.renderers.primitives import (
        repair_margin_lengths,
    )
    style = FakeStyle({'margin-bottom': '1emem'})

    assert repair_margin_lengths(style) == [('margin-bottom', '1emem')]
    assert style.get('margin-bottom') == '0'


def test_empty_value_is_reset():
    # float('') fails the same way float('olid') does.
    from calibre_plugins.markdown.output.renderers.primitives import (
        repair_margin_lengths,
    )
    style = FakeStyle({'margin-top': ''})

    assert repair_margin_lengths(style) == [('margin-top', '')]
    assert style.get('margin-top') == '0'


def test_missing_margins_are_not_invented():
    from calibre_plugins.markdown.output.renderers.primitives import (
        repair_margin_lengths,
    )
    style = FakeStyle({'text-indent': '2em'})

    assert repair_margin_lengths(style) == []
    assert style.cssdict() == {'text-indent': '2em'}


def test_other_sides_are_left_alone():
    # Only the top/bottom margins are float()ed by the renderer; the left/right
    # ones must not be rewritten behind the book's back.
    from calibre_plugins.markdown.output.renderers.primitives import (
        repair_margin_lengths,
    )
    style = FakeStyle({'margin-left': '#20F2f0', 'margin-right': 'olid'})

    assert repair_margin_lengths(style) == []
    assert style.get('margin-left') == '#20F2f0'


def test_repair_is_idempotent():
    from calibre_plugins.markdown.output.renderers.primitives import (
        repair_margin_lengths,
    )
    style = FakeStyle({'margin-bottom': 'olid'})

    assert repair_margin_lengths(style) == [('margin-bottom', 'olid')]
    assert repair_margin_lengths(style) == []


def test_style_without_the_calibre_accessors_is_skipped():
    from calibre_plugins.markdown.output.renderers.primitives import (
        repair_margin_lengths,
    )

    assert repair_margin_lengths(object()) == []


# ------------------------------------------------------------- the wiring

def test_dump_text_repairs_the_style_before_rendering():
    style = FakeStyle({'margin-bottom': 'olid'})
    mlizer = _mlizer()

    mlizer.dump_text(_elem(src='images/1.jpg'), FakeStylizer(style))

    assert style.get('margin-bottom') == '0'
    assert mlizer._repaired_margins == [('margin-bottom', 'olid')]


def test_dump_text_keeps_a_readable_margin():
    style = FakeStyle({'margin-bottom': '2em'})
    mlizer = _mlizer()

    mlizer.dump_text(_elem(src='images/1.jpg'), FakeStylizer(style))

    assert style.get('margin-bottom') == '2em'
    assert mlizer._repaired_margins == []


def test_summary_line_names_the_values_once():
    from calibre_plugins.markdown.output.renderers.primitives import (
        margin_repair_summary,
    )

    summary = margin_repair_summary(
        [('margin-bottom', 'olid'), ('margin-bottom', 'olid'),
         ('margin-top', '1emem')])

    assert '3' in summary
    assert 'olid' in summary and '1emem' in summary
    assert summary.count('olid') == 1
