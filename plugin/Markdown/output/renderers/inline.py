# -*- coding: utf-8 -*-
"""Inline markup wrappers and fenced code blocks.

Markup written as delimiters ("~~", "*", "==") or as raw HTML tags (<sup>,
<sub>) wraps its children and reads the tail that follows it; a <pre> is
written as a fenced code block, with the language the book declares in its
class or data attributes when there is one.
"""

from calibre.ebooks.oeb.base import barename

from calibre_plugins.markdown.utils.helpers import extract_code_language


class InlineMixin(object):
    """Inline markup written as delimiters or as raw HTML, and
    fenced code blocks.
    """

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

