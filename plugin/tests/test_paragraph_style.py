# -*- coding: utf-8 -*-
"""The paragraph_style option: helper behavior and option wiring.

'block' (default) keeps the standard Markdown layout where a blank line
separates paragraphs. 'single' drops blank lines so every content line
stands as its own paragraph line - except the ones that are not a paragraph
separation: the blank lines inside a fenced code block, the one that ends a
quote block, and the ones around the blocks Markdown reads across consecutive
lines (a list, a table, a definition list, a footnote definition).
"""

from calibre_plugins.markdown.output.convert_flow import apply_prefs_to_opts
from calibre_plugins.markdown.utils.helpers import apply_paragraph_style
from calibre_plugins.markdown.output.output_plugin import MarkdownOutput
from calibre_plugins.markdown.utils.prefs import (
    DEFAULTS,
    EXPORT_OPTION_KEYS,
    serialize_customization,
)

BLOCK_TEXT = (
    '---\n'
    'title: Book\n'
    '---\n\n'
    '## Table of Contents\n\n'
    '- [One](#one)\n\n'
    '# One {#one}\n\n'
    'First paragraph.\n\n'
    'Second paragraph.\n\n'
    '```python\n'
    'keep = [\n\n'
    ']\n'
    '```\n\n'
    '| a | b |\n'
    '|---|---|\n'
    '| 1 | 2 |\n\n'
    '> quoted\n'
)


def test_block_style_keeps_text_unchanged():
    assert apply_paragraph_style(BLOCK_TEXT, 'block') == BLOCK_TEXT


SINGLE_TEXT = (
    '---\n'
    'title: Book\n'
    '---\n'
    '## Table of Contents\n'
    '\n'
    '- [One](#one)\n'
    '\n'
    '# One {#one}\n'
    'First paragraph.\n'
    'Second paragraph.\n'
    '```python\n'
    'keep = [\n\n'
    ']\n'
    '```\n'
    '\n'
    '| a | b |\n'
    '|---|---|\n'
    '| 1 | 2 |\n'
    '\n'
    '> quoted\n'
)


def test_single_style_drops_blank_lines():
    # What is left of the blank lines: the code block's own, and the ones that
    # keep the structures (the TOC list, the table) apart from the text around
    # them - the blank line after the table included, a quote line below it
    # being read as a row of the table otherwise.
    assert apply_paragraph_style(BLOCK_TEXT, 'single') == SINGLE_TEXT


def test_single_style_keeps_code_block_content():
    out = apply_paragraph_style(BLOCK_TEXT, 'single')
    assert 'keep = [\n\n]\n' in out
    # The blank line after the fence is not a paragraph separation: the table
    # after it has to start a block of its own.
    assert '```\n\n| a | b |\n' in out


def test_single_style_keeps_table_rows():
    out = apply_paragraph_style(BLOCK_TEXT, 'single')
    assert '| a | b |\n|---|---|\n| 1 | 2 |\n' in out


def test_single_style_single_trailing_newline():
    assert apply_paragraph_style('a\n\n\nb\n\n', 'single') == 'a\nb\n'


QUOTE_BREAK_TEXT = (
    '第一段。\n'
    '\n'
    '> 结束语：\n'
    '> 好累，第一次写文，居然还是长篇。\n'
    '\n'
    '第二段。\n'
)


def test_single_style_keeps_the_blank_line_that_ends_a_quote():
    # It is not a paragraph separation: a quote is read up to the next blank
    # line, so without it the line after the quote is swallowed into it.
    assert apply_paragraph_style(QUOTE_BREAK_TEXT, 'single') == (
        '第一段。\n'
        '> 结束语：\n'
        '> 好累，第一次写文，居然还是长篇。\n'
        '\n'
        '第二段。\n')


def test_single_style_keeps_the_quote_break_before_a_heading():
    text = '> 引用\n\n### 标题\n正文\n'
    assert apply_paragraph_style(text, 'single') == text


def test_single_style_drops_the_quote_break_at_the_end_of_the_text():
    # Nothing follows: there is no line to keep out of the quote.
    assert apply_paragraph_style('正文\n\n> 引用\n\n', 'single') == \
        '正文\n> 引用\n'


def test_single_style_still_drops_the_blank_lines_between_paragraphs():
    assert apply_paragraph_style('第一段。\n\n第二段。\n', 'single') == \
        '第一段。\n第二段。\n'


def test_single_style_still_drops_the_blank_line_between_two_quotes():
    # Two quotes in a row are one quote block either way, and a quote line is
    # a paragraph line of its own once the file is read back as 'single'.
    assert apply_paragraph_style('> 甲\n\n> 乙\n', 'single') == '> 甲\n> 乙\n'


# The blocks Markdown reads across consecutive lines. The blank lines around
# them are not paragraph separations: dropping them lets the text around a
# block be read as part of it (the paragraph after a list becomes a line of
# the item, the one after a table a row of it), and python-markdown never
# starts a list or a table inside a paragraph in the first place.

LIST_TEXT = '第一段。\n\n- 甲\n- 乙\n\n第二段。\n'


def test_single_style_keeps_the_blank_lines_around_a_list():
    assert apply_paragraph_style(LIST_TEXT, 'single') == LIST_TEXT


def test_single_style_keeps_the_blank_lines_around_an_ordered_list():
    text = '第一段。\n\n1. 甲\n2. 乙\n\n第二段。\n'
    assert apply_paragraph_style(text, 'single') == text


def test_single_style_keeps_a_list_items_second_paragraph():
    # The renderer writes it as a blank line plus the item's content indent:
    # without the blank line the two paragraphs of the item become one.
    text = '- 甲\n\n\t条目的第二段\n\n- 乙\n'
    assert apply_paragraph_style(text, 'single') == text


def test_single_style_keeps_the_blank_lines_around_a_table():
    text = '第一段。\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n第二段。\n'
    assert apply_paragraph_style(text, 'single') == text


def test_single_style_keeps_the_table_caption_apart():
    text = '第一段。\n\n*表标题*\n\n| a | b |\n|---|---|\n'
    assert apply_paragraph_style(text, 'single') == text


def test_single_style_keeps_a_table_apart_from_the_heading_after_it():
    # The blank line after the table stays (the heading would be read as a row
    # of it); the one after the heading is a paragraph separation and goes.
    text = '| a | b |\n|---|---|\n| 1 | 2 |\n\n# 标题\n\n正文。\n'
    assert apply_paragraph_style(text, 'single') == \
        '| a | b |\n|---|---|\n| 1 | 2 |\n\n# 标题\n正文。\n'


def test_single_style_keeps_a_table_apart_from_the_next_table():
    text = '| a | b |\n|---|---|\n\n| c | d |\n|---|---|\n'
    assert apply_paragraph_style(text, 'single') == text


def test_single_style_keeps_the_blank_lines_around_a_definition_list():
    text = '第一段。\n\n术语\n: 释义\n\n第二段。\n'
    assert apply_paragraph_style(text, 'single') == text


def test_single_style_keeps_the_blank_line_before_footnote_definitions():
    text = '正文[^1]。\n\n[^1]: 脚注正文\n'
    assert apply_paragraph_style(text, 'single') == text


def test_single_style_keeps_the_blank_line_after_a_quoted_list():
    # The quote ends here, and that blank line is what ends it (the line above
    # the quoted list needs none: a quote interrupts a paragraph).
    text = '第一段。\n\n> - 甲\n> - 乙\n\n第二段。\n'
    assert apply_paragraph_style(text, 'single') == \
        '第一段。\n> - 甲\n> - 乙\n\n第二段。\n'


def test_single_style_keeps_the_blank_line_between_a_list_item_and_a_quote():
    # A quote interrupts a paragraph, not a list item: without the blank line
    # the quote line is read as a lazy continuation line of the item above it.
    text = '- 甲\n\n> *引文*\n'
    assert apply_paragraph_style(text, 'single') == text


def test_single_style_ends_a_quote_that_carries_unprefixed_lines():
    # A quoted <pre> is written without the ">" prefix, so its lines are lazy
    # continuation lines of the quote: the blank line after them is what ends
    # the quote, and without it the paragraph below is swallowed into it.
    text = '正文。\n\n> 引文\ncode 行\n\n正文二。\n'
    assert apply_paragraph_style(text, 'single') == \
        '正文。\n> 引文\ncode 行\n\n正文二。\n'


def test_single_style_collapses_a_run_of_blank_lines_to_one():
    # The book's CSS margins write a soft scene break on top of the block's
    # own newlines; one blank line is what separates the blocks.
    text = '正文。\n\n\n\n\n- 甲\n- 乙\n\n正文二。\n'
    assert apply_paragraph_style(text, 'single') == \
        '正文。\n\n- 甲\n- 乙\n\n正文二。\n'


def test_single_style_keeps_a_run_of_blank_lines_inside_a_fence():
    # Inside a code block the blank lines are content, not separations: they
    # are kept as they are written, run or not.
    text = 'para\n\n~~~\n\n\nstill code\n~~~\n\nafter\n'
    assert apply_paragraph_style(text, 'single') == \
        'para\n~~~\n\n\nstill code\n~~~\nafter\n'


def test_single_style_still_drops_the_blank_lines_around_a_fence():
    # A fenced code block interrupts a paragraph and needs no blank line
    # around it either, so 'single' stays compact there.
    text = '第一段。\n\n```\ncode\n```\n\n第二段。\n'
    assert apply_paragraph_style(text, 'single') == \
        '第一段。\n```\ncode\n```\n第二段。\n'


def test_single_style_still_drops_the_blank_lines_around_a_thematic_break():
    text = '第一段。\n\n* * *\n\n第二段。\n'
    assert apply_paragraph_style(text, 'single') == \
        '第一段。\n* * *\n第二段。\n'


def test_single_style_still_drops_the_blank_line_before_a_quote():
    # A quote interrupts a paragraph: the line above it needs no blank line.
    text = '第一段。\n\n> 引用\n'
    assert apply_paragraph_style(text, 'single') == '第一段。\n> 引用\n'


def test_a_pipe_line_without_an_alignment_row_is_not_a_table():
    # A table is one only with its alignment row under the first row; a line
    # that merely carries a pipe is paragraph text and stays one.
    text = '第一段。\n\n| 只是带竖线的正文\n\n第二段。\n'
    assert apply_paragraph_style(text, 'single') == \
        '第一段。\n| 只是带竖线的正文\n第二段。\n'


def test_single_style_on_empty_text():
    assert apply_paragraph_style('', 'single') == ''
    assert apply_paragraph_style(None, 'single') is None


def test_unknown_style_is_a_no_op():
    assert apply_paragraph_style(BLOCK_TEXT, 'bogus') == BLOCK_TEXT


def test_default_style_argument_is_block():
    assert apply_paragraph_style(BLOCK_TEXT) == BLOCK_TEXT


def test_tilde_fence_content_is_preserved():
    text = 'para\n\n~~~\n\nstill code\n~~~\n\nafter\n'
    out = apply_paragraph_style(text, 'single')
    assert out == 'para\n~~~\n\nstill code\n~~~\nafter\n'


HEADING_TEXT = (
    '# One\n'
    'First paragraph.\n'
    '## Two\n'
    'Second paragraph.\n'
    '#tag\n'
    'Third paragraph.\n'
)


def test_heading_blank_line_inserted():
    out = apply_paragraph_style(HEADING_TEXT, 'single',
                                blank_line_before_heading=True)
    assert out == (
        '# One\n'
        'First paragraph.\n'
        '\n'
        '## Two\n'
        'Second paragraph.\n'
        '#tag\n'
        'Third paragraph.\n'
    )


def test_heading_blank_line_off_keeps_compact_layout():
    assert apply_paragraph_style(HEADING_TEXT, 'single') == HEADING_TEXT
    assert apply_paragraph_style(HEADING_TEXT, 'single',
                                 blank_line_before_heading=False) == HEADING_TEXT


def test_heading_blank_line_ignored_in_block_style():
    assert apply_paragraph_style(HEADING_TEXT, 'block',
                                 blank_line_before_heading=True) == HEADING_TEXT


def test_heading_blank_line_not_before_file_first_line():
    out = apply_paragraph_style(HEADING_TEXT, 'single', True)
    assert out.startswith('# One\n')


def test_heading_blank_line_after_front_matter():
    text = '---\ntitle: X\n---\n# One\n'
    assert apply_paragraph_style(text, 'single', True) == \
        '---\ntitle: X\n---\n\n# One\n'


def test_heading_blank_line_not_inside_fence():
    text = 'para\n```python\n# not a heading\n```\n# Real\n'
    out = apply_paragraph_style(text, 'single', True)
    assert out == 'para\n```python\n# not a heading\n```\n\n# Real\n'


def test_blank_line_before_heading_registered():
    option = next(o for o in MarkdownOutput.options
                  if o.option.name == 'blank_line_before_heading')
    assert option.recommended_value is True
    assert 'blank_line_before_heading' in MarkdownOutput.overridable_options
    assert 'blank_line_before_heading' in EXPORT_OPTION_KEYS
    assert DEFAULTS['blank_line_before_heading'] is True


def test_blank_line_before_heading_prefs_flow():
    class Opts:
        pass

    opts = Opts()
    apply_prefs_to_opts(opts, {'blank_line_before_heading': False})
    assert opts.blank_line_before_heading is False


def test_option_registered():
    option = next(o for o in MarkdownOutput.options
                  if o.option.name == 'paragraph_style')
    assert option.recommended_value == 'block'
    assert set(option.option.choices) == {'block', 'single'}
    assert 'paragraph_style' in MarkdownOutput.overridable_options
    assert 'paragraph_style' in EXPORT_OPTION_KEYS
    assert DEFAULTS['paragraph_style'] == 'block'


def test_prefs_flow_applies_paragraph_style():
    class Opts:
        pass

    opts = Opts()
    apply_prefs_to_opts(opts, {'paragraph_style': 'single'})
    assert opts.paragraph_style == 'single'
