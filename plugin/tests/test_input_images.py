# -*- coding: utf-8 -*-
"""Input-side image handling: the keep/embed/download switch hierarchy.

The staging scan is pinned through _image_refs (html5_parser is not
importable in the venv) and urlopen is faked, so nothing here touches the
network or a real widget toolkit.
"""

import pathlib

import calibre_plugins.markdown.utils.remote_images as ri
from calibre_plugins.markdown.input.input_plugin import MarkdownInput
from calibre_plugins.markdown.utils.remote_images import save_remote_image

URL = 'https://raw.githubusercontent.com/xvxvv/cdn/master/202607/21_b6cbe1.png'
JPEG = b'\xff\xd8\xff\xe0JPEG'
PNG = b'\x89PNG\r\n\x1a\nfake-png'


class FakeResponse:
    """Matches the urlopen response surface save_remote_image uses."""

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
    def fake_urlopen(request, timeout=None):
        outcome = responses[request.full_url]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
    monkeypatch.setattr(ri, 'urlopen', fake_urlopen)


def _boom_urlopen(monkeypatch):
    def boom(request, timeout=None):
        raise AssertionError('must not download')
    monkeypatch.setattr(ri, 'urlopen', boom)


def _refs(monkeypatch, *srcs):
    """Pin the image references the plugin scans out of the HTML."""
    monkeypatch.setattr(
        MarkdownInput, '_image_refs',
        staticmethod(lambda html: list(srcs)))


class _Log:
    def __init__(self):
        self.warnings = []

    def warn(self, message):
        self.warnings.append(message)

    def info(self, *args):
        pass

    def debug(self, *args):
        pass


def _plugin(**flags):
    """A real instance with the switches preset (convert() not run)."""
    plugin = MarkdownInput()
    plugin._keep_images = flags.get('keep_images', True)
    plugin._embed_images = flags.get('embed_images', True)
    plugin._download_remote_images = flags.get(
        'download_remote_images', True)
    plugin._keep_image_sizes = flags.get('keep_image_sizes', True)
    plugin._book_dir = flags.get('book_dir')
    plugin.log = _Log()
    return plugin


# ------------------------------------------------------------- keep_images

def test_keep_images_off_strips_every_img(tmp_path, monkeypatch):
    _refs(monkeypatch)
    _boom_urlopen(monkeypatch)
    plugin = _plugin(keep_images=False)
    html = '<p>a</p><img src="%s" alt="pic"/><p>b</p>' % URL

    out = plugin.fix_resources(html, str(tmp_path / 'in'))

    assert out == '<p>a</p><p>b</p>'
    assert plugin.fix_resources_seen[0] == out
    assert not (tmp_path / 'in').exists() or list((tmp_path / 'in').iterdir()) == []


def test_keep_images_off_disables_download_too(tmp_path, monkeypatch):
    _refs(monkeypatch)
    _boom_urlopen(monkeypatch)
    base = tmp_path / 'in'
    base.mkdir()
    plugin = _plugin(keep_images=False)

    plugin.fix_resources('<img src="%s"/>' % URL, str(base))

    assert '<img' not in plugin.fix_resources_seen[0]
    assert list(base.iterdir()) == []


# ------------------------------------------------------------ embed_images

def test_embed_images_on_stages_library_images(tmp_path, monkeypatch):
    _refs(monkeypatch, 'images/1.jpg')
    book = tmp_path / 'book'
    (book / 'images').mkdir(parents=True)
    (book / 'images' / '1.jpg').write_bytes(JPEG)
    base = tmp_path / 'in'
    base.mkdir()
    plugin = _plugin(book_dir=str(book))

    plugin.fix_resources('<img src="images/1.jpg"/>', str(base))

    assert (base / 'images' / '1.jpg').read_bytes() == JPEG


def test_embed_images_off_skips_staging(tmp_path, monkeypatch):
    _refs(monkeypatch, 'images/1.jpg')
    book = tmp_path / 'book'
    (book / 'images').mkdir(parents=True)
    (book / 'images' / '1.jpg').write_bytes(JPEG)
    base = tmp_path / 'in'
    base.mkdir()
    plugin = _plugin(embed_images=False, book_dir=str(book))

    plugin.fix_resources('<img src="images/1.jpg"/>', str(base))

    assert list(base.iterdir()) == []


# -------------------------------------------------- url-escaped local images

#: How other tools spell a non-ASCII file name; the file on disk is «【壁纸】.jpg».
ENCODED = 'assets/%E3%80%90%E5%A3%81%E7%BA%B8%E3%80%91.jpg'
DECODED = 'assets/【壁纸】.jpg'
DECODED_NAME = '【壁纸】.jpg'


def test_encoded_reference_is_decoded_next_to_the_input(tmp_path, monkeypatch):
    # The file sits next to the input under its decoded name: the reference
    # has to be decoded (and the src rewritten to it) or neither the lookup
    # nor the builtin resource handling finds the image.
    _refs(monkeypatch, ENCODED)
    base = tmp_path / 'in'
    (base / 'assets').mkdir(parents=True)
    (base / 'assets' / DECODED_NAME).write_bytes(JPEG)
    plugin = _plugin()

    out = plugin.fix_resources('<img src="%s"/>' % ENCODED, str(base))

    assert 'src="%s"' % DECODED in out
    assert ENCODED not in out
    assert plugin.log.warnings == []


def test_encoded_reference_is_staged_from_the_book_folder(
        tmp_path, monkeypatch):
    _refs(monkeypatch, ENCODED)
    book = tmp_path / 'book'
    (book / 'assets').mkdir(parents=True)
    (book / 'assets' / DECODED_NAME).write_bytes(JPEG)
    base = tmp_path / 'in'
    base.mkdir()
    plugin = _plugin(book_dir=str(book))

    out = plugin.fix_resources('<img src="%s"/>' % ENCODED, str(base))

    assert (base / 'assets' / DECODED_NAME).read_bytes() == JPEG
    assert 'src="%s"' % DECODED in out
    assert ENCODED not in out
    assert plugin.log.warnings == []


def test_literal_percent_name_wins_over_decoding(tmp_path, monkeypatch):
    # A file really named 'a%20b.jpg' keeps working: the literal spelling is
    # tried first, so nothing is decoded or rewritten.
    _refs(monkeypatch, 'assets/a%20b.jpg')
    base = tmp_path / 'in'
    (base / 'assets').mkdir(parents=True)
    (base / 'assets' / 'a%20b.jpg').write_bytes(JPEG)
    plugin = _plugin()

    out = plugin.fix_resources('<img src="assets/a%20b.jpg"/>', str(base))

    assert out == '<img src="assets/a%20b.jpg"/>'
    assert plugin.log.warnings == []


def test_encoded_escape_cannot_leave_the_input_folder(tmp_path, monkeypatch):
    # '%2E%2E%2F' decodes to '../': the decoded spelling is re-checked, so the
    # reference is left alone and reported instead of escaping the folder.
    _refs(monkeypatch, '%2E%2E%2Foutside.jpg')
    base = tmp_path / 'in'
    base.mkdir()
    (tmp_path / 'outside.jpg').write_bytes(JPEG)
    plugin = _plugin(book_dir=str(tmp_path))

    out = plugin.fix_resources('<img src="%2E%2E%2Foutside.jpg"/>', str(base))

    assert out == '<img src="%2E%2E%2Foutside.jpg"/>'
    assert list(base.iterdir()) == []
    assert len(plugin.log.warnings) == 1


def test_encoded_reference_found_nowhere_is_reported(tmp_path, monkeypatch):
    # Decoding must not swallow the report: a reference that resolves nowhere
    # keeps its spelling and warns, exactly like a literal one.
    _refs(monkeypatch, 'assets/%E7%BC%BA.jpg')
    base = tmp_path / 'in'
    base.mkdir()
    plugin = _plugin()

    out = plugin.fix_resources('<img src="assets/%E7%BC%BA.jpg"/>', str(base))

    assert out == '<img src="assets/%E7%BC%BA.jpg"/>'
    assert len(plugin.log.warnings) == 1
    assert 'assets/%E7%BC%BA.jpg' in plugin.log.warnings[0]


def test_rewrite_html_image_srcs_handles_escaped_spellings():
    from calibre_plugins.markdown.utils.helpers import (
        rewrite_html_image_srcs,
    )

    html = '<img src="assets/a&amp;b.jpg"/><img src="assets/other.jpg">'
    out, count = rewrite_html_image_srcs(
        html, {'assets/a&b.jpg': 'assets/c&d.jpg'})

    assert count == 1
    assert 'src="assets/c&amp;d.jpg"' in out
    assert 'assets/other.jpg' in out
    assert rewrite_html_image_srcs('', {'a': 'b'}) == ('', 0)
    assert rewrite_html_image_srcs('x', {'a': 'a'}) == ('x', 0)


# ---------------------------------------------------- download_remote_images

def test_download_rewrites_src_and_lands_next_to_input(tmp_path, monkeypatch):
    _refs(monkeypatch)
    _patch_urlopen(monkeypatch, {URL: FakeResponse()})
    base = tmp_path / 'in'
    base.mkdir()
    plugin = _plugin()
    html = '<p>x</p><img src="%s" alt="a"/>' % URL

    plugin.fix_resources(html, str(base))

    assert (base / '21_b6cbe1.png').read_bytes() == PNG
    seen = plugin.fix_resources_seen[0]
    assert 'src="21_b6cbe1.png"' in seen
    assert URL not in seen


def test_download_off_keeps_the_remote_url(tmp_path, monkeypatch):
    _refs(monkeypatch)
    _boom_urlopen(monkeypatch)
    base = tmp_path / 'in'
    base.mkdir()
    plugin = _plugin(download_remote_images=False)

    plugin.fix_resources('<img src="%s"/>' % URL, str(base))

    assert URL in plugin.fix_resources_seen[0]
    assert list(base.iterdir()) == []


def test_download_requires_embed_images(tmp_path, monkeypatch):
    _refs(monkeypatch)
    _boom_urlopen(monkeypatch)
    base = tmp_path / 'in'
    base.mkdir()
    plugin = _plugin(embed_images=False)   # download stays on

    plugin.fix_resources('<img src="%s"/>' % URL, str(base))

    assert URL in plugin.fix_resources_seen[0]
    assert list(base.iterdir()) == []


def test_html_escaped_url_is_fetched_unescaped_and_rewritten(
        tmp_path, monkeypatch):
    _refs(monkeypatch)
    seen_urls = []

    def fake_urlopen(request, timeout=None):
        seen_urls.append(request.full_url)
        return FakeResponse()

    monkeypatch.setattr(ri, 'urlopen', fake_urlopen)
    base = tmp_path / 'in'
    base.mkdir()
    plugin = _plugin()
    raw = 'https://x/pic.png?w=1&h=2'
    html = '<img src="%s"/>' % raw.replace('&', '&amp;')

    plugin.fix_resources(html, str(base))

    assert seen_urls == [raw]
    assert (base / 'pic.png').read_bytes() == PNG
    assert 'src="pic.png"' in plugin.fix_resources_seen[0]


def test_duplicate_basenames_get_suffixes(tmp_path, monkeypatch):
    _refs(monkeypatch)
    a = 'https://cdn1/x/pic.png'
    b = 'https://cdn2/y/pic.png'
    _patch_urlopen(monkeypatch, {a: FakeResponse(), b: FakeResponse()})
    base = tmp_path / 'in'
    base.mkdir()
    plugin = _plugin()
    html = '<img src="%s"/><img src="%s"/>' % (a, b)

    plugin.fix_resources(html, str(base))

    assert (base / 'pic.png').read_bytes() == PNG
    assert (base / 'pic-2.png').read_bytes() == PNG
    seen = plugin.fix_resources_seen[0]
    assert 'src="pic.png"' in seen and 'src="pic-2.png"' in seen
    assert a not in seen and b not in seen


def test_failed_downloads_are_reported_and_kept(tmp_path, monkeypatch):
    _refs(monkeypatch)
    _patch_urlopen(monkeypatch, {URL: RuntimeError('down')})
    base = tmp_path / 'in'
    base.mkdir()
    plugin = _plugin()

    plugin.fix_resources('<img src="%s"/>' % URL, str(base))

    assert len(plugin.log.warnings) == 1
    assert 'failed to download' in plugin.log.warnings[0]
    assert URL in plugin.log.warnings[0]
    assert URL in plugin.fix_resources_seen[0]
    assert list(base.iterdir()) == []


# --------------------------------------------------------- save_remote_image

def test_save_remote_image_respects_reserved_names(tmp_path, monkeypatch):
    _patch_urlopen(monkeypatch, {URL: FakeResponse()})
    reserved = {'21_b6cbe1.png'}

    name = save_remote_image(URL, str(tmp_path), reserved)

    assert name == '21_b6cbe1-2.png'
    assert (tmp_path / name).read_bytes() == PNG
    assert name in reserved


def test_save_remote_image_failure_returns_none(tmp_path, monkeypatch):
    _patch_urlopen(monkeypatch, {URL: RuntimeError('x')})
    assert save_remote_image(URL, str(tmp_path), set()) is None


# ------------------------------------------------------------------ wiring

def test_input_options_declare_the_image_switches():
    names = {o.option.name: o for o in MarkdownInput.options}
    for name in ('keep_images', 'embed_images', 'download_remote_images'):
        assert name in names
        assert names[name].recommended_value is True


def test_input_option_keys_cover_the_image_switches():
    from calibre_plugins.markdown.utils.prefs import (
        EXPORT_OPTION_KEYS,
        INPUT_OPTION_KEYS,
    )
    for name in ('keep_images', 'embed_images', 'download_remote_images'):
        assert name in INPUT_OPTION_KEYS
    assert 'keep_images' not in EXPORT_OPTION_KEYS
    assert 'embed_images' not in EXPORT_OPTION_KEYS


def test_both_input_uis_declare_the_image_switch_rows():
    # The dialog imports Qt at module level and cannot be imported here, so
    # its rows are checked from the source. The pane builds its rows from a
    # table, so the real names and labels are compared directly.
    from calibre_plugins.markdown.input.conversion_ui import IMAGE_GROUP_ROWS

    assert IMAGE_GROUP_ROWS == (
        ('keep_images', 'Keep images'),
        ('keep_image_sizes', 'Image sizes'),
        ('embed_images', 'Embed images'),
        ('download_remote_images', 'Download remote images'),
    )
    pkg = pathlib.Path(__file__).resolve().parents[1] / 'Markdown' / 'input'
    dialog_src = (pkg / 'preference_ui.py').read_text(encoding='utf-8')
    for name, label in (('keep_images', 'Keep images'),
                        ('embed_images', 'Embed images'),
                        ('download_remote_images', 'Download remote images')):
        assert ("'%s', '%s', 'checkbox'" % (name, label)) in dialog_src
