# -*- coding: utf-8 -*-
# Enhanced MarkdownMLizer for the Markdown Output calibre plugin.
# Based on calibre upstream markdownml.py (master, 2025).

import numbers
import os
import re
from urllib.parse import unquote

from calibre.ebooks.oeb.base import XHTML_NS, barename, namespace
from calibre.ebooks.txt.markdownml import MarkdownMLizer

from calibre_plugins.markdown.utils.helpers import (
    DEFAULT_IMAGE_DIR,
    alignment_separator,
    apply_paragraph_style,
    cell_alignment,
    clean_invisible_chars,
    extract_code_language,
    find_table_caption,
    html_image_tag,
    image_size_attrs,
    is_titlepage_href,
    iter_definition_items,
    iter_table_rows,
    local_name,
    metadata_text_values,
    render_toc_block,
    render_yaml_front_matter,
    strip_pdf_page_marker_lines,
    unique_slug,
    yaml_fields_from_metadata,
)

USE_FENCED_CODE_BLOCKS = True

#: The characters calibre's MarkdownMLizer escapes in body text. The set is
#: mirrored here (instead of calling the inherited method) so that switching
#: the escape option on reproduces the historical output exactly.
MARKDOWN_ESCAPE_RE = re.compile(r'([\\`*_{}\[\]()#+!])')
MARKDOWN_UNESCAPE_RE = re.compile(r'\\([\\`*_{}\[\]()#+!])')

#: Tags whose own rendering opens a new line. A <blockquote> that starts with
#: one of these must not write the quote prefix itself: the child writes it
#: (or, for <hr> and friends, starts its own line regardless), and writing it
#: on both levels leaves a bare "> " line above the quote. Inline children
#: (text, <a>, <img>, <em>, ...) do need the prefix written for them.
BLOCK_LEVEL_TAGS = frozenset((
    'blockquote', 'div', 'dl', 'figure', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'hr', 'li', 'ol', 'p', 'pre', 'table', 'ul',
))


def _ends_with_blank_line(text):
    """True when the collected text already ends with a blank line."""
    return ''.join(text[-2:]).endswith('\n\n')


def _css_margin_break(style, side):
    '''Blank lines a top/bottom CSS margin asks for, as calibre upstream.

    Mirrors MarkdownMLizer.dump_text's "soft scene breaks" so replacing the
    inherited blockquote branch does not silently drop them; anything the
    arithmetic cannot make sense of yields no break instead of an exception.
    '''
    key = 'margin-%s' % side
    if key not in style.cssdict() or style[key] == 'auto':
        return ''
    try:
        ems = int(round(float(getattr(style, 'margin' + side.capitalize()))
                        / style.fontSize) - 1)
    except (TypeError, ValueError, ZeroDivisionError):
        return ''
    return '\n\n' * ems if ems >= 1 else ''


#: A margin length the renderer can read as a number: a bare number with an
#: optional CSS unit, or one of the keywords a margin may carry instead. Every
#: other value calibre's unit_convert() returns unchanged, and the renderer's
#: soft-scene-break code then calls float() on that string.
_CSS_LENGTH_RE = re.compile(
    r'^-?(?:\d+\.?\d*|\.\d+)(?:%|em|rem|ex|en|px|pt|pc|in|mm|cm|q)?$', re.I)
_MARGIN_KEYWORDS = frozenset(('auto', 'inherit', 'initial', 'unset'))

#: The margins the renderer reads as lengths (the left/right ones are not).
MARGIN_LENGTH_KEYS = ('margin-top', 'margin-bottom')


def _is_readable_length(value):
    if isinstance(value, numbers.Number):
        return True
    if value is None:
        return False
    text = str(value).strip()
    if text.lower() in _MARGIN_KEYWORDS:
        return True
    return bool(_CSS_LENGTH_RE.match(text))


def repair_margin_lengths(style):
    '''Read the margins this style declares unreadably as 0, and say which.

    calibre expands the `margin` shorthand itself, so a typo like
    `margin: -2em 0 olid #20F2f0` arrives here as `margin-bottom: olid`.
    unit_convert() hands a value it cannot read back unchanged and the
    renderer's soft-scene-break code then calls float() on it, which aborts the
    whole conversion - the book never exports. Such a margin is the book's own
    typo, so it is read as "no margin": upstream then computes a negative em
    count and writes no break, which keeps the export honest instead of
    inventing a length.
    '''
    getter = getattr(style, 'get', None)
    setter = getattr(style, 'set', None)
    if getter is None or setter is None:
        return []
    repaired = []
    for key in MARGIN_LENGTH_KEYS:
        value = getter(key)
        if value is None or _is_readable_length(value):
            continue
        repaired.append((key, value))
        setter(key, '0')
    return repaired


def margin_repair_summary(repaired):
    '''The single log line a book with unreadable margins leaves behind.'''
    values = sorted({str(value) for _, value in repaired})
    return ('Markdown: read %s unreadable CSS margin value(s) as 0 (%s). '
            'The book declares margins calibre cannot parse, a shorthand '
            'typo for example.' % (len(repaired), ', '.join(values)))


class EnhancedMarkdownMLizer(MarkdownMLizer):

    def extract_content(self, oeb_book, opts):
        self.log.info('Converting XHTML to enhanced Markdown formatted TXT...')
        self.opts = opts
        self.oeb_book = oeb_book
        self.in_code = False
        self.in_pre = False
        self.list = []
        self.blockquotes = 0
        self.remove_space_after_newline = False
        self._in_table_cell = False
        self._in_figure = False
        self._fenced_pre = False
        self.style_strike = False
        self.toc_entries = []
        self._heading_slugs = set()
        self.base_hrefs = [item.href for item in oeb_book.spine]
        self.map_resources(oeb_book)

        self.style_bold = False
        self.style_italic = False
        self._footnote_refs = {}
        self._footnote_defs = {}
        self._footnote_order = []
        self._footnote_label_counter = 1
        self._repaired_margins = []

        self.create_toc_entries(getattr(oeb_book, 'toc', None) or [])
        body = self.mlize_spine(oeb_book) + self._render_footnotes()
        if self._repaired_margins:
            self.log.info(margin_repair_summary(self._repaired_margins))
        body = self.tidy_up(body)
        body = clean_invisible_chars(body)
        if getattr(self.opts, 'strip_pdf_page_markers', False):
            body = strip_pdf_page_marker_lines(body)
        body = self.apply_max_line_length(body)
        return apply_paragraph_style(
            clean_invisible_chars(self.get_front_matter(oeb_book))
            + self._cover_markdown(oeb_book)
            + self.get_toc()
            + body,
            getattr(self.opts, 'paragraph_style', None) or 'block',
            getattr(self.opts, 'blank_line_before_heading', True),
        )

    def map_resources(self, oeb_book):
        '''Map every image of the book to an images/<nnnnnn>.<ext> name.

        calibre's map_resources maps only the media types its OEB_IMAGES set
        lists (gif/jpeg/png/svg); an image declared as anything else - webp,
        which calibre keeps in a separate "raster images" set, is the common
        case - keeps its in-EPUB href in the Markdown, a reference the .md
        cannot resolve, and is never part of the image export. Those remaining
        image types are mapped here, after calibre's own pass, so the names it
        already handed out (and the cover lookup reading them) stay the same.
        '''
        super().map_resources(oeb_book)
        self._map_remaining_images(oeb_book)

    def _map_remaining_images(self, oeb_book):
        '''Extend the mapping with the image media types calibre skipped.'''
        from operator import attrgetter

        def is_image(item):
            return str(getattr(item, 'media_type', '') or '') \
                .lower().startswith('image/')

        manifest = getattr(oeb_book, 'manifest', None) or []
        remaining = sorted(
            (item for item in manifest
             if getattr(item, 'href', None) and is_image(item)
             and item.href not in self.images),
            key=attrgetter('href'))
        for item in remaining:
            ext = os.path.splitext(item.href)[1]
            self.images[item.href] = '%06d%s' % (len(self.images), ext)
        if remaining:
            self.log.info(
                'Markdown: mapped %s image(s) calibre does not map (%s).'
                % (len(remaining), ', '.join(sorted({
                    os.path.splitext(item.href)[1].lower()
                    for item in remaining}))))

    def mlize_spine(self, oeb_book):
        if getattr(self.opts, 'export_cover_page', True):
            return super().mlize_spine(oeb_book)
        kept = [item for item in oeb_book.spine
                if not is_titlepage_href(getattr(item, 'href', None))]
        skipped = len(list(oeb_book.spine)) - len(kept)
        if skipped:
            self.log.info('Markdown: skipped %s cover page(s).' % skipped)
        original = oeb_book.spine
        try:
            # Upstream only iterates the spine; swap in the filtered list for
            # the duration of the call and restore it for later stages (e.g.
            # the cover lookup in _cover_markdown).
            oeb_book.spine = kept
            return super().mlize_spine(oeb_book)
        finally:
            oeb_book.spine = original

    def create_toc_entries(self, nodes, depth=0):
        for item in nodes or []:
            title = (getattr(item, 'title', None) or '').strip()
            if title:
                self.toc_entries.append((depth, title))
            self.create_toc_entries(getattr(item, 'nodes', None) or [], depth + 1)

    def _toc_heading(self):
        try:
            from calibre_plugins.markdown.translations.ui_language import (
                UI_LANG_ZH_CN,
                get_ui_language,
            )
            if get_ui_language() == UI_LANG_ZH_CN:
                return '目录'
        except Exception:
            pass
        return 'Table of Contents'

    def get_toc(self):
        if not getattr(self.opts, 'inline_toc', None) or not self.toc_entries:
            return ''
        return render_toc_block(self.toc_entries, self._toc_heading())

    def get_front_matter(self, oeb_book):
        if not getattr(self.opts, 'yaml_front_matter', True):
            return ''
        metadata = getattr(oeb_book, 'metadata', None)
        oeb_fields = {}
        if metadata is not None:
            titles = metadata_text_values(getattr(metadata, 'title', None))
            if titles:
                oeb_fields['title'] = titles[0]
            authors = metadata_text_values(getattr(metadata, 'creator', None))
            if authors:
                oeb_fields['authors'] = authors
            languages = metadata_text_values(getattr(metadata, 'language', None))
            if languages:
                oeb_fields['language'] = languages[0]
            publishers = metadata_text_values(getattr(metadata, 'publisher', None))
            if publishers:
                oeb_fields['publisher'] = publishers[0]
            tags = metadata_text_values(getattr(metadata, 'subject', None))
            if tags:
                oeb_fields['tags'] = tags
        library_meta = getattr(self.opts, 'library_metadata', None) or {}
        return render_yaml_front_matter(
            yaml_fields_from_metadata(library_meta, oeb_fields))

    def _find_cover_href(self, oeb_book):
        guide = getattr(oeb_book, 'guide', None)
        if guide is not None:
            try:
                item = guide.get('cover')
            except Exception:
                item = None
            if item is not None:
                href = getattr(item, 'href', None)
                if href:
                    return href
        metadata = getattr(oeb_book, 'metadata', None)
        covers = metadata_text_values(getattr(metadata, 'cover', None)) if metadata else []
        manifest = getattr(oeb_book, 'manifest', None)
        if not covers or manifest is None:
            return None
        cover_id = covers[0]
        for item in manifest:
            item_id = getattr(item, 'id', None) or ''
            if item_id == cover_id or getattr(item, 'href', None) == cover_id:
                return item.href
        return None

    def _cover_markdown(self, oeb_book):
        if not getattr(self.opts, 'export_cover_page', True):
            return ''
        if not getattr(self.opts, 'keep_image_references', True):
            return ''
        href = self._find_cover_href(oeb_book)
        if not href:
            return ''
        spine_hrefs = [item.href for item in oeb_book.spine]
        if href in spine_hrefs:
            return ''
        mapped = (getattr(self, 'images', None) or {}).get(href)
        if not mapped:
            return ''
        return '![Cover](%s/%s)\n\n' % (DEFAULT_IMAGE_DIR, mapped)

    def apply_max_line_length(self, text):
        max_length = int(getattr(self.opts, 'max_line_length', 0) or 0)
        if not max_length:
            return text
        if max_length < 25 and not getattr(self.opts, 'force_max_line_length', False):
            max_length = 25
        force = getattr(self.opts, 'force_max_line_length', False)
        short_lines = []
        for line in text.splitlines():
            while len(line) > max_length:
                space = line.rfind(' ', 0, max_length)
                if space != -1:
                    short_lines.append(line[:space])
                    line = line[space + 1:]
                elif force:
                    short_lines.append(line[:max_length])
                    line = line[max_length:]
                else:
                    space = line.find(' ', max_length, len(line))
                    if space != -1:
                        short_lines.append(line[:space])
                        line = line[space + 1:]
                    else:
                        short_lines.append(line)
                        line = ''
                        break
            short_lines.append(line)
        return '\n'.join(short_lines)

    def _escaping_enabled(self):
        return bool(getattr(self.opts, 'escape_markdown_chars', False))

    def prepare_string_for_markdown(self, txt):
        '''Escape the Markdown special characters, unless the user opted out.

        calibre's MarkdownMLizer always escapes, which turns chapter titles
        like `第1卷 原版(By:苏梦枕)` into `第1卷 原版\\(By:苏梦枕\\)` and author
        lists full of `+` into `\\+`. With the option off (the default) the
        text is written as it is; the trade-off is that re-rendering the file
        as Markdown may read those characters as formatting. Every caller in
        this class funnels through here, so the switch covers the body, the
        headings, the TOC-less front matter and the tails alike.
        '''
        if not self._escaping_enabled():
            return txt
        return MARKDOWN_ESCAPE_RE.sub(r'\\\1', txt)

    def _plain_heading_text(self, title):
        '''The heading text a {#slug} anchor is derived from.

        Only escaping this module added may be undone: with the option off
        there is nothing to undo and a backslash in the heading is literal.
        Both modes therefore yield the same slug for the same book.
        '''
        if not self._escaping_enabled():
            return title
        return MARKDOWN_UNESCAPE_RE.sub(r'\1', title)

    def prepare_string_for_table_cell(self, txt):
        txt = txt.replace('\n', ' ').strip()
        txt = re.sub(r'[ ]{2,}', ' ', txt)
        txt = txt.replace('|', '\\|')
        return txt

    def _should_keep_link(self, href):
        if not href or href.startswith('javascript:'):
            return False
        return True

    def _format_fragment(self, txt):
        if txt is None:
            return ''
        if self.in_pre:
            return self.prepare_string_for_pre(txt)
        if self.in_code:
            return self.remove_newlines(txt)
        return self.prepare_string_for_markdown(self.remove_newlines(txt))

    def _tail_fragment(self, elem):
        if hasattr(elem, 'tail') and elem.tail:
            return self._format_fragment(elem.tail)
        return ''

    def _contains_token(self, text, token):
        if not text:
            return False
        return token in set(part.strip().lower() for part in text.split())

    def _looks_like_external_href(self, href):
        if not href:
            return False
        return bool(re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:', href) or href.startswith('//'))

    def _looks_like_internal_href(self, href):
        return bool(href) and not self._looks_like_external_href(href)

    def _sanitize_wikilink_target(self, value):
        cleaned = (value or '').replace('\n', ' ').strip()
        cleaned = re.sub(r'\s+', ' ', cleaned)
        cleaned = cleaned.replace('[', '').replace(']', '')
        cleaned = cleaned.replace('|', '-')
        return cleaned.strip()

    def _wikilink_target_from_href(self, href):
        href = (href or '').strip()
        if not href:
            return ''
        if '#' in href:
            path_part, anchor = href.split('#', 1)
        else:
            path_part, anchor = href, ''
        path_part = unquote(path_part.split('?', 1)[0]).strip()
        anchor = unquote(anchor.split('?', 1)[0]).strip()
        if path_part:
            base = os.path.basename(path_part)
            stem, _ext = os.path.splitext(base)
            if stem:
                return self._sanitize_wikilink_target(stem)
        if anchor:
            return self._sanitize_wikilink_target(anchor)
        return ''

    def _looks_like_footnote_id(self, value):
        return bool(re.match(r'^(?:fn|footnote|note)[-_:\d\w]*$', (value or '').lower()))

    def _extract_footnote_target(self, href):
        if not href or not href.startswith('#'):
            return ''
        return href[1:].strip()

    def _is_footnote_reference(self, elem, href):
        target = self._extract_footnote_target(href)
        if not target:
            return False
        attrs = elem.attrib
        cls = attrs.get('class', '')
        role = attrs.get('role', '')
        epub_type = attrs.get('epub:type', '') + ' ' + attrs.get('{http://www.idpf.org/2007/ops}type', '')
        if self._contains_token(cls, 'noteref') or self._contains_token(cls, 'footnote-ref'):
            return True
        if role == 'doc-noteref':
            return True
        if self._contains_token(epub_type, 'noteref'):
            return True
        return self._looks_like_footnote_id(target)

    def _is_footnote_backlink(self, elem):
        if not isinstance(elem.tag, (str, bytes)) or barename(elem.tag) != 'a':
            return False
        href = (elem.attrib.get('href') or '').lower()
        cls = elem.attrib.get('class', '').lower()
        role = (elem.attrib.get('role') or '').lower()
        if href.startswith('#fnref') or href.startswith('#footnote-ref'):
            return True
        if 'backref' in cls or 'footnote-back' in cls:
            return True
        return role == 'doc-backlink'

    def _next_available_footnote_label(self):
        while True:
            label = str(self._footnote_label_counter)
            self._footnote_label_counter += 1
            if label not in self._footnote_order:
                return label

    def _footnote_label_for_target(self, target):
        target = (target or '').strip()
        if not target:
            return ''
        if target in self._footnote_refs:
            return self._footnote_refs[target]

        label = ''
        digits = re.search(r'(\d+)$', target)
        if digits:
            candidate = digits.group(1)
            if candidate not in self._footnote_order:
                label = candidate
        if not label:
            label = self._next_available_footnote_label()

        self._footnote_refs[target] = label
        if label not in self._footnote_order:
            self._footnote_order.append(label)
        return label

    def _collect_element_text_parts(self, elem, stylizer):
        text = []
        if hasattr(elem, 'text') and elem.text:
            text.append(self._format_fragment(elem.text))
        for item in elem:
            text += self.dump_text(item, stylizer)
        return text

    def _collect_footnote_definition(self, elem, stylizer):
        parts = []
        if hasattr(elem, 'text') and elem.text:
            parts.append(self._format_fragment(elem.text))
        for item in elem:
            if self._is_footnote_backlink(item):
                if hasattr(item, 'tail') and item.tail:
                    parts.append(self._format_fragment(item.tail))
                continue
            parts += self.dump_text(item, stylizer)
        text = ''.join(parts)
        text = re.sub(r'\s+', ' ', text).strip()
        text = re.sub(r'^\[\^[^\]]+\]:?\s*', '', text)
        return text

    def _capture_footnote_definition(self, elem, stylizer):
        element_id = (elem.attrib.get('id') or '').strip()
        if not element_id:
            return False
        cls = elem.attrib.get('class', '')
        role = elem.attrib.get('role', '')
        epub_type = elem.attrib.get('epub:type', '') + ' ' + elem.attrib.get('{http://www.idpf.org/2007/ops}type', '')
        is_definition = (
            element_id in self._footnote_refs
            or self._looks_like_footnote_id(element_id)
            or self._contains_token(cls, 'footnote')
            or role == 'doc-footnote'
            or self._contains_token(epub_type, 'footnote')
        )
        if not is_definition:
            return False

        label = self._footnote_label_for_target(element_id)
        definition = self._collect_footnote_definition(elem, stylizer)
        if definition:
            self._footnote_defs[label] = definition
        return True

    def _render_footnotes(self):
        if not self._footnote_defs:
            return ''
        labels = list(self._footnote_order)
        for label in sorted(self._footnote_defs.keys()):
            if label not in labels:
                labels.append(label)
        lines = ['\n']
        has_any = False
        for label in labels:
            definition = self._footnote_defs.get(label)
            if not definition:
                continue
            lines.append('[^%s]: %s\n' % (label, definition))
            has_any = True
        if not has_any:
            return ''
        lines.append('\n')
        return ''.join(lines)

    def _cell_alignment(self, cell, stylizer):
        style_align = ''
        try:
            style_align = stylizer.style(cell).get('text-align') or ''
        except Exception:
            style_align = ''
        return cell_alignment(cell, style_align)

    def _render_table(self, elem, stylizer):
        caption_elem = find_table_caption(elem)
        caption_text = ''
        if caption_elem is not None:
            caption_text = self.prepare_string_for_table_cell(
                ''.join(self._collect_element_text_parts(caption_elem, stylizer)))

        rows = []
        for child in iter_table_rows(elem):
            row = []
            for cell in child:
                if not isinstance(getattr(cell, 'tag', None), (str, bytes)):
                    continue
                ct = local_name(cell.tag)
                if ct not in ('td', 'th'):
                    continue
                self._in_table_cell = True
                parts = self.dump_text(cell, stylizer)
                self._in_table_cell = False
                cell_text = self.prepare_string_for_table_cell(''.join(parts))
                row.append((ct == 'th', cell_text, self._cell_alignment(cell, stylizer)))
            if row:
                rows.append(row)
        if not rows:
            return ['']
        lines = ['\n']
        if caption_text:
            lines.append('*%s*\n\n' % caption_text)
        for index, row in enumerate(rows):
            cells = [text for _, text, _ in row]
            lines.append('| ' + ' | '.join(cells) + ' |\n')
            if index == 0:
                seps = [align or alignment_separator('') for _, _, align in row]
                lines.append('| ' + ' | '.join(seps) + ' |\n')
        lines.append('\n')
        result = lines
        if hasattr(elem, 'tail') and elem.tail:
            result.append(self.prepare_string_for_markdown(
                self.remove_newlines(elem.tail)))
        return result

    def _wrap_delimiters(self, elem, stylizer, open_delim, close_delim):
        text = [open_delim]
        if hasattr(elem, 'text') and elem.text:
            text.append(self.prepare_string_for_markdown(
                self.remove_newlines(elem.text)))
        for item in elem:
            text += self.dump_text(item, stylizer)
        text.append(close_delim)
        if hasattr(elem, 'tail') and elem.tail:
            text.append(self.prepare_string_for_markdown(
                self.remove_newlines(elem.tail)))
        return text

    def _wrap_html_tag(self, elem, stylizer, html_tag):
        text = ['<%s>' % html_tag]
        if hasattr(elem, 'text') and elem.text:
            text.append(self.remove_newlines(elem.text))
        for item in elem:
            text += self.dump_text(item, stylizer)
        text.append('</%s>' % html_tag)
        if hasattr(elem, 'tail') and elem.tail:
            text.append(self.prepare_string_for_markdown(
                self.remove_newlines(elem.tail)))
        return text

    def _code_language_from(self, *elems):
        sources = []
        for elem in elems:
            if elem is None:
                continue
            attribs = getattr(elem, 'attrib', None) or {}
            sources.extend((
                attribs.get('class'),
                attribs.get('data-lang'),
                attribs.get('data-language'),
                attribs.get('data-brush'),
            ))
        return extract_code_language(*sources)

    def _dump_fenced_pre(self, elem, stylizer):
        lang = self._code_language_from(elem)
        text_chunks = []
        if hasattr(elem, 'text') and elem.text:
            text_chunks.append(elem.text)
        for item in elem:
            if isinstance(item.tag, (str, bytes)) and barename(item.tag) == 'code':
                lang = lang or self._code_language_from(item)
                if hasattr(item, 'text') and item.text:
                    text_chunks.append(item.text)
                for sub in item:
                    text_chunks += self.dump_text(sub, stylizer)
                if hasattr(item, 'tail') and item.tail:
                    text_chunks.append(item.tail)
            else:
                text_chunks += self.dump_text(item, stylizer)
        fence = '\n```%s\n' % lang if lang else '\n```\n'
        text = [fence]
        text.extend(text_chunks)
        text.append('\n```\n')
        if hasattr(elem, 'tail') and elem.tail:
            text.append(self.prepare_string_for_markdown(
                self.remove_newlines(elem.tail)))
        return text

    def _dump_definition_list(self, elem, stylizer):
        pairs = []
        for kind, child in iter_definition_items(elem):
            text = self.prepare_string_for_table_cell(
                ''.join(self._collect_element_text_parts(child, stylizer)))
            pairs.append((kind, text))
        rendered = []
        pending_terms = []
        for kind, text in pairs:
            if kind == 'dt':
                if text:
                    pending_terms.append(text)
                continue
            if not pending_terms:
                pending_terms = ['']
            for term in pending_terms:
                rendered.append('%s\n' % term)
            rendered.append(': %s\n\n' % text)
            pending_terms = []
        if not rendered:
            result = ['']
        else:
            result = ['\n'] + rendered
        if hasattr(elem, 'tail') and elem.tail:
            result.append(self.prepare_string_for_markdown(
                self.remove_newlines(elem.tail)))
        return result

    def _starts_with_block(self, elem):
        '''True when the first content of elem is a block level child.

        Such a child opens its own line (and writes the quote prefix itself),
        so the parent must not write another one; text and inline children
        need the prefix written for them.
        '''
        if elem.text and elem.text.strip():
            return False
        for item in elem:
            if not isinstance(getattr(item, 'tag', None), (str, bytes)):
                continue
            return local_name(item.tag) in BLOCK_LEVEL_TAGS
        return False

    def _dump_blockquote(self, elem, stylizer):
        '''Render <blockquote> as a Markdown quote whose lines start "> ".

        Upstream calibre writes the "> " prefix twice - once for the quote
        itself and again at the start of every block level child - so a quoted
        paragraph always arrives with a bare "> " line of its own. It also
        wraps the quote in "*"/"**" when the book styles it italic or bold;
        those delimiters cannot span the quote's block children, and a line
        starting with "*" reads as a list bullet, so the quote came out as
        "*> " plus a lone "*" line.

        The prefix is written once - by the first block level child when there
        is one, otherwise by this method for the text and inline content that
        follows - and the styling is written around the text itself, giving
        "> *quote*".

        A quote is ended by a blank line, and only by one: a bare ">" line
        does not end it (the reader takes the quote up to the next blank
        line, so the line after such a close comes back swallowed into the
        quote as a lazy continuation line). The blank line that ends the
        quote is the leading newline of the block that follows; text that
        follows the quote directly - its tail - gets one written for it here.
        '''
        style = stylizer.style(elem)
        outer_italic = self.style_italic
        outer_bold = self.style_bold

        self.blockquotes += 1
        try:
            text = []
            top = _css_margin_break(style, 'top')
            if top:
                text.append(top)
            delimiters = []
            if not self._starts_with_block(elem):
                text.append('\n' + '> ' * self.blockquotes)
                # Text and inline children have no element of their own to
                # carry the inherited styling, so it is written here. Block
                # children do have one and write it themselves - the flags
                # stay untouched for them.
                if style['font-style'] == 'italic' and not self.style_italic:
                    self.style_italic = True
                    text.append('*')
                    delimiters.append('*')
                if style['font-weight'] in ('bold', 'bolder') \
                        and not self.style_bold:
                    self.style_bold = True
                    text.append('**')
                    delimiters.append('**')
                raw_text = elem.text or ''
                direct = raw_text.strip()
                if direct:
                    text.append(self._format_fragment(direct))
                    # A trailing space that separated the text from an inline
                    # sibling is content, not formatting.
                    if raw_text[-1:].isspace() and len(elem):
                        text.append(' ')
            for item in elem:
                text += self.dump_text(item, stylizer)
            text.extend(reversed(delimiters))
            # Children leave whitespace behind (the tail of the last paragraph
            # is written as a space): drop it so the quote ends on its last
            # line of text. Line breaks stay - they are what puts the content
            # that follows on a line of its own.
            while text and not text[-1].strip() and '\n' not in text[-1]:
                text.pop()
            if text and not text[-1].endswith('\n'):
                text.append('\n')
            bottom = _css_margin_break(style, 'bottom')
            if bottom:
                text.append(bottom)
            tail = self._tail_fragment(elem)
            if tail and tail.strip():
                # The blank line that ends a quote otherwise comes from the
                # leading newline of the block after it; text that follows the
                # quote directly has no such newline, and without a blank line
                # it is read as a lazy continuation line of the quote. The
                # tail starts a line of its own, so the whitespace it carries
                # (the newlines around </blockquote>) is not content.
                if not _ends_with_blank_line(text):
                    text.append('\n')
                text.append(tail.strip())
            return text
        finally:
            self.blockquotes -= 1
            self.style_italic = outer_italic
            self.style_bold = outer_bold

    def _dump_figure(self, elem, stylizer):
        previous = self._in_figure
        self._in_figure = True
        try:
            parts = []
            if hasattr(elem, 'text') and elem.text and elem.text.strip():
                parts.append(self.prepare_string_for_markdown(
                    self.remove_newlines(elem.text)))
            caption = ''
            for item in elem:
                tag = ''
                if isinstance(getattr(item, 'tag', None), (str, bytes)):
                    tag = barename(item.tag)
                if tag == 'figcaption':
                    caption = ''.join(
                        self._collect_element_text_parts(item, stylizer)).strip()
                    continue
                parts += self.dump_text(item, stylizer)
            text = ['\n']
            text.extend(parts)
            rendered = ''.join(text)
            if caption:
                if rendered and not rendered.endswith('\n'):
                    text.append('\n')
                text.append('*%s*\n' % caption)
            text.append('\n')
            tail = self._tail_fragment(elem)
            if tail:
                text.append(tail)
            return text
        finally:
            self._in_figure = previous

    def _dump_heading(self, elem, stylizer, tag):
        level = int(tag[1])
        bq = '> ' * self.blockquotes
        parts = self._collect_element_text_parts(elem, stylizer)
        title = ''.join(parts).strip()
        title = re.sub(r'\s*\{#[^}]+\}\s*$', '', title).strip()
        plain = self._plain_heading_text(title)
        slug = ''
        if getattr(self.opts, 'heading_anchors', True) and plain:
            slug = unique_slug(plain, self._heading_slugs)
        text = ['\n', bq, '#' * level, ' ']
        if title:
            text.append(title)
        if slug:
            text.append(' {#%s}' % slug)
        text.append('\n')
        tail = self._tail_fragment(elem)
        if tail:
            text.append(tail)
        return text

    def _dump_link(self, elem, stylizer):
        attribs = elem.attrib
        href = attribs.get('href', '')
        if not (self.opts.keep_links and self._should_keep_link(href)):
            text = self._collect_element_text_parts(elem, stylizer)
            tail = self._tail_fragment(elem)
            if tail:
                text.append(tail)
            return text

        if self._is_footnote_reference(elem, href):
            label = self._footnote_label_for_target(self._extract_footnote_target(href))
            text = ['[^%s]' % label]
            tail = self._tail_fragment(elem)
            if tail:
                text.append(tail)
            return text

        link_parts = self._collect_element_text_parts(elem, stylizer)
        link_text = self._sanitize_wikilink_target(''.join(link_parts))

        if self._looks_like_internal_href(href):
            target = link_text or self._wikilink_target_from_href(href)
            if target:
                text = ['[[%s]]' % target]
                tail = self._tail_fragment(elem)
                if tail:
                    text.append(tail)
                return text

        title = ''
        if 'title' in attribs:
            remove_space = self.remove_space_after_newline
            title = ' "' + self.remove_newlines(attribs['title']) + '"'
            self.remove_space_after_newline = remove_space

        text = ['['] + link_parts + ['](' + href + title + ')']
        tail = self._tail_fragment(elem)
        if tail:
            text.append(tail)
        return text

    def _extract_task_checkbox(self, elem):
        text = getattr(elem, 'text', '') or ''
        match = re.match(r'^\s*\[(?P<state>[ xX])\]\s*', text)
        if match:
            marker = '[x] ' if match.group('state').lower() == 'x' else '[ ] '
            return marker, text[match.end():], None

        for idx, item in enumerate(elem):
            if not isinstance(item.tag, (str, bytes)) or barename(item.tag) != 'input':
                continue
            input_type = (item.attrib.get('type') or '').lower()
            if input_type != 'checkbox':
                continue
            checked_attr = item.attrib.get('checked')
            aria_checked = (item.attrib.get('aria-checked') or '').lower()
            is_checked = (
                checked_attr is not None
                or aria_checked in ('true', 'mixed')
                or (item.attrib.get('value') or '').lower() == 'true'
            )
            marker = '[x] ' if is_checked else '[ ] '
            return marker, text, idx
        return '', text, None

    def _dump_list_item(self, elem, stylizer):
        text = []
        style = stylizer.style(elem)
        tags = []
        tag = barename(elem.tag)

        if style['display'] in ('none', 'oeb-page-head', 'oeb-page-foot') \
                or style['visibility'] == 'hidden':
            if hasattr(elem, 'tail') and elem.tail:
                return [elem.tail]
            return ['']

        bq = '> ' * self.blockquotes
        if self.list:
            li = self.list[-1]
        else:
            li = {'name': 'ul', 'num': 0}

        text.append('\n')
        list_count = len(self.list)
        if (list_count - 1) > 0:
            text.append('\t' * (list_count - 1))
        text.append(bq)
        if li['name'] == 'ul':
            text.append('- ')
        elif li['name'] == 'ol':
            li['num'] += 1
            text.append(str(li['num']) + '. ')

        if style['font-style'] == 'italic' or tag in ('i', 'em'):
            if self.style_italic is False:
                text.append('*')
                tags.append('*')
                self.style_italic = True
        if style['font-weight'] in ('bold', 'bolder') or tag in ('b', 'strong'):
            if self.style_bold is False:
                text.append('**')
                tags.append('**')
                self.style_bold = True

        task_marker, first_text, skip_item_idx = self._extract_task_checkbox(elem)
        if task_marker:
            text.append(task_marker)

        if first_text:
            txt = self._format_fragment(first_text)
            text.append(txt)

        for idx, item in enumerate(elem):
            if skip_item_idx is not None and idx == skip_item_idx:
                tail = self._tail_fragment(item)
                if tail:
                    text.append(tail)
                continue
            text += self.dump_text(item, stylizer)

        tags.reverse()
        for t in tags:
            if t == '**':
                self.style_bold = False
            elif t == '*':
                self.style_italic = False
            text.append(t)

        tail = self._tail_fragment(elem)
        if tail:
            text.append(tail)

        return text

    def _dump_inline_block(self, elem, stylizer):
        text = []
        if hasattr(elem, 'text') and elem.text:
            text.append(self.prepare_string_for_markdown(
                self.remove_newlines(elem.text)))
        for item in elem:
            text += self.dump_text(item, stylizer)
        if hasattr(elem, 'tail') and elem.tail:
            text.append(self.prepare_string_for_markdown(
                self.remove_newlines(elem.tail)))
        return text

    def _html_image(self, elem, style):
        '''Render an <img> whose book declares a width/height, or None.

        ![alt](src) cannot carry the size a book sets through width/height
        attributes or CSS (width: 80%, height: auto, ...), so those images are
        written as raw HTML instead - the width/height survive into the output
        and back through the Markdown input side. Images without a declared
        size go to _markdown_image(), and everything outside "keep image
        references" stays with the upstream Markdown rendering.
        '''
        if not getattr(self.opts, 'keep_image_references', True):
            return None
        if not getattr(self.opts, 'keep_image_sizes', True):
            return None
        attribs = elem.attrib
        src = attribs.get('src')
        if not src:
            return None
        size = image_size_attrs(attribs, style)
        if size is None:
            return None
        text = [html_image_tag(
            src,
            alt=self.remove_newlines(attribs.get('alt', '') or ''),
            title=self.remove_newlines(attribs.get('title', '') or ''),
            size=size,
        )]
        tail = self._tail_fragment(elem)
        if tail:
            text.append(tail)
        return text

    def _markdown_image(self, elem):
        '''Render an <img> without a declared size as ![alt](src), or None.

        calibre's own branch - the one this replaces - writes the [] only when
        the element carries an alt attribute, and an <img> without one comes
        out as !(images/000000.jpg): the brackets are missing, so the reader
        sees text where the image should be, the picture is lost in every
        Markdown renderer, and the input side does not read the reference
        back. The brackets are therefore written even when there is no alt
        text to go in them.
        '''
        if not getattr(self.opts, 'keep_image_references', True):
            return None
        src = elem.attrib.get('src')
        if not src:
            return None
        # calibre's remove_newlines() consumes the flag that strips the space
        # a newline leaves behind; the alt text is not a line start, so the
        # state around it must survive.
        saved = getattr(self, 'remove_space_after_newline', False)
        alt = self.remove_newlines(elem.attrib.get('alt', '') or '')
        self.remove_space_after_newline = saved
        text = ['![%s](%s)' % (alt, src)]
        tail = self._tail_fragment(elem)
        if tail:
            text.append(tail)
        return text

    def _repair_margins(self, style):
        '''Read this element's unreadable margins as 0 (repair_margin_lengths).

        Called for every element before anything reads the style: upstream's
        dump_text recurses through this one, so its own unguarded float() of
        the margins only ever sees repaired values.
        '''
        repaired = repair_margin_lengths(style)
        recorded = getattr(self, '_repaired_margins', None)
        if repaired and recorded is not None:
            recorded.extend(repaired)
        return repaired

    def dump_text(self, elem, stylizer):
        if not isinstance(elem.tag, (str, bytes)) \
                or namespace(elem.tag) != XHTML_NS:
            p = elem.getparent()
            if p is not None and isinstance(p.tag, (str, bytes)) \
                    and namespace(p.tag) == XHTML_NS and elem.tail:
                return [elem.tail]
            return ['']

        tag = barename(elem.tag)
        style = stylizer.style(elem)
        self._repair_margins(style)

        if style['display'] in ('none', 'oeb-page-head', 'oeb-page-foot') \
                or style['visibility'] == 'hidden':
            if hasattr(elem, 'tail') and elem.tail:
                return [elem.tail]
            return ['']

        if tag == 'img':
            sized = self._html_image(elem, style)
            if sized is not None:
                return sized
            plain = self._markdown_image(elem)
            if plain is not None:
                return plain

        if tag == 'table' and not self._in_table_cell:
            return self._render_table(elem, stylizer)

        if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            return self._dump_heading(elem, stylizer, tag)

        if tag == 'dl':
            return self._dump_definition_list(elem, stylizer)

        if tag == 'blockquote':
            return self._dump_blockquote(elem, stylizer)

        if tag in ('li', 'div', 'aside', 'section', 'p'):
            if self._capture_footnote_definition(elem, stylizer):
                tail = self._tail_fragment(elem)
                return [tail] if tail else ['']

        if self._in_table_cell and tag in ('p', 'div'):
            return self._dump_inline_block(elem, stylizer)

        if tag in ('del', 's', 'strike'):
            return self._wrap_delimiters(elem, stylizer, '~~', '~~')

        if tag == 'sup':
            return self._wrap_html_tag(elem, stylizer, 'sup')

        if tag == 'sub':
            return self._wrap_html_tag(elem, stylizer, 'sub')

        if tag == 'cite':
            return self._wrap_delimiters(elem, stylizer, '*', '*')

        if tag == 'mark':
            return self._wrap_delimiters(elem, stylizer, '==', '==')

        if tag == 'figure':
            return self._dump_figure(elem, stylizer)

        if tag == 'figcaption' and not self._in_figure:
            return self._wrap_delimiters(elem, stylizer, '*', '*')

        if tag == 'pre' and USE_FENCED_CODE_BLOCKS:
            return self._dump_fenced_pre(elem, stylizer)

        if tag == 'a':
            return self._dump_link(elem, stylizer)

        if tag == 'li':
            return self._dump_list_item(elem, stylizer)

        if style.get('text-decoration') == 'line-through' and tag not in (
                'del', 's', 'strike', 'a'):
            text = ['~~']
            if hasattr(elem, 'text') and elem.text:
                text.append(self.prepare_string_for_markdown(
                    self.remove_newlines(elem.text)))
            for item in elem:
                text += self.dump_text(item, stylizer)
            text.append('~~')
            if hasattr(elem, 'tail') and elem.tail:
                text.append(self.prepare_string_for_markdown(
                    self.remove_newlines(elem.tail)))
            return text

        return super().dump_text(elem, stylizer)
