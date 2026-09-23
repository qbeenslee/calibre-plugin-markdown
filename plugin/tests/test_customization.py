# -*- coding: utf-8 -*-
"""Global overrides are stored in the plugin's site customization string."""

import json

from calibre_plugins.markdown.utils.prefs import (
    CUSTOMIZATION_VERSION,
    DEFAULTS,
    DEFAULT_IMAGE_OUTPUT_MODE,
    EXPORT_OPTION_KEYS,
    IMAGE_OUTPUT_MODES,
    parse_customization,
    serialize_customization,
)


def test_roundtrip():
    raw = serialize_customization({'inline_toc': False, 'image_output_mode': 'inline'})
    assert parse_customization(raw) == {'inline_toc': False, 'image_output_mode': 'inline'}


def test_empty_and_garbage_return_empty():
    assert parse_customization('') == {}
    assert parse_customization(None) == {}
    assert parse_customization('{not json') == {}


def test_non_dict_or_unknown_version_ignored():
    assert parse_customization('[1, 2]') == {}
    assert parse_customization('{"version": 99, "overrides": {"a": 1}}') == {}


def test_serialized_has_version():
    payload = json.loads(serialize_customization({}))
    assert payload['version'] == CUSTOMIZATION_VERSION
    assert payload['overrides'] == {}


def test_image_output_mode_is_registered():
    assert 'image_output_mode' in EXPORT_OPTION_KEYS
    assert 'image_output_mode' in DEFAULTS
    assert DEFAULTS['image_output_mode'] == DEFAULT_IMAGE_OUTPUT_MODE
    assert DEFAULT_IMAGE_OUTPUT_MODE in IMAGE_OUTPUT_MODES
