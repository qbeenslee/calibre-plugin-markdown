# -*- coding: utf-8 -*-
"""Remote image download: collection, fetching, rewriting, and wiring.

The conversion tests stub the writer (like test_output_options does) and
monkeypatch urlopen, so nothing here touches the network.
"""

import sys
import types

import calibre_plugins.markdown.utils.remote_images as ri
from calibre_plugins.markdown.output.output_plugin import MarkdownOutput
from calibre_plugins.markdown.utils.helpers import DEFAULT_IMAGE_DIR
from calibre_plugins.markdown.utils.remote_images import (
    collect_remote_image_urls,
    download_remote_images,
    fetch_remote_image,
    inline_remote_images,
    rewrite_remote_image_refs,
)

URL = 'https://raw.githubusercontent.com/xvxvv/cdn/master/202607/21_b6cbe1.png'
SPACED_URL = 'http://example.com/pic cover.jpg'
JPEG = b'\xff\xd8\xff\xe0JPEG'
PNG = b'\x89PNG\r\n\x1a\nfake-png'


class FakeResponse:
    """Matches the urlopen response surface fetch_remote_image uses."""

    def __init__(self, data=PNG, content_type='image/png'):
        self._data = data
        self.headers = {'Content-Type': content_type}

    def read(self, amount=-1):
        if amount is None or amount < 0:
            return self._data
        return self._data[:amount]

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def _patch_urlopen(monkeypatch, responses):
    """responses: url -> FakeResponse, or an exception to raise for it."""
    def fake_urlopen(request, timeout=None):
        outcome = responses[request.full_url]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
    monkeypatch.setattr(ri, 'urlopen', fake_urlopen)


def _md(url):
    return '![](%s)' % url


# ---------------------------------------------------------------- collection

def test_collects_both_spellings_without_duplicates():
    text = 'a %s b\n<img src="%s" width="1px" height="auto">\n<img src="%s">' \
        % (_md(URL), URL, URL)
    assert collect_remote_image_urls(text) == [URL]


def test_only_http_and_https_are_collected():
    text = ' '.join((
        _md('https://x/a.png'),
        _md('http://x/b.png'),
        _md('data:image/png;base64,AAA'),
        _md('file:///etc/passwd'),
        _md('ftp://x/c.png'),
        '<img src="javascript:x">',
    ))
    assert collect_remote_image_urls(text) == ['https://x/a.png', 'http://x/b.png']


def test_a_url_with_whitespace_is_left_alone():
    # The markdown spelling captures up to the closing paren; the guard
    # rejects the whole thing instead of fetching a truncated URL.
    assert collect_remote_image_urls(_md(SPACED_URL)) == []


def test_single_quoted_html_src_is_collected():
    assert collect_remote_image_urls("<img src='%s'>" % URL) == [URL]


def test_text_without_urls_is_untouched():
    assert collect_remote_image_urls(
        'plain text mentioning %s/x.png by name' % DEFAULT_IMAGE_DIR) == []


# ------------------------------------------------------------------ rewrite

def test_rewrite_updates_both_spellings_and_counts():
    text = '![cover](%s)\n<img src="%s" width="1px" height="auto">' % (URL, URL)
    out, count = rewrite_remote_image_refs(text, {URL: 'images/000000.png'})
    assert count == 2
    assert '![cover](images/000000.png)' in out
    assert '<img src="images/000000.png" width="1px" height="auto">' in out
    assert URL not in out


def test_rewrite_keeps_other_urls():
    other = 'https://example.com/other.png'
    text = '%s %s' % (_md(URL), _md(other))
    out, count = rewrite_remote_image_refs(text, {URL: 'images/000000.png'})
    assert count == 1
    assert other in out


# ------------------------------------------------------------------- fetch

def test_fetch_uses_the_url_extension(monkeypatch):
    _patch_urlopen(monkeypatch, {URL: FakeResponse()})
    assert fetch_remote_image(URL) == (PNG, '.png')


def test_fetch_falls_back_to_the_content_type(monkeypatch):
    url = 'https://x/img?w=100'
    _patch_urlopen(
        monkeypatch, {url: FakeResponse(content_type='image/jpeg')})
    assert fetch_remote_image(url) == (PNG, '.jpg')


def test_fetch_without_a_known_type_stores_as_img(monkeypatch):
    url = 'https://x/img'
    _patch_urlopen(
        monkeypatch, {url: FakeResponse(content_type='text/html')})
    assert fetch_remote_image(url) == (PNG, '.img')


def test_fetch_rejects_an_oversized_response(monkeypatch):
    _patch_urlopen(monkeypatch, {URL: FakeResponse()})
    assert fetch_remote_image(URL, max_bytes=4) is None


def test_fetch_rejects_empty_and_broken_responses(monkeypatch):
    _patch_urlopen(monkeypatch, {
        'https://x/empty': FakeResponse(data=b''),
        'https://x/boom': RuntimeError('no network'),
    })
    assert fetch_remote_image('https://x/empty') is None
    assert fetch_remote_image('https://x/boom') is None


# ---------------------------------------------------------------- download

def test_download_writes_files_and_rewrites(tmp_path, monkeypatch):
    _patch_urlopen(monkeypatch, {URL: FakeResponse()})
    text = '%s\n<img src="%s">' % (_md(URL), URL)
    dest = tmp_path / 'images'
    out, saved, failed = download_remote_images(text, [URL], str(dest), 3)
    assert saved == 1 and failed == []
    assert (dest / '000003.png').read_bytes() == PNG
    assert out == '![](%s/000003.png)\n<img src="%s/000003.png">' % (
        DEFAULT_IMAGE_DIR, DEFAULT_IMAGE_DIR)


def test_download_failure_keeps_the_url_and_creates_no_folder(
        tmp_path, monkeypatch):
    _patch_urlopen(monkeypatch, {URL: RuntimeError('down')})
    dest = tmp_path / 'images'
    out, saved, failed = download_remote_images(
        _md(URL), [URL], str(dest), 0)
    assert saved == 0 and failed == [URL]
    assert out == _md(URL)
    assert not dest.exists()


def test_download_handles_a_mixed_batch(tmp_path, monkeypatch):
    ok = 'https://x/ok.png'
    _patch_urlopen(monkeypatch, {URL: RuntimeError('down'), ok: FakeResponse()})
    dest = tmp_path / 'images'
    out, saved, failed = download_remote_images(
        '%s %s' % (_md(URL), _md(ok)), [URL, ok], str(dest), 0)
    assert saved == 1 and failed == [URL]
    assert (dest / '000000.png').read_bytes() == PNG
    assert _md(URL) in out and _md('%s/000000.png' % DEFAULT_IMAGE_DIR) in out


# ------------------------------------------------------------------ inline

def test_inline_embeds_a_data_uri(monkeypatch):
    _patch_urlopen(monkeypatch, {URL: FakeResponse()})
    out, count, failed = inline_remote_images(_md(URL), [URL])
    assert count == 1 and failed == []
    assert out.startswith('![](data:image/png;base64,')
    assert URL not in out


def test_inline_failure_keeps_the_url(monkeypatch):
    _patch_urlopen(monkeypatch, {URL: RuntimeError('down')})
    out, count, failed = inline_remote_images(_md(URL), [URL])
    assert count == 0 and failed == [URL]
    assert out == _md(URL)


# ----------------------------------------------------------------- convert

class _Opts:
    pass


class _Log:
    def __init__(self):
        self.infos = []
        self.warnings = []

    def info(self, message):
        self.infos.append(message)

    def warn(self, message):
        self.warnings.append(message)

    def debug(self, message):
        pass


class _FakeItem:
    def __init__(self, data, href):
        self.data = data
        self.href = href


class _FakeOEB:
    def __init__(self, items):
        self.manifest = items


def _plugin():
    """Bare instance: tests must not touch calibre widget machinery."""
    return MarkdownOutput.__new__(MarkdownOutput)


def _install_writer(monkeypatch, images, text):
    module = types.ModuleType(
        'calibre_plugins.markdown.output.markdownml_enhanced')

    class StubWriter:
        def __init__(self, log):
            self.images = images

        def extract_content(self, oeb_book, opts):
            return text

    module.EnhancedMarkdownMLizer = StubWriter
    monkeypatch.setitem(sys.modules, module.__name__, module)


def _make_opts(**kwargs):
    opts = _Opts()
    opts.newline = 'unix'
    opts.txt_output_encoding = 'utf-8'
    opts.yaml_front_matter = False
    opts.export_image_files = True
    opts.keep_image_references = True
    opts.image_output_mode = 'sidecar'
    opts.download_remote_images = True
    for key, value in kwargs.items():
        setattr(opts, key, value)
    return opts


def _convert(opts, tmp_path, log, oeb=None):
    out = tmp_path / 'book.md'
    _plugin().convert(oeb or object(), str(out), None, opts, log)
    return out.read_text(encoding='utf-8')


def test_sidecar_downloads_remote_images_and_rewrites(monkeypatch, tmp_path):
    import calibre_plugins.markdown.output.output_plugin as mo

    monkeypatch.setattr(mo, 'is_temporary_output', lambda path: False)
    _patch_urlopen(monkeypatch, {URL: FakeResponse()})
    _install_writer(
        monkeypatch, {},
        'body\n\n%s\n<img src="%s" width="1px" height="auto">\n'
        % (_md(URL), URL))
    log = _Log()
    out = _convert(_make_opts(), tmp_path, log)
    assert (tmp_path / 'book.images' / '000000.png').read_bytes() == PNG
    assert '[](book.images/000000.png)' in out
    assert 'src="book.images/000000.png" width="1px"' in out
    assert URL not in out
    assert log.warnings == []


def test_sidecar_remote_names_continue_the_manifest_sequence(
        monkeypatch, tmp_path):
    import calibre_plugins.markdown.output.output_plugin as mo

    monkeypatch.setattr(mo, 'is_temporary_output', lambda path: False)
    _patch_urlopen(monkeypatch, {URL: FakeResponse()})
    _install_writer(
        monkeypatch, {'images/local.png': '000000.jpeg'},
        '![c](images/000000.jpeg)\n\n%s\n' % _md(URL))
    oeb = _FakeOEB([_FakeItem(JPEG, 'images/local.png')])
    out = tmp_path / 'book.md'
    _plugin().convert(oeb, str(out), None, _make_opts(), _Log())
    sidecar = tmp_path / 'book.images'
    assert (sidecar / '000000.jpeg').read_bytes() == JPEG
    assert (sidecar / '000001.png').read_bytes() == PNG
    text = out.read_text(encoding='utf-8')
    assert 'book.images/000000.jpeg' in text
    assert 'book.images/000001.png' in text


def test_sidecar_download_disabled_keeps_urls(monkeypatch, tmp_path):
    import calibre_plugins.markdown.output.output_plugin as mo

    monkeypatch.setattr(mo, 'is_temporary_output', lambda path: False)

    def boom(url, **kwargs):
        raise AssertionError('must not download')

    monkeypatch.setattr(ri, 'fetch_remote_image', boom)
    _install_writer(monkeypatch, {}, 'body\n\n%s\n' % _md(URL))
    out = _convert(_make_opts(download_remote_images=False), tmp_path, _Log())
    assert _md(URL) in out
    assert not (tmp_path / 'book.images').exists()


def test_none_mode_never_downloads(monkeypatch, tmp_path):
    import calibre_plugins.markdown.output.output_plugin as mo

    monkeypatch.setattr(mo, 'is_temporary_output', lambda path: False)

    def boom(url, **kwargs):
        raise AssertionError('must not download')

    monkeypatch.setattr(ri, 'fetch_remote_image', boom)
    _install_writer(monkeypatch, {}, 'body\n\n%s\n' % _md(URL))
    out = _convert(_make_opts(image_output_mode='none'), tmp_path, _Log())
    assert _md(URL) in out


def test_inline_embeds_remote_images_as_data_uris(monkeypatch, tmp_path):
    import calibre_plugins.markdown.output.output_plugin as mo

    monkeypatch.setattr(mo, 'is_temporary_output', lambda path: False)
    _patch_urlopen(monkeypatch, {URL: FakeResponse()})
    _install_writer(monkeypatch, {}, 'body\n\n%s\n' % _md(URL))
    out = _convert(_make_opts(image_output_mode='inline'), tmp_path, _Log())
    assert 'data:image/png;base64,' in out
    assert URL not in out
    assert not (tmp_path / 'book.images').exists()


def test_failed_downloads_are_reported_and_kept(monkeypatch, tmp_path):
    import calibre_plugins.markdown.output.output_plugin as mo

    monkeypatch.setattr(mo, 'is_temporary_output', lambda path: False)
    _patch_urlopen(monkeypatch, {URL: RuntimeError('down')})
    _install_writer(monkeypatch, {}, 'body\n\n%s\n' % _md(URL))
    log = _Log()
    out = _convert(_make_opts(), tmp_path, log)
    assert len(log.warnings) == 1
    assert 'failed to download' in log.warnings[0]
    assert URL in log.warnings[0]
    assert _md(URL) in out
    assert not (tmp_path / 'book.images').exists()


def test_warn_sample_lists_at_most_five_urls():
    log = _Log()
    urls = ['https://x/%d.png' % i for i in range(7)]
    _plugin()._warn_failed_remote_images(log, urls)
    assert len(log.warnings) == 1
    assert '…' in log.warnings[0]
    assert log.warnings[0].count('https://') == 5


def test_warn_is_silent_without_failures():
    log = _Log()
    _plugin()._warn_failed_remote_images(log, [])
    assert log.warnings == []
