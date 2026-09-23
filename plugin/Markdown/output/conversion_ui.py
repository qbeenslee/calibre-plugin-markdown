# -*- coding: utf-8 -*-
"""Markdown's pane in calibre's Convert dialog (output side).

calibre asks the output plugin for its pane, so this one appears when
Markdown is the output format. The option rows are the builtin TXT Output
pane plus the Markdown-specific rows this plugin adds; the global overrides
from the customization dialog are shown as this pane's effective values.
"""

from calibre.gui2.convert.txt_output import PluginWidget as TXTPluginWidget
from calibre.gui2.convert.txt_output_ui import Ui_Form
from calibre.gui2.convert import Widget

from calibre_plugins.markdown.translations.messages import _ as _i18n
from calibre_plugins.markdown.utils.plugin_icons import pane_icon
from calibre_plugins.markdown.utils.prefs import (
    IMAGE_MODE_LABELS,
    IMAGE_OUTPUT_MODES,
    PARAGRAPH_STYLES,
    read_plugin_overrides,
)
#: Name this output plugin registers under: calibre keys its saved
#: customization (the "Customize plugin" dialog) by it, and the pane points
#: the user at that dialog.
PLUGIN_NAME = 'Markdown Output'

option = (
    "newline",
    "max_line_length",
    "force_max_line_length",
    "inline_toc",
    "keep_links",
    "keep_image_references",
    "keep_image_sizes",
    "export_cover_page",
    "use_alt_text_for_images",
    "export_image_files",
    "download_remote_images",
    "image_output_mode",
    "txt_output_encoding",
    "paragraph_style",
    "blank_line_before_heading",
    "heading_anchors",
    "escape_markdown_chars",
    "yaml_front_matter",
)

#: Rows of the "Images" group box, in display order. calibre binds a pane row
#: to its option through the opt_<name> attribute, so pulling the image rows
#: out of the "Markdown, Textile" group only moves widgets: every value is
#: still committed under the same name.
IMAGE_GROUP_OPTIONS = (
    'keep_image_references',
    'keep_image_sizes',
    'use_alt_text_for_images',
    'export_image_files',
    'download_remote_images',
    'image_output_mode',
)

#: Rows of the group the master switch governs. With "Keep images" off the
#: Markdown carries no image reference, so neither the sizes, the alt text,
#: the file export, the remote downloads nor the output mode can do anything:
#: the pane greys them out. The values are still committed - greying is a
#: hint, not a lock. The tests keep this tuple at IMAGE_GROUP_OPTIONS minus
#: the switch, so a row added to the group cannot be forgotten here.
IMAGE_DEPENDENT_OPTIONS = (
    'keep_image_sizes',
    'use_alt_text_for_images',
    'export_image_files',
    'download_remote_images',
    'image_output_mode',
)

#: Rows governed by another row *inside* the group, on top of the master
#: switch: the remote downloads and the output mode both only happen as part
#: of the file export, so they grey out with "Export image files".
IMAGE_ROW_GATES = {
    'download_remote_images': 'export_image_files',
    'image_output_mode': 'export_image_files',
}

PARAGRAPH_STYLE_LABELS = {
    'block': 'Paragraph style block',
    'single': 'Paragraph style single',
}

# Map a newline option value ('unix', 'windows', ...) to the i18n key of its
# display label, so the combo shows a localized name while still committing the
# raw value (currentData) back to the conversion options.
NEWLINE_LABELS = {
    'system': 'Newline System',
    'unix': 'Newline Unix',
    'old_mac': 'Newline Mac old',
    'windows': 'Newline Windows',
}


class TXTUIForm(Ui_Form):
    def setupUi(self, Form):
        super(TXTUIForm, self).setupUi(Form)

        def delete(layout, widget):
            layout.removeWidget(widget)
            widget.deleteLater()

        # Calibre 9.8+ uses formLayout; older releases used gridLayout.
        primary_layout = getattr(self, 'formLayout', None) or getattr(self, 'gridLayout', None)
        if primary_layout is not None:
            delete(primary_layout, self.label_4)
            delete(primary_layout, self.opt_txt_output_formatting)
        if hasattr(self, 'verticalLayout') and hasattr(self, 'opt_keep_color'):
            delete(self.verticalLayout, self.opt_keep_color)
        self._left_align_forms()
        self._add_images_group(Form)
        self._add_paragraph_style_row()
        self._add_blank_line_before_heading_row()
        self._add_heading_anchors_row()
        self._add_escape_markdown_chars_row()
        self._add_yaml_front_matter_row()
        self._add_export_cover_page_row()
        self._add_customization_hint(Form)

    def _add_customization_hint(self, Form):
        """Trailing line pointing the user at "Customize plugin".

        Every row above is a per-book setting of this conversion; the plugin's
        global defaults live in its own customization dialog.
        """
        try:
            from qt.core import QLabel
        except ImportError:
            from PyQt5.Qt import QLabel
        self.customization_hint_label = QLabel(Form)
        self.customization_hint_label.setWordWrap(True)
        self.customization_hint_label.setText(
            _i18n('Customization hint').format(plugin=PLUGIN_NAME))
        top = getattr(self, 'verticalLayout_2', None) or Form.layout()
        if top is None:
            return
        # Last line of the pane: calibre's Ui_Form closes its layout with a
        # spacer, which has to stay below the hint.
        index = top.count()
        last = top.itemAt(index - 1)
        if last is not None and last.spacerItem() is not None:
            index -= 1
        top.insertWidget(index, self.customization_hint_label)

    def _add_images_group(self, Form):
        """Add the "Images" group box, a sibling of "Markdown, Textile".

        The image rows used to sit inside the Markdown, Textile group (two of
        them and the note are calibre's own widgets, which moving into this
        group simply reparents). Rows are filled in IMAGE_GROUP_OPTIONS order;
        the runtime check in scripts/verify_image_output_pane.py compares the
        built order against that tuple.
        """
        try:
            from qt.core import QGroupBox, QVBoxLayout
        except ImportError:
            from PyQt5.Qt import QGroupBox, QVBoxLayout
        self.images_group = QGroupBox(_i18n('Images'), Form)
        self._images_layout = QVBoxLayout(self.images_group)
        top = getattr(self, 'verticalLayout_2', None) or Form.layout()
        if top is not None:
            # Directly under the Markdown, Textile group; the spacer that
            # closes the pane's layout stays last.
            anchor = getattr(self, 'groupBox_3', None)
            index = top.indexOf(anchor) if anchor is not None else -1
            top.insertWidget(
                index + 1 if index >= 0 else top.count(), self.images_group)
        self._images_layout.addWidget(self.opt_keep_image_references)
        self._add_keep_image_sizes_row()
        self._images_layout.addWidget(self.opt_use_alt_text_for_images)
        self._add_export_image_files_row()
        self._add_download_remote_images_row()
        self._add_image_output_mode_row()
        self._images_layout.addWidget(self.image_note_label)

    def _append_image_row(self, widget):
        """Append a row to the Images group box built by _add_images_group."""
        layout = getattr(self, '_images_layout', None)
        if layout is not None:
            layout.addWidget(widget)

    def _left_align_forms(self):
        # macOS styles center QFormLayout contents by default; force the
        # left-aligned look the other calibre panes use.
        try:
            from qt.core import Qt
        except ImportError:
            from PyQt5.Qt import Qt
        for name in ('formLayout', 'formLayout_2'):
            layout = getattr(self, name, None)
            if layout is None:
                continue
            layout.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
            layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)

    def _markdown_layout(self):
        """Layout of the "Markdown, Textile" group box."""
        return getattr(self, 'verticalLayout', None)

    def _add_blank_line_before_heading_row(self):
        try:
            from qt.core import QCheckBox
        except ImportError:
            from PyQt5.Qt import QCheckBox
        self.opt_blank_line_before_heading = QCheckBox()
        self.opt_blank_line_before_heading.setText(
            _i18n('Blank line before headings'))
        vertical = self._markdown_layout()
        if vertical is not None:
            # Directly under the paragraph style row.
            vertical.insertWidget(1, self.opt_blank_line_before_heading)
            return
        grid = getattr(self, 'gridLayout', None)
        if grid is not None:
            row = grid.rowCount()
            grid.addWidget(self.opt_blank_line_before_heading, row, 0, 1, 2)

    def _add_heading_anchors_row(self):
        try:
            from qt.core import QCheckBox
        except ImportError:
            from PyQt5.Qt import QCheckBox
        self.opt_heading_anchors = QCheckBox()
        self.opt_heading_anchors.setText(_i18n('Add heading anchors'))
        vertical = self._markdown_layout()
        if vertical is not None:
            # Directly under the blank-line-before-heading row.
            vertical.insertWidget(2, self.opt_heading_anchors)
            return
        grid = getattr(self, 'gridLayout', None)
        if grid is not None:
            row = grid.rowCount()
            grid.addWidget(self.opt_heading_anchors, row, 0, 1, 2)

    def _add_escape_markdown_chars_row(self):
        try:
            from qt.core import QCheckBox
        except ImportError:
            from PyQt5.Qt import QCheckBox
        self.opt_escape_markdown_chars = QCheckBox()
        self.opt_escape_markdown_chars.setText(
            _i18n('Escape Markdown special characters'))
        vertical = self._markdown_layout()
        if vertical is not None:
            # Directly under the heading anchors row.
            vertical.insertWidget(3, self.opt_escape_markdown_chars)
            return
        grid = getattr(self, 'gridLayout', None)
        if grid is not None:
            row = grid.rowCount()
            grid.addWidget(self.opt_escape_markdown_chars, row, 0, 1, 2)

    def _add_yaml_front_matter_row(self):
        try:
            from qt.core import QCheckBox
        except ImportError:
            from PyQt5.Qt import QCheckBox
        self.opt_yaml_front_matter = QCheckBox()
        self.opt_yaml_front_matter.setText(_i18n('Add YAML front matter'))
        vertical = self._markdown_layout()
        if vertical is not None:
            # Directly under the escape-markdown-chars row.
            vertical.insertWidget(4, self.opt_yaml_front_matter)
            return
        grid = getattr(self, 'gridLayout', None)
        if grid is not None:
            row = grid.rowCount()
            grid.addWidget(self.opt_yaml_front_matter, row, 0, 1, 2)

    def _add_export_cover_page_row(self):
        try:
            from qt.core import QCheckBox
        except ImportError:
            from PyQt5.Qt import QCheckBox
        self.opt_export_cover_page = QCheckBox()
        self.opt_export_cover_page.setText(_i18n('Export cover page'))
        vertical = self._markdown_layout()
        if vertical is not None:
            # Last row of the Markdown, Textile group: the cover page is not
            # one of the image rows (it processes titlepage.xhtml).
            vertical.addWidget(self.opt_export_cover_page)

    def _add_keep_image_sizes_row(self):
        try:
            from qt.core import QCheckBox
        except ImportError:
            from PyQt5.Qt import QCheckBox
        self.opt_keep_image_sizes = QCheckBox()
        self.opt_keep_image_sizes.setText(_i18n('Image sizes'))
        self._append_image_row(self.opt_keep_image_sizes)

    def _add_export_image_files_row(self):
        try:
            from qt.core import QCheckBox
        except ImportError:
            from PyQt5.Qt import QCheckBox
        self.opt_export_image_files = QCheckBox()
        self.opt_export_image_files.setText(_i18n('Export image files'))
        self._append_image_row(self.opt_export_image_files)

    def _add_download_remote_images_row(self):
        try:
            from qt.core import QCheckBox
        except ImportError:
            from PyQt5.Qt import QCheckBox
        self.opt_download_remote_images = QCheckBox()
        self.opt_download_remote_images.setText(
            _i18n('Download remote images'))
        self._append_image_row(self.opt_download_remote_images)

    def _add_image_output_mode_row(self):
        try:
            from qt.core import QComboBox, QHBoxLayout, QLabel
        except ImportError:
            from PyQt5.Qt import QComboBox, QHBoxLayout, QLabel
        self.opt_image_output_mode = QComboBox()
        self.image_output_mode_label = QLabel(_i18n('Image output mode:'))
        self.image_output_mode_label.setBuddy(self.opt_image_output_mode)
        layout = getattr(self, '_images_layout', None)
        if layout is not None:
            # Label and combo on one row, last of the Images group.
            row = QHBoxLayout()
            row.addWidget(self.image_output_mode_label)
            row.addWidget(self.opt_image_output_mode, 1)
            layout.addLayout(row)

    def _add_paragraph_style_row(self):
        try:
            from qt.core import QComboBox, QHBoxLayout, QLabel
        except ImportError:
            from PyQt5.Qt import QComboBox, QHBoxLayout, QLabel
        self.opt_paragraph_style = QComboBox()
        self.paragraph_style_label = QLabel(_i18n('Paragraph style:'))
        self.paragraph_style_label.setBuddy(self.opt_paragraph_style)
        vertical = self._markdown_layout()
        if vertical is not None:
            # Top of the Markdown, Textile group: the row the deleted TXT
            # formatting combo used to hold in General is left empty.
            row = QHBoxLayout()
            row.addWidget(self.paragraph_style_label)
            row.addWidget(self.opt_paragraph_style, 1)
            vertical.insertLayout(0, row)
            return
        grid = getattr(self, 'gridLayout', None)
        if grid is not None:
            row = grid.rowCount()
            grid.addWidget(self.paragraph_style_label, row, 0)
            grid.addWidget(self.opt_paragraph_style, row, 1)


class PluginWidget(TXTPluginWidget, TXTUIForm):

    #: English fallback for the section title calibre shows in the Convert
    #: dialog; apply_translations() re-localizes it through the plugin table.
    TITLE = _("Markdown output")
    HELP = _("Options specific to") + " Markdown " + _("output")
    COMMIT_NAME = "Markdown_output"
    #: Fallback for the pane icon: calibre's own text-file icon. __init__
    #: replaces it with the packaged images/output.png when that loads.
    ICON = 'mimetypes/txt.png'

    def __init__(self, parent, get_option, get_help, db=None, book_id=None,
                 overrides=None):
        icon = pane_icon('output.png')
        if icon is not None:
            # The icon the Convert dialog lists this pane with; assigning it
            # before Widget.__init__ lets it hand the QIcon through as-is.
            self.ICON = icon
        Widget.__init__(self, parent, option)
        self.db, self.book_id = db, book_id
        # calibre's base TXT widget already added the raw choice strings to
        # opt_newline; clear them and re-add localized labels with the real
        # value stored as item data so the combo commits the raw value.
        self.opt_newline.clear()
        for value in get_option('newline').option.choices:
            self.opt_newline.addItem(
                _i18n(NEWLINE_LABELS.get(value, value)), value)
        for value in PARAGRAPH_STYLES:
            self.opt_paragraph_style.addItem(
                _i18n(PARAGRAPH_STYLE_LABELS[value]), value)
        for value in IMAGE_OUTPUT_MODES:
            self.opt_image_output_mode.addItem(
                _i18n(IMAGE_MODE_LABELS[value]), value)

        self.initialize_options(get_option, self._translated_help(get_help), db, book_id)
        if overrides is None:
            # Real calibre never passes overrides; the pane reads the plugin's
            # saved global overrides itself, so they show up as the starting
            # values while every row stays fully editable.
            overrides = read_plugin_overrides(PLUGIN_NAME)
        self.apply_global_overrides(overrides or {})
        self.apply_translations()
        self._wire_image_rows()

    def _wire_image_rows(self):
        '''Tie the image rows' enabled state to the switches governing them.

        Runs once the pane has its values and labels, so it opens with the
        right state, and again on every toggle of the master switch or of a
        gating row.
        '''
        self.opt_keep_image_references.toggled.connect(self._sync_image_rows)
        for gate in sorted(set(IMAGE_ROW_GATES.values())):
            widget = getattr(self, 'opt_' + gate, None)
            if widget is not None:
                widget.toggled.connect(self._sync_image_rows)
        self._sync_image_rows()

    def _sync_image_rows(self):
        '''Enable each image row the switches governing it call for.

        The combo's label is part of its row and follows it; calibre's note
        belongs to the group and follows the master switch alone. Greying is
        a hint, not a lock: the rows keep their values and still commit them,
        so turning the switches back on brings them back as they were.
        '''
        for name in IMAGE_DEPENDENT_OPTIONS:
            widget = getattr(self, 'opt_' + name, None)
            if widget is not None:
                widget.setEnabled(self._image_row_enabled(name))
        label = getattr(self, 'image_output_mode_label', None)
        if label is not None:
            label.setEnabled(self._image_row_enabled('image_output_mode'))
        note = getattr(self, 'image_note_label', None)
        if note is not None:
            note.setEnabled(self.opt_keep_image_references.isChecked())

    def _image_row_enabled(self, name):
        '''True when every switch governing this image row is on.

        "Keep images" governs the whole group; a gated row (IMAGE_ROW_GATES)
        also needs the row gating it.
        '''
        if not self.opt_keep_image_references.isChecked():
            return False
        gate = IMAGE_ROW_GATES.get(name)
        if gate is None:
            return True
        gate_widget = getattr(self, 'opt_' + gate, None)
        return gate_widget is None or gate_widget.isChecked()

    def apply_translations(self):
        """Re-localize the pane title, the labels and the combobox items."""
        # The Convert dialog lists the pane by this title, the way the
        # builtin panes read "TXT output" / "EPUB output" there.
        self.TITLE = _i18n('Markdown output')
        self.opt_blank_line_before_heading.setText(_i18n('Blank line before headings'))
        self.opt_heading_anchors.setText(_i18n('Add heading anchors'))
        self.opt_escape_markdown_chars.setText(
            _i18n('Escape Markdown special characters'))
        self.opt_yaml_front_matter.setText(_i18n('Add YAML front matter'))
        self.opt_export_cover_page.setText(_i18n('Export cover page'))
        # Calibre's own rows: the pane renames them through the plugin table
        # so they follow the plugin UI language like every row this pane adds.
        self.opt_keep_links.setText(_i18n('Keep links (<a> tags)'))
        self.images_group.setTitle(_i18n('Images'))
        self.opt_keep_image_references.setText(_i18n('Keep images'))
        self.opt_keep_image_sizes.setText(_i18n('Image sizes'))
        self.opt_use_alt_text_for_images.setText(
            _i18n('Replace images by their alt attribute text'))
        self.opt_export_image_files.setText(_i18n('Export image files'))
        self.opt_download_remote_images.setText(
            _i18n('Download remote images'))
        self.image_output_mode_label.setText(_i18n('Image output mode:'))
        self.paragraph_style_label.setText(_i18n('Paragraph style:'))
        self.image_note_label.setText(_i18n('Note preserve images'))
        self.customization_hint_label.setText(
            _i18n('Customization hint').format(plugin=PLUGIN_NAME))
        for i in range(self.opt_paragraph_style.count()):
            value = self.opt_paragraph_style.itemData(i)
            self.opt_paragraph_style.setItemText(
                i, _i18n(PARAGRAPH_STYLE_LABELS.get(value, value)))
        for i in range(self.opt_image_output_mode.count()):
            value = self.opt_image_output_mode.itemData(i)
            self.opt_image_output_mode.setItemText(
                i, _i18n(IMAGE_MODE_LABELS.get(value, value)))
        for i in range(self.opt_newline.count()):
            value = self.opt_newline.itemData(i)
            self.opt_newline.setItemText(
                i, _i18n(NEWLINE_LABELS.get(value, value)))

    def _saved_book_settings(self):
        """What this pane committed for this book the last time (calibre
        stores it per book with HIGH priority). Empty for a book never
        converted from this dialog and for the bulk dialog."""
        if getattr(self, 'db', None) is None or \
                getattr(self, 'book_id', None) is None:
            return {}
        try:
            from calibre.ebooks.conversion.config import load_specifics
            return load_specifics(self.db, self.book_id)
        except Exception:
            return {}

    def apply_global_overrides(self, overrides):
        '''Seed the pane's rows with the plugin's global override values.

        The overrides are the defaults: they fill a row only when calibre has
        no per-book saved settings for it yet (a book converted before keeps
        the values it was last converted with, and those win). Rows stay
        fully editable - whatever the pane commits is saved as that book's
        settings and reaches convert() unchanged.
        '''
        saved = self._saved_book_settings()
        for name, value in (overrides or {}).items():
            if name not in self._options or name in saved:
                continue
            gui_opt = getattr(self, 'opt_' + name, None)
            if gui_opt is None:
                continue
            try:
                self.set_value(gui_opt, value)
            except Exception:
                continue

    def _translated_help(self, get_help):
        '''Translate the option help texts shown as tooltips.

        calibre hands us the help string declared on each OptionRecommendation,
        which is English for the options this plugin adds. Route it through the
        plugin i18n table (the English text is the key) so the tips follow the
        plugin UI language too. Strings calibre already localized stay as-is.
        '''
        def provider(name):
            try:
                text = get_help(name)
            except Exception:
                return None
            if not isinstance(text, str) or not text:
                return text
            return _i18n(text)
        return provider

    def _data_combos(self):
        '''Combos whose items carry the raw option value as item data.

        calibre would otherwise commit currentText() - the localized label -
        as the option value.
        '''
        return (getattr(self, 'opt_paragraph_style', None),
                getattr(self, 'opt_newline', None),
                getattr(self, 'opt_image_output_mode', None))

    def get_value_handler(self, g):
        if g in self._data_combos():
            return g.currentData()
        return super().get_value_handler(g)

    def set_value_handler(self, g, val):
        if g in self._data_combos():
            index = g.findData(val)
            g.setCurrentIndex(index if index >= 0 else 0)
            return True
        return False
