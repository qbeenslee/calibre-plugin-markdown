# -*- coding: utf-8 -*-
"""The document around the spine: TOC, YAML front matter and cover.

The TOC is written from the book's own toc tree, each entry at its depth;
the front matter from the metadata calibre passed in (the library's fields
included, when the plugin was given them); the cover is referenced as an
image when it is not part of the spine and the image mapping knows it.
"""

from calibre_plugins.markdown.utils.helpers import (
    DEFAULT_IMAGE_DIR,
    metadata_text_values,
    render_toc_block,
    render_yaml_front_matter,
    yaml_fields_from_metadata,
)


class DocumentMixin(object):
    """The document around the spine: the inline table of
    contents, the YAML front matter and the cover image reference.
    """

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

