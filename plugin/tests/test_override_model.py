# -*- coding: utf-8 -*-
"""The override model decides which global settings actually apply."""

from calibre_plugins.markdown.utils.override_model import GlobalOverrideModel
from calibre_plugins.markdown.utils.prefs import (
    DEFAULTS,
    INPUT_OPTION_KEYS,
    serialize_customization,
)


def test_nothing_enabled_by_default():
    assert GlobalOverrideModel().overrides() == {}


def test_enable_then_disable():
    model = GlobalOverrideModel()
    model.set('inline_toc', False, enabled=True)
    assert model.overrides() == {'inline_toc': False}
    model.set('inline_toc', False, enabled=False)
    assert model.overrides() == {}


def test_loads_existing_customization_and_unknown_keys():
    model = GlobalOverrideModel.from_customization(
        serialize_customization({'yaml_front_matter': False, 'ghost': 1}))
    assert model.overrides() == {'yaml_front_matter': False}
    assert model.is_enabled('yaml_front_matter')


def test_disabled_key_reports_default_value():
    model = GlobalOverrideModel()
    assert model.is_enabled('inline_toc') is False
    assert model.value('inline_toc') == DEFAULTS['inline_toc']


def test_image_output_mode_present():
    model = GlobalOverrideModel()
    model.set('image_output_mode', 'inline', enabled=True)
    assert model.overrides() == {'image_output_mode': 'inline'}


def test_load_keeps_enabled_values_only():
    raw = serialize_customization({'inline_toc': False})
    model = GlobalOverrideModel.from_customization(raw)
    model.set('newline', 'windows', enabled=False)
    assert model.overrides() == {'inline_toc': False}
    assert model.value('newline') == 'windows'


def test_the_two_dialogs_own_disjoint_key_sets():
    # Each dialog passes the key set it owns, so a payload can never drive the
    # other side's options (calibre stores one payload per plugin name).
    raw = serialize_customization(
        {'inline_toc': False, 'md_line_break': 'hard'})
    output_model = GlobalOverrideModel.from_customization(raw)
    input_model = GlobalOverrideModel.from_customization(raw, INPUT_OPTION_KEYS)
    assert output_model.overrides() == {'inline_toc': False}
    assert input_model.overrides() == {'md_line_break': 'hard'}
