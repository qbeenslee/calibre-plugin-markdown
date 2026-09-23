# -*- coding: utf-8 -*-
"""Markdown-aware paragraph style detection and reshaping (input side).

calibre's TXT Input forces paragraph_type to 'off' for .md files and leaves
the paragraph structure to Markdown itself. Markdown, though, only starts a
paragraph at a blank line: a book written the way a novel is typeset - one
paragraph per line, no blank line in between - collapses into a single
paragraph per chapter. This module detects that convention and inserts the
blank lines Markdown needs for it.

calibre's own helpers cannot be reused for that: detect_paragraph_type() and
separate_paragraphs_single_line() are written for plain text, and their
reshaping would flatten the line structure of fenced code, lists, quotes,
tables and definition lists - constructs a Markdown file carries across
consecutive lines. Here those lines are classified as BLOCK and never split
apart; only BODY lines (the paragraph lines) are reshaped. The one thing
BLOCK lines do get is the treatment described next: the text a quote block
carries is reshaped like any other text.

A quote block is a block like those, but the text it carries is text like any
other: its content is reshaped by the same rules (on its own, recursively, and
with the prefixes put back), so the paragraph style applies inside a quote
too. A paragraph break inside a quote is a prefix-only line ('>', '>>'), which
is how Markdown reads a blank line inside a quote - a bare '>' line is not
enough, a quote is read up to the next blank line.

An image that stands on a line of its own - an <img> tag or the Markdown
spelling - is a block of its own, whatever Markdown ends up wrapping it in:
'single' starts a new paragraph after it like it does after a body line, so
the image does not share a paragraph with the line below it. Every line that
opens with an inline level HTML element is read that way - the tag does not
have to be the whole line ('<img src="a"> <img src="b">', '<img> 文字',
'<a href="x"><img src="y"></a>'): Markdown treats such a line as paragraph
content, and so does the reshaping here. Block level HTML ('<div>', '<p>',
'<table>') is a structure over several lines instead and stays BLOCK: it is
a block of its own to Markdown already, and a blank line planted inside it
would only break it apart.

The module stays free of calibre imports so it can be unit tested and probed
on its own.
"""

import re
from collections import namedtuple

#: Paragraph styles, matching calibre's paragraph_type option values.
PARAGRAPH_BLOCK = 'block'       # a blank line separates paragraphs (Markdown)
PARAGRAPH_SINGLE = 'single'     # every line is a paragraph
PARAGRAPH_PRINT = 'print'       # an indented line starts a paragraph

#: Line kinds classify_lines() reports.
BLANK = 'blank'     # empty or whitespace only
BODY = 'body'       # a paragraph line - the only kind these helpers reshape
BLOCK = 'block'     # structure over consecutive lines - never split apart
                    # (a quote's content is reshaped, the quote itself is not)

#: What analyze_lines() reports per line: the kind, plus the quote structure
#: of a quote line. `depth` is the number of '>' markers (0 when the line is
#: not a quote line), `prefix` everything before the content as written (the
#: indent and the marker text, spaces between the markers included), `content`
#: what follows it, and `separator` the prefix-only line that stands for a
#: blank line at that quote level ('>', '>>'). The last three are empty for a
#: line that is not a quote. `fenced` is True for a line of a fenced code
#: block, its own ```/~~~ fences included: whatever such a line looks like,
#: it is code, not structure.
LineInfo = namedtuple(
    'LineInfo', 'kind depth prefix content separator fenced')

#: Body lines needed before a detection is trusted. Below this the file is
#: reported as 'block' and left alone.
MIN_BODY_LINES = 10
#: Share of body lines that must sit directly against another body line
#: (no blank line between) for the file to read as one paragraph per line.
TIGHT_RATIO = 0.5
#: Share (and count) of indented body lines from which 'print' is assumed.
PRINT_RATIO = 0.2
PRINT_MIN_LINES = 2

_ATX_RE = re.compile(r'^ {0,3}#{1,6}(?:\s|$)')
_FENCE_OPEN_RE = re.compile(r'^ {0,3}(`{3,}|~{3,})')
_FENCE_CLOSE_RE = re.compile(r'^(`{3,}|~{3,})[ \t]*$')
_LIST_RE = re.compile(r'^ {0,3}(?:[-*+]|\d{1,9}[.)])(?:[ \t]|$)')
_QUOTE_RE = re.compile(r'^ {0,3}>')
#: A quote line split into its indent, its run of '>' markers and the content
#: behind them: '  > > text' -> '  ', '> > ', 'text'.
_QUOTE_PARTS_RE = re.compile(
    r'^(?P<indent> {0,3})(?P<marks>(?:>[ \t]?)+)(?P<content>.*)$')
#: Four ASCII spaces or a tab is an indented code block in Markdown.
_INDENTED_RE = re.compile(r'^(?:\t| {4})')
_THEMATIC_RE = re.compile(
    r'^ {0,3}(?:(?:\*[ \t]*){3,}|(?:-[ \t]*){3,}|(?:_[ \t]*){3,})$')
_SETEXT_RE = re.compile(r'^ {0,3}(?:=+|-+)[ \t]*$')
_DEF_ITEM_RE = re.compile(r'^ {0,3}:[ \t]')
_FOOTNOTE_RE = re.compile(r'^ {0,3}\[\^[^\]]+\]:')
_HTML_RE = re.compile(r'^ {0,3}<[A-Za-z!/?]')
#: A line that opens with a tag name ('<img', '</span>'), as opposed to a
#: comment ('<!--') or a declaration ('<!DOCTYPE', '<?xml').
_HTML_TAG_RE = re.compile(r'^ {0,3}</?[A-Za-z]')
#: The elements Markdown reads as block level HTML - python-markdown's own
#: BLOCK_LEVEL_ELEMENTS, spelled out here so this module stays free of
#: calibre and of Markdown itself.
_HTML_BLOCK_TAGS = frozenset((
    'address', 'article', 'aside', 'blockquote', 'body', 'canvas', 'center',
    'colgroup', 'dd', 'details', 'div', 'dl', 'dt', 'fieldset', 'figcaption',
    'figure', 'footer', 'form', 'group', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'header', 'hgroup', 'hr', 'html', 'iframe', 'legend', 'li', 'main', 'map',
    'math', 'menu', 'nav', 'noscript', 'object', 'ol', 'option', 'output',
    'p', 'pre', 'progress', 'script', 'section', 'style', 'summary', 'table',
    'tbody', 'td', 'textarea', 'tfoot', 'th', 'thead', 'tr', 'ul', 'video',
))
#: A line that opens (or closes) one of those: Markdown reads it as a raw
#: HTML block, not as the paragraph content an inline element starts.
_HTML_BLOCK_RE = re.compile(
    r'^ {0,3}</?(?:%s)(?=[\s/>]|$)' % '|'.join(sorted(_HTML_BLOCK_TAGS)),
    re.I)
_TABLE_CELL_RE = re.compile(r':?-+:?')
#: A line that starts a paragraph in 'print' style: one or more ideographic
#: spaces (the Chinese convention) or two/three ASCII spaces before text.
#: Four ASCII spaces and tabs are code blocks, classified as BLOCK above.
_PRINT_INDENT_RE = re.compile(r'^(?:\u3000+| {2,3}(?=\S))')


def _split_lines(text):
    """Lines of text with the newline styles unified (calibre does the same)."""
    return text.replace('\r\n', '\n').replace('\r', '\n').split('\n')


def _is_fence_close(stripped, fence):
    """True when a fence line closes the opening fence."""
    match = _FENCE_CLOSE_RE.match(stripped)
    return bool(match) and match.group(1)[0] == fence[0] \
        and len(match.group(1)) >= len(fence)


def _info(kind, fenced=False):
    """LineInfo of a line that is not a quote line."""
    return LineInfo(kind, 0, '', '', '', fenced)


def _quote_info(line):
    """LineInfo of a quote line: its markers, content and separator."""
    parts = _QUOTE_PARTS_RE.match(line)
    indent = parts.group('indent')
    marks = parts.group('marks')
    depth = marks.count('>')
    return LineInfo(BLOCK, depth, indent + marks, parts.group('content'),
                    indent + '>' * depth, False)


def _protect_previous(infos):
    """Turn the preceding body line into BLOCK (setext/definition marker)."""
    if infos and infos[-1].kind == BODY:
        infos[-1] = infos[-1]._replace(kind=BLOCK)


def _is_table_separator(line):
    """True for the '| --- | :--: |' line under a Markdown table header."""
    text = line.strip()
    if '|' not in text or '-' not in text:
        return False
    cells = [cell.strip() for cell in text.strip('|').split('|')]
    return bool(cells) and all(_TABLE_CELL_RE.fullmatch(cell) for cell in cells)


def _is_list_continuation(line):
    """True for lines that belong to the list item above them."""
    if not line.strip():
        return False
    return line[:1] in (' ', '\t') or bool(_LIST_RE.match(line))


def _consume_table(lines, start, infos):
    """Classify a whole table (header, separator, rows); return the next index.

    None means the line at `start` does not open a table.
    """
    if '|' not in lines[start]:
        return None
    if start + 1 >= len(lines) or not _is_table_separator(lines[start + 1]):
        return None
    index = start
    while index < len(lines) and lines[index].strip() and '|' in lines[index]:
        infos.append(_info(BLOCK))
        index += 1
    return index


def _opens_inline_html(line):
    """True for a line whose first element is an inline level HTML tag.

    Such a line is content - a paragraph line - not a structure over several
    lines: Markdown wraps it in the paragraph it starts, whatever else the
    line carries ('<img src="a"> <img src="b">', '<img> 文字',
    '<a href="x"><img src="y"></a>'). 'single' gives it a paragraph of its
    own like any other body line, so an image line never swallows the text
    line under it. A block level element ('<div>', '<p>', '<table>') is a
    structure over several lines and stays BLOCK; a comment or a declaration
    ('<!--', '<!DOCTYPE', '<?xml') is neither.
    """
    return bool(_HTML_TAG_RE.match(line)) and not _HTML_BLOCK_RE.match(line)


def analyze_lines(lines):
    """Kind and quote structure of every line (see LineInfo).

    The kinds are what classify_lines() reports. A line of a fenced code
    block is never a quote line, however it is spelled.
    """
    infos = []
    fence = ''
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if fence:
            infos.append(_info(BLOCK, fenced=True))
            if _is_fence_close(stripped, fence):
                fence = ''
            index += 1
            continue
        if not stripped:
            infos.append(_info(BLANK))
            index += 1
            continue
        opening = _FENCE_OPEN_RE.match(line)
        if opening:
            fence = opening.group(1)
            infos.append(_info(BLOCK, fenced=True))
            index += 1
            continue
        if _QUOTE_RE.match(line):
            infos.append(_quote_info(line))
            index += 1
            continue
        if (_ATX_RE.match(line)
                or _INDENTED_RE.match(line) or _THEMATIC_RE.match(line)
                or (_HTML_RE.match(line) and not _opens_inline_html(line))
                or _FOOTNOTE_RE.match(line)):
            infos.append(_info(BLOCK))
            index += 1
            continue
        if _SETEXT_RE.match(line) or _DEF_ITEM_RE.match(line):
            # These markers need the line above them to stay attached.
            _protect_previous(infos)
            infos.append(_info(BLOCK))
            index += 1
            continue
        table_end = _consume_table(lines, index, infos)
        if table_end is not None:
            index = table_end
            continue
        if _LIST_RE.match(line):
            infos.append(_info(BLOCK))
            index += 1
            while index < len(lines) and _is_list_continuation(lines[index]):
                infos.append(_info(BLOCK))
                index += 1
            continue
        infos.append(_info(BODY))
        index += 1
    return infos


def classify_lines(lines):
    """Kind of every line: BLANK, BODY or BLOCK (see the constants)."""
    return [info.kind for info in analyze_lines(lines)]


def detect_paragraph_type(text):
    """Guess the paragraph style of Markdown text.

    Returns PARAGRAPH_SINGLE (every line is a paragraph), PARAGRAPH_PRINT
    (an indented line starts a paragraph) or PARAGRAPH_BLOCK (standard
    Markdown: blank lines separate paragraphs). Text too short or too
    irregular to tell is reported as 'block', which callers apply by
    leaving the text alone.
    """
    if not text or not text.strip():
        return PARAGRAPH_BLOCK
    lines = _split_lines(text)
    kinds = classify_lines(lines)
    body = [index for index, kind in enumerate(kinds) if kind == BODY]
    if len(body) < MIN_BODY_LINES:
        return PARAGRAPH_BLOCK
    indented = sum(1 for index in body if _PRINT_INDENT_RE.match(lines[index]))
    if indented >= PRINT_MIN_LINES and indented >= PRINT_RATIO * len(body):
        return PARAGRAPH_PRINT
    tight = sum(1 for index in body
                if index + 1 < len(kinds) and kinds[index + 1] == BODY)
    if tight >= TIGHT_RATIO * len(body):
        return PARAGRAPH_SINGLE
    return PARAGRAPH_BLOCK


def _ends_a_paragraph(line, info):
    """True for lines after which 'single' style puts a blank line.

    Body lines - an image line among them, since a line that opens with an
    inline level element is a body line and ends its paragraph instead of
    sharing one with the line under it - and the headings that a following
    line would otherwise attach to (an ATX heading or a setext underline
    ending one). A fenced code block is content the style does not touch: a
    line of it is code whatever it looks like, and the blank line after a
    heading would land inside the code - one more of them on every further
    conversion, the reshaping never settling.
    """
    if info.fenced:
        return False
    return info.kind == BODY \
        or bool(_ATX_RE.match(line)) \
        or bool(_SETEXT_RE.match(line))


def _quote_run_end(infos, start):
    """Index of the last line of the quote block that starts at `start`."""
    depth = infos[start].depth
    end = start
    while end + 1 < len(infos) and infos[end + 1].depth == depth:
        end += 1
    return end


def _prefix_quote_lines(reshaped, run):
    """Put the quote prefixes back on reshaped quote content.

    Every line the reshaping kept is written with the prefix it came in with
    ("> 文字" and ">文字" both keep their spelling); a line the reshaping
    inserted is blank, and becomes the prefix-only separator of that quote
    level. An inserted blank line never stands before a blank content line
    (there would be nothing to separate), so matching the lines left to right
    is unambiguous.
    """
    out = []
    index = 0
    for line in reshaped:
        if index < len(run) and run[index].content == line:
            out.append(run[index].prefix + line)
            index += 1
        else:
            out.append(run[0].separator)
    return out


def _reshape_quote_run(lines, infos, start, end, style):
    """Reshape the content of one quote block; return the lines to write.

    The content is text of its own, so it is reshaped by the same rules and
    the prefixes are put back afterwards - recursively, which is what makes
    the rules apply to a quote inside a quote as well.
    """
    run = infos[start:end + 1]
    content = '\n'.join(info.content for info in run)
    reshaped = restructure_paragraphs(content, style)
    if reshaped == content:
        return list(lines[start:end + 1])
    return _prefix_quote_lines(reshaped.split('\n'), run)


def _needs_a_blank_line_after_quote(lines, infos, index):
    """True when a quote block needs a blank line before the line at `index`.

    A quote block is read up to the next blank line: the line after it is
    swallowed into the quote when nothing separates them, or when it carries
    no quote prefix (a lazy continuation line). 'single' style leaves a quote
    like it leaves a paragraph, so it separates them. A setext underline or a
    definition marker belongs to the line above it and stays attached to it.
    """
    if index >= len(infos) or infos[index].kind == BLANK or infos[index].depth:
        return False
    line = lines[index]
    return not (_SETEXT_RE.match(line) or _DEF_ITEM_RE.match(line))


def _separate_single_lines(lines, infos):
    """Give every body line a blank line after it (when it has none)."""
    out = []
    index = 0
    while index < len(lines):
        info = infos[index]
        if info.depth:
            end = _quote_run_end(infos, index)
            out.extend(_reshape_quote_run(
                lines, infos, index, end, PARAGRAPH_SINGLE))
            index = end + 1
            if _needs_a_blank_line_after_quote(lines, infos, index):
                out.append('')
            continue
        out.append(lines[index])
        if _ends_a_paragraph(lines[index], info) \
                and index + 1 < len(lines) and infos[index + 1].kind != BLANK:
            out.append('')
        index += 1
    return out


def _separate_print_lines(lines, infos):
    """Start a new paragraph before every indented body line."""
    out = []
    index = 0
    while index < len(lines):
        info = infos[index]
        if info.depth:
            end = _quote_run_end(infos, index)
            out.extend(_reshape_quote_run(
                lines, infos, index, end, PARAGRAPH_PRINT))
            index = end + 1
            continue
        if (info.kind == BODY and _PRINT_INDENT_RE.match(lines[index])
                and out and out[-1].strip()):
            out.append('')
        out.append(lines[index])
        index += 1
    return out


def restructure_paragraphs(text, style):
    """Return text with the blank lines Markdown needs for the style.

    'single' makes every body line its own paragraph, 'print' starts a new
    paragraph at every indented body line. Both apply inside a quote block as
    well: the text a quote carries is text like any other, so it is reshaped
    on its own and the '>' prefixes are put back, a paragraph break inside
    the quote becoming a prefix-only line. Any other style - 'block'
    included - returns the text unchanged: it is already what Markdown
    reads. The function is idempotent: reshaped text detects as 'block'
    ('single') or reshapes to itself ('print').
    """
    if not text or style not in (PARAGRAPH_SINGLE, PARAGRAPH_PRINT):
        return text
    lines = _split_lines(text)
    infos = analyze_lines(lines)
    if style == PARAGRAPH_SINGLE:
        reshaped = _separate_single_lines(lines, infos)
    else:
        reshaped = _separate_print_lines(lines, infos)
    if reshaped == lines:
        return text
    return '\n'.join(reshaped)
