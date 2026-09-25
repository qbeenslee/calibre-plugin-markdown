# -*- coding: utf-8 -*-
"""Headings: the level one is written at and its single line of inline text.

A heading may hold a nested heading - a book, or a "transform HTML" rule
saved for it, can rename an element inside one: the deeper level wins. A
Markdown heading is one line, so everything else inside it is flattened to
plain inline text: no "**" inherited from the heading, no newline from a
<br>, no "#" run of its own for a nested heading.
"""

import re

from calibre.ebooks.oeb.base import barename

from calibre_plugins.markdown.utils.helpers import unique_slug

from calibre_plugins.markdown.output.renderers.primitives import (
    BLOCK_LEVEL_TAGS,
)


class HeadingsMixin(object):
    """Headings: the level one is written at (the deepest it
    holds) and its single line of inline text.
    """

    def _heading_level(self, elem, level):
        '''The level a heading is written at: the deepest heading it holds.

        A book - or one of the "transform HTML" rules saved for it - may name
        an element inside a heading: a rule matching "第1章" renames the <span>
        holding the chapter number, which leaves the chapter marked up as
        `<h2><h3>第1章</h3><br/>标题</h2>`. Writing both levels gives
        "## ### 第1章", so the deeper one wins: the outer element is the
        layout, the inner one carries the level the book asked for.
        '''
        deepest = level
        for item in elem:
            item_tag = getattr(item, 'tag', None)
            if not isinstance(item_tag, (str, bytes)):
                continue
            name = barename(item_tag)
            if name in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
                deepest = max(deepest, int(name[1]))
            deepest = max(deepest, self._heading_level(item, deepest))
        return deepest

    def _dump_heading_inline(self, elem, stylizer):
        '''Render one element of a heading's content as plain inline text.

        A Markdown heading is a single line, so nothing inside it may start a
        new one or decorate it: <br> becomes a space (upstream writes a hard
        line break, which ends the heading and drops the rest of the title into
        the body), a nested heading keeps its text but not its "#" run, and the
        bold or italic a child inherits from the heading is not written out -
        upstream skips the emphasis for a heading itself but not for its
        children, which is where the stray "**" came from.
        '''
        text = []
        tag = barename(elem.tag)
        if tag == 'br' or tag in BLOCK_LEVEL_TAGS:
            # A <br> and a block element end a line in the source; inside a
            # heading that becomes a space, so two <p> in one heading read
            # "甲 乙" and not "甲乙".
            text.append(' ')
        if hasattr(elem, 'text') and elem.text:
            text.append(self._format_fragment(elem.text))
        for item in elem:
            text += self.dump_text(item, stylizer)
        if hasattr(elem, 'tail') and elem.tail:
            text.append(self._format_fragment(elem.tail))
        return text

    def _dump_heading(self, elem, stylizer, tag):
        level = self._heading_level(elem, int(tag[1]))
        bq = '> ' * self.blockquotes
        previous = self._in_heading
        self._in_heading = True
        try:
            parts = self._collect_element_text_parts(elem, stylizer)
        finally:
            self._in_heading = previous
        title = re.sub(r'\s+', ' ', ''.join(parts)).strip()
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

