# -*- coding: utf-8 -*-
"""Library lookup for conversions: uuid first, unique title as fallback."""

import os

from calibre_plugins.markdown.utils.library import (
    is_temporary_output,
    resolve_book_dir,
    resolve_book_dir_for_options,
    resolve_book_info,
)


class FakeNewAPI:
    def __init__(self, books, dirs):
        self._books = books      # {book_id: {'uuid', 'title', 'authors'}}
        self._dirs = dirs        # {book_id: '/lib/Author/Title (id)/Title.epub'}

    def lookup_by_uuid(self, uuid):
        for bid, info in self._books.items():
            if info['uuid'] == uuid:
                return bid
        return None

    def search(self, query):
        # calibre matches titles loosely, so a title that merely contains the
        # queried one also counts as a hit.
        return {bid for bid, info in self._books.items()
                if 'title:"%s"' % info['title'] in query
                or _query_title(query) in info['title']}

    def field_for(self, field, book_id):
        return self._books.get(book_id, {}).get(field)

    def formats(self, book_id):
        return ('EPUB',)

    def format_abspath(self, book_id, fmt):
        assert isinstance(fmt, str) and fmt == fmt.upper(), 'fmt must be upper'
        return self._dirs.get(book_id)


def _query_title(query):
    return query.split('title:"')[-1].rstrip('"')


class FakeDB:
    """Only new_api is exposed: the legacy API is the trap we must avoid."""

    def __init__(self, books, dirs):
        self.new_api = FakeNewAPI(books, dirs)

    def format_abspath(self, *args, **kwargs):
        raise AssertionError(
            'legacy format_abspath() defaults to index_is_id=False; '
            'use new_api.format_abspath()')

    def get_metadata(self, book_id, index_is_id=True):
        assert index_is_id, 'book ids must be passed with index_is_id=True'
        return FakeBookMI()

    def close(self):
        pass


class FakeBookMI:
    """Bare metadata object: _metadata_dict reads everything via getattr."""

    title = '灰雾'
    authors = ['防静电']
    tags = []
    series = ''
    series_index = None
    publisher = ''
    languages = []
    isbn = ''
    pubdate = None
    comments = ''
    identifiers = {}


class FakeIdent:
    def __init__(self, value, scheme='uuid'):
        self.value, self.scheme = value, scheme


class FakeMeta:
    def __init__(self, identifiers, title, authors):
        self.identifier = identifiers
        self.title = [title]
        self.creator = authors


class FakeOEB:
    def __init__(self, identifiers, title, authors):
        self.metadata = FakeMeta(identifiers, title, authors)


BOOKS = {
    830: {'uuid': '994189ad-da74-4d03-8c21-39356c746582', 'title': '灰雾',
          'authors': ['防静电']},
    970: {'uuid': 'aaaaaaaa-da74-4d03-8c21-39356c746582', 'title': '其他',
          'authors': ['某人']},
}
DIRS = {
    830: '/lib/防静电/灰雾 (830)/灰雾.epub',
    970: '/lib/某人/其他 (970)/其他.epub',
}
# Shaped like a real uuid (only shaped values reach lookup_by_uuid) but
# present in no fake book, so the title fallback has to answer.
UNKNOWN_UUID = 'urn:uuid:deadbeef-1234-4567-8901-deadbeefdeadbeef'


def _oeb(idents):
    return FakeOEB(idents, '灰雾', ['防静电'])


def test_uuid_lookup_wins():
    oeb = _oeb([FakeIdent('urn:uuid:994189ad-da74-4d03-8c21-39356c746582')])
    got = resolve_book_dir(oeb, None, open_library=lambda: FakeDB(BOOKS, DIRS))
    assert got == os.path.dirname(DIRS[830])


def test_falls_back_to_unique_title_match():
    oeb = _oeb([FakeIdent(UNKNOWN_UUID)])
    got = resolve_book_dir(oeb, None, open_library=lambda: FakeDB(BOOKS, DIRS))
    assert got == os.path.dirname(DIRS[830])


def test_ambiguous_title_is_rejected():
    dup = dict(BOOKS)
    dup[831] = {'uuid': 'x', 'title': '灰雾', 'authors': ['防静电']}
    dup_dirs = dict(DIRS)
    dup_dirs[831] = '/lib/防静电/灰雾 (831)/灰雾.epub'
    oeb = _oeb([FakeIdent(UNKNOWN_UUID)])
    assert resolve_book_dir(oeb, None, open_library=lambda: FakeDB(dup, dup_dirs)) is None


def test_title_prefix_hit_is_rejected():
    # calibre would also match "灰雾 第二部" for title:"灰雾"; writing images
    # into either folder would be a guess, so refuse.
    dup = dict(BOOKS)
    dup[831] = {'uuid': 'x', 'title': '灰雾 第二部', 'authors': ['防静电']}
    dup_dirs = dict(DIRS)
    dup_dirs[831] = '/lib/防静电/灰雾 第二部 (831)/灰雾 第二部.epub'
    oeb = _oeb([FakeIdent(UNKNOWN_UUID)])
    assert resolve_book_dir(oeb, None, open_library=lambda: FakeDB(dup, dup_dirs)) is None


def test_title_mismatch_after_uuid_hit_is_rejected():
    # The uuid points at a book whose stored title differs: do not fall back
    # to the title search, that is exactly the misfire we want to avoid.
    oeb = _oeb([FakeIdent('urn:uuid:aaaaaaaa-da74-4d03-8c21-39356c746582')])
    assert resolve_book_dir(oeb, None, open_library=lambda: FakeDB(BOOKS, DIRS)) is None


def test_unavailable_library_returns_none():
    def boom():
        raise RuntimeError('no library')

    assert resolve_book_dir(_oeb([]), None, open_library=boom) is None
    assert resolve_book_dir(_oeb([]), None, open_library=lambda: None) is None


def test_is_temporary_output(monkeypatch, tmp_path):
    import calibre_plugins.markdown.utils.library as ml
    target = str(tmp_path / 'x.md')
    # Control: without the patch the real (unstubbed) calibre import would not
    # resolve, and the path does not live under calibre's temp dir.
    monkeypatch.setattr(ml, '_temp_base_dir', lambda: '/nowhere')
    assert not is_temporary_output(target)
    monkeypatch.setattr(ml, '_temp_base_dir', lambda: str(tmp_path), raising=False)
    assert is_temporary_output(target)
    assert not is_temporary_output('/tmp/elsewhere/x.md')


def test_file_objects_are_not_temporary(monkeypatch):
    import calibre_plugins.markdown.utils.library as ml
    monkeypatch.setattr(ml, '_temp_base_dir', lambda: '/tmp', raising=False)

    class Stream:
        def write(self, data):
            return len(data)

    assert is_temporary_output(Stream()) is False


def test_log_records_failures():
    messages = []

    class Log:
        def debug(self, *args):
            messages.append(args[0] if args else '')

    def boom():
        raise RuntimeError('no library')

    assert resolve_book_dir(_oeb([]), Log(), open_library=boom) is None
    assert messages and 'unavailable' in messages[0]


def test_resolve_book_info_answers_both_with_one_open():
    db = FakeDB(BOOKS, DIRS)
    opens = []

    def open_once():
        opens.append(1)
        return db

    folder, meta = resolve_book_info(
        _oeb([FakeIdent('urn:uuid:994189ad-da74-4d03-8c21-39356c746582')]),
        None, open_library=open_once)

    assert folder == os.path.dirname(DIRS[830])
    assert meta['calibre_id'] == 830
    assert meta['title'] == '灰雾'
    assert len(opens) == 1


def test_resolve_book_info_without_a_book_returns_none_pair():
    class Unknown(FakeOEB):
        def __init__(self):
            self.metadata = FakeMeta(
                [FakeIdent(UNKNOWN_UUID)], '不存在的书', ['没有人'])

    folder, meta = resolve_book_info(
        Unknown(), None, open_library=lambda: FakeDB(BOOKS, DIRS))

    assert (folder, meta) == (None, None)


def test_resolve_book_info_survives_a_failed_open():
    def boom():
        raise RuntimeError('no library')

    assert resolve_book_info(
        _oeb([]), None, open_library=boom) == (None, None)
    assert resolve_book_info(
        _oeb([]), None, open_library=lambda: None) == (None, None)


def _options(opf_path):
    return type('Opts', (), {'read_metadata_from_opf': opf_path})()


def test_options_lookup_needs_an_injected_opf():
    # CLI conversions do not inject one, and there the input file still sits
    # next to its images: no opf means no library round trip.
    opened = []
    opts = _options(None)
    assert resolve_book_dir_for_options(
        opts, None, open_library=lambda: opened.append(1)) is None
    assert not opened
    assert resolve_book_dir_for_options(
        _options('/does/not/exist.opf'), None,
        open_library=lambda: opened.append(1)) is None
    assert not opened


def test_options_lookup_resolves_the_book_folder(monkeypatch, tmp_path):
    opf = tmp_path / 'metadata.opf'
    opf.write_bytes(b'<package/>')

    class Opts:
        read_metadata_from_opf = str(opf)

    import calibre_plugins.markdown.utils.library as ml
    monkeypatch.setattr(
        ml, '_opf_identity',
        lambda path: (['994189ad-da74-4d03-8c21-39356c746582'], '灰雾'))

    got = resolve_book_dir_for_options(
        Opts(), None, open_library=lambda: FakeDB(BOOKS, DIRS))
    assert got == os.path.dirname(DIRS[830])


def test_options_lookup_without_a_match(monkeypatch, tmp_path):
    opf = tmp_path / 'metadata.opf'
    opf.write_bytes(b'<package/>')
    import calibre_plugins.markdown.utils.library as ml
    monkeypatch.setattr(ml, '_opf_identity', lambda path: ([], '不存在的书'))

    assert resolve_book_dir_for_options(
        _options(str(opf)), None,
        open_library=lambda: FakeDB(BOOKS, DIRS)) is None


def test_options_lookup_survives_a_broken_opf(monkeypatch, tmp_path):
    opf = tmp_path / 'metadata.opf'
    opf.write_bytes(b'not xml at all')
    messages = []

    class Log:
        def debug(self, *args):
            messages.append(args[0] if args else '')

    assert resolve_book_dir_for_options(_options(str(opf)), Log()) is None
    assert messages and 'metadata opf' in messages[0]


class _FakeMI:
    uuid = '994189ad-da74-4d03-8c21-39356c746582'
    identifiers = {'calibre': '994189ad-da74-4d03-8c21-39356c746582',
                   'isbn': '9780000000000'}
    title = '灰雾'


class _FakeOPF:
    def __init__(self, handle):
        pass

    def to_book_metadata(self):
        return _FakeMI()


def test_opf_identity_reads_uuid_and_title(monkeypatch, tmp_path):
    import calibre.ebooks.metadata.opf2 as opf2
    import calibre_plugins.markdown.utils.library as ml
    monkeypatch.setattr(opf2, 'OPF', _FakeOPF)
    opf = tmp_path / 'metadata.opf'
    opf.write_bytes(b'<package/>')

    uuids, title = ml._opf_identity(str(opf))

    assert uuids == ['994189ad-da74-4d03-8c21-39356c746582']
    assert title == '灰雾'


def test_opf_identity_drops_values_that_are_not_uuids(monkeypatch, tmp_path):
    import calibre.ebooks.metadata.opf2 as opf2
    import calibre_plugins.markdown.utils.library as ml

    class MI:
        uuid = 'REEDEN:0a1b2c'
        identifiers = {'calibre': 'title:'}
        title = '灰雾'

    class OPF:
        def __init__(self, handle):
            pass

        def to_book_metadata(self):
            return MI()

    monkeypatch.setattr(opf2, 'OPF', OPF)
    opf = tmp_path / 'metadata.opf'
    opf.write_bytes(b'<package/>')

    uuids, title = ml._opf_identity(str(opf))

    assert uuids == []
    assert title == '灰雾'
