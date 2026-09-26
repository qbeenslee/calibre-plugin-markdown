# -*- coding: utf-8 -*-
"""Markdown (.md) input: TXT Input plus library images and dialog options.

calibre's GUI and bulk conversions copy the book file into a temporary
folder before converting (gui2/tools.py), so a .md file is converted away
from the image folders next to it in the calibre library. TXT Input then
cannot resolve the relative image references and the output EPUB ships
without the image files. This input plugin resolves the book folder through
the injected metadata opf (calibre uuid -> read-only library lookup) and
stages the missing images into the input folder, where the standard TXT
Input resource handling picks them up.

Any folder next to the .md counts - the 'images/' folder this plugin's
output side writes, and 'assets/', 'media/' or any other name a hand-built
bundle uses. A reference spelled with URL escapes ('assets/%E3%80%90.jpg',
how other tools write non-ASCII file names) is decoded before the file is
looked up and the reference is rewritten to the decoded path, because both
the lookup and TXT Input's resource handling resolve literal paths only.

On top of TXT Input's options this plugin adds the conversion dialog pane
(input/conversion_ui.PluginWidget):
  * input_encoding      - calibre's own option (auto-detect by default)
  * md_line_break       - fold single line breaks or make them <br> (nl2br)
  * paragraph_type      - auto detects the paragraph style from the text
                          (one paragraph per line, indented starts, or
                          ordinary Markdown) and reshapes it before parsing;
                          an explicit choice is applied as it is
  * read_yaml_metadata  - use the YAML front matter as metadata (default) or
                          strip it from the text
  * keep_images         - master switch: keep the images the book
                          references (default) or drop them all
  * embed_images        - stage/embed the local images (default) or leave
                          image references as they are
  * download_remote_images - download http(s) images next to the input and
                          embed them like local ones (default; requires
                          keep_images and embed_images)
  * keep_image_sizes    - keep the width/height the Markdown declares on its
                          images (default) or drop them
  * markdown_extensions - which python-markdown extensions to enable

The reshaping behind paragraph_type is Markdown aware
(input/paragraphs): TXT Input forces paragraph_type='off' for .md and its
plain text helpers would flatten the line structure of code blocks, lists,
quotes and tables, so the style is applied here instead - inside a quote
block as well, whose lines become the paragraphs of the quote.
"""

import codecs
import hashlib
import os
import re
import shutil
from html import unescape as _html_unescape
from urllib.parse import unquote as _url_unquote

from calibre.customize.conversion import OptionRecommendation
from calibre.ebooks.conversion.plugins.txt_input import TXTInput
from calibre.utils.localization import _

from calibre_plugins.markdown.input import paragraphs
from calibre_plugins.markdown.utils.helpers import (
    rewrite_html_image_srcs,
    strip_image_sizes,
    strip_image_tags,
)
from calibre_plugins.markdown.utils.remote_images import (
    collect_remote_image_urls,
    rewrite_remote_image_refs,
    save_remote_image,
)
from calibre_plugins.markdown.utils.library import (
    resolve_book_dir_for_options,
)
from calibre_plugins.markdown.utils.prefs import (
    INPUT_OPTION_KEYS,
    parse_customization,
)

#: URL schemes that never name a local file we could stage.
_REMOTE_SCHEMES = frozenset(
    ('http', 'https', 'ftp', 'file', 'data', 'mailto'))

_UNRESOLVED_MESSAGE = (
    'Markdown: {} image reference(s) could not be found next to the input '
    'file or in the calibre library, the output will not include them: {}')

#: md_line_break values.
LINE_BREAK_FOLD = 'fold'
LINE_BREAK_HARD = 'hard'

#: Default for markdown_extensions. calibre's own default is
#: 'footnotes, tables, toc'; the additions are what this plugin's Markdown
#: output actually writes (fenced code blocks, definition lists and
#: {#slug} heading anchors), so its own files round-trip as written.
DEFAULT_MARKDOWN_EXTENSIONS = (
    'footnotes, tables, fenced_code, def_list, attr_list, toc')

_YAML_DELIMITERS = (b'---', b'...')
_YAML_LANGUAGE_RE = re.compile(
    rb'^[ \t]*language[ \t]*:[ \t]*([^\r\n]+)', re.M)
_YAML_KEY_RE = re.compile(rb'^[ \t]{0,3}([A-Za-z0-9_.-]+):[ \t]*(.*)$')
_YAML_LIST_ITEM_RE = re.compile(rb'^[ \t]+-[ \t]+(.+?)[ \t]*$')

#: Front matter keys calibre's meta mapping does not know under their YAML
#: name; the value is what it does read (this plugin's own Markdown output
#: writes 'description', calibre maps 'comments'/'summary').
_YAML_ALIASES = {b'description': b'comments'}

_OPTION_HELP_LINE_BREAK = (
    'How a single line break inside a paragraph is rendered. "fold" joins '
    'the lines (standard Markdown); "hard" turns every line break into a '
    '<br> (the nl2br extension).')

_OPTION_HELP_YAML = (
    'Read the YAML block at the very start of the document as book '
    'metadata (title, authors, language, tags, description). When off the '
    'block is removed from the text instead.')

_OPTION_HELP_PARAGRAPH = (
    'Paragraph structure to assume. "auto" detects it from the text: a file '
    'with one paragraph per line gets the blank lines Markdown needs, an '
    'ordinary Markdown file is left alone. An explicit choice is applied as '
    'it is. Reshaping never splits code blocks, lists or tables apart, and '
    'a quote block stays one quote: its lines become the paragraphs inside '
    'it, and a blank line separates the quote from what follows.')

_OPTION_HELP_EXTENSIONS = (
    'Enable extensions to Markdown syntax. Extensions are formatting that '
    'is not part of the standard Markdown format.')

_OPTION_HELP_KEEP_SIZES = (
    'Keep the width/height the Markdown declares on its images (width/height '
    'attributes or inline styles). Uncheck to drop those sizes, so the images '
    'enter the book at their natural size instead.')

_OPTION_HELP_KEEP_IMAGES = (
    'Keep the images the Markdown references. Uncheck to remove every '
    'image (and its alt text) from the converted book.')

_OPTION_HELP_EMBED_IMAGES = (
    'Embed local images into the converted book: files in any folder next '
    'to the input (images/, assets/, ...) or in the calibre book folder, '
    'including references whose file names are written with URL escapes. '
    'Uncheck to leave image references as they are.')

_OPTION_HELP_DOWNLOAD_REMOTE = (
    'Download remote images (http/https URLs) and embed them into the '
    'book like local ones. Requires "Keep images" and "Embed images"; '
    'failed downloads are skipped and reported in the conversion report.')


def split_yaml_front_matter(data):
    """Return (front_matter_bytes, body_bytes) for a leading YAML block.

    (None, data) means there is no complete front matter block. calibre
    strips a leading BOM before decoding; the pieces carry it along so the
    rest of the pipeline sees the same bytes minus the block.
    """
    if not data:
        return None, data
    bom = codecs.BOM_UTF8 if data.startswith(codecs.BOM_UTF8) else b''
    lines = data[len(bom):].splitlines(keepends=True)
    if not lines or lines[0].strip() != b'---':
        return None, data
    for index in range(1, len(lines)):
        if lines[index].strip() in _YAML_DELIMITERS:
            block = bom + b''.join(lines[:index + 1])
            rest = bom + b''.join(lines[index + 1:])
            return block, rest
    return None, data


def normalize_yaml_front_matter(block):
    """Rewrite the front matter into the form calibre's meta reads.

    python-markdown's meta extension understands 'key: value' lines (and
    4-space continuations) only, so a classic YAML list

        tags:
          - 出版
          - 玄幻

    would leave '- 出版' behind as body text. Repeating the key instead
    ('tags: 出版') is exactly what the extension turns into a list value.

    'description' is aliased to 'comments' as well: calibre maps comments
    (and summary) from the front matter, not description, while the
    Markdown this plugin writes uses the description key.
    """
    if not block:
        return block
    out = []
    current = None      # key of the last value-less 'key:' line
    pending = None      # that line, held back until we know what follows
    for line in block.splitlines(keepends=True):
        text = line.rstrip(b'\r\n')
        ending = line[len(text):]
        item = _YAML_LIST_ITEM_RE.match(text)
        if item and current:
            out.append(b'%s: %s%s' % (current, item.group(1).strip(), ending))
            pending = None
            continue
        if pending is not None:
            # No list item followed: the bare 'key:' line stays as it was.
            out.append(pending)
            pending = None
        key = _YAML_KEY_RE.match(text)
        if key is not None and not key.group(2).strip():
            current = _YAML_ALIASES.get(key.group(1), key.group(1))
            pending = b'%s:%s' % (current, ending)
            continue
        current = None
        if key is not None and key.group(1) in _YAML_ALIASES:
            text = _YAML_ALIASES[key.group(1)] + text[key.end(1):]
            line = text + ending
        out.append(line)
    if pending is not None:
        out.append(pending)
    return b''.join(out)


def yaml_front_matter_language(block):
    """Return the language declared in a YAML front matter block, or ''."""
    if not block:
        return ''
    match = _YAML_LANGUAGE_RE.search(block)
    if not match:
        return ''
    value = match.group(1).decode('utf-8', 'replace')
    value = value.split('#', 1)[0].strip().strip('"\'')
    parts = value.split()
    return parts[0] if parts else ''


#: Encodings calibre maps to gbk when auto detecting (Word mislabels them).
_GB2312_ALIASES = frozenset((
    'gb2312', 'chinese', 'csiso58gb231280', 'euc-cn', 'euccn',
    'eucgb2312-cn', 'gb2312-1980', 'gb2312-80', 'iso-ir-58',
))

#: Byte order marks TXT Input strips before decoding. The longer marks come
#: first so a UTF-32 file is not read as UTF-16.
_BOMS = (codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE,
         codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE, codecs.BOM_UTF8)


def decode_body(data, options):
    """Decode input bytes the way TXT Input would, for inspection only.

    Detection has to read the text before TXT Input gets to it. The decoded
    string is never handed on directly: whoever calls this encodes the
    reshaped text as UTF-8 and announces that through options.input_encoding,
    so the encoding is never guessed twice.
    """
    encoding = getattr(options, 'input_encoding', '') or ''
    if not encoding:
        from calibre.ebooks.chardet import detect

        detected = detect(data[:4096]) or {}
        encoding = detected.get('encoding') or ''
        if encoding.lower().replace('_', '-').strip() in _GB2312_ALIASES:
            encoding = 'gbk'
    if not encoding:
        encoding = 'utf-8'
    for bom in _BOMS:
        if data.startswith(bom):
            data = data[len(bom):]
            break
    return data.decode(encoding, 'replace')


def _replace_options(base, replacements):
    """Rebuild an options set, replacing entries with the same option name."""
    names = {opt.option.name for opt in replacements}
    kept = {opt for opt in base if opt.option.name not in names}
    return kept.union(replacements)


class _ReplayStream:
    """Pre-processed input bytes wrapped with the original stream's name."""

    def __init__(self, data, name):
        self._data = data
        self.name = name

    def read(self, *args):
        return self._data

    def seek(self, *args):
        return 0


def _local_image_relpath(src):
    """Return the in-folder relative path of a local image, or None.

    None means the reference is not a local relative file (remote URL,
    data URI, absolute path, or a path that could escape the input
    folder): those are none of this plugin's business. Every folder inside
    the input folder counts, not just 'images/'.
    """
    src = str(src or '').strip()
    if not src or os.path.isabs(src):
        return None
    if src.split(':', 1)[0].lower() in _REMOTE_SCHEMES:
        return None
    parts = [part for part in re.split(r'[\\/]+', src)
             if part not in ('', '.')]
    if not parts or '..' in parts:
        return None
    return os.path.join(*parts)


def _decoded_image_relpath(src):
    """Return the URL-decoded in-folder path of a local reference, or None.

    Other tools spell non-ASCII file names with URL escapes
    ('assets/%E3%80%90.jpg'); the file on disk carries the decoded name, so
    the reference only resolves once it is decoded. None means there is
    nothing to decode (the caller keeps the literal spelling then) or the
    decoded value is not a local in-folder path: decoding can smuggle a
    '../' escape in as '%2E%2E%2F', so the boundary is checked again on the
    decoded spelling.
    """
    raw = str(src or '').strip()
    if _local_image_relpath(raw) is None:
        return None
    decoded = _url_unquote(raw)
    if decoded == raw:
        return None
    return _local_image_relpath(decoded)


def _readable_file(path):
    if not path:
        return False
    return os.path.isfile(path) and os.access(path, os.R_OK)


def _content_digest(data):
    """Return a digest of the bytes about to be written, or '' if not bytes.

    '' means there is nothing to compare (the caller writes the file as it
    always did); anything else is the key half of the shifted-file cache in
    MarkdownInput.shift_file.
    """
    if not isinstance(data, (bytes, bytearray)):
        return ''
    return hashlib.sha256(bytes(data)).hexdigest()


def _image_in_book_folder(book_dir, rel):
    """Return the image inside the book folder, or None.

    Relative references in the Markdown are rooted at the book folder;
    hand-built bundles sometimes keep images next to the .md itself.
    """
    if not book_dir:
        return None
    candidates = (os.path.join(book_dir, rel),
                  os.path.join(book_dir, os.path.basename(rel)))
    for candidate in candidates:
        if _readable_file(candidate):
            return candidate
    return None


class MarkdownInput(TXTInput):
    name = 'Markdown Input'
    author = 'Qbeenslee'
    version = (3, 20, 9)
    description = _('Convert Markdown files to HTML, with library images.')
    file_types = {'md', 'markdown'}
    commit_name = 'markdown_input'
    # TXT Input (builtin) claims .md as well. Both default to priority 1 and
    # calibre picks the first plugin claiming the format, so 2 makes this
    # plugin the one that handles Markdown conversions.
    priority = 2

    # TXT Input's own choices stay available on the CLI; the pane offers the
    # subset that makes sense for Markdown.
    options = _replace_options(TXTInput.options, (
        OptionRecommendation(
            name='md_line_break',
            recommended_value=LINE_BREAK_FOLD,
            level=OptionRecommendation.LOW,
            choices=[LINE_BREAK_FOLD, LINE_BREAK_HARD],
            help=_OPTION_HELP_LINE_BREAK,
        ),
        OptionRecommendation(
            name='read_yaml_metadata',
            recommended_value=True,
            level=OptionRecommendation.LOW,
            help=_OPTION_HELP_YAML,
        ),
        OptionRecommendation(
            name='keep_images',
            recommended_value=True,
            level=OptionRecommendation.LOW,
            help=_OPTION_HELP_KEEP_IMAGES,
        ),
        OptionRecommendation(
            name='embed_images',
            recommended_value=True,
            level=OptionRecommendation.LOW,
            help=_OPTION_HELP_EMBED_IMAGES,
        ),
        OptionRecommendation(
            name='download_remote_images',
            recommended_value=True,
            level=OptionRecommendation.LOW,
            help=_OPTION_HELP_DOWNLOAD_REMOTE,
        ),
        OptionRecommendation(
            name='keep_image_sizes',
            recommended_value=True,
            level=OptionRecommendation.LOW,
            help=_OPTION_HELP_KEEP_SIZES,
        ),
        OptionRecommendation(
            name='paragraph_type',
            recommended_value='auto',
            level=OptionRecommendation.LOW,
            choices=list(TXTInput.ui_data['paragraph_types']),
            help=_OPTION_HELP_PARAGRAPH,
        ),
        OptionRecommendation(
            name='markdown_extensions',
            recommended_value=DEFAULT_MARKDOWN_EXTENSIONS,
            level=OptionRecommendation.LOW,
            help=_OPTION_HELP_EXTENSIONS,
        ),
    ))

    def convert(self, stream, options, file_ext, log, accelerators):
        self._keep_images = bool(getattr(options, 'keep_images', True))
        self._embed_images = bool(getattr(options, 'embed_images', True))
        self._download_remote_images = bool(
            getattr(options, 'download_remote_images', True))
        self._keep_image_sizes = bool(
            getattr(options, 'keep_image_sizes', True))
        self._book_dir = resolve_book_dir_for_options(options, log)
        self._yaml_language = ''
        self._shifted_by_content = {}
        stream = self._prepare_stream(stream, options, log)
        oeb = super().convert(stream, options, file_ext, log, accelerators)
        self._apply_yaml_language(oeb)
        return oeb

    def is_customizable(self):
        return True

    def config_widget(self):
        from calibre.customize.ui import plugin_customization
        from calibre_plugins.markdown.input.preference_ui import ConfigWidget

        try:
            raw = plugin_customization(self)
        except Exception:
            raw = ''
        return ConfigWidget(raw)

    def save_settings(self, config_widget):
        from calibre.customize.ui import customize_plugin
        from calibre_plugins.markdown.utils.prefs import serialize_customization

        customize_plugin(
            self, serialize_customization(config_widget.overrides()))

    def gui_configuration_widget(self, parent, get_option_by_name,
                                 get_option_help, db, book_id=None):
        """The conversion dialog pane shown for Markdown input."""
        from calibre.customize.ui import plugin_customization
        from calibre_plugins.markdown.input.conversion_ui import PluginWidget

        try:
            overrides = parse_customization(plugin_customization(self))
        except Exception:
            overrides = {}
        return PluginWidget(parent, get_option_by_name, get_option_help,
                            db, book_id, overrides=overrides)

    def _prepare_stream(self, stream, options, log=None):
        """Read the input, drop the YAML block when asked, hand it on.

        The dialog options need the raw bytes before TXT Input decodes
        them; the builtin pipeline then runs unchanged on the wrapper.
        The YAML block, when kept, is passed through untouched: its lines
        are front matter, not text to reshape.
        """
        self._apply_line_break_extensions(options)
        data = stream.read()
        if not isinstance(data, (bytes, bytearray)):
            return stream
        data = bytes(data)
        block, rest = split_yaml_front_matter(data)
        head = b''
        if block is not None and getattr(options, 'read_yaml_metadata', True):
            self._yaml_language = yaml_front_matter_language(block)
            head = normalize_yaml_front_matter(block)
        rest = self._restructure_paragraphs(rest, options, log)
        return _ReplayStream(head + rest, getattr(stream, 'name', None))

    def _restructure_paragraphs(self, data, options, log=None):
        """Apply the paragraph style to the body before Markdown parses it.

        Markdown starts a paragraph at a blank line only, so a file written
        one paragraph per line ('single') or with indented paragraph starts
        ('print') collapses into a single paragraph per chapter. TXT Input
        forces paragraph_type='off' for .md files, so the style is detected
        and applied here; the reshaping itself is Markdown aware, never
        splits code, lists or tables apart, and applies to the text a quote
        block carries as well - a quote stays one quote, its lines become
        the paragraphs inside it.

        Reshaped text is handed on as UTF-8 (and announced through
        input_encoding) because it was decoded once to be inspected. When
        nothing needs reshaping the original bytes are returned untouched.
        """
        if not data.strip():
            return data
        try:
            choice = getattr(options, 'paragraph_type', None) or 'auto'
            if choice in ('block', 'off'):
                return data
            text = decode_body(data, options)
            if choice == 'auto':
                style = paragraphs.detect_paragraph_type(text)
            elif choice == 'unformatted':
                # No blank lines, no indents: every line is a paragraph.
                style = paragraphs.PARAGRAPH_SINGLE
            else:
                style = choice
            if style == paragraphs.PARAGRAPH_BLOCK:
                self._log_debug(
                    'paragraph style: auto detected block, text left as is'
                    if choice == 'auto' else
                    'paragraph style: %s, text left as is' % style, log)
                return data
            reshaped = paragraphs.restructure_paragraphs(text, style)
            if reshaped == text:
                self._log_debug(
                    'paragraph style: %s, already in shape' % style, log)
                return data
            self._log_debug(
                'paragraph style: %s%s, %d blank line(s) inserted'
                % (style, ' (auto detected)' if choice == 'auto' else '',
                   reshaped.count('\n') - text.count('\n')), log)
            options.input_encoding = 'utf-8'
            return reshaped.encode('utf-8')
        except Exception as exc:
            self._log_debug('paragraph detection skipped: %r' % (exc,), log)
            return data

    def _apply_line_break_extensions(self, options):
        """Keep md_line_break and markdown_extensions in agreement.

        'hard' enables python-markdown's nl2br, 'fold' disables it. The
        pane offers nl2br only through the line-break choice, so this is
        the single source of truth for that extension.
        """
        mode = getattr(options, 'md_line_break', LINE_BREAK_FOLD)
        raw = getattr(options, 'markdown_extensions', '') or ''
        names = [name.strip() for name in raw.split(',') if name.strip()]
        wanted = mode == LINE_BREAK_HARD
        if wanted == ('nl2br' in names):
            return
        if wanted:
            names.append('nl2br')
        else:
            names = [name for name in names if name != 'nl2br']
        options.markdown_extensions = ', '.join(names)

    def _apply_yaml_language(self, oeb):
        """Apply the language declared in the YAML front matter.

        calibre maps title/authors/tags/description from the front matter
        itself but ignores 'language', and falls back to the UI language
        when nothing declares one - so the YAML value replaces whatever is
        there. Library metadata is merged later in the pipeline and still
        wins over it.
        """
        language = getattr(self, '_yaml_language', '')
        if not language or oeb is None:
            return
        try:
            from calibre.utils.localization import canonicalize_lang

            code = canonicalize_lang(language) or language
            if code.lower() in ('und', ''):
                return
            metadata = oeb.metadata
            metadata.clear('language')
            metadata.add('language', code)
            self._log_debug('language %r taken from YAML front matter' % code)
        except Exception as exc:
            self._log_debug('could not apply the YAML language: %r' % (exc,))

    def fix_resources(self, html, base_dir):
        """Keep/stage/download images, then run the builtin resource handling.

        "Keep images" is the master switch: off, every <img> tag goes and
        neither staging nor downloading runs. On, local images are staged
        (embed_images) and remote ones downloaded next to the input
        (embed_images + download_remote_images), so the builtin resource
        handling embeds them like any other local file. A local reference
        spelled with URL escapes is rewritten to the decoded path on the
        way, so the builtin finds the file it names.

        The builtin handling embeds one file per <img> element; images with
        identical bytes share a single file through shift_file below, so a
        book that uses the same image many times ships it once.
        """
        if not self._wants_images():
            html = strip_image_tags(html)
            self._log_debug('images dropped (keep_images is off)')
        else:
            if self._wants_embed_images():
                html = self._stage_library_images(html, base_dir)
            if self._wants_remote_images():
                html = self._fetch_remote_images(html, base_dir)
        if not self._wants_image_sizes():
            # "Keep image sizes" off: the images enter the book with no size
            # at all, as if the Markdown never declared one.
            html = strip_image_sizes(html)
            self._log_debug('image sizes dropped (keep_image_sizes is off)')
        return super().fix_resources(html, base_dir)

    def shift_file(self, fname, data):
        """Write the file the builtin handling asks for, once per content.

        TXT Input calls this once per <img> element and its own version
        hands every call a fresh name ('x.png', 'x-1.png', ...) because the
        copy it wrote before is already there - so a Markdown file using one
        image 110 times ships 110 copies of it. Identical bytes are written
        once instead: the cache key is the extension (it decides the media
        type) plus a digest of the data, so every spelling of one image, and
        two file names carrying the same bytes, end up as a single file that
        all the references point at.
        """
        digest = _content_digest(data)
        if not digest:
            return super().shift_file(fname, data)
        cache = self._shifted_file_cache()
        key = (os.path.splitext(fname)[1].lower(), digest)
        cached = cache.get(key)
        if cached is not None and os.path.exists(cached):
            self._log_debug('reusing %s for %s' % (os.path.basename(cached),
                                                   fname))
            return cached
        path = super().shift_file(fname, data)
        cache[key] = path
        return path

    def _shifted_file_cache(self):
        """The files this conversion wrote, keyed by (extension, digest)."""
        cache = getattr(self, '_shifted_by_content', None)
        if cache is None:
            cache = self._shifted_by_content = {}
        return cache

    def _wants_images(self):
        return getattr(self, '_keep_images', True)

    def _wants_embed_images(self):
        return getattr(self, '_embed_images', True)

    def _wants_remote_images(self):
        return self._wants_embed_images() and getattr(
            self, '_download_remote_images', True)

    def _fetch_remote_images(self, html, base_dir):
        """Download remote images next to the input; rewrite their src.

        Named apart from the _download_remote_images switch this runs for.
        The rewritten references are ordinary local ones, so the builtin
        resource handling embeds the downloaded files like any staged
        image. A src value is HTML-escaped in the markup (&amp; in query
        strings), so the fetch unescapes it while the rewrite keys keep
        the spelling the html carries. Failures are skipped and reported.
        """
        try:
            urls = collect_remote_image_urls(html)
        except Exception as exc:
            self._log_debug('could not scan image references: %r' % (exc,))
            return html
        if not urls:
            return html
        reserved = (
            set(os.listdir(base_dir)) if os.path.isdir(base_dir) else set())
        names = {}
        failed = []
        for url in urls:
            name = save_remote_image(_html_unescape(url), base_dir, reserved)
            if name is None:
                failed.append(url)
                continue
            names[url] = name
        if names:
            html, _count = rewrite_remote_image_refs(html, names)
            self._log_debug('downloaded %d remote image(s)' % len(names))
        self._warn_remote_failures(failed)
        return html

    def _warn_remote_failures(self, failed):
        """Report the remote images that could not be downloaded."""
        if not failed:
            return
        log = getattr(self, 'log', None)
        if log is None:
            return
        from calibre_plugins.markdown.translations.messages import (
            REMOTE_DOWNLOAD_FAILED_MESSAGE as _message,
            _ as _i18n,
        )

        unique = sorted(set(failed))
        sample = '、'.join(unique[:5])
        if len(unique) > 5:
            sample += ' …'
        log.warn(_i18n(_message).format(len(unique), sample))

    def _wants_image_sizes(self):
        return getattr(self, '_keep_image_sizes', True)

    def _stage_library_images(self, html, base_dir):
        """Copy the book folder's images next to the input; decode references.

        A file already next to the input file is left to the builtin
        fix_resources, path checks included. References that resolve nowhere
        are reported: silently dropping them is the failure mode this plugin
        exists to prevent. Returns the html to hand on, with every reference
        that had to be decoded pointing at the path it actually resolved to.
        """
        if not html or not base_dir:
            return html
        try:
            refs = self._image_refs(html)
        except Exception as exc:
            self._log_debug('could not scan image references: %r' % (exc,))
            return html
        book_dir = getattr(self, '_book_dir', None)
        unresolved = []
        rewrites = {}
        for src in refs:
            try:
                resolved = self._resolve_local_image(src, base_dir, book_dir)
            except Exception as exc:
                self._log_debug('could not stage image %r: %r' % (src, exc))
                continue
            if resolved is None:
                unresolved.append(str(src))
            elif resolved:
                rewrites[str(src)] = resolved
        if rewrites:
            html, count = rewrite_html_image_srcs(html, rewrites)
            self._log_debug('decoded %d image reference(s) to the path they '
                            'resolved to' % count)
        if unresolved:
            self._warn_unresolved(unresolved)
        return html

    def _resolve_local_image(self, src, base_dir, book_dir):
        """Resolve one reference against the input folder and the book folder.

        Returns '' when nothing has to change (not a local relative file, or
        the image already sits next to the input under the spelling the
        Markdown uses), the decoded relative path when the reference was
        rewritten to it, and None when the image is found nowhere. The
        literal spelling always wins, so a file really named 'a%20b.jpg'
        keeps working.
        """
        rel = _local_image_relpath(src)
        if rel is None:
            return ''
        if _readable_file(os.path.join(base_dir, rel)):
            return ''
        decoded = _decoded_image_relpath(src)
        if decoded is not None and _readable_file(
                os.path.join(base_dir, decoded)):
            self._log_debug('using the decoded image name %s' % decoded)
            return decoded
        for candidate in (rel, decoded):
            if candidate is None:
                continue
            source = _image_in_book_folder(book_dir, candidate)
            if source is None:
                continue
            dest = os.path.join(base_dir, candidate)
            parent = os.path.dirname(dest)
            if parent:
                os.makedirs(parent, exist_ok=True)
            shutil.copy2(source, dest)
            self._log_debug(
                'staged library image %s as %s' % (source, candidate))
            return candidate if candidate != rel else ''
        return None

    def _warn_unresolved(self, refs):
        log = getattr(self, 'log', None)
        if log is None:
            return
        from calibre_plugins.markdown.translations.messages import _ as _i18n

        unique = sorted(set(refs))
        sample = '、'.join(unique[:5])
        if len(unique) > 5:
            sample += ' …'
        log.warn(_i18n(_UNRESOLVED_MESSAGE).format(len(unique), sample))

    def _image_refs(self, html):
        from html5_parser import parse

        return [src for src in parse(html).xpath('//img/@src') if src]

    def _log_debug(self, message, log=None):
        # Before convert() runs calibre has not set self.log yet, so the
        # early steps (stream preparation) pass their own logger along.
        log = log if log is not None else getattr(self, 'log', None)
        if log is not None:
            log.debug('Markdown: %s' % message)


def register_markdown_input_plugin(installation_type=None):
    """Add MarkdownInput to calibre's plugin registry, once.

    A plugin zip exposes exactly one Plugin subclass - calibre's zipplugin
    loader keeps plugin_classes[0] - so this plugin cannot be a second
    top-level class in the package __init__. MarkdownOutput.initialize()
    registers it instead. The instance is put in front of the registry:
    plugin_for_input_format() takes the first plugin claiming a format, and
    the builtin TXT Input claims .md as well.
    """
    from calibre.customize import ui as customize_ui

    plugins = customize_ui._initialized_plugins
    if any(isinstance(plugin, MarkdownInput) for plugin in plugins):
        return None
    plugin = MarkdownInput(None)
    if installation_type is not None:
        plugin.installation_type = installation_type
    if customize_ui.is_disabled(plugin):
        return None
    plugins.insert(0, plugin)
    return plugin
