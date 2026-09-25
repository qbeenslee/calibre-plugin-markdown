# -*- coding: utf-8 -*-
"""The renderer split: the mixins stay independent and none shadows another.

The renderer is assembled from one mixin per rendering domain (see
docs/specs/2026-09-26-output-renderer-split.md). Two of the properties the
split relies on are invisible at runtime and easy to break by accident:

* a method defined by two mixins would be silently taken from the earlier
  one, so the later definition would be dead code;
* a mixin importing another mixin would make the renderer's module graph
  depend on import order - and the calibre-debug verify scripts seed the
  source tree module by module, in a fixed order, so that import would
  either fail there or, worse, silently resolve against the installed zip.

Both are checked here, together with the shape of the assembled class.
"""

import ast
import pathlib

from calibre.ebooks.txt.markdownml import MarkdownMLizer

from calibre_plugins.markdown.output import renderers
from calibre_plugins.markdown.output.markdownml_enhanced import (
    EnhancedMarkdownMLizer,
)

#: The mixins the renderer is assembled from, one module each.
MIXIN_MODULES = (
    'blocks', 'document', 'footnotes', 'headings', 'inline', 'lists',
    'media', 'primitives', 'tables', 'text',
)

RENDERERS_PREFIX = 'calibre_plugins.markdown.output.renderers.'

#: Inside the plugin, a mixin may only reach for these: the shared helper
#: layer, the UI language (imported lazily by the TOC heading) and the
#: primitives module. Anything else - another mixin, the renderer itself -
#: is a boundary violation.
ALLOWED_PLUGIN_IMPORTS = (
    'calibre_plugins.markdown.utils',
    'calibre_plugins.markdown.translations',
    RENDERERS_PREFIX + 'primitives',
)


def _mixin_classes():
    return [cls for cls in EnhancedMarkdownMLizer.__mro__
            if cls.__module__.startswith(RENDERERS_PREFIX)]


def test_every_renderer_module_is_present():
    root = pathlib.Path(renderers.__file__).parent
    stems = {path.stem for path in root.glob('*.py')} - {'__init__'}

    assert stems == set(MIXIN_MODULES)


def test_every_domain_is_mixed_in():
    assert {cls.__module__.rsplit('.', 1)[-1] for cls in _mixin_classes()} \
        == set(MIXIN_MODULES) - {'primitives'}


def test_no_method_is_defined_by_two_mixins():
    seen = {}
    for cls in _mixin_classes():
        for name, value in vars(cls).items():
            if name.startswith('__'):
                continue
            assert name not in seen, \
                '%s is defined by both %s and %s' % (name, seen[name], cls)
            seen[name] = cls
            # The mixin must actually be part of the assembled class: a
            # module whose class was left out of the bases would never run.
            assert getattr(EnhancedMarkdownMLizer, name) is value, name


def test_the_super_chain_ends_at_calibre_markdownmlizer():
    assert EnhancedMarkdownMLizer.__mro__[-2] is MarkdownMLizer


def test_mixins_import_nothing_but_the_allowed_modules():
    root = pathlib.Path(renderers.__file__).parent
    for path in sorted(root.glob('*.py')):
        if path.name == '__init__.py':
            continue
        tree = ast.parse(path.read_text(encoding='utf-8'))
        classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]
        expected = 0 if path.name == 'primitives.py' else 1
        assert len(classes) == expected, path.name
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            module = node.module or ''
            if module.startswith('calibre_plugins.'):
                assert module.startswith(ALLOWED_PLUGIN_IMPORTS), \
                    '%s imports %s' % (path.name, module)
