# -*- coding: utf-8 -*-
"""<hr> is written "***": upstream's "* * *" reads as a row of bullets.

calibre writes the thematic break as "* * *" - the same break, spelled the
way a bulleted list with three empty items looks. "***" is the spelling the
rest of the Markdown world uses, and python-markdown (the parser reading the
.md back) reads both as <hr>. Everything else about the element - the scene
breaks its margins ask for, the newlines around it, its tail - stays as
calibre writes it.
"""

import types

from calibre.ebooks.txt.markdownml import MarkdownMLizer
from calibre_plugins.markdown.output.markdownml_enhanced import (
    EnhancedMarkdownMLizer,
)

XHTML_NS = 'http://www.w3.org/1999/xhtml'
#: What calibre's own dump_text writes for <hr>: the newline that opens the
#: element's line, the break, and the newline that closes it.
UPSTREAM_HR = ['\n* * *', '\n']


class Log:
    def info(self, message):
        pass


class FakeStyle(dict):
    def __init__(self, **overrides):
        super().__init__({
            'display': 'block',
            'visibility': 'visible',
            'font-style': 'normal',
            'font-weight': 'normal',
        })
        self.update(overrides)
        self.marginTop = 0
        self.marginBottom = 0
        self.fontSize = 1

    def cssdict(self):
        return dict(self)


class FakeStylizer:
    def style(self, elem):
        return FakeStyle()


class Hr:
    tag = '{%s}hr' % XHTML_NS
    text = None
    tail = None
    attrib = {}

    def __iter__(self):
        return iter(())

    def __len__(self):
        return 0

    def getparent(self):
        return None


def _mlizer():
    mlizer = EnhancedMarkdownMLizer(Log())
    mlizer.opts = types.SimpleNamespace()
    mlizer.blockquotes = 0
    mlizer.style_italic = False
    mlizer.style_bold = False
    mlizer.in_pre = False
    mlizer.in_code = False
    mlizer._in_table_cell = False
    mlizer._in_figure = False
    return mlizer


def test_hr_is_written_as_three_asterisks(monkeypatch):
    monkeypatch.setattr(MarkdownMLizer, 'dump_text',
                        lambda self, elem, stylizer: list(UPSTREAM_HR),
                        raising=False)
    out = _mlizer().dump_text(Hr(), FakeStylizer())
    assert out == ['\n***', '\n']
    assert ''.join(out) == '\n***\n'


def test_hr_leaves_the_rest_of_the_element_alone(monkeypatch):
    # The scene break a margin asks for and the element's tail are calibre's.
    monkeypatch.setattr(
        MarkdownMLizer, 'dump_text',
        lambda self, elem, stylizer: ['\n\n', '\n* * *', '\n', 'tail'],
        raising=False)
    out = _mlizer().dump_text(Hr(), FakeStylizer())
    assert out == ['\n\n', '\n***', '\n', 'tail']
