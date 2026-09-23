# -*- coding: utf-8 -*-
"""The input plugin's "Customize plugin" wiring.

The dialog itself needs a real widget toolkit (input/preference_ui.py imports
Qt at module level, the way calibre's own plugin dialogs do), so the tests
here cover the plugin-side plumbing: which stored payload reaches the dialog,
what save_settings() stores, and that the dialog owns the input key set. The
dialog's own value handling is verified on the real thing by
scripts/verify_md_input_prefs.py.
"""

import sys
import types

import pytest

from calibre_plugins.markdown.input.input_plugin import MarkdownInput
from calibre_plugins.markdown.utils.prefs import (
    EXPORT_OPTION_KEYS,
    INPUT_OPTION_KEYS,
    parse_customization,
    serialize_customization,
)

DIALOG_MODULE = 'calibre_plugins.markdown.input.preference_ui'


class _FakeConfigWidget:
    """Stand-in for input.preference_ui.ConfigWidget (no Qt in the venv)."""

    def __init__(self, customization=''):
        self.customization = customization
        self.enabled = {'md_line_break': 'hard'}

    def overrides(self):
        return dict(self.enabled)


@pytest.fixture
def fake_dialog(monkeypatch):
    module = types.ModuleType(DIALOG_MODULE)
    module.ConfigWidget = _FakeConfigWidget
    monkeypatch.setitem(sys.modules, DIALOG_MODULE, module)
    return _FakeConfigWidget


def test_is_customizable():
    # Preferences -> Plugins only enables the button when this is True.
    assert MarkdownInput().is_customizable() is True


def test_config_widget_receives_the_stored_payload(monkeypatch, fake_dialog):
    import calibre.customize.ui as customize_ui

    raw = serialize_customization({'md_line_break': 'hard'})
    monkeypatch.setattr(customize_ui, 'plugin_customization',
                        lambda plugin: raw, raising=False)

    widget = MarkdownInput().config_widget()

    assert isinstance(widget, fake_dialog)
    assert widget.customization == raw


def test_config_widget_survives_a_broken_lookup(monkeypatch, fake_dialog):
    import calibre.customize.ui as customize_ui

    def boom(plugin):
        raise RuntimeError('no config')

    monkeypatch.setattr(customize_ui, 'plugin_customization', boom,
                        raising=False)

    assert MarkdownInput().config_widget().customization == ''


def test_save_settings_stores_a_versioned_payload(monkeypatch):
    import calibre.customize.ui as customize_ui

    seen = {}
    monkeypatch.setattr(
        customize_ui, 'customize_plugin',
        lambda plugin, custom: seen.update(plugin=plugin, custom=custom),
        raising=False)
    plugin = MarkdownInput()

    plugin.save_settings(_FakeConfigWidget())

    assert seen['plugin'] is plugin
    # Only the enabled keys are stored, tagged with the payload version.
    assert parse_customization(seen['custom']) == {'md_line_break': 'hard'}


def test_the_dialog_owns_the_input_options():
    assert set(INPUT_OPTION_KEYS) == {
        'input_encoding', 'md_line_break', 'paragraph_type',
        'read_yaml_metadata', 'keep_images', 'embed_images',
        'download_remote_images', 'keep_image_sizes',
        'markdown_extensions'}
    # The two dialogs store their payloads in separate plugin slots. Both
    # sides now show a download_remote_images switch (and the size option):
    # a name shared across slots carries the same meaning on each side.
    assert set(INPUT_OPTION_KEYS) & set(EXPORT_OPTION_KEYS) == {
        'keep_image_sizes', 'download_remote_images'}
