# -*- coding: utf-8 -*-
"""The plugin UI language is calibre's, with no setting of the plugin's own.

Chinese (Simplified or Traditional) reads the Simplified Chinese table, every
other language the English source strings. The suite pins a language through
set_ui_language() where it wants a specific table; these tests cover the
detection behind it and the removal of the old preference.
"""

import pathlib

import pytest

from calibre_plugins.markdown.translations import messages, ui_language
from calibre_plugins.markdown.translations.messages import _ as _i18n
from calibre_plugins.markdown.utils import prefs as prefs_module

PREFERENCE_UI = (pathlib.Path(__file__).resolve().parents[1]
                 / 'Markdown' / 'output' / 'preference_ui.py')

UI_LANG_EN = ui_language.UI_LANG_EN
UI_LANG_ZH_CN = ui_language.UI_LANG_ZH_CN


@pytest.fixture(autouse=True)
def language_is_not_left_pinned():
    """Unpin the language per test and restore the previous state after it.

    Detection caches what it read, so a test that makes calibre look Chinese
    must not leave the rest of the session on the Chinese table.
    """
    previous = ui_language._current_ui_lang
    ui_language.set_ui_language(None)
    yield
    ui_language.set_ui_language(previous)


@pytest.fixture
def calibre_language(monkeypatch):
    """Make calibre's get_lang() report the value the test wants."""
    import calibre.utils.localization as localization

    def set_lang(lang):
        monkeypatch.setattr(localization, 'get_lang', lambda: lang,
                            raising=False)

    return set_lang


def test_chinese_calibre_ui_reads_the_chinese_table(calibre_language):
    # get_lang() returns calibre's stored code, while CALIBRE_OVERRIDE_LANG
    # passes through as the user typed it, so spellings like 'zh-Hans' count
    # as Chinese too. Traditional Chinese reads the same table: Simplified
    # Chinese is the only Chinese the plugin has.
    for lang in ('zh_CN', 'zh', 'zh_SG', 'zh_TW', 'zh-HK', 'zh-Hans'):
        calibre_language(lang)
        assert ui_language.detect_calibre_ui_language() == UI_LANG_ZH_CN, lang


def test_other_calibre_ui_languages_read_the_english_table(calibre_language):
    for lang in ('en', 'en_US', 'de_DE', 'ja', ''):
        calibre_language(lang)
        assert ui_language.detect_calibre_ui_language() == UI_LANG_EN, lang


def test_calibre_that_cannot_be_asked_reads_the_english_table(monkeypatch):
    # The test venv has no calibre to ask: the import or the call fails and
    # English is the fallback instead of an exception out of a label lookup.
    import calibre.utils.localization as localization

    monkeypatch.delattr(localization, 'get_lang', raising=False)
    assert ui_language.detect_calibre_ui_language() == UI_LANG_EN

    def boom():
        raise RuntimeError('calibre prefs are not there yet')

    monkeypatch.setattr(localization, 'get_lang', boom, raising=False)
    assert ui_language.detect_calibre_ui_language() == UI_LANG_EN


def test_first_lookup_reads_calibre(calibre_language):
    calibre_language('zh_CN')
    assert ui_language.get_ui_language() == UI_LANG_ZH_CN
    # The message table follows the language the lookup returned.
    assert _i18n('Markdown output') == 'Markdown 输出'


def test_language_is_read_once_per_process(calibre_language):
    # calibre asks for a restart after a language change, so the read is
    # cached: a running session keeps the language calibre was started with.
    calibre_language('zh_CN')
    assert ui_language.get_ui_language() == UI_LANG_ZH_CN
    calibre_language('en_US')
    assert ui_language.get_ui_language() == UI_LANG_ZH_CN


def test_pinned_language_wins_over_calibre(calibre_language):
    calibre_language('zh_CN')
    ui_language.set_ui_language(UI_LANG_EN)
    assert ui_language.get_ui_language() == UI_LANG_EN
    assert _i18n('Markdown output') == 'Markdown output'


def test_unpinning_resumes_calibre_detection(calibre_language):
    ui_language.set_ui_language(UI_LANG_EN)
    calibre_language('zh_CN')
    ui_language.set_ui_language(None)
    assert ui_language.get_ui_language() == UI_LANG_ZH_CN


def test_language_setting_is_gone():
    # The dialog row, its prefs key and the functions behind it are gone: the
    # language is calibre's to decide now.
    assert 'ui_language' not in prefs_module.DEFAULTS
    for name in ('stored_ui_language', 'save_ui_language',
                 'ensure_prefs_initialized'):
        assert not hasattr(prefs_module, name), name
    for name in ('apply_ui_language_from_prefs', 'ui_language_combo_items'):
        assert not hasattr(ui_language, name), name
    for key in ('Interface language:', 'English', 'Simplified Chinese'):
        assert key not in messages._MESSAGES, key


def test_customization_dialog_shows_no_language_row():
    # The venv has no Qt, so the dialog cannot be built here; the source not
    # mentioning the row is as close as the suite can get to the dialog.
    source = PREFERENCE_UI.read_text('utf-8')
    assert 'ui_lang' not in source
    assert 'Interface language' not in source


def test_conversion_panes_do_not_touch_the_language_setting():
    # Importing them proves the module imports were cleaned up with the calls.
    from calibre_plugins.markdown.input import conversion_ui as input_pane
    from calibre_plugins.markdown.output import conversion_ui as output_pane

    for module in (input_pane, output_pane):
        assert not hasattr(module, 'apply_ui_language_from_prefs')
