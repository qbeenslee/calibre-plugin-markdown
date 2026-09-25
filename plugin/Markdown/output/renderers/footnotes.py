# -*- coding: utf-8 -*-
"""Footnotes: reference detection, labels and the definition block.

A link that points at a note is written as "[^n]", the note itself as a
"[^n]: ..." definition collected into one block at the end of the book, and
the labels keep the digits the book uses whenever they are still free.
"""

import re

from calibre.ebooks.oeb.base import barename


class FootnotesMixin(object):
    """Footnotes: what counts as a note reference and as a
    definition, the labels both carry, and the block the definitions
    are collected into at the end of the book.
    """

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

    def _is_footnote_definition(self, elem):
        '''True when this element is a footnote definition (not its content).

        Split out of _capture_footnote_definition so the list item renderer
        can tell a footnote <p>/<div> from the wrapper around the item's text
        before it decides to write it on the item's own line.
        '''
        attrib = getattr(elem, 'attrib', None) or {}
        element_id = (attrib.get('id') or '').strip()
        if not element_id:
            return False
        cls = attrib.get('class', '')
        role = attrib.get('role', '')
        epub_type = attrib.get('epub:type', '') + ' ' + attrib.get(
            '{http://www.idpf.org/2007/ops}type', '')
        return (
            element_id in self._footnote_refs
            or self._looks_like_footnote_id(element_id)
            or self._contains_token(cls, 'footnote')
            or role == 'doc-footnote'
            or self._contains_token(epub_type, 'footnote')
        )

    def _capture_footnote_definition(self, elem, stylizer):
        if not self._is_footnote_definition(elem):
            return False
        element_id = (elem.attrib.get('id') or '').strip()

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

