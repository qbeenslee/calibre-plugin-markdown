# -*- coding: utf-8 -*-
"""The plugin's own icons for the conversion panes.

calibre's Convert dialog lists every input/output pane with the icon its
widget reports (``Widget.config_icon()``); the panes here hand it the PNGs
under the package's ``images/`` folder instead of calibre's generic
text-file icon.

The images travel inside the installed zip: calibre injects ``get_resources``
into every module it loads from a plugin zip. When the source tree is run
directly (scripts/, tests) the same file is read from disk instead.
"""

import os

#: Package folder holding the pane icons, as named inside the plugin zip.
RESOURCE_DIR = 'images'

#: filename -> QIcon, so opening the Convert dialog does not re-read and
#: re-decode the PNG every time a pane is built.
_ICON_CACHE = {}


def read_icon_data(filename):
    """Bytes of ``images/<filename>``, or None when it cannot be read."""
    name = RESOURCE_DIR + '/' + filename
    # calibre's zipplugin loader puts this in the module namespace; it is
    # absent when the source tree is imported directly.
    get_resources = globals().get('get_resources')
    if get_resources is not None:
        data = get_resources(name, print_tracebacks_for_missing_resources=False)
        if data:
            return data
    path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..',
        RESOURCE_DIR, filename)
    try:
        with open(path, 'rb') as handle:
            return handle.read()
    except OSError:
        return None


def pane_icon(filename):
    """QIcon for ``images/<filename>``, or None when it cannot be built.

    None makes the caller keep its fallback icon: the panes must still build
    where Qt is absent (the test venv) or the resource is missing.
    """
    cached = _ICON_CACHE.get(filename)
    if cached is not None:
        return cached
    data = read_icon_data(filename)
    if data is None:
        return None
    try:
        from qt.core import QIcon, QPixmap
    except ImportError:
        return None
    pixmap = QPixmap()
    if not pixmap.loadFromData(data):
        return None
    icon = QIcon(pixmap)
    _ICON_CACHE[filename] = icon
    return icon
