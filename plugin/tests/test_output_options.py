# -*- coding: utf-8 -*-
"""Global overrides and image target selection in MarkdownOutput."""

import os
import sys
import types

from calibre_plugins.markdown.utils.helpers import DEFAULT_IMAGE_DIR
from calibre_plugins.markdown.output.output_plugin import MarkdownOutput
from calibre_plugins.markdown.utils.prefs import serialize_customization


class Opts:
    pass


class Log:
    def __init__(self):
        self.warnings = []

    def warn(self, message):
        self.warnings.append(message)

    def info(self, message):
        pass

    def debug(self, message):
        pass


def _plugin():
    """Bare instance: tests must not touch calibre widget machinery."""
    plugin = MarkdownOutput.__new__(MarkdownOutput)
    plugin.site_customization = None
    return plugin


def test_site_customization_never_beats_the_conversion_dialog(monkeypatch,
                                                              tmp_path):
    """The customization payload seeds the pane's starting values only.

    A pane-committed value reaches convert() with HIGH priority (calibre
    saves it as the book's conversion settings), so re-applying the payload
    here would silently undo whatever the user changed in the dialog -
    including unchecking "Add YAML front matter".
    """
    import types

    import calibre_plugins.markdown.output.output_plugin as mo

    module = types.ModuleType(
        'calibre_plugins.markdown.output.markdownml_enhanced')

    class StubWriter:
        def __init__(self, log):
            pass

        def extract_content(self, oeb_book, opts):
            return 'body\n'

    module.EnhancedMarkdownMLizer = StubWriter
    monkeypatch.setitem(sys.modules, module.__name__, module)

    plugin = _plugin()
    plugin.site_customization = serialize_customization(
        {'yaml_front_matter': True})
    opts = Opts()
    opts.yaml_front_matter = False   # what the pane committed
    opts.newline = 'unix'
    opts.txt_output_encoding = 'utf-8'
    opts.export_image_files = False  # keep the test off the image export path
    monkeypatch.setattr(mo, 'is_temporary_output', lambda path: True)

    out = tmp_path / 'book.md'
    plugin.convert(object(), str(out), None, opts, Log())
    assert opts.yaml_front_matter is False
    assert out.read_text(encoding='utf-8') == 'body\n'


class _Store:
    """ConfigProxy-like store: reads come back as copies, writes are counted.

    Copying on read is what lets a test tell "the payload was moved with
    config[...] = ..." - the way calibre persists it - apart from "the
    in-memory dict happened to be mutated".
    """

    def __init__(self, payloads=None):
        self.payloads = dict(payloads or {})
        self.writes = 0

    def __getitem__(self, key):
        return dict(self.payloads[key])

    def __setitem__(self, key, value):
        self.writes += 1
        self.payloads[key] = dict(value)


def _patch_store(monkeypatch, payloads):
    """Point calibre's per-plugin customization store at `payloads`."""
    import calibre.customize.ui as customize_ui

    store = _Store({'plugin_customization': payloads})
    monkeypatch.setattr(customize_ui, 'config', store, raising=False)
    return store


def test_customization_payload_follows_the_plugin_rename(monkeypatch):
    # calibre keys the payload by plugin name, so the overrides saved under
    # the name this plugin used before the rename have to move along.
    payload = serialize_customization({'inline_toc': False})
    store = _patch_store(monkeypatch, {'Markdown': payload})
    _plugin()._migrate_legacy_customization()
    assert store.payloads['plugin_customization'] == {'Markdown Output': payload}


def test_migration_leaves_a_payload_of_the_current_name_alone(monkeypatch):
    # A payload saved under the current name - even an empty one, meaning
    # "no overrides" - wins, so the migration neither runs twice nor undoes
    # a cleared dialog.
    payload = serialize_customization({'inline_toc': False})
    store = _patch_store(monkeypatch,
                         {'Markdown': payload, 'Markdown Output': ''})
    _plugin()._migrate_legacy_customization()
    assert store.payloads['plugin_customization'] == {
        'Markdown': payload, 'Markdown Output': ''}
    assert store.writes == 0


def test_migration_survives_a_broken_store(monkeypatch):
    # The store is calibre internals; when it cannot be read the plugin must
    # still initialize.
    import calibre.customize.ui as customize_ui

    monkeypatch.delattr(customize_ui, 'config', raising=False)
    _plugin()._migrate_legacy_customization()


def test_library_conversion_targets_book_folder(monkeypatch):
    import calibre_plugins.markdown.output.output_plugin as mo
    monkeypatch.setattr(mo, 'is_temporary_output', lambda path: True)
    monkeypatch.setattr(mo, 'resolve_book_dir',
                        lambda oeb, log: '/lib/Author/Title (7)')
    dest, rewrite = _plugin()._resolve_image_target(
        None, '/tmp/x.md', 'whatever', None, 'sidecar')
    assert dest == os.path.join('/lib/Author/Title (7)', DEFAULT_IMAGE_DIR)
    assert rewrite is None          # md already refers to images/<file>


def test_library_conversion_without_lookup_is_skipped(monkeypatch):
    import calibre_plugins.markdown.output.output_plugin as mo
    monkeypatch.setattr(mo, 'is_temporary_output', lambda path: True)
    monkeypatch.setattr(mo, 'resolve_book_dir', lambda oeb, log: None)
    log = Log()
    assert _plugin()._resolve_image_target(
        None, '/tmp/x.md', 'o', log, 'sidecar') == (None, None)
    assert log.warnings


def test_plain_target_uses_sidecar(monkeypatch):
    import calibre_plugins.markdown.output.output_plugin as mo
    monkeypatch.setattr(mo, 'is_temporary_output', lambda path: False)
    dest, rewrite = _plugin()._resolve_image_target(
        None, '/tmp/x.md', 'o', None, 'sidecar')
    assert dest == '/tmp/x.images'
    assert rewrite == 'x.images'


def test_non_sidecar_modes_skip_disk(monkeypatch):
    import calibre_plugins.markdown.output.output_plugin as mo
    monkeypatch.setattr(mo, 'is_temporary_output', lambda path: True)
    for mode in ('inline', 'none'):
        assert _plugin()._resolve_image_target(
            None, '/tmp/x.md', 'o', None, mode) == (None, None)


def test_image_output_mode_option_exists():
    names = {option.option.name for option in MarkdownOutput.options}
    assert 'image_output_mode' in names
    option = next(o for o in MarkdownOutput.options
                  if o.option.name == 'image_output_mode')
    assert option.recommended_value == 'sidecar'
    assert set(option.option.choices) == {'sidecar', 'inline', 'none'}


def test_image_export_rows_reach_the_conversion_pane():
    """The image export switch and its mode lived in prefs and the
    customization dialog only: a single-book conversion could not turn the
    image export off (or switch it to data URIs) without the dialog. The
    pane carries both now; without a row calibre's Widget raises at
    construction (an option with no opt_<name> widget) and the value the
    user picks would never be committed.
    """
    from calibre_plugins.markdown.output import conversion_ui
    from calibre_plugins.markdown.utils.prefs import EXPORT_OPTION_KEYS

    for name in ('export_image_files', 'image_output_mode'):
        assert name in conversion_ui.option
        assert name in MarkdownOutput.overridable_options
        assert name in EXPORT_OPTION_KEYS
    assert hasattr(conversion_ui.TXTUIForm, '_add_export_image_files_row')
    assert hasattr(conversion_ui.TXTUIForm, '_add_image_output_mode_row')
    option = next(o for o in MarkdownOutput.options
                  if o.option.name == 'export_image_files')
    assert option.recommended_value is True


def test_image_mode_labels_cover_every_mode():
    """The conversion pane and the customization dialog read the same
    label table, so it has to carry an entry for every mode value."""
    from calibre_plugins.markdown.utils.prefs import (
        IMAGE_MODE_LABELS,
        IMAGE_OUTPUT_MODES,
    )

    assert tuple(IMAGE_MODE_LABELS) == tuple(IMAGE_OUTPUT_MODES)


def test_image_rows_form_their_own_group():
    """The pane's image options sit in an "Images" group box of their own,
    a sibling of "Markdown, Textile".

    calibre binds a row to its option through the opt_<name> attribute, so
    regrouping is a layout-only change: the committed names, the first two
    rows ("Keep images", "Image sizes") and the options left behind all stay
    as they are.
    """
    from calibre_plugins.markdown.output.conversion_ui import (
        IMAGE_GROUP_OPTIONS,
        option,
    )

    assert IMAGE_GROUP_OPTIONS == (
        'keep_image_references', 'keep_image_sizes', 'use_alt_text_for_images',
        'export_image_files', 'download_remote_images', 'image_output_mode')
    assert set(IMAGE_GROUP_OPTIONS) <= set(option)
    # No option is listed twice (the tuple used to carry keep_image_sizes
    # twice once the row had moved), and the cover page stays a Markdown row.
    assert len(set(option)) == len(option)
    assert 'export_cover_page' not in IMAGE_GROUP_OPTIONS


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
    from calibre_plugins.markdown.output.conversion_ui import (
        IMAGE_DEPENDENT_OPTIONS,
        PluginWidget,
    )

    pane = PluginWidget.__new__(PluginWidget)
    pane.opt_keep_image_references = _CheckBox(checked)
    pane.image_output_mode_label = _CheckBox()
    pane.image_note_label = _CheckBox()
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
    from calibre_plugins.markdown.output.conversion_ui import (
        IMAGE_DEPENDENT_OPTIONS,
        IMAGE_GROUP_OPTIONS,
    )

    assert (set(IMAGE_DEPENDENT_OPTIONS) | {'keep_image_references'}
            == set(IMAGE_GROUP_OPTIONS))
    assert 'keep_image_references' not in IMAGE_DEPENDENT_OPTIONS
    # The cover page lives in the Markdown, Textile group and stays as it is.
    assert 'export_cover_page' not in IMAGE_DEPENDENT_OPTIONS


def test_image_rows_are_disabled_while_keep_images_is_off():
    pane = _image_pane(checked=False)

    pane._sync_image_rows()

    greyed = {name for name, row in pane.image_rows.items() if not row.enabled}
    assert greyed == set(pane.image_rows)
    # The label of the mode combo and calibre's note belong to the group and
    # grey out with it; the master switch stays clickable - that is how the
    # images come back.
    assert pane.image_output_mode_label.enabled is False
    assert pane.image_note_label.enabled is False
    assert pane.opt_keep_image_references.enabled is True

    pane.opt_keep_image_references.checked = True
    pane._sync_image_rows()

    assert [name for name, row in pane.image_rows.items() if not row.enabled] == []
    assert pane.image_output_mode_label.enabled is True
    assert pane.image_note_label.enabled is True


def test_rows_without_a_widget_are_skipped():
    # The pane must survive a row that never got built (the loop reads
    # opt_<name> through getattr, the way apply_global_overrides does).
    pane = _image_pane(checked=False, names=('keep_image_sizes',))

    pane._sync_image_rows()

    assert pane.image_rows['keep_image_sizes'].enabled is False


def test_wiring_connects_the_switches_and_seeds_the_rows():
    pane = _image_pane(checked=False)

    pane._wire_image_rows()

    assert pane.opt_keep_image_references.slots == [pane._sync_image_rows]
    assert pane.opt_export_image_files.slots == [pane._sync_image_rows]
    assert [name for name, row in pane.image_rows.items() if row.enabled] == []


def test_export_files_gate_the_download_and_the_mode():
    # Second level: the remote downloads and the output mode both only happen
    # as part of the file export, so both grey out with "Export image files"
    # while the other image rows stay editable.
    pane = _image_pane(checked=True)
    pane.opt_export_image_files.checked = False

    pane._sync_image_rows()

    assert pane.image_rows['download_remote_images'].enabled is False
    assert pane.image_rows['image_output_mode'].enabled is False
    assert pane.image_output_mode_label.enabled is False
    assert {name for name, row in pane.image_rows.items() if row.enabled} \
        == set(pane.image_rows) - {'download_remote_images', 'image_output_mode'}

    pane.opt_export_image_files.checked = True
    pane._sync_image_rows()

    assert pane.image_rows['download_remote_images'].enabled is True
    assert pane.image_rows['image_output_mode'].enabled is True
    assert pane.image_output_mode_label.enabled is True


def test_the_gate_and_the_master_switch_stack():
    pane = _image_pane(checked=False)
    pane.opt_export_image_files.checked = False

    pane._sync_image_rows()

    assert [name for name, row in pane.image_rows.items() if row.enabled] == []
    assert pane.image_output_mode_label.enabled is False

    pane.opt_keep_image_references.checked = True
    pane._sync_image_rows()

    # Both gated rows stay grey (their gate is still off) while every other
    # row is editable again; the mode label follows its own row.
    assert {name for name, row in pane.image_rows.items() if not row.enabled} \
        == {'download_remote_images', 'image_output_mode'}
    assert pane.image_output_mode_label.enabled is False
    assert pane.image_note_label.enabled is True

    pane.opt_export_image_files.checked = True
    pane._sync_image_rows()

    assert pane.image_output_mode_label.enabled is True


def test_gates_are_rows_of_the_group():
    from calibre_plugins.markdown.output.conversion_ui import (
        IMAGE_DEPENDENT_OPTIONS,
        IMAGE_ROW_GATES,
    )

    # The gate table names rows of the group on both sides of the pair, so
    # neither the gating nor the gated row can be dropped from the pane.
    assert set(IMAGE_ROW_GATES) <= set(IMAGE_DEPENDENT_OPTIONS)
    for name, gate in IMAGE_ROW_GATES.items():
        assert gate in IMAGE_DEPENDENT_OPTIONS, gate
        assert gate != name


def test_yaml_front_matter_has_a_row_on_the_conversion_pane():
    """The option lived in prefs and the customization dialog only: converting
    a single book could not turn the YAML block off. The pane carries it now
    (calibre's Widget raises at construction when an option has no widget)."""
    from calibre_plugins.markdown.output import conversion_ui

    assert 'yaml_front_matter' in conversion_ui.option
    assert hasattr(conversion_ui.TXTUIForm, '_add_yaml_front_matter_row')
    assert 'yaml_front_matter' in MarkdownOutput.overridable_options
    option = next(o for o in MarkdownOutput.options
                  if o.option.name == 'yaml_front_matter')
    assert option.recommended_value is True


def test_download_remote_images_option_exists():
    names = {option.option.name for option in MarkdownOutput.options}
    assert 'download_remote_images' in names
    option = next(o for o in MarkdownOutput.options
                  if o.option.name == 'download_remote_images')
    assert option.recommended_value is True


def test_download_remote_images_rows_reach_both_uis():
    """The switch lives on the conversion pane and in the customization
    dialog; calibre's Widget raises at pane construction when an option has
    no opt_<name> widget, so the row must exist for real conversions."""
    import pathlib

    from calibre_plugins.markdown.output import conversion_ui
    from calibre_plugins.markdown.utils.prefs import (
        DEFAULTS,
        EXPORT_OPTION_KEYS,
    )

    assert 'download_remote_images' in conversion_ui.option
    assert hasattr(conversion_ui.TXTUIForm,
                   '_add_download_remote_images_row')
    assert 'download_remote_images' in MarkdownOutput.overridable_options
    assert 'download_remote_images' in EXPORT_OPTION_KEYS
    assert DEFAULTS['download_remote_images'] is True
    # The customization dialog imports Qt at module level and cannot be
    # brought in here; its BOOL_OPTIONS row is checked from the source as a
    # tripwire against the row being dropped there.
    dialog_src = (
        pathlib.Path(__file__).resolve().parents[1]
        / 'Markdown' / 'output' / 'preference_ui.py'
    ).read_text(encoding='utf-8')
    assert "('download_remote_images', 'Download remote images')" \
        in dialog_src


def test_customization_dialog_is_options_only():
    """3.19.0: no "About Markdown" / "Markdown capabilities" buttons (and no
    dialogs behind them) in the Customize plugin dialog any more."""
    import pathlib

    dialog_src = (
        pathlib.Path(__file__).resolve().parents[1]
        / 'Markdown' / 'output' / 'preference_ui.py'
    ).read_text(encoding='utf-8')
    for needle in ('PluginAboutDialog', 'MarkdownSupportDialog', 'about_btn',
                   'support_btn'):
        assert needle not in dialog_src, needle


def test_output_plugin_is_customizable():
    assert MarkdownOutput.is_customizable(_plugin()) is True


def test_overridable_options_match_prefs():
    """The convert() whitelist and the customization model must not drift."""
    from calibre_plugins.markdown.utils.prefs import EXPORT_OPTION_KEYS

    assert set(MarkdownOutput.overridable_options) == set(EXPORT_OPTION_KEYS)
