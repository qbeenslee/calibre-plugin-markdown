# -*- coding: utf-8 -*-
"""The Markdown input plugin's "Customize plugin" UI.

Preferences -> Plugins -> "Markdown Input" -> Customize plugin. Like the
output side's dialog every row starts disabled: only the options the user
explicitly enables are stored (calibre keeps them in this plugin's own
customization slot) and MarkdownInput.convert() applies them on top of
whatever the conversion dialog or the CLI decided.

Qt is imported at module level, the way calibre's own plugin dialogs do; the
value-handling methods only touch the widget they are handed, so they stay
readable without a running widget toolkit.
"""

try:
    from qt.core import (
        QCheckBox,
        QComboBox,
        QHBoxLayout,
        QLabel,
        QListWidget,
        QListWidgetItem,
        QVBoxLayout,
        QWidget,
        Qt,
    )
except ImportError:  # calibre 5 and older shipped PyQt5 directly
    from PyQt5.Qt import (
        QCheckBox,
        QComboBox,
        QHBoxLayout,
        QLabel,
        QListWidget,
        QListWidgetItem,
        QVBoxLayout,
        QWidget,
        Qt,
    )

from calibre_plugins.markdown.input.conversion_ui import (
    AUTO_ENCODING,
    EXTENSIONS,
    LINE_BREAK_LABELS,
    PARAGRAPH_CHOICES,
    PARAGRAPH_LABELS,
    extensions_from_value,
    extensions_to_value,
    is_auto_encoding,
)
from calibre_plugins.markdown.input.input_plugin import (
    DEFAULT_MARKDOWN_EXTENSIONS,
    LINE_BREAK_FOLD,
    LINE_BREAK_HARD,
)
from calibre_plugins.markdown.translations.messages import _ as _i18n
from calibre_plugins.markdown.utils.override_model import GlobalOverrideModel
from calibre_plugins.markdown.utils.prefs import INPUT_OPTION_KEYS

#: (option name, i18n label, widget kind) in display order. The kind selects
#: both the value widget and how its value is read back.
ROW_SPECS = (
    ('input_encoding', 'Input character encoding:', 'encoding'),
    ('md_line_break', 'Single line breaks:', 'combo'),
    ('paragraph_type', 'Input paragraph style:', 'combo'),
    ('read_yaml_metadata', 'Read YAML front matter metadata', 'checkbox'),
    ('keep_images', 'Keep images', 'checkbox'),
    ('embed_images', 'Embed images', 'checkbox'),
    ('download_remote_images', 'Download remote images', 'checkbox'),
    ('keep_image_sizes', 'Keep image sizes', 'checkbox'),
    ('markdown_extensions', 'Markdown extensions:', 'extensions'),
)

#: What an enabled row shows before the user stored a value: the input
#: plugin's own recommended values (see MarkdownInput.options).
ROW_DEFAULTS = {
    'input_encoding': '',                # '' = detect the encoding ('auto')
    'md_line_break': LINE_BREAK_FOLD,
    'paragraph_type': 'auto',
    'read_yaml_metadata': True,
    'keep_images': True,
    'embed_images': True,
    'download_remote_images': True,
    'keep_image_sizes': True,
    'markdown_extensions': DEFAULT_MARKDOWN_EXTENSIONS,
}


class ConfigWidget(QWidget):
    """Customization widget shown by calibre's "Customize plugin" button."""

    def __init__(self, customization='', parent=None):
        super().__init__(parent)
        self.model = GlobalOverrideModel.from_customization(
            customization, INPUT_OPTION_KEYS)
        self._rows = {}
        self._ext_items = {}
        self._loading = False
        self._build_ui()
        self._restore_model()
        self.apply_translations()

    def overrides(self):
        """The overrides the user enabled, ready for save_settings()."""
        return self.model.overrides()

    # --- UI ---------------------------------------------------------------
    def _build_ui(self):
        # Stored so the value handlers work without re-importing Qt.
        self._checked = Qt.CheckState.Checked
        self._unchecked = Qt.CheckState.Unchecked

        layout = QVBoxLayout(self)
        self.intro_label = QLabel(self)
        self.intro_label.setWordWrap(True)
        layout.addWidget(self.intro_label)

        for key, label_text, kind in ROW_SPECS:
            self._add_row(layout, key, label_text, kind)

        layout.addStretch(1)

    def _add_row(self, layout, key, label_text, kind):
        row = QHBoxLayout()
        toggle = QCheckBox(self)
        widget = self._build_value_widget(key, kind)
        widget.setEnabled(False)
        row.addWidget(toggle)
        label = None
        if kind == 'checkbox':
            # A checkbox carries its own caption; a second label next to it
            # would print the same option name twice.
            widget.setText(_i18n(label_text))
        else:
            label = QLabel(_i18n(label_text), self)
            label.setBuddy(widget)
            row.addWidget(label)
        row.addWidget(widget, 1)
        layout.addLayout(row)
        # label_text is kept as the i18n source string: reading it back from
        # the label would return the already-translated text and switching
        # language could not go back to English.
        self._rows[key] = (toggle, widget, label, label_text, kind)
        toggle.toggled.connect(
            lambda checked, k=key: self._on_toggle(k, checked))
        if kind == 'checkbox':
            widget.stateChanged.connect(
                lambda _state, k=key, w=widget: self._on_value(k, w.isChecked()))
        elif kind == 'encoding':
            widget.editTextChanged.connect(
                lambda _text, k=key, w=widget: self._on_value(
                    k, self._value_of(k, w)))
        elif kind == 'combo':
            widget.currentIndexChanged.connect(
                lambda _index, k=key, w=widget: self._on_value(k, w.currentData()))
        else:  # extensions checklist
            widget.itemChanged.connect(
                lambda _item, k=key, w=widget: self._on_value(k, self._value_of(k, w)))

    def _build_value_widget(self, key, kind):
        if kind == 'encoding':
            from calibre.gui2.widgets import EncodingComboBox

            combo = EncodingComboBox(self)
            # calibre's combo has a blank first entry for "detect the
            # encoding"; name it the way the conversion pane shows it.
            combo.setItemText(0, AUTO_ENCODING)
            return combo
        if kind == 'checkbox':
            return QCheckBox(self)
        if kind == 'combo':
            combo = QComboBox(self)
            if key == 'md_line_break':
                choices = tuple(
                    (LINE_BREAK_LABELS[value], value)
                    for value in (LINE_BREAK_FOLD, LINE_BREAK_HARD))
            else:
                choices = tuple(
                    (PARAGRAPH_LABELS[value], value)
                    for value in PARAGRAPH_CHOICES)
            for label_key, value in choices:
                combo.addItem(_i18n(label_key), value)
            return combo
        # The same checklist the conversion pane shows, so the two agree on
        # what "the enabled extensions" means.
        listing = QListWidget(self)
        for name, label_key in EXTENSIONS:
            item = QListWidgetItem(
                '%s - %s' % (name, _i18n(label_key)), listing)
            item.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            item.setData(Qt.ItemDataRole.UserRole, name)
            self._ext_items[name] = item
        return listing

    def _restore_model(self):
        self._loading = True
        try:
            for key, (toggle, widget, _label, _label_text, _kind) in self._rows.items():
                value = self.model.value(key)
                if value is None:
                    value = ROW_DEFAULTS[key]
                self._set_value_of(key, widget, value)
                enabled = self.model.is_enabled(key)
                toggle.setChecked(enabled)
                widget.setEnabled(enabled)
        finally:
            self._loading = False

    # --- value handling ---------------------------------------------------
    def _on_value(self, key, value):
        if self._loading:
            return
        toggle = self._rows[key][0]
        self.model.set(key, value, enabled=toggle.isChecked())

    def _on_toggle(self, key, checked):
        toggle, widget, _label, _label_text, _kind = self._rows[key]
        widget.setEnabled(checked)
        self.model.set(key, self._value_of(key, widget), enabled=checked)

    def _value_of(self, key, widget):
        """The widget's current value in the option's own form."""
        kind = self._rows[key][4]
        if kind == 'extensions':
            return extensions_to_value(
                name for name, item in self._ext_items.items()
                if item.checkState() == self._checked)
        if kind == 'checkbox':
            return widget.isChecked()
        if kind == 'encoding':
            text = str(widget.currentText()).strip()
            # 'auto' is the label for the option's empty "detect the
            # encoding" value; anything else is a real encoding name.
            return '' if is_auto_encoding(text) else text
        return widget.currentData()                       # 'combo'

    def _set_value_of(self, key, widget, value):
        kind = self._rows[key][4]
        if kind == 'extensions':
            wanted = extensions_from_value(value)
            for name, item in self._ext_items.items():
                item.setCheckState(
                    self._checked if name in wanted else self._unchecked)
        elif kind == 'checkbox':
            widget.setChecked(bool(value))
        elif kind == 'encoding':
            text = '' if value is None else str(value).strip()
            widget.setCurrentText(text or AUTO_ENCODING)
        else:                                             # 'combo'
            index = widget.findData(value)
            widget.setCurrentIndex(index if index >= 0 else 0)

    # --- translations -----------------------------------------------------
    def apply_translations(self):
        """Re-localize the intro, the row labels and their choices."""
        self.intro_label.setText(_i18n('Input customization intro'))
        for key, (toggle, widget, label, label_text, kind) in self._rows.items():
            toggle.setText(_i18n('Override globally'))
            if label is None:
                widget.setText(_i18n(label_text))
            else:
                label.setText(_i18n(label_text))
            if kind == 'combo':
                labels = (LINE_BREAK_LABELS if key == 'md_line_break'
                          else PARAGRAPH_LABELS)
                for index in range(widget.count()):
                    label_key = labels.get(widget.itemData(index))
                    if label_key:
                        widget.setItemText(index, _i18n(label_key))
        for name, label_key in EXTENSIONS:
            item = self._ext_items.get(name)
            if item is not None:
                item.setText('%s - %s' % (name, _i18n(label_key)))
