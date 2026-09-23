# -*- coding: utf-8 -*-
"""Read-only lookup of the calibre library folder that owns a conversion.

Conversion plugins are handed neither a db nor a book_id, so the book folder
is derived from OEB metadata. The library is always opened read-only; every
failure path returns None so that conversion still produces the .md file.
"""

import os
import re

# Only values shaped like a UUID reach lookup_by_uuid: other identifier
# schemes (REEDEN:<hex>, isbn, urls, ...) could never hit and would just
# burn a query. calibre writes its own identifier into EPUBs with a
# `uuid:` / `calibre:` prefix rather than the EPUB2 `urn:uuid:` form.
_UUID_SHAPED_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I)
_UUID_PREFIXES = ('urn:uuid:', 'uuid:', 'calibre:')


def _temp_base_dir():
    from calibre.ptempfile import base_dir
    return base_dir()


def is_temporary_output(output_path):
    """True when calibre owns the output target (library/bulk conversion).

    calibre writes conversions to PersistentTemporaryFile() inside
    ptempfile.base_dir(); the CLI and "save to disk" hand us a real path.
    """
    if hasattr(output_path, 'write'):
        return False
    path = os.path.abspath(str(output_path or ''))
    base = os.path.abspath(str(_temp_base_dir() or ''))
    return bool(base) and path.startswith(base + os.sep)


def _open_library_read_only():
    from calibre.db.legacy import LibraryDatabase
    from calibre.library import current_library_path

    path = current_library_path()
    if not path or not os.path.isdir(path):
        return None
    return LibraryDatabase(path, read_only=True)


def _iter_uuids(oeb_book):
    """Yield bare, uuid-shaped identifier values from the OEB metadata.

    Everything else can only miss in lookup_by_uuid, and calibre's own EPUB
    identifier carries a `uuid:` / `calibre:` prefix instead of `urn:uuid:`.
    """
    for ident in getattr(getattr(oeb_book, 'metadata', None), 'identifier', None) or []:
        value = str(getattr(ident, 'value', '') or '').strip()
        for prefix in _UUID_PREFIXES:
            if value.lower().startswith(prefix):
                value = value[len(prefix):].strip()
                break
        if _UUID_SHAPED_RE.match(value):
            yield value


def _oeb_title(oeb_book):
    title = getattr(getattr(oeb_book, 'metadata', None), 'title', None) or []
    return str(title[0] if title else '').strip()


def _book_dir(db, book_id, oeb_title):
    """Return the book folder, or None when the stored title does not match."""
    api = db.new_api
    for fmt in api.formats(book_id) or ():
        abspath = api.format_abspath(book_id, str(fmt).upper())
        if abspath:
            folder = os.path.dirname(abspath)
            if not oeb_title or api.field_for('title', book_id) == oeb_title:
                return folder
            return None
    return None


def _report(log, message, exc):
    if log is not None:
        log.debug('Markdown: %s: %r' % (message, exc))


def _with_library(opener, log, messages, action):
    """Open the library read-only, run action(db), always close it.

    Every failure yields None: a plugin's image export must never break a
    conversion. `messages` is a (open_failed, lookup_failed) pair so the log
    tells the two apart.
    """
    open_message, lookup_message = messages
    try:
        db = opener()
    except Exception as exc:
        _report(log, open_message, exc)
        return None
    if db is None:
        return None
    try:
        return action(db)
    except Exception as exc:
        _report(log, lookup_message, exc)
        return None
    finally:
        close = getattr(db, 'close', None)
        if callable(close):
            try:
                close()
            except Exception as exc:
                _report(log, 'could not close the library', exc)


def _identify_by_uuid_and_title(api, uuids, title):
    """Return the calibre book_id for the given identifiers, or None.

    Strategy: calibre uuid (only present when calibre injected its metadata
    opf) first, then a unique title match. A uuid hit names one specific
    book; if its stored title does not match we stop instead of letting the
    title search pick a different book - that misfire is exactly what the
    verification exists to prevent.
    """
    for uuid in uuids:
        book_id = api.lookup_by_uuid(uuid)
        if book_id is None:
            continue
        if not title or api.field_for('title', book_id) == title:
            return book_id
        return None
    if title:
        hits = sorted(api.search('title:"%s"' % title.replace('"', '')) or set())
        if len(hits) == 1:
            return hits[0]
    return None


def _identify_book(api, oeb_book):
    """Return the calibre book_id for the converted book, or None."""
    return _identify_by_uuid_and_title(
        api, _iter_uuids(oeb_book), _oeb_title(oeb_book))


def resolve_book_dir(oeb_book, log=None, open_library=None):
    """Return the absolute folder of the source book, or None.

    Anything ambiguous or unreachable yields None instead of a guess.
    Conversions needing both the folder and the metadata dict should call
    resolve_book_info() instead - one read-only open serves both.
    """
    opener = open_library or _open_library_read_only

    def action(db):
        book_id = _identify_book(db.new_api, oeb_book)
        if book_id is None:
            return None
        return _book_dir(db, book_id, _oeb_title(oeb_book))

    return _with_library(
        opener, log,
        ('library unavailable, skipping image export',
         'library lookup failed, skipping image export'),
        action)


def library_metadata_for_oeb(oeb_book, log=None, open_library=None):
    """Return calibre library metadata for the book being converted, or None.

    Conversion plugins get no db and no book_id, and only GUI conversions
    hand us calibre's metadata opf. This fills the gap for YAML front matter
    on the same read-only lookup used for image export.
    """
    opener = open_library or _open_library_read_only

    def action(db):
        book_id = _identify_book(db.new_api, oeb_book)
        if book_id is None:
            return None
        return _metadata_dict(
            db.get_metadata(book_id, index_is_id=True), book_id)

    return _with_library(
        opener, log,
        ('library unavailable, skipping metadata lookup',
         'library lookup failed, skipping metadata lookup'),
        action)


def resolve_book_info(oeb_book, log=None, open_library=None):
    """Answer both conversion questions with a single read-only open.

    Returns (folder, metadata): the source book folder for the sidecar image
    export and the metadata dict for YAML front matter. Either entry is None
    when it could not be determined, and every failure path yields
    (None, None) so the conversion still produces the .md file.
    """
    opener = open_library or _open_library_read_only

    def action(db):
        book_id = _identify_book(db.new_api, oeb_book)
        if book_id is None:
            return None, None
        return (
            _book_dir(db, book_id, _oeb_title(oeb_book)),
            _metadata_dict(
                db.get_metadata(book_id, index_is_id=True), book_id),
        )

    result = _with_library(
        opener, log,
        ('library unavailable, skipping book lookup',
         'library lookup failed, skipping book lookup'),
        action)
    if result is None:
        return None, None
    return result


def _opf_identity(opf_path):
    """Return (uuids, title) from calibre's injected metadata opf.

    GUI and bulk conversions pass `read_metadata_from_opf`; create_opf_file
    writes the library uuid into that opf, which is the identifier that maps
    straight back to the book.
    """
    from calibre.ebooks.metadata.opf2 import OPF

    with open(opf_path, 'rb') as handle:
        mi = OPF(handle).to_book_metadata()
    identifiers = getattr(mi, 'identifiers', None) or {}
    candidates = [getattr(mi, 'uuid', None)]
    if isinstance(identifiers, dict):
        candidates.extend(identifiers.get(key) for key in ('calibre', 'uuid'))
    uuids = []
    for value in candidates:
        value = str(value or '').strip()
        if value and _UUID_SHAPED_RE.match(value) and value not in uuids:
            uuids.append(value)
    return uuids, str(getattr(mi, 'title', None) or '').strip()


def resolve_book_dir_for_options(opts, log=None, open_library=None):
    """Return the folder of the book being converted, or None.

    Input plugins get neither a db nor a book_id, and GUI/bulk conversions
    copy the book file into a temporary folder (gui2/tools.py) - taking a
    .md file away from the images/ folder that sits next to it in the
    library. calibre does hand the conversion an opf carrying the library
    uuid (`read_metadata_from_opf`), so the folder is resolved through the
    same read-only library lookup the output side uses. CLI conversions do
    not inject an opf; there the input file still sits in the book folder
    and None is the right answer.
    """
    opf_path = getattr(opts, 'read_metadata_from_opf', None)
    if not opf_path:
        return None
    opf_path = str(opf_path)
    if not os.path.isfile(opf_path):
        return None
    try:
        uuids, title = _opf_identity(opf_path)
    except Exception as exc:
        _report(log, 'could not read the injected metadata opf', exc)
        return None
    if not uuids and not title:
        return None

    opener = open_library or _open_library_read_only

    def action(db):
        book_id = _identify_by_uuid_and_title(db.new_api, uuids, title)
        if book_id is None:
            return None
        return _book_dir(db, book_id, title)

    return _with_library(
        opener, log,
        ('library unavailable, skipping the library image lookup',
         'library lookup failed, skipping the library image lookup'),
        action)


def _metadata_dict(mi, book_id):
    """Mirror the fields YAML front matter expects, without touching the db."""
    from calibre_plugins.markdown.utils.helpers import (
        format_pubdate,
        html_to_plain,
    )

    identifiers = getattr(mi, 'identifiers', None) or {}
    isbn = ''
    if isinstance(identifiers, dict):
        isbn = identifiers.get('isbn') or ''
    languages = getattr(mi, 'languages', None) or []
    return {
        'title': getattr(mi, 'title', None) or '',
        'authors': list(getattr(mi, 'authors', None) or []),
        'language': str(languages[0] or '').strip() if languages else '',
        'publisher': getattr(mi, 'publisher', None) or '',
        'tags': list(getattr(mi, 'tags', None) or []),
        'series': getattr(mi, 'series', None) or '',
        'series_index': getattr(mi, 'series_index', None),
        'isbn': isbn or getattr(mi, 'isbn', None) or '',
        'pubdate': format_pubdate(getattr(mi, 'pubdate', None)),
        'description': html_to_plain(getattr(mi, 'comments', None) or ''),
        'calibre_id': book_id,
    }
