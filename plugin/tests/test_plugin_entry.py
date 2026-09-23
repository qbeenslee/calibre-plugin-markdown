# -*- coding: utf-8 -*-
"""The zip exposes the Markdown output plugin plus the .md input plugin."""

import importlib

import calibre_plugins.markdown as plugin_pkg
from calibre.customize import Plugin
from calibre_plugins.markdown.input.input_plugin import MarkdownInput
from calibre_plugins.markdown.output.output_plugin import MarkdownOutput


def test_package_exposes_a_single_plugin_class():
    # calibre's zipplugin loader keeps plugin_classes[0] of the package
    # module: a second Plugin subclass here would shadow the output plugin.
    classes = [obj for obj in vars(plugin_pkg).values()
               if isinstance(obj, type) and issubclass(obj, Plugin)
               and obj is not Plugin]
    assert classes == [MarkdownOutput]


def test_output_plugin_is_exposed():
    assert hasattr(plugin_pkg, 'MarkdownOutput')
    assert MarkdownOutput.file_type == 'md'


def test_input_plugin_claims_markdown_only():
    assert {'md', 'markdown'} <= MarkdownInput.file_types
    assert 'txt' not in MarkdownInput.file_types
    # TXT Input (builtin) claims .md too; the higher priority is what makes
    # calibre pick this plugin for the format.
    assert MarkdownInput.priority > 1


def test_version_constants_agree():
    # 3.20.5: a Markdown file that uses the same image many times now ships
    # it once. TXT Input embeds one file per <img> element and gives every
    # copy a fresh name ('x.png', 'x-1.png', ...) because the copy it wrote
    # before is already there, so 110 references to one 110 KB picture
    # produced a 13 MB EPUB with 110 copies of it; identical bytes are now
    # written once and every reference points at that one file.
    # 3.20.4: a book whose CSS declares a margin calibre cannot read (the
    # `margin: -2em 0 olid #20F2f0` shorthand typo expands to
    # `margin-bottom: olid`, and `1em 1em 1em 1emem` to `1emem`) no longer
    # aborts the conversion: the renderer reads such a margin as 0 before
    # upstream's unguarded float() ever sees it, and logs one line saying so.
    # 3.20.3: an <img> without a width/height and without an alt attribute
    # exports as ![](path) instead of !(path). calibre's own branch writes the
    # brackets only when the element carries an alt attribute, so the picture
    # came out as text - dropped by every Markdown renderer, not read back by
    # the input side, and skipped by the folder rewrite / data URI inlining
    # that match the ![alt](path) spelling.
    # 3.20.2: both conversion panes tie their image rows to the "Keep images"
    # switch: unchecking it greys out the rest of the "Images" group (sizes,
    # embedding / alt text, remote downloads, file export, output mode),
    # checking it brings them back with their values untouched. A second
    # level on top of it: the output side's "Export image files" also governs
    # "Download remote images" and the output mode (both only happen as part
    # of the export), and the input side's "Embed images" governs "Download
    # remote images" (downloading is how a remote image gets embedded).
    # 3.20.1: a line that opens with an inline level HTML element is a body
    # line again, whatever else it carries: 'single' gives every image line a
    # paragraph of its own (several images on one line, a wrapper around them,
    # text beside them) instead of leaving the line glued to the text below
    # it. Block level HTML ('<div>', '<p>', '<table>') is still a structure
    # over several lines and stays out of the reshaping.
    # 3.20.0: both conversion panes end with a hint pointing at that plugin's
    # "Customize plugin" dialog (per-book settings here, global defaults
    # there); it follows the plugin UI language like every pane string.
    # 3.19.0: the "Customize plugin" dialog is options only - the "About
    # Markdown" and "Markdown capabilities" buttons (with both dialogs behind
    # them, and the i18n entries they were the only readers of) are gone.
    # 3.18.0: the plugin has no language setting of its own any more - the
    # customization dialog's "Interface language:" row is gone and the UI
    # follows calibre's language (Chinese reads the Chinese table, every
    # other language the English one).
    # 3.17.0: the paragraph style applies inside a quote block (every quoted
    # line its own paragraph, separated by a prefix-only '>' line), and a
    # quote block is separated from what follows it by a blank line - on the
    # output side no bare '>' closing line any more, since a quote is read up
    # to the next blank line and the line after a bare '>' close came back
    # swallowed into the quote. A fenced code block is left alone whatever
    # its lines look like, so a '====' line inside one no longer grows a
    # blank line on every conversion. An image on a line of its own (an <img>
    # tag or the ![]() spelling) is a paragraph of its own too: 'single'
    # separates it from the line below it instead of packing both into one
    # <p>.
    assert plugin_pkg.PLUGIN_VERSION == '3.20.6'
    assert plugin_pkg.PLUGIN_VERSION_TUPLE == (3, 20, 6)
    assert MarkdownOutput.version == (3, 20, 6)
    assert MarkdownInput.version == (3, 20, 6)


def test_plugin_names():
    # "Markdown" alone names the format, so the output plugin reads as the
    # counterpart of the "Markdown Input" companion it registers.
    assert MarkdownOutput.name == 'Markdown Output'
    assert plugin_pkg.PLUGIN_NAME == MarkdownOutput.name
    assert MarkdownInput.name == 'Markdown Input'


def test_initialize_registers_the_input_plugin(monkeypatch):
    import calibre.customize.ui as customize_ui

    monkeypatch.setattr(customize_ui, '_initialized_plugins', [])
    monkeypatch.setattr(customize_ui, 'is_disabled', lambda plugin: False)

    MarkdownOutput(None).initialize()

    assert any(isinstance(plugin, MarkdownInput)
               for plugin in customize_ui._initialized_plugins)


def test_initialize_survives_a_registration_failure(monkeypatch):
    from calibre_plugins.markdown.input import input_plugin

    def boom(*args, **kwargs):
        raise RuntimeError('no registry')

    monkeypatch.setattr(input_plugin, 'register_markdown_input_plugin', boom)

    MarkdownOutput(None).initialize()


def test_no_interface_action_entry():
    assert not hasattr(plugin_pkg, 'PLUGIN_ACTUAL_PLUGIN')


def test_removed_modules_are_gone():
    # Legacy helpers, plus the flat module names the 3.4.1 layout replaced
    # with the input/ output/ utils/ translations/ subpackages.
    for name in ('action', 'conversion_log', 'markdown_stats', 'icons',
                 'markdown_input', 'markdown_output', 'markdown_paragraphs',
                 'markdown_helpers', 'markdown_library', 'markdownml_enhanced',
                 'input_ui', 'dialogs', 'ui', 'prefs', 'i18n',
                 'override_model', 'convert_flow'):
        try:
            importlib.import_module('calibre_plugins.markdown.%s' % name)
        except ImportError:
            continue
        raise AssertionError('%s should have been deleted' % name)
