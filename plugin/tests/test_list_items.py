# -*- coding: utf-8 -*-
"""<li> rendering: the item's text stays on the "- " line.

Books wrap the text of a list item in a <p> (the "loose list" shape), and
calibre's own renderer writes that paragraph as a block of its own: it opens
with a newline, so the item came out as a bullet with nothing after it and the
text on the next line, outside the item -

    -
    大一的林晓晓，舞蹈系。

- and the whitespace the book indents its markup with was folded into a space
before the text ("-  " with the text still on the next line). Here the <p>
around the text is dropped (a Markdown item *is* a paragraph), the bullet's
line carries the item's first block, and a further block of the item - a second
paragraph, a nested list, a quote - is written on lines of its own, a further
paragraph indented so that it stays inside the item.
"""

import re
import types

import pytest

from calibre.ebooks.txt.markdownml import MarkdownMLizer
from calibre_plugins.markdown.output.markdownml_enhanced import (
    EnhancedMarkdownMLizer,
)
from calibre_plugins.markdown.utils.helpers import local_name

XHTML_NS = 'http://www.w3.org/1999/xhtml'

#: The real base class is calibre's MarkdownMLizer; under the test stubs it is
#: whatever conftest put there, and the parts the renderer delegates to are
#: filled in by the fixtures below (the stub has none of them). It is named
#: explicitly - and not taken from the renderer's MRO, which now holds the
#: renderer mixins - so the patches always land on the class the renderer
#: delegates to.
STUB_BASE = MarkdownMLizer


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
    def __init__(self, tag, text=None, children=(), tail=None, attrib=None):
        self.tag = '{%s}%s' % (XHTML_NS, tag)
        self.text = text
        self.tail = tail
        self.attrib = dict(attrib or {})
        self.children = list(children)

    def __iter__(self):
        return iter(self.children)

    def __len__(self):
        return len(self.children)

    def getparent(self):
        return None


def _mlizer(**opts):
    mlizer = EnhancedMarkdownMLizer(Log())
    values = {
        'keep_links': True,
        'keep_image_references': True,
        'keep_image_sizes': True,
        'escape_markdown_chars': False,
        'heading_anchors': True,
    }
    values.update(opts)
    mlizer.opts = types.SimpleNamespace(**values)
    mlizer.list = []
    mlizer.blockquotes = 0
    mlizer.in_pre = False
    mlizer.in_code = False
    mlizer.style_italic = False
    mlizer.style_bold = False
    mlizer.remove_space_after_newline = False
    mlizer._in_table_cell = False
    mlizer._in_figure = False
    mlizer._in_heading = False
    mlizer._item_line = None
    mlizer._heading_slugs = set()
    mlizer._footnote_refs = {}
    mlizer._footnote_defs = {}
    mlizer._footnote_order = []
    mlizer._footnote_label_counter = 1
    return mlizer


def _render(elem, styles=None, **opts):
    mlizer = _mlizer(**opts)
    return ''.join(mlizer.dump_text(elem, FakeStylizer(styles)))


def _item(children=(), text=None, **kwargs):
    """A one-item <ul> around the given <li> content."""
    item = FakeElem('li', text=text, children=list(children), **kwargs)
    return FakeElem('ul', children=[item])


@pytest.fixture(autouse=True)
def _upstream(monkeypatch):
    """Fill in calibre's own dump_text/remove_newlines on the stub base class.

    The enhanced renderer delegates what it does not handle itself to the
    inherited MarkdownMLizer, which the stub does not provide: <p>/<div> open
    and close a line of their own, <ul>/<ol> keep the list stack the item
    numbering reads, inline elements write their text and recurse, and
    remove_newlines folds a text node the way calibre does (the whitespace of
    an indented book arrives here as spaces, which is what the item renderer
    has to make sense of).
    """

    def dump_text(self, elem, stylizer):
        tag = local_name(elem.tag)
        text = []
        tags = []
        if tag in ('p', 'div'):
            text.append('\n')
            tags.append('\n')
            self.remove_space_after_newline = True
        if tag in ('ul', 'ol'):
            tags.append(tag)
            self.list.append({'name': tag, 'num': 0})
        if getattr(elem, 'text', None):
            text.append(self.remove_newlines(elem.text))
        for child in elem:
            text += self.dump_text(child, stylizer)
        for t in reversed(tags):
            if t in ('ul', 'ol'):
                self.list.pop()
                text.append('\n')
            else:
                text.append(t)
        if getattr(elem, 'tail', None):
            text.append(self.remove_newlines(elem.tail))
        return text

    def remove_newlines(self, text):
        text = text.replace('\r\n', ' ')
        text = text.replace('\n', ' ')
        text = text.replace('\r', ' ')
        text = re.sub(r'[ ]{2,}', ' ', text)
        text = re.sub(r'\t+', '', text)
        if self.remove_space_after_newline:
            text = re.sub(r'^ +', '', text)
            self.remove_space_after_newline = False
        return text

    monkeypatch.setattr(STUB_BASE, 'dump_text', dump_text, raising=False)
    monkeypatch.setattr(STUB_BASE, 'remove_newlines', remove_newlines,
                        raising=False)


# ------------------------------------------------- the bullet's own line

def test_a_paragraph_wrapped_item_keeps_its_text_on_the_bullet_line():
    item = _item([FakeElem('p', text='大一的林晓晓，舞蹈系。')])

    out = _render(item)

    assert out == '\n- 大一的林晓晓，舞蹈系。\n'


def test_the_newline_after_li_does_not_add_a_second_space():
    # <li>\n<p>text</p>\n</li>: the newline is formatting, and folding it into
    # a space is what left "-  " with the text on the next line.
    item = _item([FakeElem('p', text='甲')], text='\n')

    out = _render(item)

    assert out == '\n- 甲\n'
    assert '-  ' not in out


def test_the_tail_of_the_item_is_not_written_into_the_line():
    item = _item([FakeElem('p', text='甲', tail='\n')], tail='\n')

    out = _render(item)

    assert out == '\n- 甲\n'


def test_a_plain_text_item_is_unchanged():
    assert _render(_item(text='甲')) == '\n- 甲\n'


def test_a_div_wrapped_item_is_flattened_the_same_way():
    item = _item([FakeElem('div', text='甲')])

    assert _render(item) == '\n- 甲\n'


def test_the_item_keeps_the_inline_markup_of_its_paragraph():
    para = FakeElem('p', text='见 ')
    para.children.append(FakeElem('a', text='链接',
                                  attrib={'href': 'chapter.html'}))
    item = _item([para])

    assert _render(item) == '\n- 见 [[链接]]\n'


def test_an_ordered_item_numbers_its_wrapped_paragraph():
    item = FakeElem('li', text='\n', children=[FakeElem('p', text='甲')])
    listing = FakeElem('ol', children=[item, FakeElem(
        'li', text='\n', children=[FakeElem('p', text='乙')])])

    assert _render(listing) == '\n1. 甲\n2. 乙\n'


# ------------------------------------------------- further blocks of the item

def test_a_second_paragraph_stays_inside_the_item():
    item = _item([FakeElem('p', text='甲'), FakeElem('p', text='乙')])

    out = _render(item)

    assert out == '\n- 甲\n\n\t乙\n'


def test_inline_text_before_a_paragraph_keeps_it_on_a_line_of_its_own():
    item = _item([FakeElem('span', text='甲'), FakeElem('p', text='乙')])

    out = _render(item)

    assert out == '\n- 甲\n\n\t乙\n'


def test_a_nested_list_keeps_its_own_line():
    inner = FakeElem('ul', children=[FakeElem('li', text='子项')])
    item = _item([inner], text='父项')

    out = _render(item)

    assert out == '\n- 父项\n\t- 子项\n\n'


def test_an_item_that_holds_only_a_nested_list_marks_the_item():
    # <li><ol><li>x</li></ol></li>: the item has no text of its own, so the
    # nested list is what its bullet holds - it stays indented under it.
    inner = FakeElem('ol', children=[FakeElem('li', text='子项')])
    item = _item([inner], text='\n')

    out = _render(item)

    assert out == '\n- \n\t1. 子项\n\n'


def test_a_quote_of_the_item_keeps_the_bullet_line():
    item = _item([FakeElem('blockquote', text='引文')])

    out = _render(item)

    assert out == '\n- > 引文\n\n'


def test_a_heading_of_the_item_keeps_the_bullet_line():
    item = _item([FakeElem('h3', text='小标题')])

    out = _render(item)

    assert out == '\n- ### 小标题 {#小标题}\n\n'


def test_the_whitespace_before_a_block_is_not_left_on_the_line_above_it():
    # <li><p>甲</p>\n<ul>…</ul></li>: the newline between them is written as a
    # space by the fold, which used to trail the line of the paragraph.
    inner = FakeElem('ul', text='\n', children=[FakeElem('li', text='子项')])
    item = _item([FakeElem('p', text='甲', tail='\n'), inner])

    out = _render(item)

    assert out == '\n- 甲\n\t- 子项\n\n'


# ------------------------------------------------------------ emphasis, notes

def test_a_bold_item_does_not_open_its_emphasis_twice():
    bold_item = FakeElem('li', text='\n',
                         children=[FakeElem('p', text='甲')])
    listing = FakeElem('ul', children=[bold_item])

    out = _render(listing, {id(bold_item): FakeStyle(
        **{'font-weight': 'bold'})})

    assert out == '\n- **甲**\n'


def test_a_footnote_definition_is_collected_instead_of_written_on_the_item():
    note = FakeElem('p', text='脚注正文', attrib={'id': 'fn1'})
    item = _item([note], text='\n')
    mlizer = _mlizer()

    out = ''.join(mlizer.dump_text(item, FakeStylizer()))

    assert mlizer._footnote_defs == {'1': '脚注正文'}
    assert out == '\n- \n'


def test_the_item_keeps_the_trailing_content_a_book_writes_after_it():
    item = _item([FakeElem('p', text='甲', tail='，后记')], tail='\n')

    out = _render(item)

    assert out == '\n- 甲，后记\n'


def test_an_empty_item_is_still_a_bullet():
    out = _render(_item([]))

    assert re.match(r'^- $', out.split('\n')[1])
