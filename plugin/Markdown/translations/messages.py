# -*- coding: utf-8 -*-
"""Message table behind the plugin's own `_()`.

The English text is the lookup key; `_()` returns the entry for the language
translations.ui_language currently has selected. The tables also carry the
conversion-option help ("hint") strings, so their keys must stay in sync with
the OptionRecommendation help texts in output/output_plugin.py and
input/input_plugin.py.
"""

__license__ = 'GPL 3'

from calibre_plugins.markdown.translations.ui_language import (
    UI_LANG_EN,
    UI_LANG_ZH_CN,
    get_ui_language,
)


def _T(en, zh_cn):
    return {UI_LANG_EN: en, UI_LANG_ZH_CN: zh_cn}


#: Shared by both plugins: the warning a failed remote-image download
#: produces. The references stay as URLs; only the conversion report
#: carries the news.
REMOTE_DOWNLOAD_FAILED_MESSAGE = (
    'Markdown: {} remote image(s) failed to download, their references '
    'were kept as URLs: {}')


_MESSAGES = {
    'Markdown': _T('Markdown', 'Markdown'),
    'Markdown output': _T('Markdown output', 'Markdown 输出'),
    'About recommendations intro': _T(
        'Recommended utilities from Nowtiny (excluding this plugin):',
        '来自 Nowtiny 的推荐小工具（不含当前插件）：',
    ),
    'About recommendations site link': _T(
        'Explore more on <a href="{url}">Nowtiny</a>',
        '在 <a href="{url}">Nowtiny</a> 查看更多工具',
    ),
    'About lineage': _T(
        'Based on The_book\'s Markdown Output plugin for calibre.\n'
        'Original thread: {url}\n'
        'This is a community-maintained version (module: markdown_output).',
        '基于 The_book 的 calibre Markdown Output 插件。\n'
        '原帖：{url}\n'
        '当前为社区维护版本（模块名：markdown_output）。',
    ),
    'About maintainer': _T(
        'Maintainer: {author}\n'
        'Last updated: {date}',
        '维护者：{author}\n'
        '最后更新：{date}',
    ),
    'About quick start': _T(
        'Quick start:\n'
        '1. Add Markdown to the main toolbar (Preferences → Toolbars & menus).\n'
        '2. Select one or more books in your library.\n'
        '3. Click Markdown, choose export options, then pick a folder to save .md files.',
        '快速上手：\n'
        '1. 在「偏好设置 → 工具栏和菜单」中将 Markdown 加入主工具栏。\n'
        '2. 在书库中选中一本或多本书。\n'
        '3. 点击 Markdown，设置导出选项，再选择保存 .md 文件的文件夹。',
    ),
    'Export to Markdown': _T('Export to Markdown', '导出为 Markdown'),
    'Export intro': _T(
        'Export selected books as Markdown files. Choose target folder after confirm.',
        '导出所选图书为 Markdown 文件。确认后选择目标目录。',
    ),
    'Export options heading': _T('Markdown output options', 'Markdown 输出选项'),
    'Add table of contents at the beginning': _T(
        'Add table of contents at the beginning',
        '在开头添加目录',
    ),
    'Hint inline toc': _T(
        'Insert top TOC. Fast section jump.',
        '插入文首目录。快速跳转章节。',
    ),
    'Keep links': _T('Keep links', '保留链接'),
    'Keep links (<a> tags)': _T('Keep links (<a> tags)', '保留链接（<a>标签）'),
    'Hint keep links': _T(
        'Keep Markdown links. Preserve anchor and URL jumps.',
        '保留 Markdown 链接。保留锚点与网址跳转。',
    ),
    'Keep image references': _T('Keep image references', '保留图片引用'),
    'Keep image sizes': _T('Keep image sizes', '保留图片尺寸'),
    #: The conversion panes' "Images" group shows the same two switches under
    #: these shorter names ('Image sizes' for keep_image_sizes on both sides);
    #: the customization dialogs keep the longer 'Keep ...' rows above.
    'Images': _T('Images', '图片'),
    'Image sizes': _T('Image sizes', '图片尺寸'),
    'Export cover page': _T('Export cover page', '导出封面页'),
    'Hint keep images': _T(
        'Keep image references. Write ![alt](path) in the Markdown.',
        '保留图片引用。在 Markdown 中写入 ![替代文字](路径)。',
    ),
    'Export image files': _T('Export image files', '导出图片文件'),
    'Hint export images': _T(
        'Copy image files next to the .md into a sibling .images folder.',
        '将图片复制到 .md 旁的 .images 目录。',
    ),
    'Keep images': _T('Keep images', '保留图片'),
    'Embed images': _T('Embed images', '内嵌图片'),
    'Download remote images': _T('Download remote images', '下载远程图片'),
    REMOTE_DOWNLOAD_FAILED_MESSAGE: _T(
        REMOTE_DOWNLOAD_FAILED_MESSAGE,
        'Markdown：{} 张远程图片下载失败，其引用保持为 URL：{}',
    ),
    'Add YAML front matter': _T('Add YAML front matter', '添加 YAML 文首元数据'),
    'Hint yaml front matter': _T(
        'Write title, authors, language, publisher, tags, series, isbn, pubdate, description, and calibre_id.',
        '从书库元数据写入标题、作者、语言、出版社、标签、系列、ISBN、出版日期、简介与 calibre_id。',
    ),
    'Filename pattern:': _T('Filename pattern:', '文件名格式：'),
    'Filename pattern title': _T('Title', '书名'),
    'Filename pattern author title': _T('Author - Title', '作者 - 书名'),
    'Filename pattern author folder': _T('Author / Title', '作者 / 书名'),
    'Filename pattern series title': _T('Series 01 - Title', '系列 01 - 书名'),
    'Hint filename title': _T(
        'Save as Title.md. Same as previous versions.',
        '保存为「书名.md」。与旧版相同。',
    ),
    'Hint filename author title': _T(
        'Save as Author - Title.md. Avoids title collisions in one folder.',
        '保存为「作者 - 书名.md」。减少同目录重名。',
    ),
    'Hint filename author folder': _T(
        'Save as Author/Title.md. Groups books by author.',
        '保存为「作者/书名.md」。按作者分子目录。',
    ),
    'Hint filename series title': _T(
        'Save as Series 01 - Title.md. Falls back to title when there is no series.',
        '保存为「系列 01 - 书名.md」。无系列时回退为书名。',
    ),
    'Strip PDF page markers': _T(
        'Strip PDF page markers from the Markdown body',
        '从正文去掉 PDF 页码标记',
    ),
    'Hint strip pdf pages': _T(
        'Remove standalone Page-12 / link to page 12 lines. Off by default to avoid deleting real text.',
        '删除独立的 Page-12 / link to page 12 行。默认关闭，以免误删正文。',
    ),
    'Use alt text for images': _T(
        'Use alt text for images (when image references are off)',
        '使用图片 alt 文本（在未保留图片引用时）',
    ),
    #: The conversion pane's "Images" group row; calibre's own .ui label for
    #: the same option ("Replace images by their alt attribute text") follows
    #: calibre's UI language, this one follows the plugin's.
    'Replace images by their alt attribute text': _T(
        'Replace images by their alt attribute text',
        '将图片替换为其 alt 属性文本',
    ),
    'Hint use alt': _T(
        'Insert alt text. Effective when image references are off.',
        '插入 alt 文本。关闭图片引用时生效。',
    ),
    'Line width:': _T('Line width:', '最大行宽：'),
    'Wrap mode default': _T('Default (no wrap) — recommended', '默认（不折行）— 推荐'),
    'Wrap mode 80': _T('80 characters', '80 字符'),
    'Wrap mode custom': _T('Custom', '自定义'),
    'Wrap custom label': _T('Characters per line:', '每行字符数：'),
    'Wrap hint default': _T(
        'Keep logical paragraph lines. Best for Obsidian, VS Code, Typora, GitHub.',
        '保持段落逻辑一行。最适配 Obsidian、VS Code、Typora、GitHub。',
    ),
    'Wrap hint 80': _T(
        'Wrap at 80 chars. Fit terminal and fixed-width reading.',
        '按 80 字符折行。适配终端与固定列宽阅读。',
    ),
    'Wrap hint custom': _T(
        'Wrap by custom width. Use when fixed output width is required.',
        '按自定义宽度折行。用于固定宽度输出场景。',
    ),
    'Force max line length': _T('Force max line length', '强制按最大行宽折行'),
    'Hint force wrap': _T(
        'Force line break at limit. May split words.',
        '强制在上限处断行。可能拆分单词。',
    ),
    'Newline type:': _T('Newline type:', '换行类型：'),
    'Newline Unix': _T('Unix', 'Unix'),
    'Newline Windows': _T('Windows', 'Windows'),
    'Newline Mac old': _T('Mac(old)', 'Mac(旧设备)'),
    'Hint newline unix': _T(
        'Use LF (\\n): each new line uses one line-feed character. This is the most common option in Markdown tools.',
        '每次换行只用一个换行符（\\n）。这是最常见、兼容性最好的选择。',
    ),
    'Hint newline windows': _T(
        'Use CRLF (\\r\\n): each new line uses carriage-return plus line-feed. Best for many native Windows text tools.',
        '每次换行使用“回车+换行”（\\r\\n）两个字符。更适合很多 Windows 原生文本工具。',
    ),
    'Hint newline mac old': _T(
        'Use CR only (\\r). Target Classic Mac devices.',
        '使用仅 CR（\\r）。目标 Classic Mac 旧设备。',
    ),
    'About': _T('About', '关于'),
    'OK': _T('OK', '确定'),
    'Start processing': _T('Start processing', '开始处理'),
    'Cancel': _T('Cancel', '取消'),
    'Cancel save': _T('Cancel save', '取消保存'),
    'Save As': _T('Save As', '另存为'),
    'Pick processed Markdown file': _T(
        'Pick processed Markdown file',
        '选择已处理的 Markdown 文件',
    ),
    'Saved as': _T('Saved as: {}', '已另存为：{}'),
    'Save failed': _T('Save failed: {}', '另存失败：{}'),
    'Export selected books to Markdown (.md)': _T(
        'Export selected books to Markdown (.md)',
        '将所选书籍导出为 Markdown（.md）',
    ),
    'Select folder to save Markdown files': _T(
        'Select folder to save Markdown files',
        '选择保存 Markdown 文件的文件夹',
    ),
    'No library open': _T('No library open', '未打开书库'),
    'Open a calibre library first.': _T(
        'Open a calibre library first.',
        '请先打开 calibre 书库。',
    ),
    'No books selected': _T('No books selected', '未选中书籍'),
    'Select books then export': _T(
        'Select one or more books in the library, then run Markdown export.',
        '请在书库中选中一本或多本书，然后运行 Markdown 导出。',
    ),
    'Cannot export': _T('Cannot export', '无法导出'),
    'No convertible format': _T(
        'None of the selected books have a convertible format.',
        '所选书籍均没有可转换的格式。',
    ),
    'Exported count': _T('Exported {} book(s) to:', '已导出 {} 本书至：'),
    'And more count': _T('… and {} more', '… 另有 {} 本'),
    'Skipped no format': _T('Skipped (no format):', '已跳过（无可用格式）：'),
    'Empty output': _T('Empty output:', '输出为空：'),
    'Failed': _T('Failed:', '失败：'),
    'Export finished with errors': _T(
        'Export finished with errors',
        '导出完成，但有错误',
    ),
    'No files written': _T('No files written', '未写入任何文件'),
    'Nothing was exported.': _T('Nothing was exported.', '未导出任何内容。'),
    'Export complete': _T('Export complete', '导出完成'),
    'Export progress': _T('Export progress', '导出进度'),
    'Processing…': _T('Processing…', '正在处理…'),
    'Processing complete': _T('Processing complete', '处理完成'),
    'Processing book ({}/{}): {}': _T(
        'Processing book ({}/{}): {}',
        '正在处理书籍（{}/{}）：{}',
    ),
    'Log pdf links summary': _T(
        'PDF: summarized {} internal links',
        'PDF：已汇总 {} 条内链',
    ),
    'Log pdf pages summary': _T(
        'PDF: summarized {} page markers',
        'PDF：已汇总 {} 个页码标记',
    ),
    'Log chapters summary': _T(
        'Detected {} chapters (summarized)',
        '已识别 {} 个章节（汇总）',
    ),
    'Log summary begin': _T('---- Log summary ----', '---- 日志汇总 ----'),
    'Log summary end': _T('---- End summary ----', '---- 汇总结束 ----'),
    'Log process start': _T('Start processing {} book(s).', '开始处理，共 {} 本书。'),
    'Log temp cache dir': _T('Temporary cache folder: {}', '临时缓存目录：{}'),
    'Log output dir': _T('Output folder: {}', '输出目录：{}'),
    'Log skipped formats': _T('Skipped (no convertible format): {}', '已跳过（无可转换格式）：{}'),
    'Log processing book': _T(
        'Processing ({}/{}): {} [{}]',
        '正在处理（{}/{}）：{} [{}]',
    ),
    'Log book begin': _T('---- Book log ----', '---- 单书日志 ----'),
    'Log book end': _T('---- End book log ----', '---- 单书日志结束 ----'),
    'Log source format': _T('Source format: {}', '源格式：{}'),
    'Log output file': _T('Output file: {}', '输出文件：{}'),
    'Log file size': _T('File size: {}', '文件大小：{}'),
    'Log images exported': _T('Images: {} file(s) → {}', '图片：{} 个文件 → {}'),
    'Log saved count': _T('Saved {} file(s) to: {}', '已保存 {} 个文件到：{}'),
    'Log empty file': _T('Empty output file: {}', '输出为空：{}'),
    'Log failed book': _T('Failed: {}', '失败：{}'),
    'Log conv input plugin': _T('Input plugin: {}', '输入插件：{}'),
    'Log conv source file': _T('Source file: {}', '源文件：{}'),
    'Log conv found cover': _T('Found HTML cover: {}', '检测到 HTML 封面：{}'),
    'Log conv parsing': _T('Parsing content...', '正在解析内容…'),
    'Log conv merging metadata': _T('Merging metadata...', '正在合并元数据…'),
    'Log conv detecting structure': _T('Detecting structure...', '正在检测结构…'),
    'Log conv removing margins': _T('Removing fake margins...', '正在移除伪边距…'),
    'Log conv flatten css': _T('Flattening CSS...', '正在扁平化 CSS…'),
    'Log conv cleaning manifest': _T('Cleaning manifest...', '正在清理清单…'),
    'Log conv trimming files': _T('Trimming unused files...', '正在裁剪未使用文件…'),
    'Log conv creating markdown': _T('Creating Markdown...', '正在生成 Markdown…'),
    'Log conv images exported': _T(
        'Exported image files next to Markdown.',
        '已将图片文件导出到 Markdown 旁。',
    ),
    'Log conv xhtml enhanced': _T(
        'Converting XHTML to enhanced Markdown...',
        '正在将 XHTML 转为增强 Markdown…',
    ),
    'Log conv xhtml markdown': _T(
        'Converting XHTML to Markdown...',
        '正在将 XHTML 转为 Markdown…',
    ),
    'Log conv txt output': _T('TXT output written.', 'TXT 输出已写入。'),
    'Log conv txt output path': _T('TXT output written to: {}', 'TXT 输出已写入：{}'),
    'Log conv md output': _T('MD output written.', 'MD 输出已写入。'),
    'Log conv md output path': _T('MD output written to: {}', 'MD 输出已写入：{}'),
    'Log language note zh': _T(
        '中文日志说明：中文为主，保留必要英文术语。',
        '中文日志说明：中文为主，保留必要英文术语。',
    ),
    'Log language note en': _T(
        'English log note: English-first wording with key technical terms.',
        '日志语言说明（英文）：以英文表述为主，保留关键技术术语。',
    ),
    'Newline System': _T('System', '跟随系统'),
    'Note preserve images': _T(
        'To preserve images, enable "Keep images". Otherwise, "Replace images '
        'by their alt attribute text" writes the alt text instead.',
        '要保留图片，请启用「保留图片」；否则「将图片替换为其 alt 属性文本」'
        '会写入 alt 文本代替图片。',
    ),
    'Customization hint': _T(
        'Tip: these settings apply to the book being converted. Global '
        'defaults and more options live under Preferences → Plugins → '
        '{plugin} → Customize plugin.',
        '提示：这里的设置只对当前转换的书籍生效。全局默认值与更多选项见'
        '「首选项 → 插件 → {plugin} → 自定义插件」。',
    ),
    'Log stats begin': _T('---- Markdown stats ----', '---- Markdown 统计 ----'),
    'Log stats end': _T('---- End Markdown stats ----', '---- 统计结束 ----'),
    'Log stats total begin': _T(
        '---- Markdown stats (total) ----',
        '---- Markdown 统计（总计） ----',
    ),
    'Log stats total end': _T(
        '---- End total stats ----',
        '---- 总计统计结束 ----',
    ),
    'Stats heading': _T('Headings: {}', '标题：{} 次'),
    'Stats bold': _T('Bold (**): {}', '加粗（**）：{} 次'),
    'Stats italic': _T('Italic (*): {}', '斜体（*）：{} 次'),
    'Stats link': _T('Links ([]()): {}', '链接（[]()）：{} 次'),
    'Stats image': _T('Images (![]()): {}', '图片（![]()）：{} 次'),
    'Stats code block': _T('Code blocks (```): {}', '代码块（```）：{} 次'),
    'Stats inline code': _T('Inline code (`): {}', '行内代码（`）：{} 次'),
    'Stats table row': _T('Table rows (|): {}', '表格行（|）：{} 次'),
    'Stats blockquote': _T('Blockquotes (>): {}', '引用（>）：{} 次'),
    'Stats list item': _T('List items (-/1.): {}', '列表项（-/1.）：{} 次'),
    'Stats strikethrough': _T('Strikethrough (~~): {}', '删除线（~~）：{} 次'),
    'Stats task list': _T('Task lists (- [ ] / - [x]): {}', '任务列表（- [ ] / - [x]）：{} 次'),
    'Stats footnote': _T('Footnotes ([^id]): {}', '脚注（[^id]）：{} 次'),
    'Stats wikilink': _T('Wiki links ([[page]]): {}', 'Wiki 链接（[[页面]]）：{} 次'),
    'Stats definition': _T('Definition lists (: ): {}', '定义列表（: ）：{} 次'),
    'Stats highlight': _T('Highlights (==): {}', '高亮（==）：{} 次'),
    'Stats none': _T('No notable markdown patterns counted.', '未统计到非零 Markdown 项。'),
}


def _(message):
    entry = _MESSAGES.get(message)
    if entry is None:
        return message
    return entry.get(get_ui_language(), message)


# Wording used by the plugin customization dialog (added when the plugin was
# relocated to a conversion output plugin).
_MESSAGES.update({
    'Customization intro': _T(
        'Set global defaults for Markdown output. Options you enable here '
        'override the conversion dialog for every conversion.',
        '为 Markdown 输出设置全局默认值。在此处启用的选项将覆盖转换对话框中的设置，'
        '并应用于所有转换。'),
    'Override globally': _T(
        'Override globally', '全局覆盖'),
    'Image output mode:': _T(
        'Image output mode:', '图片输出方式：'),
    'Images next to the Markdown file': _T(
        'Images next to the Markdown file', '图片放在 Markdown 文件旁边'),
    'Images embedded as data URIs': _T(
        'Images embedded as data URIs', '图片以 data URI 内嵌'),
    'Do not export images': _T(
        'Do not export images', '不导出图片'),
    'Max line length:': _T(
        'Max line length:', '最大行宽：'),
    'Output encoding:': _T(
        'Output encoding:', '输出编码：'),
    'Force max line length': _T(
        'Force max line length', '强制按最大行宽断行'),
    'Newline:': _T('Newline:', '换行类型：'),
    'Paragraph style:': _T('Paragraph style:', '段落样式：'),
    'Paragraph style block': _T(
        'Block (blank lines separate paragraphs)',
        '段落块（空白行分段）'),
    'Paragraph style single': _T(
        'Single (every line is a paragraph)',
        '单行段落（每行一段）'),
    'Blank line before headings': _T(
        'Blank line before headings',
        '标题前空行'),
    'Add heading anchors': _T(
        'Add heading anchors',
        '为标题添加锚点'),
    'Escape Markdown special characters': _T(
        'Escape Markdown special characters',
        '转义 Markdown 特殊字符'),
    'Markdown: could not locate the book folder in the calibre library, images were not exported': _T(
        'Markdown: could not locate the book folder in the calibre library, '
        'images were not exported',
        'Markdown：未能在 calibre 书库中定位该书目录，未导出图片。'),
    'Markdown: {} image reference(s) could not be found next to the input '
    'file or in the calibre library, the output will not include them: {}': _T(
        'Markdown: {} image reference(s) could not be found next to the '
        'input file or in the calibre library, the output will not include '
        'them: {}',
        'Markdown：有 {} 个图片引用在输入文件旁与 calibre 书库中均未找到，'
        '输出将不包含这些图片：{}'),
})


# ---------------------------------------------------------------------------
# Conversion-option help ("hint") texts.
#
# The key is the English help string declared on the OptionRecommendation in
# markdown_output.py (gettext-style msgid). ui.py routes calibre's help
# provider through _() so the tooltips shown in the conversion dialog follow
# the plugin's UI language. Keep the English key in sync with the source text.
# ---------------------------------------------------------------------------
def _register_option_help(pairs):
    for _en, _zh in pairs:
        _MESSAGES[_en] = _T(_en, _zh)


_register_option_help((
    (
        "Type of newline to use. Options are ['old_mac', 'system', 'unix', "
        "'windows']. Default is 'system'. Use 'old_mac' for compatibility "
        "with Mac OS 9 and earlier. For macOS use 'unix'. 'system' will "
        "default to the newline type used by this OS.",
        "换行符类型。可选值：['old_mac', 'system', 'unix', 'windows']。"
        "默认 'system'。'old_mac' 用于兼容 Mac OS 9 及更早系统；"
        "macOS 请使用 'unix'；'system' 使用当前操作系统的换行符。",
    ),
    (
        "Specify the character encoding of the output document. The default is utf-8.",
        "指定输出文档的字符编码，默认 utf-8。",
    ),
    (
        "Add Table of Contents to beginning of the book.",
        "在全书开头插入目录。",
    ),
    (
        "The maximum number of characters per line. This splits on the first "
        "space before the specified value. If no space is found the line will "
        "be broken at the space after and will exceed the specified value. "
        "Also, there is a minimum of 25 characters. Use 0 to disable line splitting.",
        "每行最大字符数。在指定长度之前第一个空格处断行；若找不到空格，则在其后的"
        "空格处断行，实际长度会超过设定值。另有 25 字符下限。设为 0 表示不折行。",
    ),
    (
        "Force splitting on the max-line-length value when no space is present. "
        "Also allows max-line-length to be below the minimum",
        "没有空格时也在最大行宽处强制断行，并允许最大行宽低于下限。",
    ),
    (
        "Do not remove links within the document. ",
        "保留文档中的链接。",
    ),
    (
        "Do not remove image references within the document. ",
        "保留文档中的图片引用。",
    ),
    (
        "Write the width/height an image declares (width/height attributes or "
        "CSS) into the Markdown as <img src=... width=... height=...> raw HTML. "
        "Uncheck to export plain ![](path) references and drop the sizes.",
        "把图片声明的宽高（width/height 属性或 CSS）以原始 HTML 形式写入 "
        "Markdown：<img src=... width=... height=...>。取消勾选则一律导出普通的 "
        "![](路径) 引用、不输出尺寸。",
    ),
    (
        "Keep the width/height the Markdown declares on its images (width/height "
        "attributes or inline styles). Uncheck to drop those sizes, so the images "
        "enter the book at their natural size instead.",
        "保留 Markdown 中图片声明的宽高（width/height 属性或行内样式）。取消勾选则"
        "丢弃这些尺寸，图片按原始尺寸进入书籍。",
    ),
    (
        "Process titlepage.xhtml files and the cover image reference from the "
        "input book. Uncheck to skip cover/title page content in the Markdown output.",
        "处理输入书籍的 titlepage.xhtml 与封面图片引用。取消勾选可在 Markdown "
        "输出中跳过封面/扉页内容。",
    ),
    (
        "Replace images with the text from the alt attribute, if any. Ignored "
        "if the option to keep image references is specified.",
        "用图片的 alt 属性文本替换图片（若有）。若已启用「保留图片引用」则忽略此项。",
    ),
    (
        "Copy referenced image files next to the Markdown file into a sibling "
        ".images folder.",
        "把引用的图片文件复制到 Markdown 文件旁的 .images 目录。",
    ),
    (
        "Download remote images (http/https URLs the book references) when "
        "exporting image files, and store them with the local ones. Failed "
        "downloads are skipped: the reference stays a URL and a warning is "
        "written to the conversion report.",
        "导出图片文件时一并下载书中引用的远程图片（http/https 链接），"
        "与本地图片存放在一起。下载失败的图片将被跳过：引用保持为 URL，"
        "并在转换报告中给出警告。",
    ),
    (
        "Keep the images the Markdown references. Uncheck to remove every "
        "image (and its alt text) from the converted book.",
        "保留 Markdown 引用的图片。取消勾选将从转换后的书中移除所有图片"
        "（连同其替代文字）。",
    ),
    (
        "Embed local images into the converted book: files in any folder "
        "next to the input (images/, assets/, ...) or in the calibre book "
        "folder, including references whose file names are written with URL "
        "escapes. Uncheck to leave image references as they are.",
        "将本地图片内嵌进转换后的书：输入文件旁任意子目录（images/、assets/ 等）"
        "或 calibre 书籍目录中的文件都算，引用里文件名写成 URL 编码的同样识别。"
        "取消勾选则图片引用保持原样。",
    ),
    (
        'Download remote images (http/https URLs) and embed them into the '
        'book like local ones. Requires "Keep images" and "Embed images"; '
        'failed downloads are skipped and reported in the conversion '
        'report.',
        "下载远程图片（http/https 链接）并像本地图片一样内嵌进书籍。"
        "需先开启「保留图片」与「内嵌图片」；下载失败的图片将被跳过并在"
        "转换报告中给出警告。",
    ),
    (
        "Where images are written. 'sidecar' puts them next to the Markdown "
        "file (into the book folder of the calibre library for library "
        "conversions), 'inline' embeds them as base64 data URIs and 'none' "
        "exports no images.",
        "图片写入位置。'sidecar'：放在 Markdown 文件旁（书库转换时写入 calibre 书库"
        "中的书籍目录）；'inline'：以 base64 data URI 内嵌；'none'：不导出图片。",
    ),
    (
        "How paragraphs are separated. 'block' keeps the standard Markdown "
        "layout where a blank line separates paragraphs. 'single' removes "
        "blank lines (code blocks are preserved) so every line is its own paragraph.",
        "段落分隔方式。'block' 为标准 Markdown 版式，用空行分段；'single' 去掉空行"
        "（代码块保留），每行自成一段。",
    ),
    (
        "Insert a blank line before # headings when the paragraph style is "
        "'single'. Headings at the very start of the file are not preceded by a "
        "blank line. No effect with the 'block' style.",
        "段落样式为 'single' 时，在 # 标题前插入空行。文件最开头的标题前不加空行。"
        "'block' 样式下无效。",
    ),
    (
        "Append a {#slug} anchor to each heading so the table of contents links "
        "resolve. Uncheck to export plain headings.",
        "为每个标题追加 {#slug} 锚点，使目录链接可跳转。取消勾选则导出无锚点的普通标题。",
    ),
    (
        "Escape the Markdown special characters \\ ` * _ { } [ ] ( ) # + ! in "
        "the body text. Uncheck to write the source text as it is, so a title "
        "like 第1卷 原版(By:苏梦枕) stays literal; re-rendering the file as "
        "Markdown may then read those characters as formatting. Table cells "
        "and YAML front matter keep their escaping either way.",
        "转义正文中的 Markdown 特殊字符 \\ ` * _ { } [ ] ( ) # + !。取消勾选则"
        "原样输出，如「第1卷 原版(By:苏梦枕)」按字面显示；但文件重新作为 Markdown "
        "渲染时这些字符可能被解析成格式标记。表格单元格与 YAML 文首元数据始终"
        "保持转义。",
    ),
    (
        "Write YAML front matter from book metadata.",
        "根据书籍元数据写入 YAML 文首元数据。",
    ),
    (
        "Remove standalone PDF page-marker lines such as Page-12 from the "
        "Markdown body.",
        "从正文中删除独立的 PDF 页码标记行（如 Page-12）。",
    ),
))


# ---------------------------------------------------------------------------
# "Markdown input" conversion pane (shipped with the .md input plugin).
# ---------------------------------------------------------------------------
_MESSAGES.update({
    'Markdown input': _T('Markdown input', 'Markdown 输入'),
    'Options specific to Markdown input': _T(
        'Options specific to Markdown input',
        'Markdown 输入专属选项'),
    'Input customization intro': _T(
        'Set global defaults for Markdown input. Options you enable here '
        'override the conversion dialog for every Markdown conversion.',
        '为 Markdown 输入设置全局默认值。在此处启用的选项将覆盖转换对话框中的设置，'
        '并应用于所有 Markdown 转换。'),
    'Markdown extensions:': _T('Markdown extensions:', 'Markdown 扩展：'),
    'General': _T('General', '常规'),
    'Extensions': _T('Extensions', '扩展'),
    'Input character encoding:': _T(
        'Input character encoding:', '输入字符编码：'),
    'Single line breaks:': _T('Single line breaks:', '单换行处理：'),
    'Input paragraph style:': _T('Input paragraph style:', '段落样式：'),
    'Read YAML front matter metadata': _T(
        'Read YAML front matter metadata', '读取 YAML 文首元数据'),
    'Fold single line breaks': _T(
        'Fold single line breaks', '折叠为空格'),
    'Hard line breaks (<br>)': _T(
        'Hard line breaks (<br>)', '硬换行（<br>）'),
    'Paragraph style auto': _T(
        'Auto (detect paragraph type)', '自动检测段落类型'),
    'Paragraph style block': _T(
        'Block (blank line breaks paragraphs)', '块（空白行分段）'),
    'Paragraph style single': _T(
        'Single (every line is a paragraph)', '单行（每行一段）'),
    'Paragraph style print': _T(
        'Print (indent starts a paragraph)', '打印（缩进开始新段）'),
    'Extension abbr': _T('Abbreviations', '简称'),
    'Extension admonition': _T('Support admonitions', '支持警告块'),
    'Extension attr_list': _T(
        'Add attributes to HTML tags', '给 HTML 标签增加属性'),
    'Extension codehilite': _T(
        'Code highlighting via Pygments', '通过 Pygments 添加代码高亮'),
    'Extension def_list': _T('Definition lists', '定义列表'),
    'Extension extra': _T(
        'Enable various common extensions', '启用各种常用扩展'),
    'Extension fenced_code': _T(
        'Alternative code block syntax', '围栏代码块（```）'),
    'Extension footnotes': _T('Footnotes', '脚注'),
    'Extension legacy_attrs': _T(
        'Use legacy element attributes', '使用旧的元素属性'),
    'Extension legacy_em': _T(
        'Legacy underscore handling for connected words',
        '对关联词使用旧版下划线处理'),
    'Extension sane_lists': _T(
        'Do not allow mixing list types', '不允许混合的列表类型'),
    'Extension smarty': _T(
        "Markdown's internal smartypants parser",
        '使用 Markdown 内部智能标点解析器'),
    'Extension tables': _T('Support tables', '支持表格'),
    'Extension toc': _T('Generate a table of contents', '生成目录'),
    'Extension wikilinks': _T('Wiki style links', 'Wiki 样式链接'),
})

_register_option_help((
    (
        'How a single line break inside a paragraph is rendered. "fold" joins '
        'the lines (standard Markdown); "hard" turns every line break into a '
        '<br> (the nl2br extension).',
        '段落内单个换行的处理方式。"fold"：并入同一段（标准 Markdown）；'
        '"hard"：每个换行都成为 <br>（即 nl2br 扩展）。',
    ),
    (
        'Read the YAML block at the very start of the document as book '
        'metadata (title, authors, language, tags, description). When off the '
        'block is removed from the text instead.',
        '把文档最开头的 YAML 块读取为书籍元数据（title/authors/language/'
        'tags/description）。关闭时该块会从正文中移除。',
    ),
    (
        'Paragraph structure to assume. "auto" detects it from the text: a file '
        'with one paragraph per line gets the blank lines Markdown needs, an '
        'ordinary Markdown file is left alone. An explicit choice is applied as '
        'it is. Reshaping never splits code blocks, lists or tables apart, and '
        'a quote block stays one quote: its lines become the paragraphs inside '
        'it, and a blank line separates the quote from what follows.',
        '推断段落结构。"auto" 会从文本自动识别：每行一段的文件会补上 Markdown '
        '所需的空行，普通 Markdown 文件保持原样。显式选择按所选方式生效。'
        '重排不会拆散代码块、列表与表格；引用块保持为一个引用，其内部每行'
        '各自成段，引用块与后文之间保留一个空行。',
    ),
    (
        'Enable extensions to Markdown syntax. Extensions are formatting that '
        'is not part of the standard Markdown format.',
        '启用 Markdown 语法扩展。扩展是标准 Markdown 之外的各种格式支持。',
    ),
))
