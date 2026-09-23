# -*- coding: utf-8 -*-
"""Which language the plugin's own UI texts are rendered in.

calibre's UI language decides it: Chinese reads the Simplified Chinese table,
every other language the English one. The wording itself lives in
translations.messages, whose lookup asks get_ui_language() here - the import
runs inside the function that needs it, so the two translation modules can
import each other freely.
"""

__license__ = 'GPL 3'

#: UI language codes: 0=English, 1=Simplified Chinese.
UI_LANG_EN = 0
UI_LANG_ZH_CN = 1

#: The language found for calibre, or None while it has not been read yet.
_current_ui_lang = None


def set_ui_language(lang_index):
    """Pin the UI language, or None to read calibre's again (tests only)."""
    global _current_ui_lang
    _current_ui_lang = (
        lang_index if lang_index in (UI_LANG_EN, UI_LANG_ZH_CN) else None)


def get_ui_language():
    """The language the message table is read in, detected on first use.

    calibre wants a restart after a language change, so what was read once
    stays for the session.
    """
    global _current_ui_lang
    if _current_ui_lang is None:
        _current_ui_lang = detect_calibre_ui_language()
    return _current_ui_lang


def detect_calibre_ui_language():
    """The plugin language calibre's UI language maps to.

    Any Chinese variant - Simplified or Traditional, however it is spelled -
    reads the Chinese table, since that is the only Chinese the plugin has;
    every other language reads the English source strings. A calibre that
    cannot be asked (the test environment) falls back to English.
    """
    try:
        from calibre.utils.localization import get_lang
        lang = (get_lang() or '').replace('-', '_').lower()
    except Exception:
        return UI_LANG_EN
    if lang.startswith('zh'):
        return UI_LANG_ZH_CN
    return UI_LANG_EN
