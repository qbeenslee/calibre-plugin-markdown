# -*- coding: utf-8 -*-
"""The escape_markdown_chars option: body escaping in the Markdown output.

Off (the default) writes the source text as it is, so `作者：A + B` and
`第1卷 原版(By:苏梦枕)` stay literal. On restores calibre's historical
behaviour: the Markdown special characters get a backslash. Structural
escaping (table pipes, YAML front matter, HTML attributes) is never turned
off, so the file stays valid Markdown either way.
"""

import re
import types

from calibre_plugins.markdown.output.convert_flow import apply_prefs_to_opts
from calibre_plugins.markdown.output.output_plugin import MarkdownOutput
from calibre_plugins.markdown.utils.prefs import (
    DEFAULTS,
    EXPORT_OPTION_KEYS,
    serialize_customization,
)

AUTHOR_LINE = ('作者：**steve216（苏梦枕） + 枪塔神玉（潇湘夜雪） + '
               'SAILING560707 + 狗尾~续貂**')
CHAPTER_TITLE = '第1卷 原版(By:苏梦枕)'


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


def _mlizer(**opts):
    from calibre_plugins.markdown.output.markdownml_enhanced import (
        EnhancedMarkdownMLizer,
    )
    mlizer = EnhancedMarkdownMLizer(Log())
    mlizer.opts = types.SimpleNamespace(**opts)
    mlizer.blockquotes = 0
    mlizer.in_pre = False
    mlizer.in_code = False
    mlizer._heading_slugs = set()
    return mlizer


def _heading(opts, title=CHAPTER_TITLE):
    return ''.join(
        opts._dump_heading(FakeHeading(title), None, 'h2'))


def _anchor(heading_line):
    return re.search(r'\{#([^}]*)\}', heading_line).group(1)


# ------------------------------------------------------------------ the text

def test_body_escaping_is_off_by_default_verbatim():
    # No option set at all is what an old caller or an old saved preference
    # looks like: it must read as "off".
    mlizer = _mlizer()
    assert mlizer.prepare_string_for_markdown(AUTHOR_LINE) == AUTHOR_LINE
    assert mlizer.prepare_string_for_markdown(CHAPTER_TITLE) == CHAPTER_TITLE


def test_body_escaping_on_covers_the_historical_character_set():
    mlizer = _mlizer(escape_markdown_chars=True)
    for char in '\\`*_{}[]()#+!':
        assert mlizer.prepare_string_for_markdown(char) == '\\' + char
    assert mlizer.prepare_string_for_markdown('汉字 and words') == (
        '汉字 and words')


def test_body_escaping_on_reproduces_the_old_examples():
    mlizer = _mlizer(escape_markdown_chars=True)
    assert mlizer.prepare_string_for_markdown(
        '第1卷 原版(By:苏梦枕)') == '第1卷 原版\\(By:苏梦枕\\)'
    assert mlizer.prepare_string_for_markdown('A + B') == 'A \\+ B'


# ---------------------------------------------------------------- headings

def test_heading_anchor_is_identical_in_both_modes():
    # Chapter slugs feed the table of contents links, so the option may not
    # change them: the {#anchor} has to survive the round trip.
    off = _heading(_mlizer(escape_markdown_chars=False))
    on = _heading(_mlizer(escape_markdown_chars=True))
    assert off == '\n## 第1卷 原版(By:苏梦枕) {#%s}\n' % _anchor(off)
    assert on == '\n## 第1卷 原版\\(By:苏梦枕\\) {#%s}\n' % _anchor(on)
    assert _anchor(off) == _anchor(on)


def test_heading_backslash_stays_literal_when_escaping_is_off():
    # With no escaping added there is nothing to undo: a backslash in the
    # heading must not be eaten while the anchor is derived.
    heading = _heading(_mlizer(), title='C:\\path\\*x')
    assert heading == '\n## C:\\path\\*x {#%s}\n' % _anchor(heading)


# ------------------------------------------------------------------ tables

def test_table_pipes_stay_escaped_in_both_modes():
    # `|` ends the cell, it is structural rather than cosmetic: the option
    # must not be able to break the table.
    for opts in ({}, {'escape_markdown_chars': True}):
        mlizer = _mlizer(**opts)
        assert mlizer.prepare_string_for_table_cell('左 | 右') == '左 \\| 右'


def test_table_cell_keeps_only_the_structural_escape():
    mlizer = _mlizer()
    cell = mlizer.prepare_string_for_table_cell(
        mlizer.prepare_string_for_markdown('a*b | c+d'))
    assert cell == 'a*b \\| c+d'


# --------------------------------------------------------------- wiring

def test_option_registered():
    option = next(o for o in MarkdownOutput.options
                  if o.option.name == 'escape_markdown_chars')
    assert option.recommended_value is False
    assert 'escape_markdown_chars' in MarkdownOutput.overridable_options
    assert 'escape_markdown_chars' in EXPORT_OPTION_KEYS
    assert DEFAULTS['escape_markdown_chars'] is False


def test_pane_registers_the_option():
    # The customization dialog's BOOL_OPTIONS row needs a widget toolkit;
    # scripts/verify_escape_chars.py covers that on the real thing.
    from calibre_plugins.markdown.output.conversion_ui import option

    assert 'escape_markdown_chars' in option


def test_prefs_flow_applies_escape_markdown_chars():
    opts = types.SimpleNamespace()
    apply_prefs_to_opts(opts, {'escape_markdown_chars': True})
    assert opts.escape_markdown_chars is True
