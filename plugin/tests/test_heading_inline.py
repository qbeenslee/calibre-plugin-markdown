# -*- coding: utf-8 -*-
"""A heading is one line with one level marker, whatever it holds.

Books mark a chapter up as `<h2 class="head"><span>第1章</span><br/>标题</h2>`,
and one of the "transform HTML" rules saved for such a book renames the number
<span> to <h3> - so the heading ends up holding a heading of its own. Every
child used to be rendered as a block: the <br> wrote a hard line break (which
ends an ATX heading and drops the rest of the title into the body), the nested
heading wrote its own "#" run ("## ### 第1章"), and the bold the children
inherit from the heading was written out as "**" (upstream skips the emphasis
for a heading, but not for what it contains).

Here the whole content is rendered as inline text: <br> becomes a space, a
nested heading keeps its text but not its markers (the deeper level wins, since
the outer element is the layout and the inner one carries the level), and the
link, image, sup/sub and code syntax that is legal inside a heading is kept.
"""

import types

from calibre_plugins.markdown.output.markdownml_enhanced import (
    EnhancedMarkdownMLizer,
)

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
        'heading_anchors': True,
        'keep_links': True,
        'keep_image_references': True,
        'keep_image_sizes': True,
        'escape_markdown_chars': False,
    }
    values.update(opts)
    mlizer.opts = types.SimpleNamespace(**values)
    mlizer.blockquotes = 0
    mlizer.in_pre = False
    mlizer.in_code = False
    mlizer._in_table_cell = False
    mlizer._heading_slugs = set()
    return mlizer


def _render(elem, styles=None, **opts):
    mlizer = _mlizer(**opts)
    return ''.join(mlizer.dump_text(elem, FakeStylizer(styles)))


def _chapter_number_span():
    return FakeElem('span', text='第0001章')


def test_line_break_in_a_heading_becomes_a_space():
    heading = FakeElem('h2', children=[
        _chapter_number_span(), FakeElem('br', tail='我成了岳不群')])

    out = _render(heading)

    assert out == '\n## 第0001章 我成了岳不群 {#第0001章-我成了岳不群}\n'


def test_the_bold_a_child_inherits_from_the_heading_is_not_written():
    bold = FakeElem('span', text='第0001章')
    heading = FakeElem('h2', children=[bold])

    out = _render(heading, {id(bold): FakeStyle(**{'font-weight': 'bold'})})

    assert '**' not in out
    assert out == '\n## 第0001章 {#第0001章}\n'


def test_a_nested_heading_keeps_its_text_but_not_its_markers():
    heading = FakeElem('h2', children=[
        FakeElem('h3', text='第0001章'), FakeElem('br', tail='我成了岳不群')])

    out = _render(heading)

    assert '## ###' not in out
    assert out == '\n### 第0001章 我成了岳不群 {#第0001章-我成了岳不群}\n'


def test_the_deeper_of_two_nested_levels_is_the_one_written():
    heading = FakeElem('h2', children=[FakeElem('h4', text='第0001章')])

    out = _render(heading)

    assert out == '\n#### 第0001章 {#第0001章}\n'


def test_a_nested_heading_two_levels_down_still_counts():
    wrapper = FakeElem('div', children=[FakeElem('h3', text='第0001章')])
    heading = FakeElem('h2', children=[wrapper])

    out = _render(heading)

    assert out == '\n### 第0001章 {#第0001章}\n'


def test_block_children_stay_on_the_heading_line():
    heading = FakeElem('h2', children=[
        FakeElem('p', text='甲'), FakeElem('p', text='乙')])

    out = _render(heading)

    assert out.count('\n') == 2
    assert out == '\n## 甲 乙 {#甲-乙}\n'


def test_a_link_inside_a_heading_is_kept():
    link = FakeElem('a', text='参见',
                    attrib={'href': 'http://example.com/chapter'})
    heading = FakeElem('h2', text='序 ', children=[link])

    out = _render(heading)

    assert '[参见](http://example.com/chapter)' in out
    assert out.count('\n') == 2


def test_an_image_inside_a_heading_is_kept():
    image = FakeElem('img', attrib={'src': 'images/000000.jpg', 'alt': '图'})
    heading = FakeElem('h2', children=[image])

    out = _render(heading)

    assert '![图](images/000000.jpg)' in out


def test_superscript_inside_a_heading_is_kept():
    note = FakeElem('sup', text='1')
    heading = FakeElem('h2', text='第0001章', children=[note])

    out = _render(heading)

    assert '<sup>1</sup>' in out


def test_a_plain_heading_is_unchanged():
    out = _render(FakeElem('h3', text='第1章'))

    assert out == '\n### 第1章 {#第1章}\n'


def test_the_heading_stays_one_line_without_an_anchor():
    heading = FakeElem('h2', children=[
        _chapter_number_span(), FakeElem('br', tail='我成了岳不群')])

    out = _render(heading, heading_anchors=False)

    assert '{#' not in out
    assert out == '\n## 第0001章 我成了岳不群\n'
