# -*- coding: utf-8 -*-
"""List items: the bullet's own line, its blocks and the item emphasis."""

import re

from calibre.ebooks.oeb.base import barename

from calibre_plugins.markdown.output.renderers.primitives import (
    BLOCK_LEVEL_TAGS,
    ITEM_LINE_OPEN,
    ITEM_LINE_STARTED,
    ITEM_TEXT_WRAPPERS,
    _drop_leading_blank_fragments,
    _has_visible_text,
)


class ListsMixin(object):
    """List items: the bullet's own line, the blocks an item
    holds and the emphasis it opens and closes.
    """

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
        '''Render one <li> as "- item" (or "1. item") plus its blocks.

        The bullet opens the item's line, and everything the item holds that
        can stand on a line is written on it - which for the usual EPUB shape
        `<li><p>text</p></li>` means the <p> is transparent instead of opening
        a line of its own right after the bullet (see _dump_item_block). The
        whitespace an indented book puts around the item's elements is
        formatting, so it is not written into the output: it used to end up as
        a trailing space on the item's line.
        '''
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
        content_start = len(text)

        self._open_emphasis(style, tag, text, tags)

        task_marker, first_text, skip_item_idx = self._extract_task_checkbox(elem)
        if task_marker:
            text.append(task_marker)

        previous = self._item_line
        self._item_line = ITEM_LINE_OPEN
        try:
            if first_text:
                # The newline a book leaves between <li> and its first element
                # is formatting; folding it into a space put a second space
                # after the bullet ("-  text").
                rendered = self._format_fragment(first_text).lstrip()
                if rendered:
                    text.append(rendered)
                    self._item_line = ITEM_LINE_STARTED

            for idx, item in enumerate(elem):
                if skip_item_idx is not None and idx == skip_item_idx:
                    tail = self._tail_fragment(item)
                    if tail:
                        text.append(tail)
                    continue
                fragments = self.dump_text(item, stylizer)
                if self._item_line == ITEM_LINE_OPEN \
                        and _has_visible_text(fragments):
                    # Inline content (a <span>, an image, ...) opened the item's
                    # line; a block after it is a further paragraph of the item.
                    self._item_line = ITEM_LINE_STARTED
                item_tag = getattr(item, 'tag', None)
                if isinstance(item_tag, (str, bytes)) \
                        and barename(item_tag) in BLOCK_LEVEL_TAGS:
                    fragments = _drop_leading_blank_fragments(fragments)
                text += fragments
        finally:
            self._item_line = previous

        # The whitespace an indented book leaves between the item's elements is
        # written as a space by the tail handling; the item's line ends on its
        # last piece of text, as in the quote renderer. Line breaks stay - they
        # are what puts a block of the item on a line of its own.
        while len(text) > content_start and not text[-1].strip() \
                and '\n' not in text[-1]:
            text.pop()

        self._close_emphasis(tags, text)

        tail = self._tail_fragment(elem)
        if tail and tail.strip():
            text.append(tail)

        return text

    def _dump_item_block(self, elem, stylizer, tag, style):
        '''Write a block of a list item that stands on the item's own line.

        Upstream opens every block with a newline of its own, which on the
        item's line put the text under the bullet instead of next to it:
        `<li><p>text</p></li>` came out as "- " and then the text on a line of
        its own, a list item with no content. Since the "- " bullet already
        opened the line, the opening newline is not written here.

        A <p> (or <div>) around the item's text is dropped altogether - what a
        Markdown item needs is the paragraph's content, the wrapper is the
        markup's way of saying "this item is a paragraph" (see
        _dump_item_paragraph).
        '''
        first = self._item_line == ITEM_LINE_OPEN
        self._item_line = ITEM_LINE_STARTED
        if tag in ITEM_TEXT_WRAPPERS and not self._is_footnote_definition(elem):
            return self._dump_item_paragraph(elem, stylizer, style, first)
        # The block's content is its own, not the item's: a <p> inside a quote
        # is the quote's paragraph (the quote writes the prefix for it), not
        # another paragraph of the item.
        previous = self._item_line
        self._item_line = None
        try:
            parts = self.dump_text(elem, stylizer)
        finally:
            self._item_line = previous
        if parts and isinstance(parts[0], str) and parts[0].startswith('\n'):
            parts[0] = parts[0][1:]
        return parts

    def _dump_item_paragraph(self, elem, stylizer, style, first):
        '''Write the content of the <p>/<div> a list item's text is wrapped in.

        The first wrapper of an item continues the "- " line. A wrapper that
        follows content of the item is a paragraph of its own, separated by the
        blank line that separates paragraphs and indented to the item's content
        column so it stays inside the item instead of ending the list.
        '''
        previous = self._item_line
        self._item_line = None
        try:
            body = ''.join(self._dump_inline_block(elem, stylizer)).strip()
        finally:
            self._item_line = previous
        if not body:
            return []
        text = []
        tags = []
        if not first:
            text.append('\n\n' + self._item_indent())
        self._open_emphasis(style, barename(elem.tag), text, tags)
        text.append(body)
        self._close_emphasis(tags, text)
        return text

    def _item_indent(self):
        '''The indent that keeps a further paragraph inside its list item.

        One level of the tab the nested lists are indented with, which is at
        least the two columns a "- " item's content has to start at to stay
        inside the item.
        '''
        return '\t' * len(self.list)

    def _open_emphasis(self, style, tag, text, tags):
        '''Write the emphasis this element starts, and record how to close it.

        Both a list item and the <p> around its text carry the styling of the
        item, so both open the item's emphasis: an already open state is not
        opened a second time (the delimiters would nest and break the run).
        '''
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

    def _close_emphasis(self, tags, text):
        '''Close the emphasis _open_emphasis() recorded, innermost first.'''
        tags.reverse()
        for t in tags:
            if t == '**':
                self.style_bold = False
            elif t == '*':
                self.style_italic = False
            text.append(t)

