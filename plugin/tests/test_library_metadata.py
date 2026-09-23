# -*- coding: utf-8 -*-
"""YAML front matter needs library metadata that conversions do not get."""

from calibre_plugins.markdown.utils.library import library_metadata_for_oeb


class MI:
    title = '灰雾'
    authors = ['防静电']
    tags = ['小说']
    series = '灰雾'
    series_index = 1
    publisher = 'X'
    languages = ['zh']
    isbn = ''
    pubdate = None
    comments = '<p>简介</p>'
    identifiers = {}


class FakeAPI:
    def __init__(self, book_id, mi, uuid='11111111-2222-4333-8444-555555555555'):
        self._id, self._mi, self._uuid = book_id, mi, uuid

    def lookup_by_uuid(self, uuid):
        return self._id if uuid == self._uuid else None

    def field_for(self, field, book_id):
        return self._mi.title if field == 'title' else None

    def search(self, query):
        return {self._id} if 'title:"%s"' % self._mi.title in query else set()


class FakeDB:
    def __init__(self, book_id, mi, uuid='U-1'):
        self.new_api = FakeAPI(book_id, mi, uuid)
        self._mi = mi

    def get_metadata(self, book_id, index_is_id=True):
        assert index_is_id, 'book ids must be passed with index_is_id=True'
        return self._mi

    def close(self):
        pass


class FakeOEB:
    class metadata:
        identifier = [type('I', (), {
            'value': 'urn:uuid:11111111-2222-4333-8444-555555555555'})()]
        title = ['灰雾']


def test_metadata_is_read_for_matching_uuid():
    db = FakeDB(830, MI())
    meta = library_metadata_for_oeb(FakeOEB(), None, open_library=lambda: db)
    assert meta['calibre_id'] == 830
    assert meta['tags'] == ['小说']
    assert meta['title'] == '灰雾'
    assert meta['language'] == 'zh'


def test_metadata_lookup_failure_returns_none():
    def boom():
        raise RuntimeError('no library')

    assert library_metadata_for_oeb(FakeOEB(), None, open_library=boom) is None
    assert library_metadata_for_oeb(
        FakeOEB(), None, open_library=lambda: None) is None


def test_unknown_uuid_falls_back_to_title():
    # Without a usable uuid (e.g. a conversion started from a stray file) the
    # unique title match is the fallback this lookup exists for.
    db = FakeDB(830, MI(), uuid='other')
    meta = library_metadata_for_oeb(FakeOEB(), None, open_library=lambda: db)
    assert meta['calibre_id'] == 830


def test_ambiguous_book_gives_no_metadata():
    class AmbiguousAPI(FakeAPI):
        def search(self, query):
            return {830, 831}

    db = FakeDB(830, MI(), uuid='other')
    db.new_api = AmbiguousAPI(830, MI(), uuid='other')
    assert library_metadata_for_oeb(FakeOEB(), None, open_library=lambda: db) is None


def test_uuid_hit_with_title_mismatch_is_rejected():
    # Same ruling as the image folder lookup: a uuid that names a book whose
    # stored title differs must not produce metadata either.
    class OtherTitleAPI(FakeAPI):
        def field_for(self, field, book_id):
            return '另一本书' if field == 'title' else None

    db = FakeDB(830, MI())
    db.new_api = OtherTitleAPI(830, MI())
    assert library_metadata_for_oeb(
        FakeOEB(), None, open_library=lambda: db) is None
