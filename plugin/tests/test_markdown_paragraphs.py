# -*- coding: utf-8 -*-
"""Markdown aware paragraph style detection and reshaping."""

import pytest

from calibre_plugins.markdown.input.paragraphs import (
    BLANK,
    BLOCK,
    BODY,
    PARAGRAPH_BLOCK,
    PARAGRAPH_PRINT,
    PARAGRAPH_SINGLE,
    analyze_lines,
    classify_lines,
    detect_paragraph_type,
    restructure_paragraphs,
)


def single_text(lines=30, indent=''):
    """A file written the way a novel is typeset: one paragraph per line."""
    return ''.join('%s第%d行正文，每行一段。\n' % (indent, i)
                   for i in range(1, lines + 1))


def block_text(paragraphs=12):
    """Ordinary Markdown: a blank line between paragraphs."""
    return ''.join('第%d段正文，空行分段。\n\n' % i
                   for i in range(1, paragraphs + 1))


# --- classification --------------------------------------------------------

def test_structure_lines_are_protected():
    lines = [
        '# 标题',                 # ATX heading
        '正文行',                  # body
        '```python',              # fence open
        'print("hi")',            # fence content
        'print("bye")',           # fence content
        '```',                    # fence close
        '| 列 | 值 |',             # table header
        '| --- | --- |',          # table separator
        '| a | b |',              # table row
        '- 列表项一',               # list item
        '  列表续行',               # list continuation
        '> 引用一',                # quote
        '    缩进代码',             # indented code block
        '',                       # blank
        '正文行二',
    ]
    kinds = classify_lines(lines)
    assert kinds == [BLOCK, BODY] + [BLOCK] * 11 + [BLANK, BODY]


def test_setext_heading_keeps_its_underline_attached():
    kinds = classify_lines(['标题', '====', '正文'])
    assert kinds == [BLOCK, BLOCK, BODY]


def test_definition_list_keeps_term_and_definition_attached():
    # python-markdown reads the term and the ':' line as one block; a blank
    # line in between would break the definition list apart.
    kinds = classify_lines(['术语', ': 定义内容'])
    assert kinds == [BLOCK, BLOCK]


def test_blank_and_whitespace_lines_are_blank():
    assert classify_lines(['', '   ', '\t']) == [BLANK, BLANK, BLANK]


def test_inline_html_lines_are_body_block_html_lines_are_block():
    # A line that opens with an inline level element is content: Markdown
    # wraps it in the paragraph it starts, so it is a body line here. A block
    # level element (its closing tag and an unknown tag alike) is structure
    # over several lines, and so is a comment or a declaration.
    kinds = classify_lines([
        '<img src="a.jpg"> <img src="b.jpg">',
        '<a href="b.html"><img src="a.jpg"></a>',
        '<img src="a.jpg"> 文字',
        '<custom-tag>x</custom-tag>',
        '<p><img src="a.jpg"></p>',
        '<div class="x">',
        '</div>',
        '<!-- 注释 -->',
        '<!DOCTYPE html>',
    ])
    assert kinds == [BODY, BODY, BODY, BODY] + [BLOCK] * 5


# --- detection -------------------------------------------------------------

def test_single_line_document_is_single():
    assert detect_paragraph_type(single_text()) == PARAGRAPH_SINGLE


def test_blank_line_document_is_block():
    assert detect_paragraph_type(block_text()) == PARAGRAPH_BLOCK


def test_indented_starts_are_print():
    text = single_text(indent='\u3000\u3000')
    assert detect_paragraph_type(text) == PARAGRAPH_PRINT


def test_short_text_is_left_as_block():
    assert detect_paragraph_type('第一行\n第二行\n') == PARAGRAPH_BLOCK


def test_paragraph_structure_does_not_confuse_the_detection():
    # A short single line document wrapped around Markdown structure.
    text = '# 第一章\n' + single_text() + '```\ncode line\ncode line\n```\n'
    assert detect_paragraph_type(text) == PARAGRAPH_SINGLE


@pytest.mark.parametrize('text', ['', '   \n\n', None])
def test_empty_text_is_block(text):
    assert detect_paragraph_type(text) == PARAGRAPH_BLOCK


# --- reshaping -------------------------------------------------------------

def test_single_gives_every_line_its_own_paragraph():
    reshaped = restructure_paragraphs(single_text(5), PARAGRAPH_SINGLE)
    assert reshaped == ('第1行正文，每行一段。\n\n第2行正文，每行一段。\n\n'
                        '第3行正文，每行一段。\n\n第4行正文，每行一段。\n\n'
                        '第5行正文，每行一段。\n')


def test_single_does_not_touch_structure_lines():
    text = ('正文一\n'
            '正文二\n'
            '```\n'
            'print("hi")\n'
            'print("bye")\n'
            '```\n'
            '| 列 | 值 |\n'
            '| --- | --- |\n'
            '| a | b |\n'
            '术语\n'
            ': 定义\n'
            '- 项一\n'
            '- 项二\n'
            '> 引用一\n'
            '> 引用二\n'
            '结尾一\n'
            '结尾二\n')
    reshaped = restructure_paragraphs(text, PARAGRAPH_SINGLE)
    # Body lines are split apart...
    assert '正文一\n\n正文二\n\n' in reshaped
    assert '结尾一\n\n结尾二\n' in reshaped
    # ...the protected constructs keep their line structure.
    assert '```\nprint("hi")\nprint("bye")\n```' in reshaped
    assert '| --- | --- |\n| a | b |' in reshaped
    assert '术语\n: 定义' in reshaped
    assert '- 项一\n- 项二' in reshaped
    # The quote stays one block; what is one paragraph per line inside it is
    # separated with the prefix-only line, not with a blank line (that would
    # end the quote).
    assert '> 引用一\n>\n> 引用二' in reshaped


def test_single_leaves_a_fenced_code_block_alone():
    # A line inside a fence that reads like a setext underline is code, not
    # structure: the blank line 'single' puts after a heading would land
    # inside the code - and one more of them on every further conversion,
    # since the reshaping could never settle.
    text = '```\n====\n\n```\n'
    assert restructure_paragraphs(text, PARAGRAPH_SINGLE) is text
    assert restructure_paragraphs(text, PARAGRAPH_PRINT) is text


def test_single_leaves_a_heading_inside_a_fence_alone():
    text = '```\n# 不是标题\n正文行\n```\n'
    assert restructure_paragraphs(text, PARAGRAPH_SINGLE) is text


def test_single_still_separates_a_heading_outside_a_fence():
    text = '# 标题\n正文行\n```\n====\n\n```\n'
    assert restructure_paragraphs(text, PARAGRAPH_SINGLE) == \
        '# 标题\n\n正文行\n\n```\n====\n\n```\n'


def test_fence_content_leaves_the_reshaping_idempotent():
    text = '# 标题\n正文一\n正文二\n```\n====\n\n```\n结尾\n'
    once = restructure_paragraphs(text, PARAGRAPH_SINGLE)
    assert restructure_paragraphs(once, PARAGRAPH_SINGLE) == once


def test_single_gives_a_lone_image_line_its_own_paragraph():
    # A line that opens with an inline level element is paragraph content and
    # ends its paragraph: without the blank line it would share one with the
    # line below it.
    text = '正文一\n<img src="a.jpg" alt="x">\n正文二\n'
    assert restructure_paragraphs(text, PARAGRAPH_SINGLE) == \
        '正文一\n\n<img src="a.jpg" alt="x">\n\n正文二\n'


def test_single_gives_every_lone_image_line_its_own_paragraph():
    text = ('正文一\n'
            '<img src="a.jpg">\n'
            '<img src="b.jpg">\n'
            '正文二\n')
    assert restructure_paragraphs(text, PARAGRAPH_SINGLE) == \
        ('正文一\n\n<img src="a.jpg">\n\n<img src="b.jpg">\n\n正文二\n')


def test_single_gives_a_multi_image_line_its_own_paragraph():
    # The reported case: several images on one line were read as an HTML block
    # - a block of its own to Markdown, so 'single' put no blank line after
    # it and the bold line below came back inside the same paragraph.
    text = ('<img src="a.jpg" alt="x" width="300px"> <img src="b.jpg" alt="x">\n'
            '**标题文字**\n'
            '<img src="c.png" alt="x"> <img src="d.jpg" alt="x">\n')
    assert restructure_paragraphs(text, PARAGRAPH_SINGLE) == (
        '<img src="a.jpg" alt="x" width="300px"> <img src="b.jpg" alt="x">\n\n'
        '**标题文字**\n\n'
        '<img src="c.png" alt="x"> <img src="d.jpg" alt="x">\n')


def test_single_gives_every_inline_html_line_its_own_paragraph():
    # Inline level markup is content to Markdown, whatever else the line
    # carries: a wrapper around the image, several of them, or text.
    for line in ('<a href="b.html"><img src="a.jpg"></a>',
                 '<img src="a.jpg"> <img src="b.jpg">',
                 '<img src="a.jpg"> 文字',
                 '<span class="x">文字</span>'):
        text = '正文一\n%s\n正文二\n' % line
        assert restructure_paragraphs(text, PARAGRAPH_SINGLE) == \
            '正文一\n\n%s\n\n正文二\n' % line


def test_single_gives_a_lone_markdown_image_its_own_paragraph():
    # The Markdown spelling is a body line already: the same rule, spelled
    # the other way.
    text = '正文一\n![alt](a.jpg)\n正文二\n'
    assert restructure_paragraphs(text, PARAGRAPH_SINGLE) == \
        '正文一\n\n![alt](a.jpg)\n\n正文二\n'


def test_single_keeps_an_image_that_shares_its_line():
    text = '文字 <img src="a.jpg">\n正文二\n'
    assert restructure_paragraphs(text, PARAGRAPH_SINGLE) == \
        '文字 <img src="a.jpg">\n\n正文二\n'


def test_single_keeps_block_level_html_out_of_the_reshaping():
    # A block level element is a structure over several lines to Markdown -
    # a block of its own already - so nothing is inserted after it: a blank
    # line inside it would only break it apart. A comment (or a declaration)
    # is structure of the same kind.
    for line in ('<p><img src="a.jpg"></p>',
                 '<div class="x">',
                 '</div>',
                 '<!-- 注释 -->',
                 '<!DOCTYPE html>'):
        text = '正文一\n%s\n正文二\n' % line
        assert restructure_paragraphs(text, PARAGRAPH_SINGLE) == \
            '正文一\n\n%s\n正文二\n' % line


def test_single_leaves_an_indented_image_line_alone():
    # Four spaces is an indented code block, not an image block: the tag is
    # code there, and nothing is inserted after it.
    text = '     <img src="a.jpg">\n正文\n'
    assert restructure_paragraphs(text, PARAGRAPH_SINGLE) is text


def test_single_separates_a_lone_image_inside_a_quote():
    text = '> <img src="a.jpg">\n> 正文\n'
    assert restructure_paragraphs(text, PARAGRAPH_SINGLE) == \
        '> <img src="a.jpg">\n>\n> 正文\n'


def test_single_separates_a_multi_image_line_inside_a_quote():
    text = '> <img src="a.jpg"> <img src="b.jpg">\n> 正文\n'
    assert restructure_paragraphs(text, PARAGRAPH_SINGLE) == \
        '> <img src="a.jpg"> <img src="b.jpg">\n>\n> 正文\n'


def test_print_keeps_a_lone_image_line_attached():
    # 'print' starts a paragraph at an indented line only: an image line is
    # left where it is.
    text = '正文一\n<img src="a.jpg">\n正文二\n'
    assert restructure_paragraphs(text, PARAGRAPH_PRINT) is text


def test_single_keeps_setext_headings_readable():
    reshaped = restructure_paragraphs('标题\n====\n正文\n', PARAGRAPH_SINGLE)
    assert reshaped == '标题\n====\n\n正文\n'


def test_single_puts_a_blank_line_after_headings():
    reshaped = restructure_paragraphs('# 标题\n正文一\n正文二\n',
                                      PARAGRAPH_SINGLE)
    assert reshaped == '# 标题\n\n正文一\n\n正文二\n'


def test_single_is_idempotent():
    once = restructure_paragraphs(single_text(), PARAGRAPH_SINGLE)
    assert restructure_paragraphs(once, PARAGRAPH_SINGLE) == once
    # ...and the reshaped text now reads as ordinary Markdown.
    assert detect_paragraph_type(once) == PARAGRAPH_BLOCK


def test_single_html_reshaping_is_idempotent():
    text = ('<img src="a.jpg"> <img src="b.jpg">\n'
            '**标题**\n'
            '<p><img src="c.jpg"></p>\n'
            '正文\n')
    once = restructure_paragraphs(text, PARAGRAPH_SINGLE)
    assert restructure_paragraphs(once, PARAGRAPH_SINGLE) == once


def test_print_starts_a_paragraph_at_indented_lines():
    text = ('\u3000\u3000第一段第一行\n'
            '第一段第二行\n'
            '\u3000\u3000第二段第一行\n')
    assert restructure_paragraphs(text, PARAGRAPH_PRINT) == (
        '\u3000\u3000第一段第一行\n'
        '第一段第二行\n'
        '\n'
        '\u3000\u3000第二段第一行\n')


def test_print_is_idempotent():
    text = single_text(indent='\u3000\u3000')
    once = restructure_paragraphs(text, PARAGRAPH_PRINT)
    assert restructure_paragraphs(once, PARAGRAPH_PRINT) == once


def test_block_style_returns_the_text_unchanged():
    text = single_text(5)
    assert restructure_paragraphs(text, PARAGRAPH_BLOCK) is text
    assert restructure_paragraphs(text, 'unknown') is text


def test_crlf_is_normalized_when_reshaped():
    reshaped = restructure_paragraphs('第一行\r\n第二行\r\n', PARAGRAPH_SINGLE)
    assert reshaped == '第一行\n\n第二行\n'


def test_lines_already_spaced_are_returned_unchanged():
    text = '第一行\n\n第二行\n\n'
    assert restructure_paragraphs(text, PARAGRAPH_SINGLE) is text


# --- quotes ----------------------------------------------------------------
#
# A quote block ('>' lines) is structure: the quote itself is never split
# apart. Its content, though, is text like any other, so the paragraph style
# applies inside it too - a paragraph break inside a quote is a prefix-only
# line (">", ">>"), which is how Markdown reads a blank line inside a quote.

QUOTE_SAMPLE = (
    '正文一\n'
    '> ＊＊＊＊＊＊\n'
    '> 结束语：\n'
    '> 好累，第一次写文，居然还是长篇\n'
    '> ＊＊＊＊＊＊\n'
    '正文二\n'
)


def test_analyze_reports_the_quote_structure():
    infos = analyze_lines(['> a', '>> b', '  > c', '正文', '```', '> d', '```'])
    assert [info.kind for info in infos] == \
        [BLOCK, BLOCK, BLOCK, BODY, BLOCK, BLOCK, BLOCK]
    assert [(info.depth, info.prefix, info.content) for info in infos] == [
        (1, '> ', 'a'), (2, '>> ', 'b'), (1, '  > ', 'c'),
        (0, '', ''), (0, '', ''), (0, '', ''), (0, '', '')]


def test_analyze_separator_is_the_prefix_only_line():
    infos = analyze_lines(['> a', '> > b', '  > c'])
    assert [info.separator for info in infos] == ['>', '>>', '  >']


def test_analyze_marks_the_fence_and_its_content():
    infos = analyze_lines(['正文', '```', '====', '', '```', '正文二'])
    assert [info.fenced for info in infos] == \
        [False, True, True, True, True, False]
    assert [info.kind for info in infos] == \
        [BODY, BLOCK, BLOCK, BLOCK, BLOCK, BODY]


def test_single_keeps_the_spelling_of_an_indented_quote_line():
    text = '> 甲\n  > 乙\n> 丙\n'
    assert restructure_paragraphs(text, PARAGRAPH_SINGLE) == \
        '> 甲\n>\n  > 乙\n>\n> 丙\n'


def test_analyze_keeps_classify_lines_unchanged():
    lines = ['> 引用一', '> 引用二', '# 标题', '正文', '', '正文二']
    assert classify_lines(lines) == [info.kind for info in analyze_lines(lines)]


def test_single_gives_every_quote_line_its_own_paragraph():
    assert restructure_paragraphs(QUOTE_SAMPLE, PARAGRAPH_SINGLE) == (
        '正文一\n'
        '\n'
        '> ＊＊＊＊＊＊\n'
        '>\n'
        '> 结束语：\n'
        '>\n'
        '> 好累，第一次写文，居然还是长篇\n'
        '>\n'
        '> ＊＊＊＊＊＊\n'
        '\n'
        '正文二\n')


def test_single_splits_nested_quote_content_too():
    text = '> > 内层一\n> > 内层二\n'
    assert restructure_paragraphs(text, PARAGRAPH_SINGLE) == \
        '> > 内层一\n>>\n> > 内层二\n'


def test_single_keeps_the_quote_separator_in_a_fenced_quote():
    # A '>' line inside a fence is code, not a quote: nothing is inserted.
    text = '```\n> a\n> b\n```\n'
    assert restructure_paragraphs(text, PARAGRAPH_SINGLE) is text


def test_single_leaves_lists_inside_a_quote_tight():
    text = '> - 项一\n> - 项二\n'
    assert restructure_paragraphs(text, PARAGRAPH_SINGLE) is text


def test_single_keeps_a_paragraph_break_the_author_wrote_inside_a_quote():
    text = '> 引用一\n>\n> 引用二\n'
    assert restructure_paragraphs(text, PARAGRAPH_SINGLE) is text


def test_single_keeps_a_blank_line_after_a_quote():
    text = '> 引用\n\n正文\n'
    assert restructure_paragraphs(text, PARAGRAPH_SINGLE) is text


def test_single_separates_a_quote_from_the_line_that_follows_it():
    # Without a blank line the next line reads as a lazy continuation line
    # and is swallowed into the quote.
    assert restructure_paragraphs('> 引用\n正文\n', PARAGRAPH_SINGLE) == \
        '> 引用\n\n正文\n'
    assert restructure_paragraphs('> 引用\n> 引用二\n正文\n',
                                  PARAGRAPH_SINGLE) == \
        '> 引用\n>\n> 引用二\n\n正文\n'


def test_single_separates_a_quote_from_a_list_that_follows_it():
    assert restructure_paragraphs('> 引用\n- 项一\n- 项二\n',
                                  PARAGRAPH_SINGLE) == \
        '> 引用\n\n- 项一\n- 项二\n'


def test_single_does_not_split_between_a_quote_and_a_deeper_one():
    text = '> 外层\n> > 内层\n'
    assert restructure_paragraphs(text, PARAGRAPH_SINGLE) is text


def test_single_quote_reshaping_is_idempotent():
    once = restructure_paragraphs(QUOTE_SAMPLE, PARAGRAPH_SINGLE)
    assert restructure_paragraphs(once, PARAGRAPH_SINGLE) == once


def test_print_applies_inside_a_quote_too():
    text = '> 前言\n> \u3000\u3000缩进段首\n'
    assert restructure_paragraphs(text, PARAGRAPH_PRINT) == \
        '> 前言\n>\n> \u3000\u3000缩进段首\n'


def test_print_keeps_the_quote_lines_that_do_not_start_a_paragraph():
    text = '> \u3000\u3000段首\n> 段内换行\n> \u3000\u3000第二段\n'
    assert restructure_paragraphs(text, PARAGRAPH_PRINT) == \
        '> \u3000\u3000段首\n> 段内换行\n>\n> \u3000\u3000第二段\n'


def test_print_does_not_add_a_blank_line_after_a_quote():
    # 'print' keeps the author's blank lines: only 'single' turns every line
    # into a paragraph, and with it a quote has to end like one.
    text = '> 引用\n正文\n'
    assert restructure_paragraphs(text, PARAGRAPH_PRINT) is text
