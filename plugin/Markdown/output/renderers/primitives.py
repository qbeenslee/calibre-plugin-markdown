# -*- coding: utf-8 -*-
"""Free functions and constants shared by the renderer mixins.

Everything here is pure - no calibre objects, no renderer state - and the
mixin modules import from here instead of from each other, which is what
keeps them independent (and the calibre-debug verify scripts' seed order
trivial: primitives first).
"""

import numbers
import re


#: Tags whose own rendering opens a new line. A <blockquote> that starts with
#: one of these must not write the quote prefix itself: the child writes it
#: (or, for <hr> and friends, starts its own line regardless), and writing it
#: on both levels leaves a bare "> " line above the quote. Inline children
#: (text, <a>, <img>, <em>, ...) do need the prefix written for them.
BLOCK_LEVEL_TAGS = frozenset((
    'blockquote', 'div', 'dl', 'figure', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'hr', 'li', 'ol', 'p', 'pre', 'table', 'ul',
))

#: Blocks that can stand on a list item's own "- " line: the bullet already
#: opened the line, so these are written where the item stands instead of
#: opening a line of their own. Blocks that need lines of their own - a nested
#: list, a table, a fenced code block, a definition list - end the item's line
#: instead, as they always did (see _dump_item_block).
ITEM_LINE_BLOCKS = frozenset((
    'blockquote', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p',
))

#: The content of a list item is being rendered, and its own line is still
#: empty: the first block of the item continues the bullet's line (see
#: _dump_item_block).
ITEM_LINE_OPEN = 'open'

#: The content of a list item is being rendered and its own line is taken (by
#: the item's text, by inline content or by a block that opened a line of its
#: own): a block after it is a paragraph of the item of its own.
ITEM_LINE_STARTED = 'started'

#: The wrappers a list item's text comes in: a <p> (or <div>) around the text
#: is the item's own paragraph - a Markdown item *is* a paragraph - so the
#: wrapper is dropped and its content written where the item stands (see
#: _dump_item_paragraph).
ITEM_TEXT_WRAPPERS = frozenset(('div', 'p'))

#: Tags that keep their own Markdown syntax inside a heading. Everything else
#: a heading holds is flattened to plain text: a Markdown heading is one line,
#: and its "#" markers already say it is a heading - so no "**" for the bold
#: the children inherit from it, no newline from a <br>, no "#" run of its own
#: for a nested heading.
HEADING_INLINE_TAGS = frozenset((
    'a', 'cite', 'code', 'del', 'img', 'mark', 's', 'strike', 'sub', 'sup',
))


def _ends_with_blank_line(text):
    """True when the collected text already ends with a blank line."""
    return ''.join(text[-2:]).endswith('\n\n')


def _has_visible_text(fragments):
    """True when rendered fragments hold something other than whitespace."""
    return any(isinstance(part, str) and part.strip() for part in fragments)


def _drop_leading_blank_fragments(fragments):
    """Drop the blank fragments a block leaves before its own first line.

    A book indents the markup of a block (`<ul>` and its first `<li>` are on
    lines of their own), and the fold turns that whitespace into a space which
    is written before the block's own newline - a trailing space on the line
    above it, once the block is written on a line of its own.
    """
    for index, part in enumerate(fragments):
        if not isinstance(part, str):
            return fragments[index:]
        if part.strip() or '\n' in part:
            return fragments[index:]
    return []


def _css_margin_break(style, side):
    '''Blank lines a top/bottom CSS margin asks for, as calibre upstream.

    Mirrors MarkdownMLizer.dump_text's "soft scene breaks" so replacing the
    inherited blockquote branch does not silently drop them; anything the
    arithmetic cannot make sense of yields no break instead of an exception.
    '''
    key = 'margin-%s' % side
    if key not in style.cssdict() or style[key] == 'auto':
        return ''
    try:
        ems = int(round(float(getattr(style, 'margin' + side.capitalize()))
                        / style.fontSize) - 1)
    except (TypeError, ValueError, ZeroDivisionError):
        return ''
    return '\n\n' * ems if ems >= 1 else ''


#: A margin length the renderer can read as a number: a bare number with an
#: optional CSS unit, or one of the keywords a margin may carry instead. Every
#: other value calibre's unit_convert() returns unchanged, and the renderer's
#: soft-scene-break code then calls float() on that string.
_CSS_LENGTH_RE = re.compile(
    r'^-?(?:\d+\.?\d*|\.\d+)(?:%|em|rem|ex|en|px|pt|pc|in|mm|cm|q)?$', re.I)
_MARGIN_KEYWORDS = frozenset(('auto', 'inherit', 'initial', 'unset'))

#: The margins the renderer reads as lengths (the left/right ones are not).
MARGIN_LENGTH_KEYS = ('margin-top', 'margin-bottom')


def _is_readable_length(value):
    if isinstance(value, numbers.Number):
        return True
    if value is None:
        return False
    text = str(value).strip()
    if text.lower() in _MARGIN_KEYWORDS:
        return True
    return bool(_CSS_LENGTH_RE.match(text))


def repair_margin_lengths(style):
    '''Read the margins this style declares unreadably as 0, and say which.

    calibre expands the `margin` shorthand itself, so a typo like
    `margin: -2em 0 olid #20F2f0` arrives here as `margin-bottom: olid`.
    unit_convert() hands a value it cannot read back unchanged and the
    renderer's soft-scene-break code then calls float() on it, which aborts the
    whole conversion - the book never exports. Such a margin is the book's own
    typo, so it is read as "no margin": upstream then computes a negative em
    count and writes no break, which keeps the export honest instead of
    inventing a length.
    '''
    getter = getattr(style, 'get', None)
    setter = getattr(style, 'set', None)
    if getter is None or setter is None:
        return []
    repaired = []
    for key in MARGIN_LENGTH_KEYS:
        value = getter(key)
        if value is None or _is_readable_length(value):
            continue
        repaired.append((key, value))
        setter(key, '0')
    return repaired


def margin_repair_summary(repaired):
    '''The single log line a book with unreadable margins leaves behind.'''
    values = sorted({str(value) for _, value in repaired})
    return ('Markdown: read %s unreadable CSS margin value(s) as 0 (%s). '
            'The book declares margins calibre cannot parse, a shorthand '
            'typo for example.' % (len(repaired), ', '.join(values)))

