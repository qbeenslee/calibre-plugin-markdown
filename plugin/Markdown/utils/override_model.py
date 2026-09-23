# -*- coding: utf-8 -*-
"""Which global overrides the user enabled in the customization dialog.

Kept free of Qt so the semantics ("only explicitly enabled keys override the
conversion dialog") are testable without a widget toolkit.
"""

from calibre_plugins.markdown.utils.prefs import (
    DEFAULTS,
    EXPORT_OPTION_KEYS,
    parse_customization,
)


class GlobalOverrideModel:

    def __init__(self):
        self._enabled = set()
        self._values = {}

    @classmethod
    def from_customization(cls, raw, keys=EXPORT_OPTION_KEYS):
        '''Model of the overrides stored in `raw`.

        `keys` are the option names the calling dialog owns, so a payload
        written by the other side's dialog never leaks in: the input and
        output plugins keep their customization in separate slots.
        '''
        model = cls()
        for key, value in parse_customization(raw).items():
            if key in keys:
                model.set(key, value, enabled=True)
        return model

    def is_enabled(self, key):
        return key in self._enabled

    def value(self, key):
        if key in self._values:
            return self._values[key]
        return DEFAULTS.get(key)

    def set(self, key, value, enabled=True):
        self._values[key] = value
        if enabled:
            self._enabled.add(key)
        else:
            self._enabled.discard(key)

    def overrides(self):
        return {key: self._values[key] for key in self._enabled if key in self._values}
