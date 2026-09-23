# -*- coding: utf-8 -*-
"""Sized images: the book's width/height survive as raw <img> HTML.

A plain ![alt](src) cannot carry the size a book declares through width/height
attributes or CSS, so those images are exported as <img src=... width=...
height=...> instead. Everything without a declared size keeps the Markdown
form.
"""

import types

from calibre_plugins.markdown.utils.helpers import (
    html_image_tag,
    image_size_attrs,
    inline_image_references,
    rewrite_markdown_image_dir,
)

JPEG = b'\xff\xd8\xff\xe0JPEG'
XHTML = 'http://www.w3.org/1999/xhtml'


# ---------------------------------------------------------------- helpers

def test_attribute_values_win_over_css():
    # The plain width/height attributes are the book's explicit numbers; CSS
    # only fills the dimensions the attributes leave open.
    assert image_size_attrs(
        {'width': '800', 'height': '676'},
        {'width': '80%', 'height': 'auto'}) == {
            'width': '800px', 'height': '676px'}


def test_css_fills_the_dimensions_attributes_leave_open():
    assert image_size_attrs({'width': '800'}, {'height': '1200'}) == {
        'width': '800px', 'height': '1200px'}


def test_bare_numbers_become_pixels_and_units_are_kept():
    assert image_size_attrs({}, {'width': '800', 'height': '50%'}) == {
        'width': '800px', 'height': '50%'}
    assert image_size_attrs({}, {'width': '1em'}) == {
        'width': '1em', 'height': 'auto'}


def test_missing_dimension_becomes_auto():
    assert image_size_attrs({'width': '800'}, {}) == {
        'width': '800px', 'height': 'auto'}


def test_no_declared_size_is_none():
    assert image_size_attrs({}, {}) is None
    assert image_size_attrs({'width': ''}, {'height': 'auto'}) is None


def test_html_image_tag_keeps_alt_title_and_size():
    assert html_image_tag(
        'images/000123.jpg', alt='背景图', title='图 1',
        size={'width': '800px', 'height': 'auto'}) == (
            '<img src="images/000123.jpg" alt="背景图" title="图 1" '
            'width="800px" height="auto">')


def test_html_image_tag_omits_empty_alt_and_title():
    assert html_image_tag('images/1.jpg', size={'width': '50%'}) == (
        '<img src="images/1.jpg" width="50%" height="auto">')


def test_html_image_tag_escapes_attribute_values():
    tag = html_image_tag(
        'images/a&b.jpg', alt='a "quote" <b>', size={'width': '50%'})
    assert 'src="images/a&amp;b.jpg"' in tag
    assert 'alt="a &quot;quote&quot; &lt;b&gt;"' in tag


class FakeItem:
    def __init__(self, data, href='images/cover.jpeg'):
        self.data = data
        self.href = href


class FakeOEB:
    def __init__(self):
        self.manifest = [FakeItem(JPEG)]


def test_rewrite_handles_the_html_form():
    src = 'a <img src="images/000123.jpg" width="800px" height="auto"> b'
    out = rewrite_markdown_image_dir(src, 'book.images')
    assert 'src="book.images/000123.jpg"' in out
    assert 'width="800px" height="auto"' in out


def test_inline_handles_the_html_form():
    text = '<img src="images/cover.jpeg" alt="c" width="800px" height="auto">'
    out, count = inline_image_references(
        text, FakeOEB(), {'images/cover.jpeg': 'cover.jpeg'})
    assert count == 1
    assert 'src="data:image/jpeg;base64,' in out
    assert 'width="800px" height="auto"' in out


# --------------------------------------------------------------- renderer

class Log:
    def info(self, message):
        pass

    def debug(self, message):
        pass


class FakeStylizer:
    """Matches the slices of calibre's Stylizer this renderer reads."""

    def __init__(self, declared=None):
        self._style = {'display': 'block', 'visibility': 'visible'}
        self._style.update(declared or {})

    def style(self, elem):
        return self._style


def _mlizer(**opt_values):
    from calibre_plugins.markdown.output.markdownml_enhanced import (
        EnhancedMarkdownMLizer,
    )
    options = {'keep_image_references': True}
    options.update(opt_values)
    mlizer = EnhancedMarkdownMLizer(Log())
    mlizer.opts = types.SimpleNamespace(**options)
    # extract_content() normally initializes these; dump_text reads them.
    mlizer.in_pre = False
    mlizer.in_code = False
    mlizer._in_table_cell = False
    mlizer._in_figure = False
    return mlizer


def _img(**attribs):
    tail = attribs.pop('tail', None)
    return types.SimpleNamespace(
        tag='{%s}img' % XHTML, attrib=dict(attribs), tail=tail)


def _render(attribs, declared=None, **opt_values):
    mlizer = _mlizer(**opt_values)
    return ''.join(mlizer.dump_text(_img(**attribs), FakeStylizer(declared)))


def _block_upstream(monkeypatch, text):
    """Make the upstream rendering observable (the stub base has none)."""
    from calibre.ebooks.txt import markdownml

    monkeypatch.setattr(
        markdownml.MarkdownMLizer, 'dump_text',
        lambda self, elem, stylizer: ['UPSTREAM' + text], raising=False)


def test_sized_image_is_rendered_as_html():
    assert _render({'src': 'images/000123.jpg', 'width': '800',
                    'height': '676', 'alt': '背景图'}) == (
        '<img src="images/000123.jpg" alt="背景图" '
        'width="800px" height="676px">')


def test_size_from_css_alone_is_rendered_as_html():
    assert _render({'src': 'images/000123.jpg'}, {'width': '80%'}) == (
        '<img src="images/000123.jpg" width="80%" height="auto">')


def test_tail_after_a_sized_image_is_kept():
    assert _render({'src': 'images/1.jpg', 'width': '800', 'tail': '。'}) == (
        '<img src="images/1.jpg" width="800px" height="auto">。')


def test_unsized_image_keeps_the_markdown_form():
    # The plain form is the plugin's own: calibre's branch writes the [] only
    # when the <img> carries an alt attribute.
    assert _render({'src': 'images/1.jpg', 'alt': '图'}) == '![图](images/1.jpg)'


def test_unsized_image_without_alt_still_writes_the_brackets():
    # The reported bug: an <img> with no alt attribute at all came out as
    # !(images/1.jpg) - text, not an image.
    assert _render({'src': 'images/1.jpg'}) == '![](images/1.jpg)'


def test_empty_alt_writes_empty_brackets():
    assert _render({'src': 'images/1.jpg', 'alt': ''}) == '![](images/1.jpg)'


def test_tail_after_an_unsized_image_is_kept():
    assert _render({'src': 'images/1.jpg', 'tail': '。'}) == '![](images/1.jpg)。'


def test_image_without_src_keeps_the_markdown_form(monkeypatch):
    _block_upstream(monkeypatch, '')
    assert _render({'width': '800'}) == 'UPSTREAM'


def test_images_are_left_alone_without_keep_image_references(monkeypatch):
    # With "Keep images" off calibre's own branch decides: the alt text is
    # written in place of the image, nothing is hijacked here.
    _block_upstream(monkeypatch, '')
    assert _render({'src': 'images/1.jpg', 'width': '800'},
                   keep_image_references=False) == 'UPSTREAM'
    assert _render({'src': 'images/1.jpg', 'alt': '图'},
                   keep_image_references=False) == 'UPSTREAM'


def test_sizes_off_keeps_the_markdown_form():
    # "Keep image sizes" unchecked: the declared size is dropped and the
    # image exports as a plain Markdown reference.
    assert _render({'src': 'images/1.jpg', 'width': '800', 'height': '676'},
                   keep_image_sizes=False) == '![](images/1.jpg)'


def test_hidden_sized_image_stays_hidden():
    mlizer = _mlizer()
    elem = _img(src='images/1.jpg', width='800', tail='尾')
    assert ''.join(mlizer.dump_text(
        elem, FakeStylizer({'display': 'none'}))) == '尾'
