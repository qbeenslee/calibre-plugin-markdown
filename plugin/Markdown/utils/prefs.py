# -*- coding: utf-8 -*-

__license__ = 'GPL 3'

import json

from calibre.utils.config import JSONConfig

PLUGIN_SAFE_NAME = 'markdown_output'

IMAGE_OUTPUT_MODES = ('sidecar', 'inline', 'none')
DEFAULT_IMAGE_OUTPUT_MODE = 'sidecar'

#: Maps an image output mode value to the i18n key of its display label, so
#: the combo (conversion pane and customization dialog) shows a localized
#: name while still committing the raw value. Keeping the table here - next to
#: IMAGE_OUTPUT_MODES and outside any Qt module - makes both UIs share one
#: set of keys instead of duplicating the English source strings.
IMAGE_MODE_LABELS = {
    'sidecar': 'Images next to the Markdown file',
    'inline': 'Images embedded as data URIs',
    'none': 'Do not export images',
}

PARAGRAPH_STYLES = ('block', 'single')
DEFAULT_PARAGRAPH_STYLE = 'block'

CUSTOMIZATION_VERSION = 1

EXPORT_OPTION_KEYS = (
    'inline_toc',
    'keep_links',
    'keep_image_references',
    'keep_image_sizes',
    'export_cover_page',
    'use_alt_text_for_images',
    'export_image_files',
    'download_remote_images',
    'image_output_mode',
    'paragraph_style',
    'blank_line_before_heading',
    'heading_anchors',
    'escape_markdown_chars',
    'yaml_front_matter',
    'filename_pattern',
    'strip_pdf_page_markers',
    'max_line_length',
    'force_max_line_length',
    'newline',
    'txt_output_encoding',
)

#: Option names the input plugin's customization dialog may override
#: globally; the names are the per-conversion options in input/input_plugin.py.
INPUT_OPTION_KEYS = (
    'input_encoding',
    'md_line_break',
    'paragraph_type',
    'read_yaml_metadata',
    'keep_images',
    'embed_images',
    'download_remote_images',
    'keep_image_sizes',
    'markdown_extensions',
)

DEFAULTS = {
    'has_user_preferences': False,
    # Best-quality Markdown defaults: preserve structure/media, add TOC,
    # keep soft paragraphs (no hard wrap), unix newlines for editors/Git.
    'inline_toc': True,
    'keep_links': True,
    'keep_image_references': True,
    'keep_image_sizes': True,
    'export_cover_page': True,
    'use_alt_text_for_images': True,
    'export_image_files': True,
    'download_remote_images': True,
    'image_output_mode': DEFAULT_IMAGE_OUTPUT_MODE,
    'paragraph_style': DEFAULT_PARAGRAPH_STYLE,
    'blank_line_before_heading': True,
    'heading_anchors': True,
    'escape_markdown_chars': False,
    'yaml_front_matter': True,
    'filename_pattern': 'title',
    'strip_pdf_page_markers': False,
    'max_line_length': 0,
    'force_max_line_length': False,
    'newline': 'unix',
    'txt_output_encoding': 'utf-8',
    'last_output_dir': '',
    'about_shown': False,
}


def get_prefs():
    prefs = JSONConfig('plugins/{0}_settings'.format(PLUGIN_SAFE_NAME))
    for key, value in DEFAULTS.items():
        prefs.defaults[key] = value
    return prefs


def read_plugin_overrides(plugin_name):
    """The global overrides saved by the plugin customization dialog.

    They act as the starting values for a conversion pane: calibre has no
    per-book saved settings for a fresh conversion, so the pane shows these
    and whatever it commits (changed or not) is what the conversion uses.
    Returns {} when nothing was saved or calibre is unavailable (tests,
    standalone scripts).
    """
    try:
        import json

        from calibre.customize.ui import config
        payload = config['plugin_customization'].get(plugin_name)
        if not payload:
            return {}
        saved = json.loads(payload) if isinstance(payload, str) else payload
        return dict(saved.get('overrides') or {})
    except Exception:
        return {}


def save_export_options(prefs, mark_user=False, **values):
    for key in EXPORT_OPTION_KEYS:
        if key in values:
            prefs[key] = values[key]
    if mark_user:
        prefs['has_user_preferences'] = True
    prefs.commit()
    return prefs


def read_export_options(prefs):
    return {key: prefs[key] for key in EXPORT_OPTION_KEYS if key in prefs}


def serialize_customization(overrides):
    '''Encode the global overrides shown in the customization dialog.'''
    payload = {'version': CUSTOMIZATION_VERSION, 'overrides': dict(overrides or {})}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def parse_customization(raw):
    '''Extract the global override dict from a site_customization string.

    Returns {} for anything unexpected: empty input, malformed JSON, wrong
    version or a non-dict payload. Unknown keys are passed through as-is;
    the caller decides which names are real options.
    '''
    if not isinstance(raw, str):
        return {}
    raw = raw.strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except ValueError:
        return {}
    if not isinstance(payload, dict):
        return {}
    if payload.get('version') != CUSTOMIZATION_VERSION:
        return {}
    overrides = payload.get('overrides')
    if not isinstance(overrides, dict):
        return {}
    return dict(overrides)
