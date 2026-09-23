# -*- coding: utf-8 -*-

__license__ = 'GPL 3'

import os

from calibre.utils.logging import default_log


def apply_prefs_to_opts(opts, prefs):
    for key in (
        'inline_toc', 'keep_links', 'keep_image_references',
        'keep_image_sizes',
        'export_cover_page',
        'use_alt_text_for_images', 'export_image_files', 'image_output_mode',
        'paragraph_style', 'blank_line_before_heading', 'heading_anchors',
        'escape_markdown_chars',
        'yaml_front_matter', 'max_line_length',
        'force_max_line_length', 'newline', 'txt_output_encoding',
        'strip_pdf_page_markers',
    ):
        if key in prefs:
            setattr(opts, key, prefs[key])


def _ensure_md_output_registered():
    '''Make MarkdownOutput resolvable for Plumber inside this process.

    Plumber resolves output formats through calibre's plugin registry, which
    only contains *installed* plugins; scripts and smoke tests run against
    the source tree instead. Registering in memory leaves the user's plugin
    configuration untouched.
    '''
    from calibre.customize import PluginInstallationType
    import calibre.customize.ui as customize_ui
    from calibre_plugins.markdown.output.output_plugin import MarkdownOutput

    for plugin in customize_ui.output_format_plugins():
        if plugin.name == MarkdownOutput.name and plugin.file_type == 'md':
            return
    plugin = customize_ui.initialize_plugin(
        MarkdownOutput, None, PluginInstallationType.BUILTIN)
    customize_ui._initialized_plugins.append(plugin)


def convert_book_to_markdown(
    input_path, output_path, prefs, log=None, library_metadata=None,
):
    '''
    Run the conversion pipeline with our MarkdownOutput class.

    Real conversions go through calibre itself: pick Markdown as the output
    format in the conversion dialog, bulk-convert, or run
    `ebook-convert in.epub out.md`. This helper exists for scripts and
    smoke tests.
    '''
    from calibre.ebooks.conversion.plumber import Plumber
    from calibre_plugins.markdown.output.output_plugin import MarkdownOutput

    _ensure_md_output_registered()

    log = log or default_log
    parent = os.path.dirname(output_path)
    if parent and not os.path.exists(parent):
        os.makedirs(parent)

    try:
        plumber = Plumber(input_path, output_path, log)
        plumber.setup_options()
        apply_prefs_to_opts(plumber.opts, prefs)
        plumber.opts.markdown_output_path = output_path
        if library_metadata:
            plumber.opts.library_metadata = library_metadata
        output_plugin = MarkdownOutput(None)
        # Plumber.run() rebuilds plumber.opts via setup_options(), so the
        # values above would be dropped. Park them on the plugin instance
        # too; MarkdownOutput.convert() replays them onto the live opts.
        output_plugin.markdown_prefs = prefs
        output_plugin.markdown_output_path = output_path
        if library_metadata:
            output_plugin.library_metadata = library_metadata
        plumber.output_plugin = output_plugin
        plumber.run()
    finally:
        if hasattr(log, 'finish'):
            log.finish()

    return output_path
