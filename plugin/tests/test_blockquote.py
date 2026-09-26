# -*- coding: utf-8 -*-
"""<blockquote> rendering: one "> " prefix per line, styling around the text.

Upstream calibre writes the prefix twice - for the quote and again for every
block level child - and wraps the quote itself in "*"/"**" when the book
styles it italic/bold, so a plain quoted paragraph used to come out as a "*>"
line, the text and a lone "*" line (a line starting with "*" reads as a list
bullet). Here the quote reads "> *text*" and ends on its last line of text:
what ends a quote is the blank line before the next block (a bare ">" line
does not - the reader takes a quote up to the next blank line, so the line
after such a close is swallowed back into the quote as a lazy continuation
line). Text that follows the quote directly gets that blank line written for
it here, since nothing else will.
"""

import re
import types

from calibre.ebooks.txt.markdownml import MarkdownMLizer
from calibre_plugins.markdown.output.markdownml_enhanced import (
    EnhancedMarkdownMLizer,
)
from calibre_plugins.markdown.utils.helpers import local_name

XHTML_NS = 'http://www.w3.org/1999/xhtml'


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
    def __init__(self, styles=None):
        self._styles = styles or {}

    def style(self, elem):
        return self._styles.get(id(elem)) or FakeStyle()


class FakeElem:
    def __init__(self, tag, text=None, children=(), tail=None):
        self.tag = '{%s}%s' % (XHTML_NS, tag)
        self.text = text
        self.tail = tail
        self.attrib = {}
        self.children = list(children)
        for child in self.children:
            child._parent = self

    def __iter__(self):
        return iter(self.children)

    def __len__(self):
        return len(self.children)

    def getparent(self):
        return getattr(self, '_parent', None)


def _mlizer(**opts):
    mlizer = EnhancedMarkdownMLizer(Log())
    mlizer.opts = types.SimpleNamespace(**opts)
    mlizer.blockquotes = 0
    mlizer.style_italic = False
    mlizer.style_bold = False
    mlizer.in_pre = False
    mlizer.in_code = False
    mlizer._in_table_cell = False
    mlizer._in_figure = False
    return mlizer


def _paragraph_dump(mlizer, recorded=None):
    """Stand-in for the inherited dump_text: a block level child writes the
    quote prefix itself and closes its line, like calibre's paragraph branch.
    """
    def dump(elem, stylizer):
        if recorded is not None:
            recorded.append((local_name(elem.tag), mlizer.blockquotes,
                             mlizer.style_italic, mlizer.style_bold))
        return ['\n' + '> ' * mlizer.blockquotes, elem.text or '', '\n']
    return dump


def _install_upstream_inline_dump(monkeypatch):
    """Provide the calibre behavior involved in paragraph/em/br rendering."""
    def remove_newlines(self, text):
        text = re.sub(r'[\r\n]+', ' ', text)
        text = re.sub(r'[ ]{2,}', ' ', text)
        if self.remove_space_after_newline:
            text = text.lstrip(' ')
            self.remove_space_after_newline = False
        return text

    def dump_text(self, elem, stylizer):
        tag = local_name(elem.tag)
        style = stylizer.style(elem)
        text = []
        closes_line = tag == 'p'
        if closes_line:
            text.append('\n' + '> ' * self.blockquotes)
            self.remove_space_after_newline = True
        opens_italic = (tag == 'em' or style['font-style'] == 'italic') \
            and not self.style_italic
        if opens_italic:
            text.append('*')
            self.style_italic = True
        if tag == 'br':
            text.append('  \n')
            self.remove_space_after_newline = True
        if elem.text:
            text.append(self.remove_newlines(elem.text))
        for child in elem:
            text += self.dump_text(child, stylizer)
        if opens_italic:
            self.style_italic = False
            text.append('*')
        if closes_line:
            text.append('\n')
        if elem.tail:
            text.append(self.remove_newlines(elem.tail))
        return text

    monkeypatch.setattr(MarkdownMLizer, 'dump_text', dump_text, raising=False)
    monkeypatch.setattr(MarkdownMLizer, 'remove_newlines', remove_newlines,
                        raising=False)


def _styled(quote, **overrides):
    return FakeStylizer({id(quote): FakeStyle(**overrides)})


# ------------------------------------------------------------- the prefix

def test_block_child_owns_the_only_prefix():
    mlizer = _mlizer()
    mlizer.dump_text = _paragraph_dump(mlizer)
    quote = FakeElem('blockquote', text='\n',
                     children=[FakeElem('p', text='前言')])

    out = ''.join(mlizer._dump_blockquote(quote, FakeStylizer()))

    assert out == '\n> 前言\n'
    assert mlizer.blockquotes == 0


def test_inline_text_inside_the_quote_gets_the_prefix():
    mlizer = _mlizer()
    mlizer.dump_text = lambda elem, stylizer: []
    quote = FakeElem('blockquote', text='引用文字')

    out = ''.join(mlizer._dump_blockquote(quote, FakeStylizer()))

    assert out == '\n> 引用文字\n'


def test_inline_child_gets_the_prefix():
    mlizer = _mlizer()
    mlizer.dump_text = lambda elem, stylizer: [elem.text]
    quote = FakeElem('blockquote', text='\n',
                     children=[FakeElem('a', text='链接')])

    out = ''.join(mlizer._dump_blockquote(quote, FakeStylizer()))

    assert out == '\n> 链接\n'


def test_nested_quote_deepens_the_prefix():
    mlizer = _mlizer()

    def dump(elem, stylizer):
        if local_name(elem.tag) == 'blockquote':
            return mlizer._dump_blockquote(elem, stylizer)
        return _paragraph_dump(mlizer)(elem, stylizer)

    mlizer.dump_text = dump
    inner = FakeElem('blockquote', text='\n',
                     children=[FakeElem('p', text='深层')])
    quote = FakeElem('blockquote', text='\n', children=[inner])

    out = ''.join(mlizer._dump_blockquote(quote, FakeStylizer()))

    assert out == '\n> > 深层\n'
    assert mlizer.blockquotes == 0


def test_paragraph_tail_space_does_not_leave_a_whitespace_line():
    # calibre writes the tail of a paragraph as a space: left in place the
    # quote would end on a whitespace-only line.
    mlizer = _mlizer()
    mlizer.dump_text = lambda elem, stylizer: ['\n> q\n', ' ']
    quote = FakeElem('blockquote', children=[FakeElem('p')])

    out = ''.join(mlizer._dump_blockquote(quote, FakeStylizer()))

    assert out == '\n> q\n'


def test_quote_cleanup_keeps_an_already_rendered_hard_break():
    # Quote cleanup only trims whitespace fragments. A hard break emitted by
    # another renderer is content; trailing <br> is filtered before this step.
    mlizer = _mlizer()
    mlizer.dump_text = lambda elem, stylizer: ['\n> q  \n']
    quote = FakeElem('blockquote', children=[FakeElem('p')])

    out = ''.join(mlizer._dump_blockquote(quote, FakeStylizer()))

    assert out == '\n> q  \n'


def test_trailing_br_inside_italic_quote_is_redundant(monkeypatch):
    _install_upstream_inline_dump(monkeypatch)
    br = FakeElem('br', tail='\n')
    emphasis = FakeElem('em', text='最近有点时间，所以多写点，之后可能就没这么快了。',
                        children=[br])
    paragraph = FakeElem('p', children=[emphasis])
    quote = FakeElem('blockquote', text='\n', children=[paragraph])
    italic = FakeStyle(**{'font-style': 'italic'})
    styles = {id(quote): italic, id(paragraph): italic,
              id(emphasis): italic, id(br): italic}

    out = ''.join(_mlizer().dump_text(quote, FakeStylizer(styles)))

    assert out == '\n> *最近有点时间，所以多写点，之后可能就没这么快了。*\n'


def test_trailing_br_inside_plain_paragraph_is_redundant(monkeypatch):
    _install_upstream_inline_dump(monkeypatch)
    paragraph = FakeElem('p', children=[
        FakeElem('em', text='正文', children=[FakeElem('br')])])

    out = ''.join(_mlizer().dump_text(paragraph, FakeStylizer()))

    assert out == '\n*正文*\n'


def test_nonterminal_br_inside_italic_quote_keeps_break_and_prefix(monkeypatch):
    _install_upstream_inline_dump(monkeypatch)
    br = FakeElem('br', tail='第二行')
    emphasis = FakeElem('em', text='第一行', children=[br])
    paragraph = FakeElem('p', children=[emphasis])
    quote = FakeElem('blockquote', text='\n', children=[paragraph])
    italic = FakeStyle(**{'font-style': 'italic'})
    styles = {id(quote): italic, id(paragraph): italic,
              id(emphasis): italic, id(br): italic}

    out = ''.join(_mlizer().dump_text(quote, FakeStylizer(styles)))

    assert out == '\n> *第一行  \n> 第二行*\n'


def test_tail_is_separated_from_the_quote_by_a_blank_line():
    # Text after </blockquote> is text after a block: without a blank line it
    # is read as a lazy continuation line and swallowed into the quote.
    mlizer = _mlizer()
    mlizer.dump_text = lambda elem, stylizer: []
    quote = FakeElem('blockquote', text='引用', tail='尾巴')

    out = ''.join(mlizer._dump_blockquote(quote, FakeStylizer()))

    assert out == '\n> 引用\n\n尾巴'


def test_tail_newlines_do_not_pile_up_blank_lines():
    # The newlines around </blockquote> are whitespace, not content: they must
    # not add blank lines of their own.
    mlizer = _mlizer()
    mlizer.dump_text = lambda elem, stylizer: []
    quote = FakeElem('blockquote', text='引用', tail='\n\n尾巴')

    out = ''.join(mlizer._dump_blockquote(quote, FakeStylizer()))

    assert out == '\n> 引用\n\n尾巴'


def test_whitespace_tail_is_dropped():
    # The tail of a quote is the whitespace between </blockquote> and the next
    # tag: written after the last line of the quote it would leave "> " behind.
    mlizer = _mlizer()
    mlizer.dump_text = lambda elem, stylizer: []
    quote = FakeElem('blockquote', text='引用', tail='\n  ')

    out = ''.join(mlizer._dump_blockquote(quote, FakeStylizer()))

    assert out == '\n> 引用\n'


# ------------------------------------------------------- the font styling

def test_block_child_keeps_the_inherited_italic_for_itself():
    # A quoted paragraph inherits the quote's italic and is what turns it into
    # "> *text*": the quote must leave the flag free for it.
    mlizer = _mlizer()
    recorded = []
    mlizer.dump_text = _paragraph_dump(mlizer, recorded)
    quote = FakeElem('blockquote', text='\n', children=[FakeElem('p')])

    ''.join(mlizer._dump_blockquote(
        quote, _styled(quote, **{'font-style': 'italic'})))

    assert recorded == [('p', 1, False, False)]
    assert mlizer.style_italic is False


def test_inline_italic_quote_writes_the_delimiters_around_the_text():
    mlizer = _mlizer()
    mlizer.dump_text = lambda elem, stylizer: []
    quote = FakeElem('blockquote', text='引用')

    out = ''.join(mlizer._dump_blockquote(
        quote, _styled(quote, **{'font-style': 'italic'})))

    assert out == '\n> *引用*\n'
    assert mlizer.style_italic is False


def test_inline_bold_quote_writes_the_double_delimiters():
    mlizer = _mlizer()
    mlizer.dump_text = lambda elem, stylizer: []
    quote = FakeElem('blockquote', text='引用')

    out = ''.join(mlizer._dump_blockquote(
        quote, _styled(quote, **{'font-weight': 'bold'})))

    assert out == '\n> **引用**\n'
    assert mlizer.style_bold is False


def test_inline_italic_bold_quote_uses_a_triple_delimiter():
    mlizer = _mlizer()
    mlizer.dump_text = lambda elem, stylizer: []
    quote = FakeElem('blockquote', text='引用')

    out = ''.join(mlizer._dump_blockquote(
        quote, _styled(quote, **{'font-style': 'italic',
                                 'font-weight': 'bold'})))

    assert out == '\n> ***引用***\n'


def test_inline_child_does_not_repeat_the_inherited_italic():
    # The delimiters opened for the direct text also cover an inline child:
    # "*a *b**" would be broken Markdown.
    mlizer = _mlizer()
    mlizer.dump_text = lambda elem, stylizer: [elem.text]
    quote = FakeElem('blockquote', text='斜体 ',
                     children=[FakeElem('span', text='也是斜体')])

    out = ''.join(mlizer._dump_blockquote(
        quote, _styled(quote, **{'font-style': 'italic'})))

    assert out == '\n> *斜体 也是斜体*\n'


def test_plain_quote_leaves_the_children_unstyled():
    mlizer = _mlizer()
    recorded = []
    mlizer.dump_text = _paragraph_dump(mlizer, recorded)
    quote = FakeElem('blockquote', text='\n', children=[FakeElem('p')])

    ''.join(mlizer._dump_blockquote(quote, FakeStylizer()))

    assert recorded == [('p', 1, False, False)]


def test_outer_italic_survives_a_nested_quote():
    # An <em> around the quote keeps its own delimiters: only the quote's own
    # styling is written by the quote, not the context it is rendered in.
    mlizer = _mlizer()
    mlizer.style_italic = True
    mlizer.dump_text = lambda elem, stylizer: []
    quote = FakeElem('blockquote', text='引用')

    ''.join(mlizer._dump_blockquote(
        quote, _styled(quote, **{'font-style': 'italic'})))

    assert mlizer.style_italic is True


# ------------------------------------------------------------- scene break

def test_css_margin_adds_the_blank_lines_upstream_adds():
    mlizer = _mlizer()
    mlizer.dump_text = lambda elem, stylizer: []
    quote = FakeElem('blockquote', text='引用')
    style = FakeStyle(**{'margin-top': '2em'})
    style.marginTop = 2
    style.fontSize = 1

    out = ''.join(mlizer._dump_blockquote(
        quote, FakeStylizer({id(quote): style})))

    assert out == '\n\n\n> 引用\n'


# ------------------------------------------------------------ dump routing

def test_dump_text_routes_blockquote_to_the_quote_renderer():
    mlizer = _mlizer()
    seen = []
    mlizer._dump_blockquote = lambda elem, stylizer: seen.append(elem) or ['> x']
    quote = FakeElem('blockquote', text='x')

    out = ''.join(mlizer.dump_text(quote, FakeStylizer()))

    assert out == '> x'
    assert seen == [quote]
