# -*- coding: utf-8 -*-
"""The plugin's "Customize plugin" UI (Preferences -> Plugins -> Markdown).

ConfigWidget is what calibre shows on the Customize plugin button (see
MarkdownOutput.config_widget/save_settings).
"""

__license__ = 'GPL 3'

try:
    from qt.core import (
        QVBoxLayout, QLabel, QCheckBox, QHBoxLayout, QWidget,
        QComboBox, QLineEdit, QIntValidator,
    )
except ImportError:
    from PyQt5.Qt import (
        QVBoxLayout, QLabel, QCheckBox, QHBoxLayout, QWidget,
        QComboBox, QLineEdit, QIntValidator,
    )

from calibre_plugins.markdown.translations.messages import _
from calibre_plugins.markdown.utils.helpers import (
    FILENAME_PATTERN_AUTHOR_FOLDER,
    FILENAME_PATTERN_AUTHOR_TITLE,
    FILENAME_PATTERN_SERIES_TITLE,
    FILENAME_PATTERN_TITLE,
)
from calibre_plugins.markdown.utils.override_model import GlobalOverrideModel
from calibre_plugins.markdown.utils.prefs import (
    IMAGE_MODE_LABELS,
    IMAGE_OUTPUT_MODES,
)

WRAP_MODE_DEFAULT = 0
WRAP_MODE_CUSTOM = 1
FILENAME_OPTIONS = (
    ('Filename pattern title', FILENAME_PATTERN_TITLE),
    ('Filename pattern author title', FILENAME_PATTERN_AUTHOR_TITLE),
    ('Filename pattern author folder', FILENAME_PATTERN_AUTHOR_FOLDER),
    ('Filename pattern series title', FILENAME_PATTERN_SERIES_TITLE),
)
WRAP_CUSTOM_DEFAULT = 80

NEWLINE_OPTIONS = (
    ('Newline Unix', 'unix'),
    ('Newline Windows', 'windows'),
)


BOOL_OPTIONS = (
    ('inline_toc', 'Add table of contents at the beginning'),
    ('heading_anchors', 'Add heading anchors'),
    ('escape_markdown_chars', 'Escape Markdown special characters'),
    ('keep_links', 'Keep links'),
    ('keep_image_references', 'Keep image references'),
    ('keep_image_sizes', 'Keep image sizes'),
    ('export_cover_page', 'Export cover page'),
    ('export_image_files', 'Export image files'),
    ('download_remote_images', 'Download remote images'),
    ('use_alt_text_for_images', 'Use alt text for images'),
    ('yaml_front_matter', 'Add YAML front matter'),
    ('strip_pdf_page_markers', 'Strip PDF page markers'),
    ('force_max_line_length', 'Force max line length'),
    ('blank_line_before_heading', 'Blank line before headings'),
)

#: (i18n source string, value) pairs, derived from the shared table in
#: utils/prefs.py so the conversion pane and this dialog cannot drift apart.
IMAGE_MODE_OPTIONS = tuple(
    (IMAGE_MODE_LABELS[mode], mode) for mode in IMAGE_OUTPUT_MODES)

PARAGRAPH_STYLE_OPTIONS = (
    ('Paragraph style block', 'block'),
    ('Paragraph style single', 'single'),
)


class ConfigWidget(QWidget):
    """Customization widget shown by calibre's "Customize plugin" button.

    Every row starts disabled: only the options the user explicitly enables
    are stored, and MarkdownOutput.convert() applies them on top of whatever
    the conversion dialog (or the CLI) already decided.
    """

    def __init__(self, customization='', parent=None):
        super().__init__(parent)
        self.model = GlobalOverrideModel.from_customization(customization)
        self._rows = {}
        self._loading = False
        self._build_ui()
        self._restore_model()
        self.apply_translations()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.intro_label = QLabel()
        self.intro_label.setWordWrap(True)
        layout.addWidget(self.intro_label)

        for key, label in BOOL_OPTIONS:
            self._add_row(layout, key, label, QCheckBox())

        self._add_row(layout, 'image_output_mode', 'Image output mode:',
                      self._build_combo(IMAGE_MODE_OPTIONS), IMAGE_MODE_OPTIONS)
        self._add_row(layout, 'paragraph_style', 'Paragraph style:',
                      self._build_combo(PARAGRAPH_STYLE_OPTIONS), PARAGRAPH_STYLE_OPTIONS)
        self._add_row(layout, 'newline', 'Newline:',
                      self._build_combo(NEWLINE_OPTIONS), NEWLINE_OPTIONS)
        self._add_row(layout, 'filename_pattern', 'Filename pattern:',
                      self._build_combo(FILENAME_OPTIONS), FILENAME_OPTIONS)
        self._add_row(layout, 'max_line_length', 'Max line length:',
                      self._build_int_edit())
        self._add_row(layout, 'txt_output_encoding', 'Output encoding:',
                      QLineEdit())

        layout.addStretch(1)

    def _build_combo(self, options):
        combo = QComboBox()
        for label, value in options:
            combo.addItem(_(label), value)
        return combo

    def _build_int_edit(self):
        edit = QLineEdit()
        edit.setValidator(QIntValidator(0, 10000, self))
        edit.setFixedWidth(80)
        return edit

    def _add_row(self, layout, key, label_text, widget, options=None):
        row = QHBoxLayout()
        toggle = QCheckBox()
        widget.setEnabled(False)
        row.addWidget(toggle)
        label = None
        if isinstance(widget, QCheckBox):
            # A checkbox carries its own caption; a second label next to it
            # would print the same option name twice.
            widget.setText(_(label_text))
        else:
            label = QLabel(label_text)
            row.addWidget(label)
        row.addWidget(widget, 1)
        layout.addLayout(row)
        # label_text is kept as the i18n source string: reading it back from
        # the label would return the already-translated text and language
        # switching could not go back to English. For comboboxes, options is
        # the (i18n_source, value) list so the items can be re-localized too.
        self._rows[key] = (toggle, widget, label, label_text, options)
        toggle.toggled.connect(lambda checked, k=key: self._on_toggle(k, checked))
        if isinstance(widget, QCheckBox):
            widget.stateChanged.connect(
                lambda _state, k=key, w=widget: self._on_value(k, w.isChecked()))
        elif isinstance(widget, QComboBox):
            widget.currentIndexChanged.connect(
                lambda _index, k=key, w=widget: self._on_value(k, w.currentData()))
        else:
            widget.textChanged.connect(
                lambda _text, k=key, w=widget: self._on_value(k, w.text()))

    def _on_value(self, key, value):
        if self._loading:
            return
        if key == 'max_line_length':
            try:
                value = max(0, int(value))
            except (TypeError, ValueError):
                value = 0
        toggle = self._rows[key][0]
        self.model.set(key, value, enabled=toggle.isChecked())

    def _on_toggle(self, key, checked):
        toggle, widget, _label, _label_text, _options = self._rows[key]
        widget.setEnabled(checked)
        self.model.set(key, self._widget_value(widget), enabled=checked)

    def _widget_value(self, widget):
        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        if isinstance(widget, QComboBox):
            return widget.currentData()
        return widget.text()

    def _set_widget_value(self, widget, value):
        if isinstance(widget, QCheckBox):
            widget.setChecked(bool(value))
        elif isinstance(widget, QComboBox):
            index = widget.findData(value)
            widget.setCurrentIndex(index if index >= 0 else 0)
        else:
            widget.setText('' if value is None else str(value))

    def _restore_model(self):
        self._loading = True
        try:
            for key, (toggle, widget, _label, _label_text, _options) in self._rows.items():
                self._set_widget_value(widget, self.model.value(key))
                enabled = self.model.is_enabled(key)
                toggle.setChecked(enabled)
                widget.setEnabled(enabled)
        finally:
            self._loading = False

    def overrides(self):
        return self.model.overrides()

    def apply_translations(self):
        self.intro_label.setText(_('Customization intro'))
        for _key, (toggle, widget, label, label_text, options) in self._rows.items():
            toggle.setText(_('Override globally'))
            if label is None:
                widget.setText(_(label_text))
            else:
                label.setText(_(label_text))
            if isinstance(widget, QComboBox) and options:
                # Re-localize the dropdown items; keep the stored data values.
                for i, (label_key, _value) in enumerate(options):
                    widget.setItemText(i, _(label_key))
