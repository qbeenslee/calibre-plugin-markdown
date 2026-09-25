# -*- coding: utf-8 -*-
"""Escaping, text fragments and link targets.

The primitives every renderer writes text with: the escape switch and the
Markdown special character set, the fragment formatters, the wikilink target
derivation and the helpers that collect the text of an element's children.
"""

import os
import re
from urllib.parse import unquote


#: The characters calibre's MarkdownMLizer escapes in body text. The set is
#: mirrored here (instead of calling the inherited method) so that switching
#: the escape option on reproduces the historical output exactly.
MARKDOWN_ESCAPE_RE = re.compile(r'([\\`*_{}\[\]()#+!])')
MARKDOWN_UNESCAPE_RE = re.compile(r'\\([\\`*_{}\[\]()#+!])')

class TextMixin(object):
    """The text primitives every renderer writes with:
    the escape switch and its character set, the fragment formatters,
    the link and wikilink targets, and the inline text collectors.
    """

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

    def _collect_element_text_parts(self, elem, stylizer):
        text = []
        if hasattr(elem, 'text') and elem.text:
            text.append(self._format_fragment(elem.text))
        for item in elem:
            text += self.dump_text(item, stylizer)
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

