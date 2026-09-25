# -*- coding: utf-8 -*-
"""Links and images.

A link pointing inside the book becomes a wikilink, one pointing at a note
a footnote reference, and everything else a Markdown link. An image is
written as ![alt](src) unless the book gives it a size (a width/height
attribute or CSS), in which case it is written as raw HTML so the size
survives into the Markdown and back.
"""

from calibre_plugins.markdown.utils.helpers import (
    html_image_tag,
    image_size_attrs,
)


class MediaMixin(object):
    """Links (wikilinks, footnote references, Markdown links)
    and images (Markdown references or sized raw HTML).
    """

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

