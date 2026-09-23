# -*- coding: utf-8 -*-
"""MarkdownOutput.convert() wiring: when the library is touched, and how the
YAML compensation reaches the writer. The heavy calibre machinery convert()
touches is replaced by small fakes (see conftest for the import stubs).
"""

import os
import sys
import types

import calibre_plugins.markdown.utils.helpers as mh
import calibre_plugins.markdown.output.output_plugin as mo

from calibre_plugins.markdown.utils.helpers import DEFAULT_IMAGE_DIR


class Opts:
    def __init__(self, **values):
        self.export_image_files = True
        self.keep_image_references = True
        self.image_output_mode = 'sidecar'
        self.yaml_front_matter = False
        self.newline = 'unix'
        self.txt_output_encoding = 'utf-8'
        self.__dict__.update(values)


class FakeItem:
    def __init__(self, data, href):
        self.data = data
        self.href = href


class FakeOEB:
    def __init__(self, items):
        self.manifest = items


class Log:
    def __init__(self):
        self.warnings = []
        self.infos = []

    def info(self, message):
        self.infos.append(message)

    def debug(self, message):
        pass

    def warn(self, message):
        self.warnings.append(message)


class Writer:
    """Stand-in for EnhancedMarkdownMLizer; records what convert() passed it."""

    def __init__(self, text='body\n', images=None):
        self.text = text
        self.images = dict(images or {})
        self.library_metadata_at_extract = 'not-called'

    def extract_content(self, oeb_book, opts):
        self.library_metadata_at_extract = getattr(opts, 'library_metadata', None)
        return self.text


def _plugin(writer, monkeypatch):
    module = types.ModuleType('calibre_plugins.markdown.output.markdownml_enhanced')
    module.EnhancedMarkdownMLizer = lambda log: writer
    monkeypatch.setitem(sys.modules, module.__name__, module)
    plugin = mo.MarkdownOutput.__new__(mo.MarkdownOutput)
    plugin.site_customization = None
    return plugin


def test_convert_without_images_does_not_open_library(monkeypatch, tmp_path):
    lookups = []
    monkeypatch.setattr(mo, 'is_temporary_output', lambda path: True)
    monkeypatch.setattr(
        mo, 'resolve_book_dir',
        lambda oeb, log, **kwargs: lookups.append(oeb))

    def boom(oeb, log):
        raise AssertionError('library opened although nothing needs it')

    monkeypatch.setattr(mo, 'resolve_book_info', boom)
    writer = Writer(images={})
    plugin = _plugin(writer, monkeypatch)

    plugin.convert(object(), str(tmp_path / 'book.md'), None, Opts(), Log())

    assert lookups == []
    assert (tmp_path / 'book.md').exists()


def test_convert_yaml_compensation_sets_library_metadata(monkeypatch, tmp_path):
    monkeypatch.setattr(mo, 'is_temporary_output', lambda path: True)
    monkeypatch.setattr(
        mo, 'resolve_book_info',
        lambda oeb, log: (None, {'calibre_id': 7}))
    writer = Writer(images={})
    plugin = _plugin(writer, monkeypatch)

    plugin.convert(
        object(), str(tmp_path / 'book.md'), None,
        Opts(yaml_front_matter=True), Log())

    assert writer.library_metadata_at_extract == {'calibre_id': 7}


def test_convert_single_lookup_serves_yaml_and_images(monkeypatch, tmp_path):
    # With YAML wanted and sidecar images present, resolve_book_info runs
    # once and its folder feeds the image export directly: no second open.
    monkeypatch.setattr(mo, 'is_temporary_output', lambda path: True)
    monkeypatch.setattr(
        mo, 'resolve_book_info',
        lambda oeb, log: ('/lib/Author/Title (7)', {'calibre_id': 7}))

    def forbidden(oeb, log, **kwargs):
        raise AssertionError('second library lookup for the same conversion')

    monkeypatch.setattr(mo, 'resolve_book_dir', forbidden)
    written = {}

    def fake_export(oeb_book, image_map, md_path, dest_dir=None):
        written['dest'] = dest_dir
        return 1

    monkeypatch.setattr(mh, 'export_mapped_images', fake_export)
    # The image must be referenced by the finished Markdown, otherwise the
    # export is skipped before it ever resolves a folder.
    writer = Writer('body\n\n![a](images/a.png)\n',
                    images={'images/a.png': 'a.png'})
    plugin = _plugin(writer, monkeypatch)

    plugin.convert(
        object(), str(tmp_path / 'book.md'), None,
        Opts(yaml_front_matter=True), Log())

    assert written['dest'] == os.path.join('/lib/Author/Title (7)',
                                           DEFAULT_IMAGE_DIR)
    assert writer.library_metadata_at_extract == {'calibre_id': 7}


def test_convert_failed_shared_lookup_warns_without_second_open(monkeypatch,
                                                                tmp_path):
    monkeypatch.setattr(mo, 'is_temporary_output', lambda path: True)
    monkeypatch.setattr(mo, 'resolve_book_info',
                        lambda oeb, log: (None, None))

    def forbidden(oeb, log, **kwargs):
        raise AssertionError('second library lookup for the same conversion')

    monkeypatch.setattr(mo, 'resolve_book_dir', forbidden)
    writer = Writer('body\n\n![a](images/a.png)\n',
                    images={'images/a.png': 'a.png'})
    plugin = _plugin(writer, monkeypatch)
    log = Log()

    plugin.convert(
        object(), str(tmp_path / 'book.md'), None,
        Opts(yaml_front_matter=True), log)

    assert any('could not locate the book folder' in message
               for message in log.warnings)


def test_convert_unknown_image_mode_warns(monkeypatch, tmp_path):
    monkeypatch.setattr(mo, 'is_temporary_output', lambda path: True)
    writer = Writer('body\n\n![a](images/a.png)\n',
                    images={'images/a.png': 'a.png'})
    plugin = _plugin(writer, monkeypatch)
    log = Log()

    plugin.convert(
        object(), str(tmp_path / 'book.md'), None,
        Opts(image_output_mode='bogus'), log)

    assert any('unknown image output mode' in message for message in log.warnings)


def test_convert_unreferenced_images_write_nothing(monkeypatch, tmp_path):
    # Cover page unchecked: the writer maps the cover image but the finished
    # Markdown never mentions it, so a book whose only image is that cover
    # must come out without an images folder next to the .md.
    monkeypatch.setattr(mo, 'is_temporary_output', lambda path: False)
    writer = Writer('body\n', images={'images/cover.jpeg': '000000.jpeg'})
    plugin = _plugin(writer, monkeypatch)
    log = Log()

    plugin.convert(object(), str(tmp_path / 'book.md'), None, Opts(), log)

    assert not (tmp_path / 'book.images').exists()
    assert any('not referenced' in message for message in log.infos)


def test_convert_writes_referenced_images_next_to_the_markdown(monkeypatch,
                                                                tmp_path):
    monkeypatch.setattr(mo, 'is_temporary_output', lambda path: False)
    writer = Writer('![cover](images/000000.jpeg)\n',
                    images={'images/cover.jpeg': '000000.jpeg'})
    plugin = _plugin(writer, monkeypatch)
    oeb = FakeOEB([FakeItem(b'\xff\xd8\xff\xe0JPEG', 'images/cover.jpeg')])

    plugin.convert(oeb, str(tmp_path / 'book.md'), None, Opts(), Log())

    assert (tmp_path / 'book.images' / '000000.jpeg').read_bytes() == \
        b'\xff\xd8\xff\xe0JPEG'
