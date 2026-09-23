# -*- coding: utf-8 -*-
"""The conversion dialog's Markdown input pane: plumbing and guards.

No Qt here: the pane's value handlers only touch the widgets they are
handed, so stand-ins for the combobox / checklist are enough.
"""

import types

import pytest

from calibre_plugins.markdown.input.conversion_ui import (
    AUTO_ENCODING,
    EXTENSIONS,
    IMAGE_DEPENDENT_OPTIONS,
    IMAGE_GROUP_OPTIONS,
    IMAGE_GROUP_ROWS,
    IMAGE_ROW_GATES,
    LINE_BREAK_LABELS,
    OPTION,
    PARAGRAPH_CHOICES,
    PARAGRAPH_LABELS,
    PluginWidget,
    is_auto_encoding,
)
from calibre_plugins.markdown.input.input_plugin import MarkdownInput
from calibre_plugins.markdown.translations import messages, ui_language
from calibre_plugins.markdown.translations.messages import _ as _i18n
from calibre_plugins.markdown.utils.prefs import serialize_customization

#: calibre's Widget.get_value_handler() sentinel for "not handled here":
#: Widget.get_value() then applies its own per-type handling.
_UNHANDLED = 'this is a dummy return value, xcswx1avcx4x'


@pytest.fixture
def reset_ui_language():
    previous = ui_language._current_ui_lang
    ui_language.set_ui_language(ui_language.UI_LANG_EN)
    yield
    ui_language.set_ui_language(previous)


class _Item:
    """QListWidgetItem stand-in."""

    def __init__(self, name):
        self.name = name
        self.state = 'unchecked'

    def checkState(self):
        return self.state

    def setCheckState(self, state):
        self.state = state


class _Combo:
    """QComboBox stand-in keyed by item data."""

    def __init__(self, values):
        self.values = list(values)
        self.index = 0

    def currentData(self):
        return self.values[self.index]

    def findData(self, value):
        return self.values.index(value) if value in self.values else -1

    def setCurrentIndex(self, index):
        self.index = index


class _EncodingCombo:
    """EncodingComboBox stand-in: editable text over a list of entries."""

    def __init__(self, items=('', 'utf-8', 'gbk')):
        self.items = list(items)
        self.index = 0
        self.text = self.items[0]

    def currentText(self):
        return self.text

    def setItemText(self, index, text):
        self.items[index] = text
        if self.index == index:
            self.text = text

    def setEditText(self, text):
        self.text = text
        if text in self.items:
            self.index = self.items.index(text)


def _pane(extension_names=('tables', 'fenced_code')):
    pane = PluginWidget.__new__(PluginWidget)
    pane._checked = 'checked'
    pane._unchecked = 'unchecked'
    pane.md_items = {name: _Item(name) for name in extension_names}
    pane.opt_markdown_extensions = object()
    return pane


def test_extension_value_comes_from_the_checked_boxes():
    pane = _pane()
    pane.md_items['fenced_code'].state = 'checked'
    assert pane.get_value_handler(pane.opt_markdown_extensions) == 'fenced_code'


def test_extension_value_restores_the_boxes():
    pane = _pane()
    assert pane.set_value_handler(
        pane.opt_markdown_extensions, 'tables, fenced_code') is True
    assert pane.md_items['tables'].state == 'checked'
    assert pane.md_items['fenced_code'].state == 'checked'
    assert pane.get_value_handler(pane.opt_markdown_extensions) == (
        'tables, fenced_code')


def test_extension_value_replaces_the_previous_selection():
    pane = _pane()
    pane.md_items['tables'].state = 'checked'
    assert pane.set_value_handler(pane.opt_markdown_extensions, 'nope') is True
    assert pane.md_items['tables'].state == 'unchecked'
    assert pane.get_value_handler(pane.opt_markdown_extensions) == ''


def test_extension_list_widget_owns_the_change_signal():
    pane = _pane()
    connected = []
    pane.opt_markdown_extensions = types.SimpleNamespace(
        itemChanged=types.SimpleNamespace(connect=connected.append))
    slot = object()

    pane.connect_gui_obj_handler(pane.opt_markdown_extensions, slot)

    assert connected == [slot]


def test_other_widgets_are_not_handled_here():
    pane = _pane()
    with pytest.raises(NotImplementedError):
        pane.connect_gui_obj_handler(object(), object())


def test_combo_values_use_item_data():
    pane = _pane()
    for name, values in (('opt_md_line_break', ['fold', 'hard']),
                         ('opt_paragraph_type', ['auto', 'single'])):
        combo = _Combo(values)
        setattr(pane, name, combo)
        assert pane.set_value_handler(combo, values[-1]) is True
        assert combo.index == len(values) - 1
        assert pane.get_value_handler(combo) == values[-1]


def test_unknown_combo_value_falls_back_to_the_first_item():
    pane = _pane()
    combo = _Combo(['auto', 'single'])
    pane.opt_paragraph_type = combo

    assert pane.set_value_handler(combo, 'nope') is True

    assert combo.index == 0


def test_encoding_value_shows_auto_for_the_unset_option():
    pane = _pane()
    combo = _EncodingCombo()
    pane.opt_input_encoding = combo

    # calibre's unset value means "detect the encoding": the pane names it
    # instead of leaving the combo's blank first entry showing.
    assert pane.set_value_handler(combo, None) is True
    assert combo.currentText() == AUTO_ENCODING
    assert pane.set_value_handler(combo, '   ') is True
    assert combo.currentText() == AUTO_ENCODING
    assert pane.set_value_handler(combo, 'gbk') is True
    assert combo.currentText() == 'gbk'


def test_auto_encoding_commits_as_the_unset_option_value():
    pane = _pane()
    combo = _EncodingCombo((AUTO_ENCODING, 'utf-8', 'gbk'))
    pane.opt_input_encoding = combo

    assert pane.get_value_handler(combo) is None
    combo.setEditText('Auto ')          # typed by hand, loosely spelled
    assert pane.get_value_handler(combo) is None
    combo.setEditText('gbk')
    # A real name goes back to calibre's own EncodingComboBox handling, which
    # validates it and maps unknown names to None (auto detect) as well.
    assert pane.get_value_handler(combo) == _UNHANDLED


def test_auto_encoding_label_is_recognized_loosely():
    # The conversion pane and the customization dialog share this test, so
    # both treat hand-typed spellings the same way.
    assert is_auto_encoding('auto') is True
    assert is_auto_encoding(' Auto ') is True
    assert is_auto_encoding('AUTO') is True
    assert is_auto_encoding('gbk') is False
    assert is_auto_encoding('') is False
    assert is_auto_encoding(None) is False


def test_pane_options_are_declared_by_the_plugin():
    # Every opt_<name> the pane builds must be resolvable by calibre's
    # get_option_by_name, otherwise initialize_options() fails at runtime.
    names = {opt.option.name for opt in MarkdownInput.options}
    names |= {opt.option.name for opt in MarkdownInput.common_options}
    assert set(OPTION) <= names


def test_pane_commits_under_its_own_name():
    # Kept apart from the builtin TXT Input pane's 'txt_input' defaults.
    assert PluginWidget.COMMIT_NAME == 'markdown_input'


def test_image_rows_form_their_own_group():
    # The four image switches live in a group box of their own, a sibling of
    # the Markdown group: "Keep images" first, "Image sizes" second, and
    # neither of them left in the group the text options use.
    assert IMAGE_GROUP_OPTIONS == (
        'keep_images', 'keep_image_sizes', 'embed_images',
        'download_remote_images')
    assert set(IMAGE_GROUP_OPTIONS) <= set(OPTION)
    assert set(OPTION) - set(IMAGE_GROUP_OPTIONS) == {
        'input_encoding', 'md_line_break', 'paragraph_type',
        'read_yaml_metadata', 'markdown_extensions'}


class _CheckBox:
    """QCheckBox stand-in: records the enabled flag and the wired slots."""

    def __init__(self, checked=True):
        self.checked = checked
        self.enabled = True
        self.slots = []
        self.toggled = types.SimpleNamespace(connect=self.slots.append)

    def isChecked(self):
        return self.checked

    def setEnabled(self, flag):
        self.enabled = flag


def _image_pane(checked=True, names=None):
    """Bare pane whose image rows are stand-ins (no Qt in the test venv)."""
    pane = _pane()
    pane.opt_keep_images = _CheckBox(checked)
    pane.image_rows = {}
    for name in (IMAGE_DEPENDENT_OPTIONS if names is None else names):
        row = _CheckBox()
        pane.image_rows[name] = row
        setattr(pane, 'opt_' + name, row)
    return pane


def test_image_dependent_rows_are_the_rest_of_the_group():
    # "Keep images" governs every other row of the Images group; both tuples
    # come from the group's own table, so a row added later cannot be
    # forgotten here, and the master switch never disables itself.
    assert set(IMAGE_DEPENDENT_OPTIONS) | {'keep_images'} == set(
        IMAGE_GROUP_OPTIONS)
    assert 'keep_images' not in IMAGE_DEPENDENT_OPTIONS


def test_image_rows_are_disabled_while_keep_images_is_off():
    pane = _image_pane(checked=False)

    pane._sync_image_rows()

    greyed = {name for name, row in pane.image_rows.items() if not row.enabled}
    assert greyed == set(pane.image_rows)
    # The master switch stays clickable - that is how the images come back.
    assert pane.opt_keep_images.enabled is True

    pane.opt_keep_images.checked = True
    pane._sync_image_rows()

    assert [name for name, row in pane.image_rows.items() if not row.enabled] == []


def test_rows_without_a_widget_are_skipped():
    # The pane must survive a row that never got built (the loop reads
    # opt_<name> through getattr, the way apply_global_overrides does).
    pane = _image_pane(checked=False, names=('keep_image_sizes',))

    pane._sync_image_rows()

    assert pane.image_rows['keep_image_sizes'].enabled is False


def test_wiring_connects_the_switches_and_seeds_the_rows():
    pane = _image_pane(checked=False)

    pane._wire_image_rows()

    assert pane.opt_keep_images.slots == [pane._sync_image_rows]
    assert pane.opt_embed_images.slots == [pane._sync_image_rows]
    assert [name for name, row in pane.image_rows.items() if row.enabled] == []


def test_remote_download_needs_the_local_embed():
    # Second level: with "Embed images" off there is nothing a download
    # could attach to, so the row greys out while the others stay editable.
    pane = _image_pane(checked=True)
    pane.opt_embed_images.checked = False

    pane._sync_image_rows()

    assert pane.image_rows['download_remote_images'].enabled is False
    assert pane.image_rows['keep_image_sizes'].enabled is True
    assert pane.image_rows['embed_images'].enabled is True

    pane.opt_embed_images.checked = True
    pane._sync_image_rows()

    assert pane.image_rows['download_remote_images'].enabled is True


def test_the_gate_and_the_master_switch_stack():
    pane = _image_pane(checked=False)
    pane.opt_embed_images.checked = False

    pane._sync_image_rows()

    assert [name for name, row in pane.image_rows.items() if row.enabled] == []

    # The master switch back on: the gated row stays grey (its own gate is
    # still off) while every other row is editable again.
    pane.opt_keep_images.checked = True
    pane._sync_image_rows()

    assert [name for name, row in pane.image_rows.items() if not row.enabled] \
        == ['download_remote_images']


def test_gates_are_rows_of_the_group():
    # The gate table names rows of the group on both sides of the pair, so
    # neither the gating nor the gated row can be dropped from the pane.
    assert set(IMAGE_ROW_GATES) <= set(IMAGE_DEPENDENT_OPTIONS)
    for name, gate in IMAGE_ROW_GATES.items():
        assert gate in IMAGE_DEPENDENT_OPTIONS, gate
        assert gate != name


def test_image_group_labels_are_translated():
    # Every row of the Images group reads its label from the plugin table, so
    # the group follows the plugin UI language like the other groups.
    for _name, key in IMAGE_GROUP_ROWS:
        assert key in messages._MESSAGES, key


def test_extension_grid_is_calibre_minus_the_governed_ones():
    from calibre.ebooks.conversion.plugins.txt_input import MD_EXTENSIONS

    offered = {name for name, _key in EXTENSIONS}

    assert offered == set(MD_EXTENSIONS) - {'meta', 'nl2br'}


def test_paragraph_choices_stay_within_calibre_choices():
    from calibre.ebooks.conversion.plugins.txt_input import TXTInput

    assert set(PARAGRAPH_CHOICES) <= set(TXTInput.ui_data['paragraph_types'])


@pytest.mark.usefixtures('reset_ui_language')
def test_every_pane_label_has_a_translation():
    keys = [key for _name, key in EXTENSIONS]
    keys += list(LINE_BREAK_LABELS.values())
    keys += list(PARAGRAPH_LABELS.values())
    keys += [label for _name, label in IMAGE_GROUP_ROWS]
    keys += [
        'Markdown input', 'Options specific to Markdown input', 'General',
        'Markdown', 'Images', 'Extensions', 'Input character encoding:',
        'Single line breaks:', 'Input paragraph style:',
        'Read YAML front matter metadata',
    ]
    assert [key for key in keys if key not in messages._MESSAGES] == []


@pytest.mark.usefixtures('reset_ui_language')
def test_group_and_field_labels_are_chinese_in_zh():
    ui_language.set_ui_language(ui_language.UI_LANG_ZH_CN)
    for key in ('General', 'Images', 'Extensions',
                'Input character encoding:', 'Single line breaks:',
                'Input paragraph style:', 'Read YAML front matter metadata',
                'Keep images', 'Image sizes', 'Embed images',
                'Download remote images',
                'Fold single line breaks', 'Hard line breaks (<br>)'):
        translated = _i18n(key)
        assert translated != key, key
        assert any(ord(c) > 0x4e00 for c in translated), key


@pytest.mark.usefixtures('reset_ui_language')
def test_option_help_texts_are_translated_both_ways():
    from calibre_plugins.markdown.input import input_plugin

    for text in (input_plugin._OPTION_HELP_LINE_BREAK,
                 input_plugin._OPTION_HELP_YAML,
                 input_plugin._OPTION_HELP_PARAGRAPH,
                 input_plugin._OPTION_HELP_KEEP_IMAGES,
                 input_plugin._OPTION_HELP_EMBED_IMAGES,
                 input_plugin._OPTION_HELP_DOWNLOAD_REMOTE,
                 input_plugin._OPTION_HELP_KEEP_SIZES,
                 input_plugin._OPTION_HELP_EXTENSIONS):
        assert text in messages._MESSAGES
        assert _i18n(text) == text          # English is the source string
        ui_language.set_ui_language(ui_language.UI_LANG_ZH_CN)
        assert any(ord(c) > 0x4e00 for c in _i18n(text))
        ui_language.set_ui_language(ui_language.UI_LANG_EN)


def test_gui_configuration_widget_builds_the_pane(monkeypatch):
    import calibre.customize.ui as customize_ui

    from calibre_plugins.markdown.input import conversion_ui

    seen = {}

    class FakePane:
        def __init__(self, *args, **kwargs):
            seen['args'] = args
            seen['kwargs'] = kwargs

    monkeypatch.setattr(conversion_ui, 'PluginWidget', FakePane)
    monkeypatch.setattr(
        customize_ui, 'plugin_customization',
        lambda plugin: serialize_customization({'md_line_break': 'hard'}),
        raising=False)

    got = MarkdownInput(None).gui_configuration_widget(
        'parent', 'getopt', 'gethelp', 'db', 919)

    assert isinstance(got, FakePane)
    assert seen['args'] == ('parent', 'getopt', 'gethelp', 'db', 919)
    # The customization dialog's overrides are handed to the pane, which shows
    # them as this conversion's effective values.
    assert seen['kwargs'] == {'overrides': {'md_line_break': 'hard'}}


def _override_pane(options=OPTION):
    pane = _pane()
    pane._options = list(options)
    pane.applied = {}
    pane.set_value = lambda gui_opt, val: pane.applied.__setitem__(gui_opt, val)
    return pane


def test_global_overrides_reach_the_pane_widgets():
    pane = _override_pane()
    pane.opt_md_line_break = 'widget:breaks'
    pane.opt_paragraph_type = 'widget:paragraph'
    pane.apply_global_overrides(
        {'md_line_break': 'hard', 'paragraph_type': 'single'})
    assert pane.applied == {
        'widget:breaks': 'hard', 'widget:paragraph': 'single'}


def test_overrides_outside_the_pane_options_are_skipped():
    # The output dialog's keys are stored under their own plugin name, but a
    # payload handed to this pane may still carry them: only the options this
    # pane displays may be applied.
    pane = _override_pane()
    pane.opt_md_line_break = 'widget:breaks'
    pane.apply_global_overrides({'md_line_break': 'hard', 'inline_toc': False})
    assert pane.applied == {'widget:breaks': 'hard'}


def test_override_without_a_widget_is_skipped():
    pane = _override_pane()
    pane.apply_global_overrides({'md_line_break': 'hard'})
    assert pane.applied == {}


def test_failing_override_is_swallowed():
    pane = _override_pane()

    def boom(gui_opt, val):
        raise ValueError('bad value')

    pane.set_value = boom
    pane.opt_md_line_break = 'widget:breaks'
    pane.apply_global_overrides({'md_line_break': 'hard'})
