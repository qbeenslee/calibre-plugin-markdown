# -*- coding: utf-8 -*-
"""Tables and definition lists.

A <table> becomes a Markdown pipe table - its caption as an italic line
above it, the alignment each cell declares carried into the separator row -
and a <dl> a definition list, every term on a line of its own with its
description after ": ".
"""

from calibre_plugins.markdown.utils.helpers import (
    alignment_separator,
    cell_alignment,
    find_table_caption,
    iter_definition_items,
    iter_table_rows,
    local_name,
)


class TablesMixin(object):
    """Markdown pipe tables - captions, rows and the alignment
    row - and definition lists.
    """

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

