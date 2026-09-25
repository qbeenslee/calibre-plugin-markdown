# -*- coding: utf-8 -*-
"""Quote blocks and figures.

A <blockquote> is written as a Markdown quote whose "> " prefix is written
exactly once - by the first block level child, or by the quote renderer
itself when the quote opens with text or inline content - and a <figure> as
its content plus its figcaption written as an italic line.
"""

from calibre.ebooks.oeb.base import barename

from calibre_plugins.markdown.utils.helpers import local_name

from calibre_plugins.markdown.output.renderers.primitives import (
    BLOCK_LEVEL_TAGS,
    _css_margin_break,
    _ends_with_blank_line,
)


class BlocksMixin(object):
    """The blocks that hold other blocks: quote blocks and
    figures.
    """

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

