import os

from calibre.customize.conversion import OutputFormatPlugin, OptionRecommendation
from calibre.ebooks.conversion.plugins.txt_output import TXTOutput, NEWLINE_TYPES

from calibre_plugins.markdown.utils.library import (
    is_temporary_output,
    resolve_book_dir,
    resolve_book_info,
)
from calibre_plugins.markdown.utils.prefs import (
    DEFAULT_PARAGRAPH_STYLE,
    PARAGRAPH_STYLES,
    parse_customization,
)

# Sentinel for _resolve_image_target: the shared library lookup has not run,
# so the method must resolve the folder itself (books without images never
# reach it, keeping the library closed for them). None means the lookup ran
# and failed - retrying would just open the library a second time.
_BOOK_FOLDER_UNRESOLVED = object()

#: Plugin names this plugin was installed under before. calibre keys the
#: customization payload (the global overrides of the customization dialog) by
#: plugin name, so initialize() moves a payload saved under an old name to the
#: current one once instead of silently resetting the user's overrides.
LEGACY_CUSTOMIZATION_NAMES = ('Markdown',)


class MarkdownOutput(TXTOutput):
    name = "Markdown Output"
    author = "Qbeenslee"
    version = (3, 20, 4)
    file_type = "md"
    commit_name = "md_output"
    ui_data = {
        "newline_types": NEWLINE_TYPES,
    }

    # Option names the customization dialog may override globally. Anything
    # else in a customization payload is ignored instead of being pushed
    # blindly onto the conversion options.
    overridable_options = frozenset((
        "inline_toc",
        "keep_links",
        "keep_image_references",
        "keep_image_sizes",
        "export_cover_page",
        "use_alt_text_for_images",
        "export_image_files",
        "download_remote_images",
        "image_output_mode",
        "paragraph_style",
        "blank_line_before_heading",
        "heading_anchors",
        "escape_markdown_chars",
        "yaml_front_matter",
        "filename_pattern",
        "strip_pdf_page_markers",
        "max_line_length",
        "force_max_line_length",
        "newline",
        "txt_output_encoding",
    ))

    options = {
        OptionRecommendation(
            name="newline",
            recommended_value="unix",
            level=OptionRecommendation.LOW,
            short_switch="n",
            choices=NEWLINE_TYPES,
            help=_(
                "Type of newline to use. Options are %s. Default is 'system'. "
                "Use 'old_mac' for compatibility with Mac OS 9 and earlier. "
                "For macOS use 'unix'. 'system' will default to the newline "
                "type used by this OS."
            )
            % sorted(NEWLINE_TYPES),
        ),
        OptionRecommendation(
            name="txt_output_encoding",
            recommended_value="utf-8",
            level=OptionRecommendation.LOW,
            help=_(
                "Specify the character encoding of the output document. "
                "The default is utf-8."
            ),
        ),
        OptionRecommendation(
            name="inline_toc",
            recommended_value=True,
            level=OptionRecommendation.LOW,
            help=_("Add Table of Contents to beginning of the book."),
        ),
        OptionRecommendation(
            name="max_line_length",
            recommended_value=0,
            level=OptionRecommendation.LOW,
            help=_(
                "The maximum number of characters per line. This splits on "
                "the first space before the specified value. If no space is found "
                "the line will be broken at the space after and will exceed the "
                "specified value. Also, there is a minimum of 25 characters. "
                "Use 0 to disable line splitting."
            ),
        ),
        OptionRecommendation(
            name="force_max_line_length",
            recommended_value=False,
            level=OptionRecommendation.LOW,
            help=_(
                "Force splitting on the max-line-length value when no space "
                "is present. Also allows max-line-length to be below the minimum"
            ),
        ),
        OptionRecommendation(
            name="keep_links",
            recommended_value=True,
            level=OptionRecommendation.LOW,
            help=_("Do not remove links within the document. "),
        ),
        OptionRecommendation(
            name="keep_image_references",
            recommended_value=True,
            level=OptionRecommendation.LOW,
            help=_("Do not remove image references within the document. "),
        ),
        OptionRecommendation(
            name="keep_image_sizes",
            recommended_value=True,
            level=OptionRecommendation.LOW,
            help=_(
                "Write the width/height an image declares (width/height "
                "attributes or CSS) into the Markdown as <img src=... width=... "
                "height=...> raw HTML. Uncheck to export plain ![](path) "
                "references and drop the sizes."
            ),
        ),
        OptionRecommendation(
            name="export_cover_page",
            recommended_value=True,
            level=OptionRecommendation.LOW,
            help=_(
                "Process titlepage.xhtml files and the cover image "
                "reference from the input book. Uncheck to skip cover/"
                "title page content in the Markdown output."
            ),
        ),
        OptionRecommendation(
            name="use_alt_text_for_images",
            recommended_value=True,
            level=OptionRecommendation.LOW,
            help=_(
                "Replace images with the text from the alt attribute, if any. "
                "Ignored if the option to keep image references is specified."
            ),
        ),
        OptionRecommendation(
            name="export_image_files",
            recommended_value=True,
            level=OptionRecommendation.LOW,
            help=_(
                "Copy referenced image files next to the Markdown file "
                "into a sibling .images folder."
            ),
        ),
        OptionRecommendation(
            name="download_remote_images",
            recommended_value=True,
            level=OptionRecommendation.LOW,
            help=_(
                "Download remote images (http/https URLs the book "
                "references) when exporting image files, and store them "
                "with the local ones. Failed downloads are skipped: the "
                "reference stays a URL and a warning is written to the "
                "conversion report."
            ),
        ),
        OptionRecommendation(
            name="image_output_mode",
            recommended_value="sidecar",
            level=OptionRecommendation.LOW,
            choices=["sidecar", "inline", "none"],
            help=_(
                "Where images are written. 'sidecar' puts them next to the "
                "Markdown file (into the book folder of the calibre library "
                "for library conversions), 'inline' embeds them as base64 "
                "data URIs and 'none' exports no images."
            ),
        ),
        OptionRecommendation(
            name="paragraph_style",
            recommended_value=DEFAULT_PARAGRAPH_STYLE,
            level=OptionRecommendation.LOW,
            choices=list(PARAGRAPH_STYLES),
            help=_(
                "How paragraphs are separated. 'block' keeps the standard "
                "Markdown layout where a blank line separates paragraphs. "
                "'single' removes blank lines (code blocks are preserved) "
                "so every line is its own paragraph."
            ),
        ),
        OptionRecommendation(
            name="blank_line_before_heading",
            recommended_value=True,
            level=OptionRecommendation.LOW,
            help=_(
                "Insert a blank line before # headings when the paragraph "
                "style is 'single'. Headings at the very start of the file "
                "are not preceded by a blank line. No effect with the "
                "'block' style."
            ),
        ),
        OptionRecommendation(
            name="heading_anchors",
            recommended_value=True,
            level=OptionRecommendation.LOW,
            help=_(
                "Append a {#slug} anchor to each heading so the table of "
                "contents links resolve. Uncheck to export plain headings."
            ),
        ),
        OptionRecommendation(
            name="escape_markdown_chars",
            recommended_value=False,
            level=OptionRecommendation.LOW,
            help=_(
                "Escape the Markdown special characters \\ ` * _ { } [ ] ( ) "
                "# + ! in the body text. Uncheck to write the source text as "
                "it is, so a title like 第1卷 原版(By:苏梦枕) stays literal; "
                "re-rendering the file as Markdown may then read those "
                "characters as formatting. Table cells and YAML front matter "
                "keep their escaping either way."
            ),
        ),
        OptionRecommendation(
            name="yaml_front_matter",
            recommended_value=True,
            level=OptionRecommendation.LOW,
            help=_("Write YAML front matter from book metadata."),
        ),
        OptionRecommendation(
            name="strip_pdf_page_markers",
            recommended_value=False,
            level=OptionRecommendation.LOW,
            help=_(
                "Remove standalone PDF page-marker lines such as "
                "Page-12 from the Markdown body."
            ),
        ),
    }

    def initialize(self):
        '''Register the companion Markdown input plugin.

        A calibre plugin zip exposes exactly one Plugin subclass, so the
        input plugin that packages library images into EPUBs lives in its
        own module and is added to the registry here. A registration
        failure must never take the output plugin down with it.
        '''
        self._migrate_legacy_customization()
        try:
            from calibre_plugins.markdown.input.input_plugin import (
                register_markdown_input_plugin,
            )

            register_markdown_input_plugin(
                getattr(self, 'installation_type', None))
        except Exception:
            from calibre.utils.logging import default_log

            default_log.debug(
                'Markdown: could not register the Markdown input plugin')

    def convert(self, oeb_book, output_path, input_plugin, opts, log):
        from calibre.ebooks.txt.newlines import TxtNewlines, specified_newlines
        from calibre.utils.cleantext import clean_ascii_chars
        from calibre_plugins.markdown.output.markdownml_enhanced import (
            EnhancedMarkdownMLizer,
        )
        from calibre_plugins.markdown.utils.helpers import (
            export_mapped_images,
            inline_image_references,
            referenced_image_map,
            rewrite_markdown_image_dir,
        )
        from calibre_plugins.markdown.utils.remote_images import (
            collect_remote_image_urls,
            download_remote_images,
            inline_remote_images,
        )

        # Plumber.run() calls setup_options() which rebuilds opts from scratch,
        # so anything set on plumber.opts before run() is lost. Re-apply the
        # values the caller stashed on this plugin instance.
        self._restore_stashed_options(opts)

        # Real GUI/CLI conversions never fill the plugin option
        # opts.library_metadata (only convert_flow.convert_book_to_markdown
        # passes it explicitly). GUI conversions do hand us calibre's metadata
        # opf - with the calibre uuid, which is what makes the lookup below
        # succeed - but the front matter reader only takes title/authors/
        # language/publisher/tags from the oeb metadata, so the calibre-only
        # fields (calibre_id, series, ...) would be lost. Recover them through
        # the same read-only lookup the image export uses.
        final_md = self._final_markdown_path(opts, output_path)
        book_folder = _BOOK_FOLDER_UNRESOLVED
        if (getattr(opts, 'yaml_front_matter', True)
                and not getattr(opts, 'library_metadata', None)
                and is_temporary_output(output_path)):
            # One read-only open answers both conversion questions: the YAML
            # metadata and - when the sidecar image export will need it - the
            # book folder. Without this the library is only opened later, and
            # only when images will actually be written.
            folder, library_meta = resolve_book_info(oeb_book, log)
            if library_meta:
                setattr(opts, 'library_metadata', library_meta)
            if self._wants_image_folder(opts, final_md, output_path):
                book_folder = folder

        setattr(opts, "txt_output_formatting", "markdown")
        self.writer = EnhancedMarkdownMLizer(log)

        txt = self.writer.extract_content(oeb_book, opts)
        txt = clean_ascii_chars(txt)

        if (
            getattr(opts, 'export_image_files', True)
            and getattr(opts, 'keep_image_references', True)
            and final_md
        ):
            mapped = getattr(self.writer, 'images', None) or {}
            # map_resources() maps every image in the manifest, referenced or
            # not (the cover image outlives a skipped cover page that way).
            # Only what the Markdown mentions may be written; when nothing is
            # left, no folder is created either.
            image_map = referenced_image_map(txt, mapped)
            skipped = len(mapped) - len(image_map)
            if skipped:
                log.info('Markdown: skipped %s image(s) not referenced by the '
                         'Markdown output.' % skipped)
            mode = getattr(opts, 'image_output_mode', 'sidecar')
            remote_urls = []
            if getattr(opts, 'download_remote_images', True):
                remote_urls = collect_remote_image_urls(txt)
            if mode == 'inline':
                txt, count = inline_image_references(txt, oeb_book, image_map)
                if count:
                    log.info('Embedded %s image(s) as data URIs.' % count)
                if remote_urls:
                    txt, count, failed = inline_remote_images(
                        txt, remote_urls)
                    if count:
                        log.info('Embedded %s remote image(s) as data URIs.'
                                 % count)
                    self._warn_failed_remote_images(log, failed)
            elif mode == 'none':
                log.info('Image export disabled by configuration.')
            elif mode == 'sidecar':
                # Only a write needs the target folder; a book without images
                # must not open the library (design 4.4). A book whose only
                # images are remote ones needs the folder all the same.
                if image_map or remote_urls:
                    dest, rewrite = self._resolve_image_target(
                        oeb_book, final_md, output_path, log, mode,
                        book_folder=book_folder)
                    if dest:
                        written = 0
                        if image_map:
                            written = export_mapped_images(
                                oeb_book, image_map, final_md, dest_dir=dest)
                        if remote_urls:
                            # Rewrite the URLs before the folder rename pass:
                            # the downloaded copies are references like the
                            # local ones and take the sidecar prefix with
                            # them.
                            txt, saved, failed = download_remote_images(
                                txt, remote_urls, dest, len(mapped))
                            written += saved
                            self._warn_failed_remote_images(log, failed)
                        if written:
                            if rewrite:
                                txt = rewrite_markdown_image_dir(txt, rewrite)
                            log.info('Exported %s image file(s) to %s'
                                     % (written, dest))
            else:
                log.warn('Markdown: unknown image output mode %r, '
                         'images were not exported.' % (mode,))

        log.debug('\tReplacing newlines with selected type...')
        txt = specified_newlines(TxtNewlines(opts.newline).newline, txt)

        close = False
        if not hasattr(output_path, 'write'):
            close = True
            if not os.path.exists(os.path.dirname(output_path)) \
                    and os.path.dirname(output_path) != '':
                os.makedirs(os.path.dirname(output_path))
            out_stream = open(output_path, 'wb')
        else:
            out_stream = output_path

        out_stream.seek(0)
        out_stream.truncate()
        out_stream.write(txt.encode(opts.txt_output_encoding, 'replace'))

        if close:
            out_stream.close()

    def _migrate_legacy_customization(self):
        '''Move a customization payload saved under a former plugin name.

        calibre keys the payload by plugin name, so the rename would silently
        drop the global overrides the user saved. They are moved to the
        current name once. A payload already saved under the current name -
        even an empty one - always wins, so a cleared dialog stays cleared
        and the migration never runs twice.
        '''
        try:
            from calibre.customize.ui import config

            stored = config['plugin_customization']
            if self.name in stored:
                return
            for name in LEGACY_CUSTOMIZATION_NAMES:
                legacy = stored.get(name)
                if not (isinstance(legacy, str) and legacy.strip()):
                    continue
                stored[self.name] = legacy
                del stored[name]
                config['plugin_customization'] = stored
                from calibre.utils.logging import default_log

                default_log.debug(
                    'Markdown Output: moved the plugin customization payload '
                    'from %r to %r' % (name, self.name))
                return
        except Exception:
            pass

    def _wants_image_folder(self, opts, final_md, output_path):
        '''True when the sidecar image export will need the book folder.'''
        return (
            is_temporary_output(output_path)
            and bool(final_md)
            and getattr(opts, 'image_output_mode', 'sidecar') == 'sidecar'
            and getattr(opts, 'export_image_files', True)
            and getattr(opts, 'keep_image_references', True)
        )

    def _resolve_image_target(self, oeb_book, md_path, output_path, log, mode,
                              book_folder=_BOOK_FOLDER_UNRESOLVED):
        '''Return (dest_dir, rewrite_name) for image export.

        (None, None) means: do not export. rewrite_name is None when the
        Markdown already points at the right folder (library conversion
        writes into <book folder>/images). book_folder carries the folder
        resolved by the shared library lookup in convert(); the sentinel
        _BOOK_FOLDER_UNRESOLVED means that lookup did not run and
        resolve_book_dir must be tried here.
        '''
        from calibre_plugins.markdown.translations.messages import _ as _i18n
        from calibre_plugins.markdown.utils.helpers import (
            DEFAULT_IMAGE_DIR,
            image_sidecar_name,
            image_sidecar_path,
        )

        if mode != 'sidecar':
            return None, None
        if is_temporary_output(output_path):
            folder = (resolve_book_dir(oeb_book, log)
                      if book_folder is _BOOK_FOLDER_UNRESOLVED
                      else book_folder)
            if not folder:
                if log is not None:
                    log.warn(_i18n(
                        'Markdown: could not locate the book folder in the '
                        'calibre library, images were not exported'))
                return None, None
            return os.path.join(folder, DEFAULT_IMAGE_DIR), None
        if not md_path:
            return None, None
        return image_sidecar_path(md_path), image_sidecar_name(md_path)

    def _warn_failed_remote_images(self, log, failed):
        '''Report the remote images that could not be downloaded.

        Their references stay as URLs and the conversion continues; the
        warning surfaces in calibre's conversion job report. The sample
        lists at most five URLs so one bad host cannot flood the report.
        '''
        if not failed or log is None:
            return
        from calibre_plugins.markdown.translations.messages import (
            REMOTE_DOWNLOAD_FAILED_MESSAGE as _message,
            _ as _i18n,
        )

        unique = sorted(set(failed))
        sample = ', '.join(unique[:5])
        if len(unique) > 5:
            sample += ' …'
        log.warn(_i18n(_message).format(len(unique), sample))

    def _restore_stashed_options(self, opts):
        '''Re-apply options stashed on this instance by convert_book_to_markdown.

        Plumber.run() starts with setup_options() -> self.opts = OptionValues(),
        discarding every value written to plumber.opts beforehand. The caller
        therefore parks the plugin preferences on the output plugin instance and
        we replay them here, once the final opts object exists.
        '''
        from calibre_plugins.markdown.output.convert_flow import apply_prefs_to_opts

        prefs = getattr(self, 'markdown_prefs', None)
        if prefs:
            apply_prefs_to_opts(opts, prefs)
        library_meta = getattr(self, 'library_metadata', None)
        if library_meta is not None:
            setattr(opts, 'library_metadata', library_meta)
        output_path = getattr(self, 'markdown_output_path', None)
        if output_path:
            setattr(opts, 'markdown_output_path', output_path)

    def _final_markdown_path(self, opts, output_path):
        final_md = getattr(opts, 'markdown_output_path', None)
        if not final_md and not hasattr(output_path, 'write'):
            final_md = output_path
        return final_md

    def is_customizable(self):
        return True

    def config_widget(self):
        from calibre.customize.ui import plugin_customization
        from calibre_plugins.markdown.output.preference_ui import ConfigWidget

        try:
            raw = plugin_customization(self)
        except Exception:
            raw = ''
        return ConfigWidget(raw)

    def save_settings(self, config_widget):
        from calibre.customize.ui import customize_plugin
        from calibre_plugins.markdown.utils.prefs import serialize_customization

        customize_plugin(self, serialize_customization(config_widget.overrides()))

    def gui_configuration_widget(
        self, parent, get_option_by_name, get_option_help, db, book_id=None
    ):
        from calibre_plugins.markdown.output.conversion_ui import PluginWidget
        overrides = {}
        try:
            from calibre.customize.ui import plugin_customization
            overrides = parse_customization(plugin_customization(self))
        except Exception:
            overrides = {}
        return PluginWidget(
            parent, get_option_by_name, get_option_help, db, book_id,
            overrides=overrides)
