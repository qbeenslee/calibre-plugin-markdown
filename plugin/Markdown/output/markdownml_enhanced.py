# -*- coding: utf-8 -*-
# Enhanced MarkdownMLizer for the Markdown Output calibre plugin.
# Based on calibre upstream markdownml.py (master, 2025).
#
# The renderer is assembled from one mixin per rendering domain; the mixins
# live in .renderers/ and the class below keeps the state, the per book
# lifecycle and the dump_text() dispatch.

import os

from calibre.ebooks.oeb.base import XHTML_NS, barename, namespace
from calibre.ebooks.txt.markdownml import MarkdownMLizer

from calibre_plugins.markdown.utils.helpers import (
    apply_paragraph_style,
    clean_invisible_chars,
    is_titlepage_href,
    strip_pdf_page_marker_lines,
)
from calibre_plugins.markdown.output.renderers.blocks import BlocksMixin
from calibre_plugins.markdown.output.renderers.document import DocumentMixin
from calibre_plugins.markdown.output.renderers.footnotes import FootnotesMixin
from calibre_plugins.markdown.output.renderers.headings import HeadingsMixin
from calibre_plugins.markdown.output.renderers.inline import InlineMixin
from calibre_plugins.markdown.output.renderers.lists import ListsMixin
from calibre_plugins.markdown.output.renderers.media import MediaMixin
from calibre_plugins.markdown.output.renderers.primitives import (
    BLOCK_LEVEL_TAGS,
    HEADING_INLINE_TAGS,
    ITEM_LINE_BLOCKS,
    ITEM_LINE_STARTED,
    margin_repair_summary,
    repair_margin_lengths,
)
from calibre_plugins.markdown.output.renderers.tables import TablesMixin
from calibre_plugins.markdown.output.renderers.text import TextMixin

USE_FENCED_CODE_BLOCKS = True


class EnhancedMarkdownMLizer(
        ListsMixin, DocumentMixin, MediaMixin, TablesMixin, BlocksMixin,
        HeadingsMixin, InlineMixin, FootnotesMixin, TextMixin,
        MarkdownMLizer):

    #: Set while a heading's content is collected: it is rendered as inline
    #: text (see _dump_heading_inline). Reset per book in extract_content();
    #: the class attribute covers a renderer that was built by hand.
    _in_heading = False

    #: Set while the content of a list item is being written: ITEM_LINE_OPEN
    #: while the item's own line is still empty (the first block of the item
    #: continues it, see _dump_item_block), ITEM_LINE_STARTED once it is taken,
    #: None anywhere else. Reset per book in extract_content(); the class
    #: attribute covers a renderer that was built by hand.
    _item_line = None

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
        self._in_heading = False
        self._item_line = None
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

        if self._in_heading and tag not in HEADING_INLINE_TAGS:
            return self._dump_heading_inline(elem, stylizer)

        if self._item_line and tag in BLOCK_LEVEL_TAGS:
            if tag in ITEM_LINE_BLOCKS:
                return self._dump_item_block(elem, stylizer, tag, style)
            # A block that needs lines of its own - a nested list, a table, a
            # fenced code block - ends the item's line instead of continuing
            # it; what follows it is no longer the item's first content.
            self._item_line = ITEM_LINE_STARTED

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
