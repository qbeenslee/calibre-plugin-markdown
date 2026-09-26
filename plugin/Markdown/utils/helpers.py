# -*- coding: utf-8 -*-
# Calibre-free helpers for Markdown export (tables, TOC, YAML, images).

from __future__ import print_function

import os
import re
from collections import namedtuple
from urllib.parse import quote

TABLE_ROW_WRAPPERS = ('thead', 'tbody', 'tfoot')
IMAGE_SIDECAR_SUFFIX = '.images'
DEFAULT_IMAGE_DIR = 'images'

_LANG_TOKEN_RE = re.compile(
    r'^(?:language|lang|highlight|highlight-source)-([A-Za-z0-9+#]+)$',
    re.I,
)
_LANG_BRUSH_RE = re.compile(
    r'(?:language|lang|highlight|brush)[-:=\s]+([A-Za-z0-9+#]+)',
    re.I,
)
_YAML_SPECIAL_RE = re.compile(r'[:#\[\]{},&*!|>\'"%@`]')
_BARE_LANG_SKIP = frozenset((
    'preformatted', 'highlight', 'code', 'source', 'prettyprint',
    'hljs', 'syntax', 'listing', 'pre', 'blockquote',
))

FILENAME_PATTERN_TITLE = 'title'
FILENAME_PATTERN_AUTHOR_TITLE = 'author_title'
FILENAME_PATTERN_AUTHOR_FOLDER = 'author_folder'
FILENAME_PATTERN_SERIES_TITLE = 'series_title'
FILENAME_PATTERNS = (
    FILENAME_PATTERN_TITLE,
    FILENAME_PATTERN_AUTHOR_TITLE,
    FILENAME_PATTERN_AUTHOR_FOLDER,
    FILENAME_PATTERN_SERIES_TITLE,
)

_INVISIBLE_CHAR_RE = re.compile('[\u00ad\u200b\u200c\u200d\u2060\ufeff]')
_PDF_PAGE_LINE_RE = re.compile(
    r'^\s*(?:Page[-\s]\d+|link to page\s*\d+)\s*$',
    re.I | re.M,
)
_HTML_TAG_RE = re.compile(r'<[^>]+>')
_HTML_BR_RE = re.compile(r'<br\s*/?>', re.I)
_HTML_P_RE = re.compile(r'</p>', re.I)


def sanitize_filename(title, default='Unknown'):
    title = (title or '').strip()
    title = re.sub(r'[\\/:*?"<>|]', '_', title)
    title = re.sub(r'\s+', ' ', title).strip()
    return title or default


def first_author(authors):
    if isinstance(authors, (list, tuple)):
        for item in authors:
            name = str(item or '').strip()
            if name:
                return name
        return ''
    return str(authors or '').strip()


def format_series_index(value, pad=False):
    if value is None or value == '':
        return ''
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value).strip()
    if number.is_integer():
        number = int(number)
        if pad:
            return '%02d' % number
        return str(number)
    return ('%g' % number).rstrip('0').rstrip('.')


def build_output_relpath(meta, pattern=FILENAME_PATTERN_TITLE):
    meta = meta or {}
    title = sanitize_filename(meta.get('title'))
    author = sanitize_filename(first_author(meta.get('authors')))
    series = sanitize_filename(meta.get('series'), default='')
    index = format_series_index(meta.get('series_index'), pad=True)
    if pattern == FILENAME_PATTERN_AUTHOR_TITLE:
        return '%s - %s' % (author, title)
    if pattern == FILENAME_PATTERN_AUTHOR_FOLDER:
        return '%s/%s' % (author, title)
    if pattern == FILENAME_PATTERN_SERIES_TITLE:
        if series and index:
            return '%s %s - %s' % (series, index, title)
        if series:
            return '%s - %s' % (series, title)
        return title
    return title


def html_to_plain(text):
    text = text or ''
    text = _HTML_BR_RE.sub('\n', text)
    text = _HTML_P_RE.sub('\n', text)
    text = _HTML_TAG_RE.sub('', text)
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
    text = text.replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('&quot;', '"')
    text = re.sub(r'[ \t]+\n', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def format_pubdate(value):
    if value is None or value == '':
        return ''
    year = getattr(value, 'year', None)
    if year is not None:
        if int(year) < 1000:
            return ''
        try:
            return '%04d-%02d-%02d' % (value.year, value.month, value.day)
        except Exception:
            return ''
    text = str(value).strip()
    if len(text) >= 10 and text[4] == '-':
        return text[:10]
    return text


def clean_invisible_chars(text):
    return _INVISIBLE_CHAR_RE.sub('', text or '')


def strip_pdf_page_marker_lines(text):
    if not text:
        return text
    cleaned = _PDF_PAGE_LINE_RE.sub('', text)
    return re.sub(r'\n{3,}', '\n\n', cleaned)


PARAGRAPH_STYLE_BLOCK = 'block'
PARAGRAPH_STYLE_SINGLE = 'single'
_FENCE_MARKER_RE = re.compile(r'^\s*(```|~~~)')
_HEADING_LINE_RE = re.compile(r'^#{1,6}(?:\s|$)')
_QUOTE_PREFIX_RE = re.compile(r'^(?: {0,3}>[ \t]?)+')
#: A line that opens a list item - the spelling the renderers write ("- 项",
#: "1. 项", nested with tabs or two spaces) and the CommonMark one besides.
_LIST_LINE_RE = re.compile(r'^[ \t]*(?:[-*+]|\d{1,9}[.)])(?:[ \t]|$)')
#: A thematic break. The '<hr>' the renderer writes is "* * *", which only the
#: thematic break reading makes sense of: as a list item it is not a block the
#: blank lines around it have to be kept for (a thematic break interrupts a
#: paragraph and needs no blank line at all).
_THEMATIC_LINE_RE = re.compile(
    r'^ {0,3}(?:(?:\*[ \t]*){3,}|(?:-[ \t]*){3,}|(?:_[ \t]*){3,})$')
#: A table row: the pipe tables the renderer writes always open with one.
_TABLE_ROW_RE = re.compile(r'^[ \t]*\|')
_TABLE_CELL_RE = re.compile(r':?-+:?')
#: The ": 释义" line under a definition list's term.
_DEF_ITEM_LINE_RE = re.compile(r'^[ \t]*:[ \t]')
#: A footnote definition, "[^1]: 正文".
_FOOTNOTE_LINE_RE = re.compile(r'^[ \t]*\[\^[^\]]+\]:')
#: A line that carries nothing but the delimiters a run of emphasis is closed
#: with: a quote written in italics opens its "*" on the line the quote starts
#: and closes it on a line of its own, under the last line of the quote. The
#: list reading would call it a bullet with no content, and the blank line a
#: block gets in front of it leaves the run it closes unmatched.
_DELIMITER_LINE_RE = re.compile(r'^ {0,3}(?:\*{1,2}|_{1,2}|~{2})[ \t]*$')

#: What one line of the finished Markdown is for the 'single' style's
#: blank-line rules: the structure it carries (one of the kinds below) and
#: whether it is a line inside a quote block.
_Line = namedtuple('_Line', 'kind quoted')

#: A blank line. It is kept only where it separates structure, not paragraphs.
_BLANK = 'blank'
#: A line of a fenced code block - its fences included. Blank lines in there
#: are content.
_FENCED = 'fenced'
#: A line of a quote block other than the structures below ("quote content").
_QUOTE = 'quote'
#: A list item, or a line that continues one (the indented second paragraph of
#: an item, a nested block of it).
_LIST = 'list'
#: A table row (the header, the alignment row, the data rows).
_TABLE = 'table'
#: The "*标题*" line the renderer writes above a table.
_CAPTION = 'caption'
#: The term line of a definition list (the line above a ": 释义" line).
_DEF_TERM = 'def-term'
#: The ": 释义" line of a definition list.
_DEF_ITEM = 'def-item'
#: A footnote definition, "[^1]: 正文".
_FOOTNOTE = 'footnote'
#: A thematic break, "* * *".
_THEMATIC = 'thematic'
#: Everything else: paragraphs, headings, the lines of inline HTML.
_TEXT = 'text'
#: Not a kind a line is classified as - a heading is a heading only on the
#: line it is written on, whatever the classification of that line is - but
#: the block one heading line is for the blank lines.
_HEADING = 'heading'
#: The group the term line of a definition list and its ": 释义" line share:
#: the two are one block, a term being a term only with its definition under
#: it.
_DEF = 'def'

#: The block group a kind's lines belong to for the blank-line rules:
#: consecutive lines of one group, with no blank line between them, are one
#: block (the rows of a table, the items of a list). A block named here is
#: one a blank line is written before and after; a caption has a group of its
#: own, the table under it being a table only with a blank line above it.
#: _TEXT names no group: a paragraph is the text 'single' compacts.
#:
#: The groups are the blocks Markdown reads across consecutive lines (a list,
#: a table, a definition list, a footnote definition - dropping the blank
#: line around one lets the text next to it be read as part of it, and
#: python-markdown never starts one inside a paragraph), a quote block (a
#: quote is read up to the next blank line), a fenced code block and a
#: thematic break - written apart from the text around them, which keeps
#: 'single' readable where the renderer put a block inside a run of prose.
_BLOCK_GROUPS = {
    _FENCED: _FENCED,
    _LIST: _LIST,
    _TABLE: _TABLE,
    _CAPTION: _CAPTION,
    _DEF_TERM: _DEF,
    _DEF_ITEM: _DEF,
    _FOOTNOTE: _FOOTNOTE,
    _QUOTE: _QUOTE,
    _THEMATIC: _THEMATIC,
}


def _following_content_indexes(lines):
    '''For every line, the index of the next line with content (None past the end).'''
    following = [None] * len(lines)
    next_index = None
    for index in range(len(lines) - 1, -1, -1):
        following[index] = next_index
        if lines[index].strip():
            next_index = index
    return following


def _strip_quote_prefix(line):
    '''The content of a line without the ">" markers it carries.

    The structure behind the markers is the structure of the line: a quote
    holding a list ("- > 引文", "> - 甲") is a list at that quote level.
    '''
    return _QUOTE_PREFIX_RE.sub('', line, count=1)


def _is_table_delimiter(line):
    '''True for the "| --- | :-: |" alignment row under a table header.

    A table is only a table when that row follows its first row, which is how
    the line above it is told from a paragraph that happens to carry a pipe.
    '''
    text = _strip_quote_prefix(line).strip()
    if '|' not in text or '-' not in text:
        return False
    cells = [cell.strip() for cell in text.strip('|').split('|')]
    return bool(cells) and all(_TABLE_CELL_RE.fullmatch(cell) for cell in cells)


def _starts_a_table(lines, following, index):
    '''True when the line at index opens a table (its own next line aligns it).'''
    if index is None:
        return False
    after = following[index]
    return after is not None and _is_table_delimiter(lines[after])


def _classify_lines(lines, following):
    '''What every line is for the blank-line rules (see the kinds above).

    The lookahead a classification needs is the next line with content: the
    term of a definition list and the caption above a table are only that
    because of the line under them. A line of a fenced code block is never
    anything else - its content is code, whatever it looks like - and a table
    or a list ends at the first line that is neither a row of it nor a line
    that continues it.
    '''
    classified = []
    fence = ''
    in_table = False
    in_list = False
    lazy_quote = False
    for index, line in enumerate(lines):
        marker = _FENCE_MARKER_RE.match(line)
        if marker or fence:
            if marker:
                char = marker.group(1)[0]
                if not fence:
                    fence = char
                elif char == fence:
                    fence = ''
            classified.append(_Line(_FENCED, False))
            continue
        if not line.strip():
            classified.append(_Line(_BLANK, False))
            in_table = False
            lazy_quote = False
            continue

        content = _strip_quote_prefix(line)
        quoted = bool(_QUOTE_PREFIX_RE.match(line))
        if in_table and _TABLE_ROW_RE.match(content):
            classified.append(_Line(_TABLE, quoted))
            lazy_quote = quoted
            continue
        in_table = False
        if _THEMATIC_LINE_RE.match(content):
            classified.append(_Line(_THEMATIC, quoted))
            lazy_quote = False
            continue
        if _LIST_LINE_RE.match(content):
            in_list = True
            classified.append(_Line(_LIST, quoted))
            lazy_quote = quoted
            continue
        if _DEF_ITEM_LINE_RE.match(content):
            classified.append(_Line(_DEF_ITEM, quoted))
            lazy_quote = quoted
            continue
        if _FOOTNOTE_LINE_RE.match(content):
            classified.append(_Line(_FOOTNOTE, quoted))
            lazy_quote = quoted
            continue
        if _TABLE_ROW_RE.match(content) and _starts_a_table(lines, following, index):
            in_table = True
            classified.append(_Line(_TABLE, quoted))
            lazy_quote = quoted
            continue
        if in_list and content[:1] in (' ', '\t'):
            # The second paragraph of a list item (the renderer indents it to
            # the item's content column) or a block inside it.
            classified.append(_Line(_LIST, quoted))
            continue
        if quoted:
            classified.append(_Line(_QUOTE, quoted))
            lazy_quote = True
            continue
        if lazy_quote:
            # A quote is read up to the next blank line: a plain text line
            # after a quote line is a lazy continuation line of the quote and
            # the blank line after it is what ends the quote. The shape comes
            # from a quoted <pre>, which the renderer writes without a ">"
            # prefix; without this the whole rest of the file would be read
            # as one lazy quote.
            classified.append(_Line(_QUOTE, True))
            continue
        in_list = False
        after = following[index]
        if _starts_a_table(lines, following, after):
            classified.append(_Line(_CAPTION, quoted))
            continue
        if after is not None \
                and _DEF_ITEM_LINE_RE.match(_strip_quote_prefix(lines[after])):
            classified.append(_Line(_DEF_TERM, quoted))
            continue
        classified.append(_Line(_TEXT, quoted))
    return classified


def _block_group(line_info):
    '''The block group a classified line belongs to - None for a paragraph.

    A line inside a quote is of the quote's group whatever it carries: a
    quoted list is a list inside a quote block, and what the blank line has
    to end is the quote, not the list.
    '''
    if line_info.quoted:
        return _QUOTE
    return _BLOCK_GROUPS.get(line_info.kind)


#: The lines of one block: the group it belongs to (None for a run of
#: paragraph lines, _HEADING for one heading line) and the indexes of its
#: lines.
_Block = namedtuple('_Block', 'group indexes')


def _content_blocks(lines, classified):
    '''Group the content lines into the blocks the blank lines go around.

    Consecutive lines of one group are one block - the rows of a table, the
    items of a list - and a blank line or a line of another group ends one:
    what follows a blank line is a block of its own (the second paragraph of
    a list item, the table under its caption), and a line of another group is
    a block the blank line between the two separates. A heading line is a
    block of its own whatever it follows, so that the blank line it may need
    above it is written for it and not for the text above.

    A quote is the exception: the blank lines inside one are the quote's own
    paragraph separations and go, so quote lines stay one block whatever is
    between them - two quote blocks written one under the other are read as
    one, and a quote line is a paragraph line of its own once the file is
    read back as 'single'.

    The blank lines inside a fenced code block are content: they are
    classified as fenced lines of the block, so they never end it.
    '''
    blocks = []
    ended = True
    for index, line in enumerate(lines):
        info = classified[index]
        if not line.strip() and info.kind != _FENCED:
            ended = True
            continue
        group = _block_group(info)
        heading = info.kind != _FENCED and _HEADING_LINE_RE.match(line)
        if blocks and not heading and _DELIMITER_LINE_RE.match(line):
            # The delimiters closing a run the renderer opened above belong to
            # the block that opened it, blank line or not.
            group = blocks[-1].group
            ended = False
        elif ended and group == _QUOTE and blocks \
                and blocks[-1].group == _QUOTE:
            # The blank lines a quote carries are its own paragraph
            # separations: they go, so the quote stays one block.
            ended = False
        if ended or heading or group is None \
                or not blocks or blocks[-1].group != group:
            blocks.append(_Block(_HEADING if heading else group, [index]))
        else:
            blocks[-1].indexes.append(index)
        ended = False
    return blocks


#: The "---" rule that opens and closes the YAML front matter.
_FRONT_MATTER_RULE = '---'


def _split_front_matter(lines):
    '''The YAML front matter at the top of the file, and the lines under it.

    Its rules read as thematic breaks (and a field whose value is a comment
    as a heading), so the blank lines this module writes would land inside
    the front matter and break it. It is taken out whole - a front matter
    holds no blank line of its own - and written back as it stands.
    '''
    if not lines or lines[0].strip() != _FRONT_MATTER_RULE:
        return [], lines
    for index in range(1, len(lines)):
        line = lines[index].strip()
        if not line:
            break
        if line == _FRONT_MATTER_RULE:
            return lines[:index + 1], lines[index + 1:]
    return [], lines


def apply_paragraph_style(text, style=PARAGRAPH_STYLE_BLOCK,
                          blank_line_before_heading=False):
    '''Reshape paragraph separation in the finished Markdown.

    'block' (default) keeps the standard Markdown layout where a blank line
    separates paragraphs. 'single' drops blank lines so every content line
    stands as its own paragraph line, and writes one before and one after
    every block instead (see _BLOCK_GROUPS): a fenced code block, a quote
    block, a thematic break, a list, a table with its caption, a definition
    list and a footnote definition. A block at the very start or end of the
    file gets the one blank line it has a side to get it on. With
    blank_line_before_heading a heading gets a blank line before it as well -
    never after it, and never a heading that is the first line of the file.

    A run of blank lines the renderer left (a soft scene break from the CSS
    margins of the book, on top of the block's own newlines) collapses to the
    one blank line that does the separating - the blank lines inside a fenced
    code block are content and are kept as they are written.
    '''
    if not text or style != PARAGRAPH_STYLE_SINGLE:
        return text
    lines = text.splitlines()
    front_matter, lines = _split_front_matter(lines)
    following = _following_content_indexes(lines)
    classified = _classify_lines(lines, following)
    blocks = _content_blocks(lines, classified)
    kept = []
    for position, block in enumerate(blocks):
        after = block.group is not None and block.group != _HEADING
        before = after or (block.group == _HEADING
                           and blank_line_before_heading)
        # The front matter above is content of its own, so the first block
        # under it is not the first block of the file.
        if (position or front_matter) and (
                before or (position
                           and blocks[position - 1].group
                           not in (None, _HEADING))):
            kept.append('')
        kept.extend(lines[index] for index in block.indexes)
    if not front_matter:
        return '\n'.join(kept) + '\n'
    head = '\n'.join(front_matter) + '\n'
    if not kept:
        return head
    return head + '\n'.join(kept) + '\n'


TITLEPAGE_BASENAMES = frozenset(('titlepage.xhtml', 'titlepage.html'))


def is_titlepage_href(href):
    '''True when a spine href points at a cover/title page file.

    calibre-generated EPUBs name the page titlepage.xhtml; the .html
    spelling is accepted for hand-built books.
    '''
    base = os.path.basename(str(href or '').strip())
    return base.lower() in TITLEPAGE_BASENAMES


def yaml_fields_from_metadata(library_meta, oeb_fields=None):
    '''Prefer library metadata, then OEB-derived fields. Empty values omitted.'''
    library_meta = library_meta or {}
    oeb_fields = oeb_fields or {}
    keys = (
        'title', 'authors', 'language', 'publisher', 'tags',
        'series', 'series_index', 'isbn', 'pubdate', 'description',
        'calibre_id',
    )
    fields = []
    for key in keys:
        value = library_meta.get(key)
        if value in (None, '', [], ()):
            value = oeb_fields.get(key)
        if key == 'series_index' and value not in (None, ''):
            value = format_series_index(value)
        if value not in (None, '', [], ()):
            fields.append((key, value))
    return fields


def local_name(tag):
    if not isinstance(tag, (str, bytes)):
        return ''
    if isinstance(tag, bytes):
        tag = tag.decode('utf-8', 'replace')
    if '}' in tag:
        return tag.rsplit('}', 1)[-1]
    return tag


def iter_table_rows(elem):
    '''Yield <tr> elements, including those wrapped in thead/tbody/tfoot.'''
    rows = []
    for child in elem:
        name = local_name(getattr(child, 'tag', None))
        if name == 'tr':
            rows.append(child)
        elif name in TABLE_ROW_WRAPPERS:
            rows.extend(iter_table_rows(child))
    return rows


def find_table_caption(elem):
    for child in elem:
        if local_name(getattr(child, 'tag', None)) == 'caption':
            return child
    return None


def alignment_separator(align):
    value = (align or '').strip().lower()
    if value in ('center', 'middle'):
        return ':---:'
    if value in ('right', 'end'):
        return '---:'
    if value in ('left', 'start', 'justify'):
        return ':---'
    return '---'


def cell_alignment(elem, style_align=None):
    attribs = getattr(elem, 'attrib', None) or {}
    align = attribs.get('align') or ''
    if not align:
        align = style_align or ''
    return alignment_separator(align)


def extract_code_language(*sources):
    for raw in sources:
        if not raw:
            continue
        text = str(raw).strip()
        if not text:
            continue
        for part in re.split(r'\s+', text):
            match = _LANG_TOKEN_RE.match(part)
            if match:
                return match.group(1).lower()
        match = _LANG_BRUSH_RE.search(text)
        if match:
            return match.group(1).lower()
        if (
            re.match(r'^[A-Za-z][A-Za-z0-9+#]*$', text)
            and text.lower() not in _BARE_LANG_SKIP
        ):
            return text.lower()
    return ''


def slugify(text):
    value = (text or '').strip().lower()
    value = re.sub(r'[^\w\s\-]', '', value, flags=re.UNICODE)
    value = re.sub(r'\s+', '-', value)
    value = re.sub(r'-{2,}', '-', value).strip('-')
    return value or 'section'


def unique_slug(title, used):
    base = slugify(title)
    slug = base
    counter = 1
    while slug in used:
        slug = '%s-%d' % (base, counter)
        counter += 1
    used.add(slug)
    return slug


def render_toc_block(entries, heading='Table of Contents'):
    '''entries: iterable of (depth, title).'''
    items = []
    used = set()
    for depth, title in entries or []:
        title = (title or '').strip()
        if not title:
            continue
        slug = unique_slug(title, used)
        indent = '  ' * max(0, int(depth or 0))
        items.append('%s- [%s](#%s)\n' % (indent, title, slug))
    if not items:
        return ''
    return '## %s\n\n%s\n' % (heading, ''.join(items))


def yaml_quote(value):
    text = str(value).replace('\r\n', '\n').strip()
    if not text:
        return "''"
    needs_quotes = (
        _YAML_SPECIAL_RE.search(text)
        or text[:1] in '-?'
        or '\n' in text
        or text != text.strip()
    )
    if needs_quotes:
        escaped = text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
        return '"%s"' % escaped
    return text


def render_yaml_front_matter(fields):
    '''fields: sequence of (key, value) where value is str or list/tuple of str.'''
    if not fields:
        return ''
    lines = ['---']
    wrote = False
    for key, value in fields:
        if value is None or value == '' or value == [] or value == ():
            continue
        if isinstance(value, (list, tuple)):
            cleaned = [str(item).strip() for item in value if str(item).strip()]
            if not cleaned:
                continue
            if len(cleaned) == 1:
                lines.append('%s: %s' % (key, yaml_quote(cleaned[0])))
            else:
                lines.append('%s:' % key)
                for item in cleaned:
                    lines.append('  - %s' % yaml_quote(item))
        else:
            lines.append('%s: %s' % (key, yaml_quote(value)))
        wrote = True
    if not wrote:
        return ''
    lines.append('---\n')
    return '\n'.join(lines) + '\n'


def metadata_text_values(container):
    values = []
    for item in container or []:
        value = getattr(item, 'value', None)
        if value is None:
            value = str(item)
        value = str(value).strip()
        if value:
            values.append(value)
    return values


def image_sidecar_path(md_path):
    root, _ext = os.path.splitext(md_path)
    return root + IMAGE_SIDECAR_SUFFIX


def image_sidecar_name(md_path):
    return os.path.basename(image_sidecar_path(md_path))


def is_markdown_bundle_taken(md_path):
    return os.path.exists(md_path) or os.path.exists(image_sidecar_path(md_path))


def encode_image_dir(name):
    return quote(name or DEFAULT_IMAGE_DIR, safe='.-_')


_LENGTH_RE = re.compile(r'^[0-9.]+$')


def escape_html_attr(value):
    '''Escape a value for use inside a double-quoted HTML attribute.'''
    text = str(value or '')
    for char, entity in (('&', '&amp;'), ('<', '&lt;'), ('>', '&gt;'),
                         ('"', '&quot;')):
        text = text.replace(char, entity)
    return text


def _length_value(raw):
    '''Normalise one declared length; '' when it declares nothing.

    Bare numbers are pixels - the form both calibre's attribute migration and
    hand-built EPUBs use - and relative units stay exactly as declared.
    '''
    value = str(raw or '').strip()
    if not value or value.lower() == 'auto':
        return ''
    if _LENGTH_RE.match(value):
        return value + 'px'
    return value


def image_size_attrs(attribs, declared_css=None):
    '''Return {'width': ..., 'height': ...} for an <img>, or None.

    The element's own width/height attributes win; the CSS declarations
    (calibre's Style carries the matching rules, a style="" attribute and the
    attribute values it migrated) only fill the dimensions the attributes
    leave open. A dimension nobody declares becomes 'auto' so the renderer
    keeps the aspect ratio; with neither declared the caller keeps the plain
    Markdown form instead.
    '''
    attribs = attribs or {}
    declared = declared_css or {}
    sizes = {}
    declared_any = False
    for name in ('width', 'height'):
        value = _length_value(attribs.get(name)) or _length_value(
            declared.get(name))
        if value:
            declared_any = True
        sizes[name] = value or 'auto'
    if not declared_any:
        return None
    return sizes


def html_image_tag(src, alt='', title='', size=None):
    '''Render an <img> carrying the size the book declared.'''
    size = size or {}
    parts = ['src="%s"' % escape_html_attr(src)]
    if alt:
        parts.append('alt="%s"' % escape_html_attr(alt))
    if title:
        parts.append('title="%s"' % escape_html_attr(title))
    parts.append('width="%s"' % escape_html_attr(size.get('width') or 'auto'))
    parts.append('height="%s"' % escape_html_attr(size.get('height') or 'auto'))
    return '<img %s>' % ' '.join(parts)


def _html_img_src_pattern(old_dir):
    '''Match the src of an <img> that points into old_dir.'''
    return re.compile(
        r'(<img\b[^>]*?\bsrc=["\'])%s/' % re.escape(old_dir), re.I)


_IMG_TAG_RE = re.compile(r'<img\b[^>]*>', re.I)
_IMG_SIZE_ATTR_RE = re.compile(
    r'\s+(?:width|height)\s*=\s*(?:"[^"]*"|\'[^\']*\'|[^\s>]+)', re.I)
_STYLE_ATTR_RE = re.compile(r'\sstyle\s*=\s*(["\'])(.*?)\1', re.I | re.S)


def _strip_style_sizes(css):
    '''Drop the width/height declarations from an inline style value.'''
    kept = []
    for part in css.split(';'):
        prop = part.split(':', 1)[0].strip().lower()
        if prop in ('width', 'height'):
            continue
        part = part.strip()
        if part:
            kept.append(part)
    return '; '.join(kept)


def strip_image_sizes(html):
    '''Remove the size every <img> declares (width/height attr and style).

    Used when "Keep image sizes" is off: the images then enter the book
    without a size, as if the Markdown never declared one. Everything else on
    the tag - alt, class, other styles, max-width - is left untouched, and
    only the <img> tags themselves are rewritten.
    '''
    if not html or 'img' not in html.lower():
        return html

    def rewrite(match):
        tag = _IMG_SIZE_ATTR_RE.sub('', match.group(0))
        style = _STYLE_ATTR_RE.search(tag)
        if style is None:
            return tag
        cleaned = _strip_style_sizes(style.group(2))
        if not cleaned:
            return tag[:style.start()] + tag[style.end():]
        return tag[:style.start()] + ' style="%s"' % cleaned + tag[style.end():]

    return _IMG_TAG_RE.sub(rewrite, html)


def strip_image_tags(html):
    '''Remove every <img> tag (used when the master "Keep images" is off).

    The whole element goes - alt text included - so the converted book
    carries no image references at all; only <img> tags are touched.
    '''
    if not html or 'img' not in html.lower():
        return html
    return _IMG_TAG_RE.sub('', html)


def rewrite_html_image_srcs(html, replacements):
    '''Point the <img> src of every listed reference at its replacement.

    replacements maps the src value as written in the html to the value to
    write. Only the src value changes - alt/width/height and the rest of the
    tag stay - and both quote styles count. A value that the html carries in
    its escaped spelling (an '&' file name reads '&amp;' in the markup) is
    matched as well; the replacement is escaped to fit the attribute either
    way. Returns (new_html, replaced_count).
    '''
    if not html or not replacements:
        return html, 0
    count = 0
    for old, new in replacements.items():
        old = str(old or '')
        new = str(new or '')
        if not old or not new or old == new:
            continue
        spellings = [old]
        escaped_old = escape_html_attr(old)
        if escaped_old != old:
            spellings.append(escaped_old)
        rewritten = escape_html_attr(new)
        for spelling in spellings:
            pattern = re.compile(
                r'(<img\b[^>]*?\bsrc=["\'])%s(["\'])' % re.escape(spelling),
                re.I)
            html, replaced = pattern.subn(
                lambda match: match.group(1) + rewritten + match.group(2),
                html)
            count += replaced
    return html, count


def rewrite_markdown_image_dir(text, new_dir, old_dir=DEFAULT_IMAGE_DIR):
    '''Point every image reference spelling at another folder.'''
    if not text or not new_dir:
        return text
    encoded = encode_image_dir(new_dir)
    text = re.sub(r'(!\[[^\]]*\]\()%s/' % re.escape(old_dir),
                  r'\1%s/' % encoded, text)
    return _html_img_src_pattern(old_dir).sub(r'\1%s/' % encoded, text)


def copy_markdown_bundle(src_md, dest_md):
    '''Copy a .md file and its sibling .images directory if present.'''
    import shutil
    shutil.copy2(src_md, dest_md)
    src_sidecar = image_sidecar_path(src_md)
    dest_sidecar = image_sidecar_path(dest_md)
    if os.path.isdir(src_sidecar):
        if os.path.exists(dest_sidecar):
            shutil.rmtree(dest_sidecar)
        shutil.copytree(src_sidecar, dest_sidecar)
    return dest_md


def manifest_item_bytes(item):
    if item is None:
        return None
    data = getattr(item, 'data', None)
    if data is None:
        return None
    if isinstance(data, (bytes, bytearray)):
        return bytes(data)
    if hasattr(data, 'getroottree') or hasattr(data, 'tag'):
        try:
            from lxml import etree
            return etree.tostring(data, encoding='utf-8', xml_declaration=True)
        except Exception:
            return None
    if isinstance(data, str):
        return data.encode('utf-8')
    return None


def _href_to_item(oeb_book):
    href_to_item = {}
    for item in getattr(oeb_book, 'manifest', None) or []:
        href = getattr(item, 'href', None)
        if href:
            href_to_item[href] = item
    return href_to_item


def referenced_image_map(text, image_map):
    '''Keep only the mapped images the finished Markdown references.

    map_resources() registers every image in the book manifest, so images the
    Markdown never mentions - the cover image when the cover page was skipped,
    an image only used by a stylesheet - would otherwise be written next to a
    file that cannot use them. Callers hand the result to the image export, so
    an unreferenced-only book exports nothing and leaves no folder behind.
    '''
    if not text or not image_map:
        return {}
    referenced = {}
    for href, fname in image_map.items():
        base = os.path.basename(str(fname or ''))
        # Mapped names are unique %06d names, so a reference can only belong
        # to the entry it names.
        if base and ('%s/%s' % (DEFAULT_IMAGE_DIR, base)) in text:
            referenced[href] = fname
    return referenced


def export_mapped_images(oeb_book, image_map, md_path, dest_dir=None):
    '''Write mapped OEB images into dest_dir (default: sibling .images).

    Returns the number of files written. Nothing is created when there is
    nothing to write, so a skipped conversion leaves no empty folder behind
    and an existing (empty) target folder is never removed.
    '''
    image_map = image_map or {}
    dest_dir = dest_dir or (image_sidecar_path(md_path) if md_path else None)
    if not image_map or not dest_dir:
        return 0
    href_to_item = _href_to_item(oeb_book)
    pending = []
    for href, fname in image_map.items():
        data = manifest_item_bytes(href_to_item.get(href))
        if not data or not fname:
            continue
        pending.append((os.path.join(dest_dir, os.path.basename(str(fname))), data))
    if not pending:
        return 0
    os.makedirs(dest_dir, exist_ok=True)
    for dest, data in pending:
        with open(dest, 'wb') as handle:
            handle.write(data)
    return len(pending)


def _data_uri(fname, payload):
    '''Encode image bytes as an inline data URI for the given file name.'''
    import base64
    ext = os.path.splitext(str(fname))[1].lower()[1:]
    mime = {
        'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'jfif': 'image/jpeg',
        'png': 'image/png', 'gif': 'image/gif', 'webp': 'image/webp',
        'svg': 'image/svg+xml', 'bmp': 'image/bmp', 'tif': 'image/tiff',
        'tiff': 'image/tiff', 'ico': 'image/x-icon', 'avif': 'image/avif',
    }.get(ext, 'application/octet-stream')
    return 'data:%s;base64,%s' % (
        mime, base64.b64encode(payload).decode('ascii'))


def inline_image_references(text, oeb_book, image_map):
    '''Replace images/<file> references with base64 data URIs.

    Both spellings are inlined - ![alt](images/x) and the raw-HTML
    <img src="images/x" width=...> sized images produce. Returns
    (new_text, replaced_count). Unmapped references are left alone; an image
    referenced more than once counts once per reference.
    '''
    image_map = image_map or {}
    if not text or not image_map:
        return text, 0
    href_to_item = _href_to_item(oeb_book)
    count = 0
    for href, fname in image_map.items():
        data = manifest_item_bytes(href_to_item.get(href))
        if not data or not fname:
            continue
        base = os.path.basename(str(fname))
        uri = _data_uri(base, data)
        pattern = re.compile(
            r'(!\[[^\]]*\]\()%s/%s\)'
            % (re.escape(DEFAULT_IMAGE_DIR), re.escape(base)))
        text, replaced = pattern.subn(lambda m: m.group(1) + uri + ')', text)
        # The sized form keeps its width/height/alt attributes: only the src
        # value is swapped.
        html_pattern = re.compile(
            r'(<img\b[^>]*?\bsrc=["\'])%s/%s(["\'])'
            % (re.escape(DEFAULT_IMAGE_DIR), re.escape(base)), re.I)
        text, html_replaced = html_pattern.subn(
            lambda m: m.group(1) + uri + m.group(2), text)
        count += replaced + html_replaced
    return text, count


def iter_definition_items(elem):
    '''Collect dt/dd pairs, including those wrapped in div/section.'''
    items = []
    for child in elem:
        name = local_name(getattr(child, 'tag', None))
        if name in ('dt', 'dd'):
            items.append((name, child))
        elif name in ('div', 'section'):
            items.extend(iter_definition_items(child))
    return items


def render_definition_list(pairs):
    '''pairs: iterable of (term_or_none, definition). Multiple terms can precede one def.'''
    lines = []
    pending_terms = []
    for kind, text in pairs:
        text = (text or '').strip()
        if kind == 'dt':
            if text:
                pending_terms.append(text)
            continue
        if kind != 'dd':
            continue
        if not pending_terms:
            pending_terms = ['']
        for term in pending_terms:
            lines.append('%s\n' % term)
        lines.append(': %s\n\n' % text)
        pending_terms = []
    if not lines:
        return ''
    return '\n' + ''.join(lines)
