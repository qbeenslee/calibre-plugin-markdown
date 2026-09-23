# -*- coding: utf-8 -*-
"""Test scaffolding for the Markdown conversion output plugin.

calibre ships its own frozen interpreter and a huge Qt stack; the plugin
modules import `calibre.*` at module level. In the project venv none of that
exists, so we install minimal stubs and register the plugin source directory
as the package `calibre_plugins.markdown` (the name calibre uses at runtime).

Only what the import chain actually needs gets stubbed: the plugin
`__init__.py` below pulls in `output/output_plugin` (OutputFormatPlugin,
OptionRecommendation, TXTOutput and the builtin `_`), and the lazy imports
inside `MarkdownOutput.convert()` pull in `output/convert_flow` (default_log),
`calibre.ebooks.txt.newlines` and `calibre.utils.cleantext`.
"""

import builtins
import importlib.util
import pathlib
import sys
import types

PKG_DIR = pathlib.Path(__file__).resolve().parents[1] / 'Markdown'

# Names that must look like packages, so imports of their submodules behave.
PACKAGE_NAMES = (
    'calibre',
    'calibre.ebooks',
    'calibre.ebooks.conversion',
    'calibre.ebooks.conversion.plugins',
    'calibre.ebooks.metadata',
    'calibre.ebooks.txt',
    'calibre.gui2',
    'calibre.gui2.convert',
    'calibre.utils',
)


#: python-markdown extensions calibre's TXT Input knows about. The Markdown
#: input pane must offer exactly these minus the ones governed by dedicated
#: options (meta -> read_yaml_metadata, nl2br -> md_line_break).
_MD_EXTENSION_NAMES = (
    'abbr', 'admonition', 'attr_list', 'codehilite', 'def_list', 'extra',
    'fenced_code', 'footnotes', 'legacy_attrs', 'legacy_em', 'meta',
    'nl2br', 'sane_lists', 'smarty', 'tables', 'toc', 'wikilinks',
)

#: The language codes the tests exercise through canonicalize_lang.
_CANONICAL_LANGS = {'zh': 'zho', 'zh-cn': 'zho', 'zho': 'zho'}


class _StubGuiWidget:
    """Matches calibre's Widget enough for PluginWidget unit tests."""

    def __init__(self, parent, options):
        self._options = list(options)

    def get_value_handler(self, g):
        # calibre's Widget returns this sentinel for widgets a pane does not
        # handle itself; Widget.get_value() then falls back to its per-type
        # handling (the EncodingComboBox included).
        return 'this is a dummy return value, xcswx1avcx4x'


class _StubGui2PluginWidget(_StubGuiWidget):
    pass


class _StubUiForm:
    pass


class _StubMarkdownMLizer:
    """Base-class stub recording what EnhancedMarkdownMLizer feeds it."""

    def __init__(self, log=None):
        self.log = log
        self.mlize_seen_spine = None

    def mlize_spine(self, oeb_book):
        self.mlize_seen_spine = list(oeb_book.spine)
        return ''

    def remove_newlines(self, text):
        return text

    def prepare_string_for_markdown(self, text):
        return text

    def prepare_string_for_pre(self, text):
        return text


def _mod(name, **attrs):
    """Get-or-create a module object and attach attributes to it."""
    module = sys.modules.get(name)
    if module is None:
        module = types.ModuleType(name)
        sys.modules[name] = module
    if name in PACKAGE_NAMES:
        module.__path__ = []
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


class _Plugin:
    name = 'Stub Plugin'
    version = (0, 0, 0)

    def __init__(self, plugin_path=None):
        self.plugin_path = plugin_path
        self.site_customization = None


class _InterfaceActionBase(_Plugin):
    actual_plugin = None

    def load_actual_plugin(self, gui):
        raise NotImplementedError


class _ConversionOption:
    """Matches calibre's ConversionOption: option metadata lives here."""

    def __init__(self, name=None, choices=None, help=None, **kwargs):
        self.name = name
        self.choices = choices
        self.help = help
        self.__dict__.update(kwargs)


class _OptionRecommendation:
    LOW, MED, HIGH = 1, 2, 3

    def __init__(self, recommended_value=None, level=1, **kwargs):
        # calibre passes everything except the value/level on to
        # ConversionOption, so `name` and `choices` live on self.option.
        self.recommended_value = recommended_value
        self.level = level
        self.option = _ConversionOption(**kwargs)
        if self.option.choices and recommended_value not in self.option.choices:
            raise ValueError(
                'OpRec: %s: Recommended value not in choices' % self.option.name)


class _OutputFormatPlugin(_Plugin):
    name = 'Stub Output Plugin'
    file_type = 'stub'
    options = {}
    ui_data = {}


class _TXTOutput(_OutputFormatPlugin):
    def convert(self, oeb_book, output_path, input_plugin, opts, log):
        raise NotImplementedError


class _OPF:
    """Stand-in for calibre's opf2.OPF; tests replace it per case."""

    def __init__(self, *args, **kwargs):
        raise NotImplementedError


class _InputFormatPlugin(_Plugin):
    name = 'Stub Input Plugin'
    file_types = set()
    options = set()
    common_options = {
        _OptionRecommendation(name='input_encoding', recommended_value=None,
                              level=1),
    }
    ui_data = {}

    def convert(self, stream, options, file_ext, log, accelerators):
        raise NotImplementedError


class _TXTInput(_InputFormatPlugin):
    """Matches TXT Input's markdown contract: fix_resources(html, base_dir)."""

    name = 'Stub TXT Input'
    file_types = {'txt', 'md'}
    ui_data = {'paragraph_types': {
        'auto': 'auto', 'block': 'block', 'single': 'single',
        'print': 'print', 'unformatted': 'unformatted', 'off': 'off'}}

    def fix_resources(self, html, base_dir):
        self.fix_resources_seen = (html, base_dir)
        return html


class _TxtNewlines:
    """Matches calibre's TxtNewlines(newline).newline round trip."""

    def __init__(self, newline):
        self.newline = newline


class _NullLog:
    """Stand-in for calibre.utils.logging.default_log (never used by tests)."""

    def info(self, *args, **kwargs):
        pass

    def debug(self, *args, **kwargs):
        pass

    def warn(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


class _JSONConfig(dict):
    """In-memory stand-in for calibre.utils.config.JSONConfig.

    Unlike the real thing this is neither a per-name singleton nor
    persistent: `commit()` does nothing and nothing is written to disk.
    """

    def __init__(self, name):
        super().__init__()
        self.name = name
        self.defaults = {}

    def __getitem__(self, key):
        if key in self.defaults and not dict.__contains__(self, key):
            return self.defaults[key]
        return dict.__getitem__(self, key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def commit(self):
        pass


def _stub_detect(raw):
    """Matches calibre.ebooks.chardet.detect closely enough for tests."""
    try:
        raw.decode('utf-8')
    except UnicodeDecodeError:
        return {'encoding': 'gbk', 'confidence': 0.5}
    return {'encoding': 'utf-8', 'confidence': 0.99}


def _install_stubs():
    if not hasattr(builtins, '_'):
        builtins._ = lambda text: text

    _mod('calibre')
    customize = _mod('calibre.customize',
                     InterfaceActionBase=_InterfaceActionBase, Plugin=_Plugin)
    customize.ui = _mod('calibre.customize.ui', _initialized_plugins=[],
                        is_disabled=lambda plugin: False)
    _mod('calibre.customize.conversion', OutputFormatPlugin=_OutputFormatPlugin,
         InputFormatPlugin=_InputFormatPlugin,
         OptionRecommendation=_OptionRecommendation)
    _mod('calibre.ebooks')
    _mod('calibre.ebooks.chardet', detect=_stub_detect)
    _mod('calibre.ebooks.conversion')
    _mod('calibre.ebooks.conversion.plugins')
    _mod('calibre.ebooks.conversion.plugins.txt_input', TXTInput=_TXTInput,
         MD_EXTENSIONS={name: name for name in _MD_EXTENSION_NAMES})
    _mod('calibre.ebooks.conversion.plugins.txt_output', TXTOutput=_TXTOutput,
         NEWLINE_TYPES=['system', 'unix', 'old_mac'])
    _mod('calibre.ebooks.metadata')
    _mod('calibre.ebooks.metadata.opf2', OPF=_OPF)
    _mod('calibre.ebooks.txt')
    _mod('calibre.ebooks.txt.newlines', TxtNewlines=_TxtNewlines,
         specified_newlines=lambda newline, text: text)
    _mod('calibre.ebooks.txt.markdownml', MarkdownMLizer=_StubMarkdownMLizer)
    _mod('calibre.ebooks.oeb.base',
         XHTML_NS='http://www.w3.org/1999/xhtml',
         barename=lambda tag: str(tag).rsplit('}', 1)[-1],
         namespace=lambda tag: str(tag).split('}', 1)[0].lstrip('{')
         if '}' in str(tag) else '')
    _mod('calibre.gui2')
    _mod('calibre.gui2.convert', Widget=_StubGuiWidget)
    _mod('calibre.gui2.convert.txt_output',
         PluginWidget=_StubGui2PluginWidget)
    _mod('calibre.gui2.convert.txt_output_ui', Ui_Form=_StubUiForm)
    _mod('calibre.utils')
    _mod('calibre.utils.config', JSONConfig=_JSONConfig)
    _mod('calibre.utils.cleantext', clean_ascii_chars=lambda text: text)
    _mod('calibre.utils.localization', _=lambda text: text,
         canonicalize_lang=lambda value: _CANONICAL_LANGS.get(
             str(value or '').lower(), value or None))
    _mod('calibre.utils.logging', default_log=_NullLog())


def _register_plugin_package():
    if 'calibre_plugins.markdown' in sys.modules:
        return sys.modules['calibre_plugins.markdown']

    calibre_plugins = _mod('calibre_plugins')
    calibre_plugins.__path__ = [str(PKG_DIR.parent)]

    # Execute the real __init__.py so tests see the same module object that
    # calibre builds at runtime (constants included).
    spec = importlib.util.spec_from_file_location(
        'calibre_plugins.markdown', PKG_DIR / '__init__.py',
        submodule_search_locations=[str(PKG_DIR)])
    module = importlib.util.module_from_spec(spec)
    sys.modules['calibre_plugins.markdown'] = module
    spec.loader.exec_module(module)
    return module


def pytest_configure(config):
    _install_stubs()
    _register_plugin_package()
