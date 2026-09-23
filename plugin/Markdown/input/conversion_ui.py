# -*- coding: utf-8 -*-
"""Conversion dialog pane for Markdown input.

calibre's Convert dialog asks the *input* plugin for its pane, so this one
appears when the input format is Markdown. Values are ordinary per-book
conversion options and are saved under COMMIT_NAME 'markdown_input', kept
apart from the builtin TXT Input pane's 'txt_input' entries.
"""

from calibre.gui2.convert import Widget

from calibre_plugins.markdown.input.input_plugin import (
    LINE_BREAK_FOLD,
    LINE_BREAK_HARD,
)
from calibre_plugins.markdown.translations.messages import _ as _i18n
from calibre_plugins.markdown.utils.plugin_icons import pane_icon
from calibre_plugins.markdown.utils.prefs import read_plugin_overrides

#: Name this input plugin registers under: calibre keys its saved
#: customization (the "Customize plugin" dialog) by it, and the pane points
#: the user at that dialog.
PLUGIN_NAME = 'Markdown Input'

#: Option names the pane commits; the widgets are the opt_<name> attributes.
OPTION = (
    'input_encoding',
    'md_line_break',
    'paragraph_type',
    'read_yaml_metadata',
    'keep_images',
    'embed_images',
    'download_remote_images',
    'keep_image_sizes',
    'markdown_extensions',
)

#: Paragraph styles offered for Markdown input, in display order. calibre's
#: option also has 'unformatted' and 'off'; the pane leaves those to the CLI.
PARAGRAPH_CHOICES = ('auto', 'block', 'single', 'print')

#: (option name, i18n source string of its label) of the pane's "Images"
#: group box, in display order. 'Keep images' is the group's master switch,
#: 'Image sizes' the second row; the pane builds the rows from this table so
#: the group and OPTION cannot drift apart.
IMAGE_GROUP_ROWS = (
    ('keep_images', 'Keep images'),
    ('keep_image_sizes', 'Image sizes'),
    ('embed_images', 'Embed images'),
    ('download_remote_images', 'Download remote images'),
)

#: Option names the "Images" group commits, in the same order.
IMAGE_GROUP_OPTIONS = tuple(name for name, _label in IMAGE_GROUP_ROWS)

#: Rows of the group the master switch governs. With "Keep images" off every
#: image (and its alt text) is dropped before they could do anything, so the
#: pane greys them out. The values are still committed: greying is a hint,
#: not a lock. The tests keep this tuple at IMAGE_GROUP_OPTIONS minus the
#: switch, so a row added to the group cannot be forgotten here.
IMAGE_DEPENDENT_OPTIONS = (
    'keep_image_sizes',
    'embed_images',
    'download_remote_images',
)

#: Rows governed by another row *inside* the group, on top of the master
#: switch: downloading a remote image is how it gets embedded, so "Download
#: remote images" greys out with "Embed images" (its help says so too).
IMAGE_ROW_GATES = {
    'download_remote_images': 'embed_images',
}

PARAGRAPH_LABELS = {
    'auto': 'Paragraph style auto',
    'block': 'Paragraph style block',
    'single': 'Paragraph style single',
    'print': 'Paragraph style print',
}

LINE_BREAK_LABELS = {
    LINE_BREAK_FOLD: 'Fold single line breaks',
    LINE_BREAK_HARD: 'Hard line breaks (<br>)',
}

#: Label the encoding combo shows for calibre's "detect the encoding" value
#: (an empty string): the combo's own first entry is blank, which reads as
#: "nothing picked" rather than as a choice. Both the conversion pane and
#: the customization dialog show it.
AUTO_ENCODING = 'auto'


def is_auto_encoding(text):
    """True for combo text that stands for calibre's "detect the encoding"."""
    return str(text).strip().lower() == AUTO_ENCODING

#: (python-markdown extension, i18n key for its description). 'meta' is
#: governed by read_yaml_metadata and 'nl2br' by md_line_break, so neither
#: is offered as a checkbox here.
EXTENSIONS = (
    ('abbr', 'Extension abbr'),
    ('admonition', 'Extension admonition'),
    ('attr_list', 'Extension attr_list'),
    ('codehilite', 'Extension codehilite'),
    ('def_list', 'Extension def_list'),
    ('extra', 'Extension extra'),
    ('fenced_code', 'Extension fenced_code'),
    ('footnotes', 'Extension footnotes'),
    ('legacy_attrs', 'Extension legacy_attrs'),
    ('legacy_em', 'Extension legacy_em'),
    ('sane_lists', 'Extension sane_lists'),
    ('smarty', 'Extension smarty'),
    ('tables', 'Extension tables'),
    ('toc', 'Extension toc'),
    ('wikilinks', 'Extension wikilinks'),
)


def extensions_from_value(value):
    """Option value ('a, b') -> set of enabled extension names."""
    return {name.strip() for name in str(value or '').split(',') if name.strip()}


def extensions_to_value(names):
    """Enabled extension names -> the option's comma separated value."""
    return ', '.join(names)


class PluginWidget(Widget):

    #: Fallback for the pane icon: calibre's own text-file icon. __init__
    #: replaces it with the packaged images/input.png when that loads.
    ICON = 'mimetypes/txt.png'
    COMMIT_NAME = 'markdown_input'

    def __init__(self, parent, get_option, get_help, db=None, book_id=None,
                 overrides=None):
        icon = pane_icon('input.png')
        if icon is not None:
            # The icon the Convert dialog lists this pane with; assigning it
            # before Widget.__init__ lets it hand the QIcon through as-is.
            self.ICON = icon
        Widget.__init__(self, parent, OPTION)
        self.db, self.book_id = db, book_id
        self.TITLE = _i18n('Markdown input')
        self.HELP = _i18n('Options specific to Markdown input')
        for value in (LINE_BREAK_FOLD, LINE_BREAK_HARD):
            self.opt_md_line_break.addItem(
                _i18n(LINE_BREAK_LABELS[value]), value)
        for value in PARAGRAPH_CHOICES:
            self.opt_paragraph_type.addItem(
                _i18n(PARAGRAPH_LABELS[value]), value)
        self.initialize_options(
            get_option, self._translated_help(get_help), db, book_id)
        if overrides is None:
            # Real calibre never passes overrides; the pane reads the plugin's
            # saved global overrides itself, so they show up as the starting
            # values while every row stays fully editable.
            overrides = read_plugin_overrides(PLUGIN_NAME)
        self.apply_global_overrides(overrides or {})
        self._wire_image_rows()

    def _wire_image_rows(self):
        '''Tie the image rows' enabled state to the switches governing them.

        Runs after apply_global_overrides() so the pane opens with the right
        state for the values it shows, and again on every toggle of the
        master switch or of a gating row.
        '''
        self.opt_keep_images.toggled.connect(self._sync_image_rows)
        for gate in sorted(set(IMAGE_ROW_GATES.values())):
            widget = getattr(self, 'opt_' + gate, None)
            if widget is not None:
                widget.toggled.connect(self._sync_image_rows)
        self._sync_image_rows()

    def _sync_image_rows(self):
        '''Enable each image row the switches governing it call for.

        Greying is a hint, not a lock: the rows keep their values and still
        commit them, so turning the switches back on brings them back exactly
        as they were.
        '''
        for name in IMAGE_DEPENDENT_OPTIONS:
            widget = getattr(self, 'opt_' + name, None)
            if widget is not None:
                widget.setEnabled(self._image_row_enabled(name))

    def _image_row_enabled(self, name):
        '''True when every switch governing this image row is on.

        "Keep images" governs the whole group; a gated row (IMAGE_ROW_GATES)
        also needs the row gating it.
        '''
        if not self.opt_keep_images.isChecked():
            return False
        gate = IMAGE_ROW_GATES.get(name)
        if gate is None:
            return True
        gate_widget = getattr(self, 'opt_' + gate, None)
        return gate_widget is None or gate_widget.isChecked()

    def _saved_book_settings(self):
        """What this pane committed for this book the last time (calibre
        stores it per book with HIGH priority). Empty for a book never
        converted from this dialog."""
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

    def setupUi(self, Form):
        try:
            from qt.core import (
                QCheckBox,
                QComboBox,
                QFormLayout,
                QGroupBox,
                QLabel,
                QListWidget,
                QListWidgetItem,
                Qt,
                QVBoxLayout,
            )
        except ImportError:  # calibre 5 and older shipped PyQt5 directly
            from PyQt5.Qt import (
                QCheckBox,
                QComboBox,
                QFormLayout,
                QGroupBox,
                QLabel,
                QListWidget,
                QListWidgetItem,
                Qt,
                QVBoxLayout,
            )

        from calibre.gui2.widgets import EncodingComboBox

        # Stored so the value handlers work without importing Qt.
        self._checked = Qt.CheckState.Checked
        self._unchecked = Qt.CheckState.Unchecked

        outer = QVBoxLayout(Form)

        general = QGroupBox(_i18n('General'), Form)
        general_form = QFormLayout(general)
        encoding_label = QLabel(_i18n('Input character encoding:'), general)
        self.opt_input_encoding = EncodingComboBox(general)
        # The combo's first entry is calibre's blank "auto detect"; name it so
        # the default reads as a choice.
        self.opt_input_encoding.setItemText(0, AUTO_ENCODING)
        encoding_label.setBuddy(self.opt_input_encoding)
        general_form.addRow(encoding_label, self.opt_input_encoding)
        line_break_label = QLabel(_i18n('Single line breaks:'), general)
        self.opt_md_line_break = QComboBox(general)
        line_break_label.setBuddy(self.opt_md_line_break)
        general_form.addRow(line_break_label, self.opt_md_line_break)
        outer.addWidget(general)

        markdown = QGroupBox(_i18n('Markdown'), Form)
        markdown_form = QFormLayout(markdown)
        paragraph_label = QLabel(_i18n('Input paragraph style:'), markdown)
        self.opt_paragraph_type = QComboBox(markdown)
        paragraph_label.setBuddy(self.opt_paragraph_type)
        markdown_form.addRow(paragraph_label, self.opt_paragraph_type)
        self.opt_read_yaml_metadata = QCheckBox(
            _i18n('Read YAML front matter metadata'), markdown)
        markdown_form.addRow(self.opt_read_yaml_metadata)
        outer.addWidget(markdown)

        # The image switches get their own group box, a sibling of "General",
        # "Markdown" and "Extensions", so the pane reads as "how the text is
        # read" plus "what happens to the images".
        images = QGroupBox(_i18n('Images'), Form)
        images_form = QFormLayout(images)
        for name, label in IMAGE_GROUP_ROWS:
            box = QCheckBox(_i18n(label), images)
            setattr(self, 'opt_' + name, box)
            images_form.addRow(box)
        outer.addWidget(images)

        extension_box = QGroupBox(_i18n('Extensions'), Form)
        extension_layout = QVBoxLayout(extension_box)
        self.opt_markdown_extensions = QListWidget(extension_box)
        self.md_items = {}
        for name, key in EXTENSIONS:
            item = QListWidgetItem(
                '%s - %s' % (name, _i18n(key)), self.opt_markdown_extensions)
            item.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.md_items[name] = item
        extension_layout.addWidget(self.opt_markdown_extensions)
        outer.addWidget(extension_box)

        # Closing line of the pane: every row above is a per-book conversion
        # setting, so say where the plugin-wide defaults live.
        self.customization_hint_label = QLabel(
            _i18n('Customization hint').format(plugin=PLUGIN_NAME), Form)
        self.customization_hint_label.setWordWrap(True)
        outer.addWidget(self.customization_hint_label)

        # macOS styles center QFormLayout contents by default; force the
        # left-aligned look the other calibre panes use. The output pane
        # corrects its own forms the same way (_left_align_forms).
        for form in (general_form, markdown_form, images_form):
            form.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
            form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        outer.addStretch(1)

    def get_value_handler(self, g):
        if g is getattr(self, 'opt_input_encoding', None):
            if is_auto_encoding(g.currentText()):
                # The option's unset value means "detect the encoding" to
                # calibre; the pane only gives it a name.
                return None
            # A real encoding name is calibre's own to validate: anything it
            # does not know comes back as None (auto detect) as well.
            return super().get_value_handler(g)
        if g is getattr(self, 'opt_markdown_extensions', None):
            return extensions_to_value(
                name for name, item in self.md_items.items()
                if item.checkState() == self._checked)
        if g in (getattr(self, 'opt_md_line_break', None),
                 getattr(self, 'opt_paragraph_type', None)):
            return g.currentData()
        return super().get_value_handler(g)

    def set_value_handler(self, g, val):
        if g is getattr(self, 'opt_input_encoding', None):
            text = str(val).strip() if val else ''
            g.setEditText(text or AUTO_ENCODING)
            return True
        if g is getattr(self, 'opt_markdown_extensions', None):
            wanted = extensions_from_value(val)
            for name, item in self.md_items.items():
                item.setCheckState(
                    self._checked if name in wanted else self._unchecked)
            return True
        if g in (getattr(self, 'opt_md_line_break', None),
                 getattr(self, 'opt_paragraph_type', None)):
            index = g.findData(val)
            g.setCurrentIndex(index if index >= 0 else 0)
            return True
        return False

    def connect_gui_obj_handler(self, gui_obj, slot):
        if gui_obj is not getattr(self, 'opt_markdown_extensions', None):
            raise NotImplementedError()
        gui_obj.itemChanged.connect(slot)

    def _translated_help(self, get_help):
        """Translate the option help texts shown as tooltips.

        calibre hands us the help string declared on each
        OptionRecommendation; route it through the plugin i18n table (the
        English text is the key) so the tips follow the plugin UI language.
        """
        def provider(name):
            try:
                text = get_help(name)
            except Exception:
                return None
            if not isinstance(text, str) or not text:
                return text
            return _i18n(text)
        return provider
