# -*- coding: utf-8 -*-
"""The conversion pane reflects the plugin's layering:

calibre's per-book saved settings (whatever the pane committed last time)
are the starting values; the plugin customization payload only fills rows
the book has none for. Rows stay fully editable - what the pane commits is
saved as the book's settings and reaches convert() unchanged.
"""

import sys
import types

from calibre_plugins.markdown.output.conversion_ui import PluginWidget


class StubWidget:
    """The widget apply_global_overrides() feeds a value into."""

    def __init__(self, name, value=None):
        self.name = name
        self.value = value


def _pane(options=('inline_toc', 'paragraph_style'), book_id=None):
    pane = PluginWidget.__new__(PluginWidget)
    pane._options = list(options)
    pane.db = object()
    pane.book_id = book_id
    return pane


def _config_stub(saved):
    module = types.ModuleType('calibre.ebooks.conversion.config')
    module.load_specifics = lambda db, book_id: saved
    return module


def test_book_saved_settings_win_over_the_defaults(monkeypatch):
    monkeypatch.setitem(sys.modules,
                        'calibre.ebooks.conversion.config',
                        _config_stub({'inline_toc': True}))
    pane = _pane(book_id=7)
    applied = {}

    def record(gui_opt, val):
        applied[gui_opt.name] = val

    pane.set_value = record
    toc = StubWidget('toc', value=True)   # calibre's own per-book value
    pane.opt_inline_toc = toc
    pane.apply_global_overrides({'inline_toc': False})
    # The default False was skipped: the book keeps its saved True.
    assert applied == {}
    assert toc.value is True


def test_defaults_fill_rows_without_saved_settings(monkeypatch):
    monkeypatch.setitem(sys.modules,
                        'calibre.ebooks.conversion.config',
                        _config_stub({}))
    pane = _pane(book_id=7)
    applied = {}

    def record(gui_opt, val):
        applied[gui_opt.name] = val

    pane.set_value = record
    toc = StubWidget('toc')
    pane.opt_inline_toc = toc
    pane.apply_global_overrides({'inline_toc': False})
    assert applied == {'toc': False}


def test_no_book_context_means_the_defaults_apply(monkeypatch):
    # The bulk dialog (and scripts) have no per-book settings: the defaults
    # are all there is.
    monkeypatch.setitem(sys.modules,
                        'calibre.ebooks.conversion.config',
                        _config_stub({'never': 'called'}))
    pane = _pane(book_id=None)
    applied = {}

    def record(gui_opt, val):
        applied[gui_opt.name] = val

    pane.set_value = record
    toc = StubWidget('toc')
    pane.opt_inline_toc = toc
    pane.apply_global_overrides({'inline_toc': False})
    assert applied == {'toc': False}


def test_options_without_pane_widget_are_skipped(monkeypatch):
    monkeypatch.setitem(sys.modules,
                        'calibre.ebooks.conversion.config',
                        _config_stub({}))
    pane = _pane(options=('inline_toc',), book_id=None)
    applied = {}

    def record(gui_opt, val):
        applied[gui_opt.name] = val

    pane.set_value = record
    toc = StubWidget('toc')
    pane.opt_inline_toc = toc
    # image_output_mode is a pane option with its own row, but it is not one
    # of this pane's _options here, so it is skipped like any unknown key.
    pane.apply_global_overrides(
        {'inline_toc': True, 'image_output_mode': 'none', 'not_an_option': 1})
    assert applied == {'toc': True}


def test_image_output_mode_override_reaches_its_row(monkeypatch):
    # The new image rows are seeded by the customization payload exactly like
    # the older ones: a book with no saved settings of its own starts from
    # the global value.
    monkeypatch.setitem(sys.modules,
                        'calibre.ebooks.conversion.config',
                        _config_stub({}))
    pane = _pane(options=('export_image_files', 'image_output_mode'),
                 book_id=None)
    applied = {}

    def record(gui_opt, val):
        applied[gui_opt.name] = val

    pane.set_value = record
    pane.opt_export_image_files = StubWidget('files')
    pane.opt_image_output_mode = StubWidget('mode')
    pane.apply_global_overrides(
        {'export_image_files': False, 'image_output_mode': 'inline'})
    assert applied == {'files': False, 'mode': 'inline'}


def test_missing_widget_attribute_is_skipped(monkeypatch):
    monkeypatch.setitem(sys.modules,
                        'calibre.ebooks.conversion.config',
                        _config_stub({}))
    pane = _pane(options=('inline_toc', 'paragraph_style'), book_id=None)
    pane.set_value = lambda gui_opt, val: None
    # No opt_paragraph_style attribute: must not raise.
    pane.apply_global_overrides({'paragraph_style': 'single'})


def test_set_value_failure_is_swallowed(monkeypatch):
    monkeypatch.setitem(sys.modules,
                        'calibre.ebooks.conversion.config',
                        _config_stub({}))
    pane = _pane(options=('inline_toc',), book_id=None)

    def boom(gui_opt, val):
        raise ValueError('bad value')

    pane.set_value = boom
    toc = StubWidget('toc')
    pane.opt_inline_toc = toc
    pane.apply_global_overrides({'inline_toc': False})
    assert toc.value is None


def test_empty_or_none_overrides_do_nothing(monkeypatch):
    monkeypatch.setitem(sys.modules,
                        'calibre.ebooks.conversion.config',
                        _config_stub({}))
    pane = _pane(book_id=None)
    calls = []
    pane.set_value = lambda gui_opt, val: calls.append(gui_opt)
    toc = StubWidget('toc')
    pane.opt_inline_toc = toc
    pane.apply_global_overrides({})
    pane.apply_global_overrides(None)
    assert calls == []
