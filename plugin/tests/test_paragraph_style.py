# -*- coding: utf-8 -*-
"""The paragraph_style option: helper behavior and option wiring.

'block' (default) keeps the standard Markdown layout where a blank line
separates paragraphs. 'single' drops blank lines so every content line
stands as its own paragraph line.
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
    '- [One](#one)\n'
    '# One {#one}\n'
    'First paragraph.\n'
    'Second paragraph.\n'
    '```python\n'
    'keep = [\n\n'
    ']\n'
    '```\n'
    '| a | b |\n'
    '|---|---|\n'
    '| 1 | 2 |\n'
    '> quoted\n'
)


def test_single_style_drops_blank_lines():
    # The only blank lines left are inside the fenced code block.
    assert apply_paragraph_style(BLOCK_TEXT, 'single') == SINGLE_TEXT


def test_single_style_keeps_code_block_content():
    out = apply_paragraph_style(BLOCK_TEXT, 'single')
    assert 'keep = [\n\n]\n' in out
    assert '```\n| a | b |\n' in out


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
