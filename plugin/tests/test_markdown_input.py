# -*- coding: utf-8 -*-
"""Markdown input: staged library images plus the pane's option handling."""

import codecs
import types

import pytest

import calibre_plugins.markdown.input.input_plugin as input_mod
from calibre_plugins.markdown.input.input_plugin import (
    MarkdownInput,
    decode_body,
    normalize_yaml_front_matter,
    split_yaml_front_matter,
    yaml_front_matter_language,
)
from calibre_plugins.markdown.utils.prefs import serialize_customization

JPEG = b'\xff\xd8\xff\xe0JPEG'

FRONT_MATTER = (
    '---\n'
    'title: 尘缘\n'
    'authors: 烟雨江南\n'
    'language: zho\n'
    'tags:\n'
    '  - 出版\n'
    '  - 玄幻\n'
    'description: 仙界天河边的一块青石。\n'
    'calibre_id: 919\n'
    '---\n'
    '# 作品相关\n'
    '\n'
    '![背景图](images/1.jpg)\n'
).encode('utf-8')

BODY = '# 作品相关\n\n![背景图](images/1.jpg)\n'.encode('utf-8')


def _b(text):
    """UTF-8 bytes (byte literals cannot hold non-ASCII source characters)."""
    return text.encode('utf-8')


class _Options:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class _Stream:
    def __init__(self, data, name='/tmp/book.md'):
        self._data = data
        self.name = name

    def read(self, *args):
        return self._data


def _refs(monkeypatch, *srcs):
    """Pin the image references the plugin scans out of the HTML."""
    monkeypatch.setattr(
        MarkdownInput, '_image_refs',
        staticmethod(lambda html: list(srcs)))


def _book_folder(tmp_path, name='book'):
    book = tmp_path / name
    (book / 'images').mkdir(parents=True)
    return book


def test_missing_image_is_staged_from_the_book_folder(tmp_path, monkeypatch):
    base = tmp_path / 'input'
    base.mkdir()
    book = _book_folder(tmp_path)
    (book / 'images' / '1.jpg').write_bytes(JPEG)
    plugin = MarkdownInput()
    plugin._book_dir = str(book)
    _refs(monkeypatch, 'images/1.jpg')

    plugin._stage_library_images('<img src="images/1.jpg"/>', str(base))

    assert (base / 'images' / '1.jpg').read_bytes() == JPEG


def test_image_next_to_the_input_file_wins(tmp_path, monkeypatch):
    base = tmp_path / 'input'
    (base / 'images').mkdir(parents=True)
    (base / 'images' / '1.jpg').write_bytes(b'local')
    book = _book_folder(tmp_path)
    (book / 'images' / '1.jpg').write_bytes(JPEG)
    plugin = MarkdownInput()
    plugin._book_dir = str(book)
    _refs(monkeypatch, 'images/1.jpg')

    plugin._stage_library_images('<img src="images/1.jpg"/>', str(base))

    assert (base / 'images' / '1.jpg').read_bytes() == b'local'


def test_image_missing_everywhere_writes_nothing(tmp_path, monkeypatch):
    base = tmp_path / 'input'
    base.mkdir()
    book = _book_folder(tmp_path)
    plugin = MarkdownInput()
    plugin._book_dir = str(book)
    _refs(monkeypatch, 'images/1.jpg')

    plugin._stage_library_images('<img src="images/1.jpg"/>', str(base))

    assert list(base.iterdir()) == []


def test_image_at_the_book_folder_root_is_found(tmp_path, monkeypatch):
    # Hand-built bundles sometimes keep images next to the .md itself.
    base = tmp_path / 'input'
    base.mkdir()
    book = _book_folder(tmp_path)
    (book / '1.jpg').write_bytes(JPEG)
    plugin = MarkdownInput()
    plugin._book_dir = str(book)
    _refs(monkeypatch, 'images/1.jpg')

    plugin._stage_library_images('<img src="images/1.jpg"/>', str(base))

    assert (base / 'images' / '1.jpg').read_bytes() == JPEG


@pytest.mark.parametrize('src', [
    'http://example.com/a.jpg',
    'https://example.com/a.jpg',
    'data:image/jpeg;base64,AAAA',
    '/absolute/a.jpg',
    '../escape.jpg',
    'images/../../escape.jpg',
])
def test_references_that_could_escape_are_ignored(tmp_path, monkeypatch, src):
    base = tmp_path / 'input'
    base.mkdir()
    book = _book_folder(tmp_path)
    (book / 'a.jpg').write_bytes(JPEG)
    (book / 'escape.jpg').write_bytes(JPEG)
    plugin = MarkdownInput()
    plugin._book_dir = str(book)
    _refs(monkeypatch, src)

    plugin._stage_library_images('<img src="%s"/>' % src, str(base))

    assert list(base.iterdir()) == []


def test_without_a_book_folder_nothing_is_staged(tmp_path, monkeypatch):
    base = tmp_path / 'input'
    base.mkdir()
    plugin = MarkdownInput()
    plugin._book_dir = None
    _refs(monkeypatch, 'images/1.jpg')

    plugin._stage_library_images('<img src="images/1.jpg"/>', str(base))

    assert list(base.iterdir()) == []


def test_unreadable_book_folder_is_ignored(tmp_path, monkeypatch):
    base = tmp_path / 'input'
    base.mkdir()
    plugin = MarkdownInput()
    plugin._book_dir = str(tmp_path / 'gone')
    _refs(monkeypatch, 'images/1.jpg')

    plugin._stage_library_images('<img src="images/1.jpg"/>', str(base))

    assert list(base.iterdir()) == []


def test_fix_resources_stages_then_delegates(tmp_path, monkeypatch):
    base = tmp_path / 'input'
    base.mkdir()
    book = _book_folder(tmp_path)
    (book / 'images' / '1.jpg').write_bytes(JPEG)
    plugin = MarkdownInput()
    plugin._book_dir = str(book)
    _refs(monkeypatch, 'images/1.jpg')
    html = '<img src="images/1.jpg"/>'

    assert plugin.fix_resources(html, str(base)) == html
    assert (base / 'images' / '1.jpg').read_bytes() == JPEG
    assert plugin.fix_resources_seen == (html, str(base))


def test_register_markdown_input_plugin(monkeypatch):
    import calibre.customize.ui as customize_ui

    monkeypatch.setattr(customize_ui, '_initialized_plugins', [])
    monkeypatch.setattr(customize_ui, 'is_disabled', lambda plugin: False)

    registered = input_mod.register_markdown_input_plugin()
    assert isinstance(registered, MarkdownInput)
    assert customize_ui._initialized_plugins == [registered]

    # Registering twice must not duplicate the plugin.
    assert input_mod.register_markdown_input_plugin() is None
    assert customize_ui._initialized_plugins == [registered]


def test_register_keeps_the_plugin_in_front(monkeypatch):
    # plugin_for_input_format() returns the first plugin claiming the
    # format, and the builtin TXT Input claims .md as well.
    import calibre.customize.ui as customize_ui

    class Other:
        name = 'Stub TXT Input'

    monkeypatch.setattr(customize_ui, '_initialized_plugins', [Other()])
    monkeypatch.setattr(customize_ui, 'is_disabled', lambda plugin: False)

    registered = input_mod.register_markdown_input_plugin((3, 0, 0))

    assert customize_ui._initialized_plugins[0] is registered
    assert registered.installation_type == (3, 0, 0)


def test_register_skips_a_disabled_plugin(monkeypatch):
    import calibre.customize.ui as customize_ui

    monkeypatch.setattr(customize_ui, '_initialized_plugins', [])
    monkeypatch.setattr(customize_ui, 'is_disabled', lambda plugin: True)

    assert input_mod.register_markdown_input_plugin() is None
    assert customize_ui._initialized_plugins == []


class _RecordingLog:
    def __init__(self):
        self.warnings = []
        self.debugs = []

    def debug(self, *args):
        self.debugs.append(args[0] if args else '')

    def warn(self, message):
        self.warnings.append(message)


def test_unresolved_images_are_reported_once(tmp_path, monkeypatch):
    base = tmp_path / 'input'
    base.mkdir()
    book = _book_folder(tmp_path)
    plugin = MarkdownInput()
    plugin._book_dir = str(book)
    plugin.log = _RecordingLog()
    _refs(monkeypatch, 'images/1.jpg', 'images/1.jpg', 'images/2.jpg')

    plugin._stage_library_images('<img src="images/1.jpg"/>', str(base))

    assert len(plugin.log.warnings) == 1
    assert '1.jpg' in plugin.log.warnings[0]
    assert '2.jpg' in plugin.log.warnings[0]


def test_resolved_images_are_not_reported(tmp_path, monkeypatch):
    base = tmp_path / 'input'
    base.mkdir()
    book = _book_folder(tmp_path)
    (book / 'images' / '1.jpg').write_bytes(JPEG)
    plugin = MarkdownInput()
    plugin._book_dir = str(book)
    plugin.log = _RecordingLog()
    _refs(monkeypatch, 'images/1.jpg')

    plugin._stage_library_images('<img src="images/1.jpg"/>', str(base))

    assert plugin.log.warnings == []


def test_convert_resolves_the_book_folder(monkeypatch):
    from calibre.ebooks.conversion.plugins.txt_input import TXTInput

    plugin = MarkdownInput()
    seen = []

    def fake_resolve(opts, log):
        seen.append(opts)
        return '/lib/book'

    monkeypatch.setattr(input_mod, 'resolve_book_dir_for_options', fake_resolve)
    monkeypatch.setattr(TXTInput, 'convert', lambda self, *args: 'oeb')
    opts = _md_options()

    assert plugin.convert(_Stream(BODY), opts, 'md', None, {}) == 'oeb'
    assert plugin._book_dir == '/lib/book'
    assert seen == [opts]


# --- YAML front matter -----------------------------------------------------

def test_split_front_matter_lf():
    block, rest = split_yaml_front_matter(FRONT_MATTER)
    assert block.startswith(b'---\n') and block.endswith(b'---\n')
    assert b'title' in block
    assert rest == BODY


def test_split_front_matter_crlf_keeps_bom_on_both_pieces():
    data = codecs.BOM_UTF8 + FRONT_MATTER.replace(b'\n', b'\r\n')
    block, rest = split_yaml_front_matter(data)
    assert block.startswith(codecs.BOM_UTF8) and b'title' in block
    assert rest == codecs.BOM_UTF8 + BODY.replace(b'\n', b'\r\n')


def test_split_without_front_matter_leaves_data_alone():
    assert split_yaml_front_matter(BODY) == (None, BODY)
    assert split_yaml_front_matter(b'') == (None, b'')


def test_unclosed_front_matter_is_not_stripped():
    data = b'---\ntitle: x\n\nno closing delimiter\n'
    assert split_yaml_front_matter(data) == (None, data)


def test_dots_terminator_closes_the_block():
    _block, rest = split_yaml_front_matter(b'---\na: 1\n...\nbody\n')
    assert rest == b'body\n'


@pytest.mark.parametrize('block,expected', [
    (b'---\nlanguage: zho\n---\n', 'zho'),
    (b'---\nlanguage: "zh-CN"\n---\n', 'zh-CN'),
    (b"---\nlanguage: 'zh'\n---\n", 'zh'),
    (b'---\nlanguage: zh  # comment\n---\n', 'zh'),
    (b'---\n  language:\tzho\n---\n', 'zho'),
    (b'---\ntitle: x\n---\n', ''),
    (b'---\nlanguage:\n---\n', ''),
    (b'', ''),
])
def test_yaml_language_values(block, expected):
    assert yaml_front_matter_language(block) == expected


def test_yaml_list_items_become_repeated_keys():
    # python-markdown's meta extension cannot read YAML lists; the repeated
    # key form is what it turns into a list value. Left as-is, '- 出版'
    # would show up as body text in the converted book.
    block, _rest = split_yaml_front_matter(FRONT_MATTER)

    normalized = normalize_yaml_front_matter(block)

    assert _b('tags: 出版\n') in normalized
    assert _b('tags: 玄幻\n') in normalized
    assert _b('- 出版') not in normalized


def test_bare_key_line_is_replaced_by_its_first_item():
    # 'tags:' with no value would otherwise become an empty subject.
    block, _rest = split_yaml_front_matter(FRONT_MATTER)

    normalized = normalize_yaml_front_matter(block)

    assert b'tags:\n' not in normalized


def test_description_is_aliased_to_comments():
    # calibre maps comments/summary from the front matter, not description;
    # this plugin's own output writes 'description'.
    block, _rest = split_yaml_front_matter(FRONT_MATTER)

    normalized = normalize_yaml_front_matter(block)

    assert _b('comments: 仙界天河边的一块青石。\n') in normalized
    assert b'description:' not in normalized


def test_normalizing_keeps_the_other_lines():
    block, rest = split_yaml_front_matter(FRONT_MATTER)

    normalized = normalize_yaml_front_matter(block)

    for line in (b'---\n', _b('title: 尘缘'), _b('authors: 烟雨江南'),
                 b'language: zho', b'calibre_id: 919'):
        assert line in normalized
    assert rest == BODY


def test_a_bare_key_without_items_is_kept():
    data = b'---\ntags:\n---\n'
    block, _rest = split_yaml_front_matter(data)

    assert normalize_yaml_front_matter(block) == data


def test_four_space_list_items_are_repeated_keys_too():
    data = '---\ntags:\n    - 出版\n---\n'.encode('utf-8')
    block, _rest = split_yaml_front_matter(data)

    assert normalize_yaml_front_matter(block) == (
        '---\ntags: 出版\n---\n'.encode('utf-8'))


def test_four_space_continuations_are_left_alone():
    data = b'---\ntitle: first\n    second line\n---\n'
    block, _rest = split_yaml_front_matter(data)

    assert normalize_yaml_front_matter(block) == block


def test_top_level_dash_lines_are_left_alone():
    data = b'---\ntitle: x\n---\n\n- body item\n'
    block, _rest = split_yaml_front_matter(data)

    assert normalize_yaml_front_matter(block) == block


def test_list_items_without_a_key_are_left_alone():
    data = b'---\n  - orphan\n---\n'
    block, _rest = split_yaml_front_matter(data)

    assert normalize_yaml_front_matter(block) == block


# --- paragraph style -------------------------------------------------------

def _single_document(lines=30):
    """One paragraph per line, the layout of a typeset novel."""
    return ''.join('第%d行正文，每行一段。\n' % i for i in range(1, lines + 1))


def test_auto_detects_single_line_paragraphs():
    data = _b('# 第一章\n' + _single_document())
    opts = _md_options(input_encoding='utf-8')
    result = MarkdownInput()._restructure_paragraphs(data, opts)

    assert result.decode('utf-8').startswith(
        '# 第一章\n\n第1行正文，每行一段。\n\n第2行正文')
    assert opts.input_encoding == 'utf-8'


def test_auto_leaves_standard_markdown_alone():
    data = _b(''.join('第%d段正文，空行分段。\n\n' % i for i in range(1, 13)))
    opts = _md_options(input_encoding='utf-8')
    result = MarkdownInput()._restructure_paragraphs(data, opts)

    assert result == data
    assert opts.input_encoding == 'utf-8'


def test_auto_leaves_short_text_alone():
    data = _b('第一行\n第二行\n')
    opts = _md_options(input_encoding='utf-8')

    assert MarkdownInput()._restructure_paragraphs(data, opts) == data


def test_auto_detects_the_encoding_when_none_is_given():
    data = _b(_single_document())
    opts = _md_options()                    # input_encoding unset: auto
    result = MarkdownInput()._restructure_paragraphs(data, opts)

    assert b'\n\n' in result
    assert opts.input_encoding == 'utf-8'


def test_a_gbk_document_is_handed_on_as_utf8():
    data = _single_document().encode('gbk')
    opts = _md_options(input_encoding='gbk')
    result = MarkdownInput()._restructure_paragraphs(data, opts)

    assert result.decode('utf-8').startswith('第1行正文，每行一段。\n\n')
    assert opts.input_encoding == 'utf-8'


@pytest.mark.parametrize('choice', ['single', 'unformatted'])
def test_explicit_style_is_applied_without_detection(choice):
    data = _b('第一行\n第二行\n')
    opts = _md_options(paragraph_type=choice, input_encoding='utf-8')
    result = MarkdownInput()._restructure_paragraphs(data, opts)

    assert result.decode('utf-8') == '第一行\n\n第二行\n'


def test_explicit_print_uses_the_indented_lines():
    data = _b('一段一行\n\u3000\u3000另一段\n')
    opts = _md_options(paragraph_type='print', input_encoding='utf-8')
    result = MarkdownInput()._restructure_paragraphs(data, opts)

    assert result.decode('utf-8') == '一段一行\n\n\u3000\u3000另一段\n'


@pytest.mark.parametrize('choice', ['block', 'off'])
def test_block_and_off_leave_the_text_alone(choice):
    data = _b(_single_document())
    opts = _md_options(paragraph_type=choice, input_encoding='utf-8')

    assert MarkdownInput()._restructure_paragraphs(data, opts) == data


def test_a_missing_paragraph_type_reads_as_auto():
    data = _b(_single_document())
    opts = _md_options(paragraph_type=None, input_encoding='utf-8')

    assert b'\n\n' in MarkdownInput()._restructure_paragraphs(data, opts)


def test_decode_body_prefers_the_given_encoding():
    assert decode_body('正文'.encode('gbk'), _Options(input_encoding='gbk')) == '正文'
    assert decode_body(b'\xef\xbb\xbf' + _b('正文'),
                       _Options(input_encoding='utf-8')) == '正文'


# --- single line breaks ----------------------------------------------------

def test_hard_line_breaks_enable_nl2br():
    opts = _Options(md_line_break='hard', markdown_extensions='tables, toc')
    MarkdownInput()._apply_line_break_extensions(opts)
    assert opts.markdown_extensions == 'tables, toc, nl2br'


def test_fold_line_breaks_disable_nl2br():
    opts = _Options(md_line_break='fold',
                    markdown_extensions='tables, nl2br, toc')
    MarkdownInput()._apply_line_break_extensions(opts)
    assert opts.markdown_extensions == 'tables, toc'


@pytest.mark.parametrize('mode,expected', [
    ('hard', 'tables, nl2br'), ('fold', 'tables')])
def test_line_breaks_are_idempotent(mode, expected):
    opts = _Options(md_line_break=mode, markdown_extensions='tables')
    plugin = MarkdownInput()
    plugin._apply_line_break_extensions(opts)
    plugin._apply_line_break_extensions(opts)
    assert opts.markdown_extensions == expected


# --- convert() -------------------------------------------------------------

def _md_options(**kwargs):
    values = dict(read_yaml_metadata=True, paragraph_type='auto',
                  md_line_break='fold', markdown_extensions='tables')
    values.update(kwargs)
    return _Options(**values)


def _patch_conversion(monkeypatch, fake_convert):
    from calibre.ebooks.conversion.plugins.txt_input import TXTInput

    monkeypatch.setattr(TXTInput, 'convert', fake_convert)
    monkeypatch.setattr(input_mod, 'resolve_book_dir_for_options',
                        lambda opts, log: None)


def test_yaml_is_stripped_when_reading_is_off(monkeypatch):
    seen = {}

    def fake_convert(self, stream, options, file_ext, log, accelerators):
        seen['data'] = stream.read()
        seen['name'] = stream.name
        return None

    _patch_conversion(monkeypatch, fake_convert)
    MarkdownInput().convert(
        _Stream(FRONT_MATTER, '/tmp/book.md'),
        _md_options(read_yaml_metadata=False), 'md', None, {})

    assert seen['data'] == BODY
    assert seen['name'] == '/tmp/book.md'


class _FakeMetadata:
    """oeb.metadata stand-in recording clear()/add() calls."""

    def __init__(self, languages=()):
        self.language = list(languages)
        self.cleared = []
        self.added = []

    def clear(self, name):
        self.cleared.append(name)
        if name == 'language':
            self.language = []

    def add(self, name, value, **kwargs):
        self.added.append((name, value))
        if name == 'language':
            self.language.append(value)


def test_yaml_is_kept_and_the_language_read(monkeypatch):
    seen = {}
    metadata = _FakeMetadata()

    def fake_convert(self, stream, options, file_ext, log, accelerators):
        seen['data'] = stream.read()
        return types.SimpleNamespace(metadata=metadata)

    _patch_conversion(monkeypatch, fake_convert)
    MarkdownInput().convert(_Stream(FRONT_MATTER), _md_options(), 'md', None, {})

    # The metadata block stays in the text (calibre's meta extension reads
    # it) and the body follows untouched.
    assert _b('title: 尘缘') in seen['data']
    assert seen['data'].endswith(BODY)
    assert metadata.added == [('language', 'zho')]


def test_yaml_language_overrides_the_calibre_default(monkeypatch):
    # calibre falls back to the UI language when nothing declares one; the
    # YAML value must still win over that guess.
    metadata = _FakeMetadata(languages=['zh'])
    oeb = types.SimpleNamespace(metadata=metadata)
    _patch_conversion(monkeypatch, lambda self, *args: oeb)

    MarkdownInput().convert(_Stream(FRONT_MATTER), _md_options(), 'md', None, {})

    assert metadata.cleared == ['language']
    assert metadata.added == [('language', 'zho')]
    assert metadata.language == ['zho']


def test_convert_normalizes_yaml_lists(monkeypatch):
    seen = {}

    def fake_convert(self, stream, options, file_ext, log, accelerators):
        seen['data'] = stream.read()
        return None

    _patch_conversion(monkeypatch, fake_convert)
    MarkdownInput().convert(_Stream(FRONT_MATTER), _md_options(), 'md', None, {})

    assert _b('tags: 出版\n') in seen['data']
    assert _b('tags: 玄幻\n') in seen['data']
    assert _b('- 出版') not in seen['data']
    assert seen['data'].endswith(BODY)


def test_convert_applies_an_explicit_paragraph_type(monkeypatch):
    seen = {}

    def fake_convert(self, stream, options, file_ext, log, accelerators):
        seen['data'] = stream.read()
        return None

    _patch_conversion(monkeypatch, fake_convert)
    opts = _md_options(paragraph_type='single', input_encoding='utf-8')
    MarkdownInput().convert(
        _Stream(_b('第一行\n第二行\n')), opts, 'md', None, {})

    # The style is applied before TXT Input runs, so its own 'off' for .md
    # files cannot discard it.
    assert seen['data'].decode('utf-8') == '第一行\n\n第二行\n'


def test_convert_leaves_a_short_auto_document_to_calibre(monkeypatch):
    seen = {}

    def fake_convert(self, stream, options, file_ext, log, accelerators):
        options.paragraph_type = 'off'
        seen['data'] = stream.read()
        seen['value'] = options.paragraph_type
        return None

    _patch_conversion(monkeypatch, fake_convert)
    MarkdownInput().convert(_Stream(BODY), _md_options(), 'md', None, {})

    assert seen['value'] == 'off'
    assert seen['data'] == BODY


def test_convert_applies_the_line_break_choice(monkeypatch):
    seen = {}

    def fake_convert(self, stream, options, file_ext, log, accelerators):
        seen['extensions'] = options.markdown_extensions
        return None

    _patch_conversion(monkeypatch, fake_convert)
    MarkdownInput().convert(_Stream(BODY), _md_options(md_line_break='hard'),
                            'md', None, {})

    assert seen['extensions'] == 'tables, nl2br'


def test_convert_ignores_the_customization_payload(monkeypatch):
    """The payload seeds the input pane's starting values only: whatever the
    conversion dialog (or CLI) commits reaches convert() and wins."""
    seen = {}

    def fake_convert(self, stream, options, file_ext, log, accelerators):
        seen['paragraph_type'] = options.paragraph_type
        seen['read_yaml_metadata'] = options.read_yaml_metadata
        return None

    _patch_conversion(monkeypatch, fake_convert)
    plugin = MarkdownInput()
    plugin.site_customization = serialize_customization(
        {'paragraph_type': 'single', 'read_yaml_metadata': False})

    plugin.convert(_Stream(BODY), _md_options(), 'md', None, {})

    assert seen['paragraph_type'] == 'auto'
    assert seen['read_yaml_metadata'] is True


def test_convert_ignores_foreign_customization_keys(monkeypatch):
    seen = {}

    def fake_convert(self, stream, options, file_ext, log, accelerators):
        seen['paragraph_type'] = options.paragraph_type
        return None

    _patch_conversion(monkeypatch, fake_convert)
    plugin = MarkdownInput()
    # An output-side key and an unknown name must not reach the conversion
    # options; the pane's own value stays authoritative.
    plugin.site_customization = serialize_customization(
        {'inline_toc': False, 'ghost': 1, 'paragraph_type': 'print'})
    opts = _md_options(paragraph_type='auto')

    plugin.convert(_Stream(BODY), opts, 'md', None, {})

    assert seen['paragraph_type'] == 'auto'
    assert not hasattr(opts, 'inline_toc')
