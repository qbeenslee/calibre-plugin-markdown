# -*- coding: utf-8 -*-
"""calibre's Markdown plugin: a Markdown output plus a companion .md input.

Package layout:

    input/          .md input plugin, its conversion pane, paragraph reshaping
    output/         output plugin, its conversion pane, customization UI
    utils/          preferences, library lookups, shared Markdown helpers
    translations/   the plugin's own message table and UI language state
    images/         pane icons the Convert dialog shows next to each pane
"""

__license__ = 'GPL 3'
__docformat__ = 'restructuredtext en'

from calibre_plugins.markdown.output.output_plugin import MarkdownOutput  # noqa: F401

# Only one Plugin subclass may live in this module: calibre's zipplugin
# loader keeps plugin_classes[0] of `calibre_plugins.markdown`, so a second
# class here would shadow the output plugin. The companion Markdown input
# plugin lives in input/input_plugin.py and is registered at runtime by
# MarkdownOutput.initialize().

PLUGIN_NAME = 'Markdown Output'
PLUGIN_DESCRIPTION = 'Convert books to Markdown text files.'
PLUGIN_VERSION_TUPLE = (3, 20, 9)
PLUGIN_VERSION = '3.20.9'
PLUGIN_MINIMUM_CALIBRE_VERSION = (6, 0, 0)
PLUGIN_RELEASED = '26 Sep, 2026'
PLUGIN_ABOUT_LAST_UPDATED = '2026-09-26'
PLUGIN_RELEASE_URL = 'https://github.com/qbeenslee/calibre-plugin-markdown'
PLUGIN_LEGACY_ORIGIN_URL = 'https://github.com/qbeenslee/calibre-plugin-markdown'
PLUGIN_AUTHOR = 'Qbeenslee'
