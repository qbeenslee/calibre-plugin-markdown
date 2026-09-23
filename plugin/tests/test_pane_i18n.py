# -*- coding: utf-8 -*-
"""The conversion pane exposes labels and hints in the plugin UI language.

Option help ("hints") shown as tooltips and the image note / newline labels
must follow the plugin UI language, not stay English.
"""

import pytest

from calibre_plugins.markdown.output.conversion_ui import NEWLINE_LABELS, PluginWidget
from calibre_plugins.markdown.output.output_plugin import MarkdownOutput
from calibre_plugins.markdown.translations.messages import _ as _i18n
from calibre_plugins.markdown.translations.ui_language import (
    UI_LANG_EN,
    UI_LANG_ZH_CN,
    _current_ui_lang,
    set_ui_language,
)

pytestmark = pytest.mark.usefixtures('reset_ui_language')


@pytest.fixture
def reset_ui_language():
    previous = _current_ui_lang
    set_ui_language(UI_LANG_EN)
    yield
    set_ui_language(previous)


def _pane(options=('inline_toc', 'newline', 'paragraph_style')):
    pane = PluginWidget.__new__(PluginWidget)
    pane._options = list(options)
    return pane


def test_help_provider_translates_known_option():
    set_ui_language(UI_LANG_ZH_CN)
    pane = _pane()
    provider = pane._translated_help(lambda name: 'Add Table of Contents to beginning of the book.')
    assert provider('inline_toc') == '在全书开头插入目录。'


def test_help_provider_passes_through_unknown_text():
    set_ui_language(UI_LANG_ZH_CN)
    pane = _pane()
    unknown = 'Some text that is not in the i18n table.'
    # Sanity: _i18n returns the input when the key is unknown.
    assert _i18n(unknown) == unknown
    provider = pane._translated_help(lambda name: unknown)
    assert provider('whatever') == unknown


def test_help_provider_returns_none_for_missing_help():
    pane = _pane()

    def boom(name):
        raise KeyError(name)

    provider = pane._translated_help(boom)
    assert provider('inline_toc') is None


def test_every_option_help_has_chinese_translation():
    set_ui_language(UI_LANG_ZH_CN)
    for op in MarkdownOutput.options:
        help_text = op.option.help
        if not help_text:
            continue
        # newline lists the concrete NEWLINE_TYPES, which differ between the
        # stubbed test environment and a real calibre; it is covered explicitly
        # below, so skip it here.
        if op.option.name == 'newline':
            continue
        translated = _i18n(help_text)
        assert translated != help_text, (
            'option %r help not translated: %r' % (op.option.name, help_text))
        assert any(ord(c) > 0x4e00 for c in translated)


class Combo:
    """Stand-in for a QComboBox whose items carry the raw value as data."""

    def __init__(self, data):
        self._data = data
        self.index = None

    def currentData(self):
        return self._data

    def findData(self, val):
        return 0 if val == self._data else -1

    def setCurrentIndex(self, i):
        self.index = i


def test_newline_combo_commits_raw_value():
    pane = _pane()
    combo = Combo('unix')
    pane.opt_newline = combo
    assert pane.get_value_handler(combo) == 'unix'
    assert pane.set_value_handler(combo, 'windows') is True
    assert combo.index == 0


def test_image_output_mode_combo_commits_raw_value():
    # Without the handler calibre would commit currentText() - the localized
    # label - and convert() would report an unknown image output mode.
    pane = _pane()
    combo = Combo('sidecar')
    pane.opt_image_output_mode = combo
    assert pane.get_value_handler(combo) == 'sidecar'
    assert pane.set_value_handler(combo, 'inline') is True
    assert combo.index == 0


def test_image_export_row_labels_are_localized():
    # "Export image files" / "Image output mode:" are shared with the
    # customization dialog, so both must resolve in each UI language.
    for key in ('Export image files', 'Image output mode:'):
        set_ui_language(UI_LANG_EN)
        en = _i18n(key)
        set_ui_language(UI_LANG_ZH_CN)
        zh = _i18n(key)
        assert en and zh and en != zh, (
            'label %r did not localize: en=%r zh=%r' % (key, en, zh))
        assert any(ord(c) > 0x4e00 for c in zh)
        assert not any(ord(c) > 0x4e00 for c in en)
    set_ui_language(UI_LANG_EN)


def test_images_group_labels_are_localized():
    # The pane's "Images" group title and the row names it sets itself must
    # resolve in both languages; calibre's own .ui labels for the link and
    # alt-text rows follow calibre's language, so the pane renames them
    # through the plugin table.
    for key in ('Images', 'Keep images', 'Image sizes',
                'Replace images by their alt attribute text',
                'Keep links (<a> tags)'):
        set_ui_language(UI_LANG_EN)
        en = _i18n(key)
        set_ui_language(UI_LANG_ZH_CN)
        zh = _i18n(key)
        assert en and zh and en != zh, (
            'label %r did not localize: en=%r zh=%r' % (key, en, zh))
        assert any(ord(c) > 0x4e00 for c in zh), key
        assert not any(ord(c) > 0x4e00 for c in en), key
    set_ui_language(UI_LANG_EN)


def test_image_mode_labels_cover_the_modes_the_pane_shows():
    # The pane fills its combo from IMAGE_MODE_LABELS; a mode without an
    # entry would show up as the raw value in every language.
    from calibre_plugins.markdown.output.conversion_ui import (
        IMAGE_MODE_LABELS,
        IMAGE_OUTPUT_MODES,
    )
    set_ui_language(UI_LANG_ZH_CN)
    for value in IMAGE_OUTPUT_MODES:
        label = _i18n(IMAGE_MODE_LABELS[value])
        assert label != IMAGE_MODE_LABELS[value]
        assert any(ord(c) > 0x4e00 for c in label)
    set_ui_language(UI_LANG_EN)


def test_newline_labels_cover_calibre_newline_types():
    # NEWLINE_LABELS must have a key for every value calibre can hand us,
    # otherwise the combo would show the raw English value.
    from calibre.ebooks.conversion.plugins.txt_output import NEWLINE_TYPES
    for value in NEWLINE_TYPES:
        assert value in NEWLINE_LABELS


def test_combobox_option_labels_translate_both_ways():
    # The image-mode and paragraph-style comboboxes (shown in both the
    # customization dialog and the conversion pane) must have a translation in
    # each language; otherwise switching UI language leaves the dropdown items
    # in one language. The i18n source strings below mirror the option tuples
    # in output/preference_ui.py / output/conversion_ui.py.
    option_labels = (
        'Images next to the Markdown file',
        'Images embedded as data URIs',
        'Do not export images',
        'Paragraph style block',
        'Paragraph style single',
    )
    for label_key in option_labels:
        set_ui_language(UI_LANG_EN)
        en = _i18n(label_key)
        set_ui_language(UI_LANG_ZH_CN)
        zh = _i18n(label_key)
        # Each language yields a distinct, non-empty string; Chinese carries CJK.
        assert en and zh and en != zh, (
            'label %r did not localize: en=%r zh=%r' % (label_key, en, zh))
        assert any(ord(c) > 0x4e00 for c in zh)
        assert not any(ord(c) > 0x4e00 for c in en)
    set_ui_language(UI_LANG_EN)


def test_paragraph_style_labels_present_in_i18n():
    # PARAGRAPH_STYLE_LABELS keys (preference_ui.py / conversion_ui.py) must resolve to
    # translated strings so the conversion pane combo shows localized text, not
    # the raw 'block'/'single'.
    from calibre_plugins.markdown.output.conversion_ui import PARAGRAPH_STYLE_LABELS
    set_ui_language(UI_LANG_ZH_CN)
    for value in ('block', 'single'):
        label = _i18n(PARAGRAPH_STYLE_LABELS[value])
        assert label != PARAGRAPH_STYLE_LABELS[value]
        assert any(ord(c) > 0x4e00 for c in label)
    set_ui_language(UI_LANG_EN)


def test_download_remote_images_label_is_localized():
    # The pane's "Download remote images" checkbox (conversion_ui) shares
    # its label with the customization dialog row, like the other image rows.
    set_ui_language(UI_LANG_EN)
    assert _i18n('Download remote images') == 'Download remote images'
    set_ui_language(UI_LANG_ZH_CN)
    label = _i18n('Download remote images')
    assert label == '下载远程图片'
    assert any(ord(c) > 0x4e00 for c in label)
    set_ui_language(UI_LANG_EN)


def test_yaml_front_matter_row_label_is_localized():
    # The pane's "Add YAML front matter" checkbox (conversion_ui) reads its
    # label from the plugin table, like the other Markdown rows.
    set_ui_language(UI_LANG_EN)
    assert _i18n('Add YAML front matter') == 'Add YAML front matter'
    set_ui_language(UI_LANG_ZH_CN)
    label = _i18n('Add YAML front matter')
    assert label == '添加 YAML 文首元数据'
    assert any(ord(c) > 0x4e00 for c in label)
    set_ui_language(UI_LANG_EN)


def test_customization_hint_points_at_each_plugin():
    # Both panes end with a line sending the user to that plugin's "Customize
    # plugin" dialog; it must read in the UI language and name the plugin the
    # way calibre lists it (the key its customization payload is stored under).
    from calibre_plugins.markdown.input import conversion_ui as input_ui
    from calibre_plugins.markdown.input.input_plugin import MarkdownInput
    from calibre_plugins.markdown.output import conversion_ui as output_ui

    assert output_ui.PLUGIN_NAME == MarkdownOutput.name
    assert input_ui.PLUGIN_NAME == MarkdownInput.name
    set_ui_language(UI_LANG_EN)
    en = _i18n('Customization hint').format(plugin=output_ui.PLUGIN_NAME)
    assert 'Markdown Output' in en and 'Customize plugin' in en
    set_ui_language(UI_LANG_ZH_CN)
    zh = _i18n('Customization hint').format(plugin=input_ui.PLUGIN_NAME)
    assert 'Markdown Input' in zh and '自定义插件' in zh
    assert any(ord(c) > 0x4e00 for c in zh)
    set_ui_language(UI_LANG_EN)


def test_pane_titles_are_localized():
    # The Convert dialog lists each pane by its TITLE: the output pane shows
    # "Markdown output" (like the builtin "TXT output" / "EPUB output" panes),
    # the input pane "Markdown input". Both are plugin-table lookups, so
    # Chinese must differ from the English source string.
    for key in ('Markdown output', 'Markdown input'):
        set_ui_language(UI_LANG_EN)
        assert _i18n(key) == key
        set_ui_language(UI_LANG_ZH_CN)
        zh = _i18n(key)
        assert zh != key, key
        assert any(ord(c) > 0x4e00 for c in zh), key
    set_ui_language(UI_LANG_EN)
    # English fallback used before apply_translations() has run.
    assert PluginWidget.TITLE == 'Markdown output'
