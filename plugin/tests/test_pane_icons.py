# -*- coding: utf-8 -*-
"""The conversion panes carry the plugin's own icons in the Convert dialog.

The PNGs live in the package under images/ so they travel inside the
installed zip; utils/plugin_icons.py reads them from the zip (calibre's
injected get_resources) or from disk (source tree), and both panes fall back
to calibre's text-file icon when the image or Qt is unavailable.
"""

from calibre_plugins.markdown.utils.plugin_icons import (
    pane_icon,
    read_icon_data,
)

_PNG_MAGIC = b'\x89PNG\r\n\x1a\n'


def test_pane_icons_ship_with_the_package():
    for filename in ('input.png', 'output.png'):
        data = read_icon_data(filename)
        assert data is not None, filename
        assert data.startswith(_PNG_MAGIC), filename


def test_missing_resource_reads_as_none():
    assert read_icon_data('does-not-exist.png') is None


def test_pane_icon_needs_qt():
    # The test venv has no qt.core: building the QIcon must degrade to None
    # so a pane keeps its fallback instead of raising on import.
    assert pane_icon('input.png') is None
    assert pane_icon('does-not-exist.png') is None


def test_panes_keep_a_calibre_fallback_icon():
    # __init__ overrides ICON with the packaged QIcon; without it the class
    # attribute still has to be a loadable calibre icon name.
    from calibre_plugins.markdown.input.conversion_ui import (
        PluginWidget as InputPane,
    )
    from calibre_plugins.markdown.output.conversion_ui import (
        PluginWidget as OutputPane,
    )

    assert InputPane.ICON == 'mimetypes/txt.png'
    assert OutputPane.ICON == 'mimetypes/txt.png'
