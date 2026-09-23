# -*- coding: utf-8 -*-
# Calibre-free helpers for Markdown export (tables, TOC, YAML, images).

from __future__ import print_function

import os
import re
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
_QUOTE_LINE_RE = re.compile(r'^ {0,3}>')


def _following_content_lines(lines):
    '''For every line, the next line that has content (None past the end).'''
    following = [None] * len(lines)
    next_line = None
    for index in range(len(lines) - 1, -1, -1):
        following[index] = next_line
        if lines[index].strip():
            next_line = lines[index]
    return following


def _ends_a_quote_block(previous, following):
    '''True for the blank line that ends a quote block.

    'single' style drops the blank lines between paragraphs, but the one
    after a quote block is not a paragraph separation: a quote is read up to
    the next blank line, so without it the line that follows is swallowed
    into the quote as a lazy continuation line. Only a line outside a quote
    needs the protection - at the end of the text there is nothing to keep
    apart from the quote.
    '''
    return bool(following) and bool(_QUOTE_LINE_RE.match(previous)) \
        and not _QUOTE_LINE_RE.match(following)


def apply_paragraph_style(text, style=PARAGRAPH_STYLE_BLOCK,
                          blank_line_before_heading=False):
    '''Reshape paragraph separation in the finished Markdown.

    'block' (default) keeps the standard Markdown layout where a blank line
    separates paragraphs. 'single' drops blank lines so every content line
    stands as its own paragraph line; the blank line that ends a quote block
    is kept - it is what ends the quote, not a paragraph separation - and
    blank lines inside a fenced code block are content and are preserved.
    With blank_line_before_heading a blank line is (re)inserted before ATX
    headings - except a heading that is the very first line of the file.
    '''
    if not text or style != PARAGRAPH_STYLE_SINGLE:
        return text
    lines = text.splitlines()
    following = _following_content_lines(lines)
    kept = []
    fence = ''
    previous = ''
    for index, line in enumerate(lines):
        marker = _FENCE_MARKER_RE.match(line)
        if marker:
            char = marker.group(1)[0]
            if not fence:
                fence = char
            elif char == fence:
                fence = ''
        if not fence and not line.strip():
            if _ends_a_quote_block(previous, following[index]):
                kept.append(line)
            continue
        if (blank_line_before_heading and not fence and kept
                and kept[-1].strip() and _HEADING_LINE_RE.match(line)):
            kept.append('')
        kept.append(line)
        if line.strip():
            previous = line
    return '\n'.join(kept) + '\n'


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
