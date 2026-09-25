# 输出渲染器拆分 实施计划

**Goal:** 把 `EnhancedMarkdownMLizer` 的 60 个方法按渲染域搬进 `output/renderers/` 的 10 个模块，
主文件只剩类状态、生命周期与 `dump_text` 分派，行为逐字节不变。

**Architecture:** 方法按域切成 9 个 mixin（纯方法容器，不写 `super()`、不持有新状态），
`EnhancedMarkdownMLizer` 多继承它们 + calibre `MarkdownMLizer`；共享常量与纯函数放
`renderers/primitives.py`，`renderers/*.py` 之间除 primitives 外互不 import，跨域调用一律走 `self.`。

**Tech Stack:** Python 3（calibre 绑定解释器 / venv 均为 3.14）、pytest、calibre-debug（真机脚本）。

**Spec:** `docs/specs/2026-09-26-output-renderer-split.md`

## 实施结果（2026-09-26，完成）

计划按 Task 1-5 执行完毕，实测证据见 spec §5。与计划的差异：

- 主文件 **303 行**（计划估 ~380），最大模块 `lists.py` 233 行；13 个 renderer 文件合计 12 个（含 `__init__.py`）。
- 结构守卫测试写成 **5 个断言**（计划里只列了 3 个），测试总数 484 → **489 passed**。
- mixin 内 import 用**绝对路径**（计划里写的是 `..utils.helpers`；从 `renderers` 出发 `..` 解析到 `output`，
  要写 `...utils` 才对——绝对路径与仓库既有风格一致，也更不易错）。
- 额外修了 2 处"方法搬走了、导入没跟上"的遗漏，都**不在**计划的清单里：
  `markdownml_enhanced.py` 的 `margin_repair_summary`（测试没覆盖，真机脚本才会崩）、
  `scripts/verify_no_broken_css_margin.py` 的 `_is_readable_length`。
- 验收方式从"只跑现有测试"升级为**双树对照**（HEAD 克隆 vs 工作区，同一脚本各跑一遍比对 PASS/FAIL）：
  13 个脚本输出完全一致，失败项全部在 HEAD 上复现（既有现象）。

## Global Constraints

- 唯一入口 `calibre_plugins.markdown.output.markdownml_enhanced.EnhancedMarkdownMLizer` 的
  导入路径与类名不变。
- **方法体逐字照搬**：不重排语句、不改注释/docstring/字符串、不改方法名与顺序无关的细节；
  迁移=整块剪切-粘贴。
- 不新增状态对象；不把 mixin 改成组合；mixin 内不写 `super()`。
- 版本 3.20.7 → 3.20.8，四处同步（`__init__.py` 的 `PLUGIN_VERSION_TUPLE`/`PLUGIN_VERSION`、
  `input/input_plugin.py:370`、`output/output_plugin.py:33`、`tests/test_plugin_entry.py` 的断言与注释）。
- 测试命令固定为：`cd /Users/lachang/Project/calibreMarkdown && .venv/bin/python -m pytest plugin/tests -q`。
- 真机脚本命令固定为：`cd /Users/lachang/Project/calibreMarkdown && /Applications/calibre.app/Contents/MacOS/calibre-debug -e scripts/<name>.py`。
- **本仓库规则：未经用户明确要求不执行 `git commit`**；计划中的阶段边界只是复查点，不提交。
- `scripts/` 与 `.venv` 均被 gitignore；脚本不删除、改完要真跑。

## 方法 → 模块映射（权威表，见 spec §3.1）

| 模块 | 方法数 | 方法 |
|---|---|---|
| `output/markdownml_enhanced.py` | 7 | `extract_content` `map_resources` `_map_remaining_images` `mlize_spine` `apply_max_line_length` `_repair_margins` `dump_text`；类属性 `_in_heading` `_item_line`；常量 `USE_FENCED_CODE_BLOCKS` |
| `renderers/primitives.py` | 0（纯函数） | 常量 `BLOCK_LEVEL_TAGS` `ITEM_LINE_BLOCKS` `ITEM_LINE_OPEN` `ITEM_LINE_STARTED` `ITEM_TEXT_WRAPPERS` `HEADING_INLINE_TAGS` `_CSS_LENGTH_RE` `_MARGIN_KEYWORDS` `MARGIN_LENGTH_KEYS`；函数 `_ends_with_blank_line` `_has_visible_text` `_drop_leading_blank_fragments` `_css_margin_break` `_is_readable_length` `repair_margin_lengths` `margin_repair_summary` |
| `renderers/text.py` | 14 | `_escaping_enabled` `prepare_string_for_markdown` `_plain_heading_text` `prepare_string_for_table_cell` `_format_fragment` `_tail_fragment` `_contains_token` `_should_keep_link` `_looks_like_external_href` `_looks_like_internal_href` `_sanitize_wikilink_target` `_wikilink_target_from_href` `_collect_element_text_parts` `_dump_inline_block`；常量 `MARKDOWN_ESCAPE_RE` `MARKDOWN_UNESCAPE_RE` |
| `renderers/footnotes.py` | 10 | `_looks_like_footnote_id` `_extract_footnote_target` `_is_footnote_reference` `_is_footnote_backlink` `_next_available_footnote_label` `_footnote_label_for_target` `_collect_footnote_definition` `_is_footnote_definition` `_capture_footnote_definition` `_render_footnotes` |
| `renderers/tables.py` | 3 | `_cell_alignment` `_render_table` `_dump_definition_list` |
| `renderers/blocks.py` | 3 | `_starts_with_block` `_dump_blockquote` `_dump_figure` |
| `renderers/headings.py` | 3 | `_heading_level` `_dump_heading_inline` `_dump_heading` |
| `renderers/inline.py` | 4 | `_wrap_delimiters` `_wrap_html_tag` `_code_language_from` `_dump_fenced_pre` |
| `renderers/lists.py` | 7 | `_extract_task_checkbox` `_dump_list_item` `_dump_item_block` `_dump_item_paragraph` `_item_indent` `_open_emphasis` `_close_emphasis` |
| `renderers/media.py` | 3 | `_dump_link` `_html_image` `_markdown_image` |
| `renderers/document.py` | 6 | `create_toc_entries` `_toc_heading` `get_toc` `get_front_matter` `_find_cover_href` `_cover_markdown` |

合计 60，与拆分前类内方法一一对应（已核 `grep -n "^    def "` 60 条、无重名）。

---

### Task 1: 建 `renderers/` 包并迁出全部 9 个 mixin + primitives

**Files:**
- Create: `plugin/Markdown/output/renderers/__init__.py`（只放 docstring，不 import 任何东西）
- Create: `renderers/primitives.py`、`text.py`、`footnotes.py`、`tables.py`、`blocks.py`、`headings.py`、`inline.py`、`lists.py`、`media.py`、`document.py`
- Read（唯一事实源，按行区间整块剪切）: `plugin/Markdown/output/markdownml_enhanced.py`（1446 行，行号见 spec §3.1 与下表）

**Interfaces:**
- Produces: 9 个 mixin 类 `ListsMixin` `DocumentMixin` `MediaMixin` `TablesMixin` `BlocksMixin` `HeadingsMixin` `InlineMixin` `FootnotesMixin` `TextMixin`（`renderers/<stem>.py`）；`primitives` 的常量与函数（名字不变）。
- 依赖规则：每个 mixin 模块只 import `renderers.primitives`、`utils.helpers`、calibre、标准库。

- [ ] **Step 1: 建包壳**

```bash
mkdir -p plugin/Markdown/output/renderers
```

`renderers/__init__.py` 内容（空壳，禁 import）：

```python
# -*- coding: utf-8 -*-
"""XHTML -> Markdown renderer mixins, one module per rendering domain.

The class itself lives in ..markdownml_enhanced; each module here holds the
methods of one domain and is mixed into it. Cross-domain calls go through
self., so the modules never import each other - only .primitives (shared
constants and free functions) and ..utils.helpers.
"""
```

- [ ] **Step 2: 逐模块剪切-粘贴**

对每个模块：按「方法 → 模块映射」把对应方法**整块**（含其上方注释）从 `markdownml_enhanced.py`
剪到新文件；不重排、不改写。行区间（拆分前）：

| 模块 | 源行区间（含每个方法上方的注释块） |
|---|---|
| `primitives.py` | 48-85（常量）+ 88-186（函数） |
| `text.py` | 40-41（两个正则）、422-513、579-585、1259-1269 |
| `footnotes.py` | 515-577、587-654 |
| `tables.py` | 656-703、769-795 |
| `blocks.py` | 797-810、812-898、900-931 |
| `headings.py` | 933-1004 |
| `inline.py` | 705-767 |
| `lists.py` | 1048-1164、1166-1229、1231-1257 |
| `media.py` | 1006-1046、1271-1329 |
| `document.py` | 305-391 |

- [ ] **Step 3: 每个新模块补文件头（docstring + 精确 import）**

按各方法实际用到的名字收敛 import，不多不少：

- `primitives.py`：`import numbers`、`import re`；无 calibre、无 helpers。
- `text.py`：`import os`、`import re`、`from urllib.parse import unquote`；无 calibre。
- `footnotes.py`：`import re`；`from calibre.ebooks.oeb.base import barename`。
- `tables.py`：`from calibre_plugins.markdown.utils.helpers import alignment_separator, cell_alignment, find_table_caption, iter_definition_items, iter_table_rows, local_name`。
- `blocks.py`：`from calibre.ebooks.oeb.base import barename`；`from ..utils.helpers import local_name`；`from .primitives import BLOCK_LEVEL_TAGS, _css_margin_break, _ends_with_blank_line`。
- `headings.py`：`from calibre.ebooks.oeb.base import barename`；`from ..utils.helpers import unique_slug`；`from .primitives import BLOCK_LEVEL_TAGS`。
- `inline.py`：`from calibre.ebooks.oeb.base import barename`；`from ..utils.helpers import extract_code_language`。
- `lists.py`：`from calibre.ebooks.oeb.base import barename`；`from .primitives import BLOCK_LEVEL_TAGS, ITEM_LINE_OPEN, ITEM_LINE_STARTED, ITEM_TEXT_WRAPPERS, _drop_leading_blank_fragments, _has_visible_text`。
- `media.py`：`from ..utils.helpers import html_image_tag, image_size_attrs`。
- `document.py`：`from ..utils.helpers import (DEFAULT_IMAGE_DIR, metadata_text_values, render_toc_block, render_yaml_front_matter, yaml_fields_from_metadata)`（`_find_cover_href`/`_cover_markdown` 不直接 import 标题页判断；`is_titlepage_href` 只在主文件的 `mlize_spine` 用）。

每个模块的类骨架：

```python
class TextMixin(object):
    """<域的职责说明，2-4 行>"""
```

（类名见 spec §3.2；`object` 显式写出，避免 mixin 之间的 MRO 歧义。）

- [ ] **Step 4: 语法与结构自检**

```bash
cd /Users/lachang/Project/calibreMarkdown && .venv/bin/python - <<'PY'
import ast, pathlib
root = pathlib.Path('plugin/Markdown/output/renderers')
for path in sorted(root.glob('*.py')):
    tree = ast.parse(path.read_text())
    classes = [n.name for n in tree.body if isinstance(n, ast.ClassDef)]
    print(path.name, path.read_text().count('\n'), classes)
PY
```

Expected: 10 个文件，9 个模块各打印一个 `*Mixin` 类（`__init__.py` 打印空列表）。

---

### Task 2: 主文件收口（继承 mixin、删已迁代码、清 import）

**Files:**
- Modify: `plugin/Markdown/output/markdownml_enhanced.py`（目标 ~380 行）

**Interfaces:**
- Consumes: Task 1 的 9 个 mixin 与 primitives。

- [ ] **Step 1: 重写文件头与类声明**

文件头只留渲染器总述 docstring 与主文件所需 import：

```python
from calibre.ebooks.oeb.base import XHTML_NS, barename, namespace
from calibre.ebooks.txt.markdownml import MarkdownMLizer

from calibre_plugins.markdown.utils.helpers import (
    apply_paragraph_style, clean_invisible_chars, is_titlepage_href,
    strip_pdf_page_marker_lines,
)
from calibre_plugins.markdown.output.renderers.blocks import BlocksMixin
from calibre_plugins.markdown.output.renderers.document import DocumentMixin
from calibre_plugins.markdown.output.renderers.footnotes import FootnotesMixin
from calibre_plugins.markdown.output.renderers.headings import HeadingsMixin
from calibre_plugins.markdown.output.renderers.inline import InlineMixin
from calibre_plugins.markdown.output.renderers.lists import ListsMixin
from calibre_plugins.markdown.output.renderers.media import MediaMixin
from calibre_plugins.markdown.output.renderers.primitives import (
    BLOCK_LEVEL_TAGS, HEADING_INLINE_TAGS, ITEM_LINE_BLOCKS,
    ITEM_LINE_STARTED, repair_margin_lengths,
)
from calibre_plugins.markdown.output.renderers.tables import TablesMixin
from calibre_plugins.markdown.output.renderers.text import TextMixin

USE_FENCED_CODE_BLOCKS = True
```

```python
class EnhancedMarkdownMLizer(
        ListsMixin, DocumentMixin, MediaMixin, TablesMixin, BlocksMixin,
        HeadingsMixin, InlineMixin, FootnotesMixin, TextMixin,
        MarkdownMLizer):
    <保留 _in_heading / _item_line 两个类属性及其整段 docstring>
    <保留 7 个生命周期/分派方法：extract_content map_resources
     _map_remaining_images mlize_spine apply_max_line_length _repair_margins dump_text>
```

- [ ] **Step 2: 确认没有残留**

```bash
cd /Users/lachang/Project/calibreMarkdown && grep -n "^    def " plugin/Markdown/output/markdownml_enhanced.py
```

Expected: 恰好 7 行，名字与映射表一致。

- [ ] **Step 3: 跑测试**

```bash
cd /Users/lachang/Project/calibreMarkdown && .venv/bin/python -m pytest plugin/tests -q
```

Expected: **484 passed**（`test_list_items.py` 的 `__mro__[1]` 在 Task 3 才改；若此处因它失败，
先做 Task 3 的 Step 1 再回来）。

---

### Task 3: 测试改造与结构守卫

**Files:**
- Modify: `plugin/tests/test_broken_css_margins.py`（2 处 import）
- Modify: `plugin/tests/test_list_items.py:35`
- Create: `plugin/tests/test_renderer_layout.py`

- [ ] **Step 1: 修两处既有测试**

`test_list_items.py:35`：

```python
from calibre.ebooks.txt.markdownml import MarkdownMLizer as STUB_BASE
```

（conftest 已把 `calibre.ebooks.txt.markdownml.MarkdownMLizer` 桩成 `_StubMarkdownMLizer`，
这里显式取基类，不再依赖 `__mro__[1]` 的位置。）

`test_broken_css_margins.py` 的全部 `repair_margin_lengths` / `margin_repair_summary`
导入改为 `from calibre_plugins.markdown.output.renderers.primitives import ...`。

- [ ] **Step 2: 新增结构守卫测试**

```python
# -*- coding: utf-8 -*-
"""The renderer split: no mixin shadows another, and mixins stay independent.

The class is assembled from one mixin per rendering domain (see
docs/specs/2026-09-26-output-renderer-split.md). Both properties the split
relies on are easy to break by accident and invisible at runtime, so they are
checked here: a method defined by two mixins would be silently taken from the
earlier one, and a mixin importing another mixin would make the seed order
of the calibre-debug verify scripts wrong.
"""

import ast
import pathlib

from calibre.ebooks.txt.markdownml import MarkdownMLizer

from calibre_plugins.markdown.output.markdownml_enhanced import (
    EnhancedMarkdownMLizer,
)


def _mixin_classes():
    return [cls for cls in EnhancedMarkdownMLizer.__mro__
            if cls.__module__.startswith(
                'calibre_plugins.markdown.output.renderers.')]


def test_every_method_is_defined_by_one_mixin_only():
    seen = {}
    for cls in _mixin_classes():
        for name, value in vars(cls).items():
            if name.startswith('__') or not callable(value):
                continue
            assert name not in seen, \
                '%s defined by both %s and %s' % (name, seen[name], cls)
            seen[name] = cls


def test_the_super_chain_ends_at_calibre_markdownmlizer():
    assert EnhancedMarkdownMLizer.__mro__[-2] is MarkdownMLizer


def test_renderer_modules_only_import_primitives():
    import calibre_plugins.markdown.output.renderers as renderers

    root = pathlib.Path(renderers.__file__).parent
    for path in sorted(root.glob('*.py')):
        if path.name == '__init__.py':
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            module = node.module or ''
            if module.startswith('..utils') or '.' not in module:
                continue
            assert module.split('.')[-1] == 'primitives', \
                '%s imports %s' % (path.name, module)
```

- [ ] **Step 3: 跑测试**

```bash
cd /Users/lachang/Project/calibreMarkdown && .venv/bin/python -m pytest plugin/tests -q
```

Expected: **489 passed**。

---

### Task 4: 20 个 `scripts/*.py` 的 seed 样板

**Files:**
- Modify: `scripts/*.py`（20 个使用 `SEED_ORDER` 的脚本）

- [ ] **Step 1: 先改一个，跑通再推广**

`scripts/verify_blockquote.py`：

```python
SUBPACKAGES = ('translations', 'utils', 'output', 'output/renderers', 'input')
SEED_ORDER = (
    ('translations', 'ui_language'), ('translations', 'messages'),
    ('utils', 'helpers'), ('utils', 'prefs'), ('utils', 'override_model'),
    ('utils', 'library'), ('utils', 'plugin_icons'),
    ('output/renderers', 'primitives'),
    ('output/renderers', 'text'), ('output/renderers', 'footnotes'),
    ('output/renderers', 'tables'), ('output/renderers', 'blocks'),
    ('output/renderers', 'headings'), ('output/renderers', 'inline'),
    ('output/renderers', 'lists'), ('output/renderers', 'media'),
    ('output/renderers', 'document'),
    ('output', 'markdownml_enhanced'), ('output', 'output_plugin'),
    ('output', 'convert_flow'), ('output', 'conversion_ui'),
    ('output', 'preference_ui'), ('input', 'paragraphs'),
    ('input', 'input_plugin'), ('input', 'conversion_ui'),
)
```

`_seed_from_source()` 里两处名字拼接加 `.replace('/', '.')`：

```python
        full_name = 'calibre_plugins.markdown.' + subpackage.replace('/', '.')
...
        full_name = 'calibre_plugins.markdown.%s.%s' % (
            subpackage.replace('/', '.'), stem)
```

- [ ] **Step 2: 真跑该脚本**

```bash
cd /Users/lachang/Project/calibreMarkdown && /Applications/calibre.app/Contents/MacOS/calibre-debug -e scripts/verify_blockquote.py
```

Expected: 全部 PASS；若出现 `installed zip shadows the source tree` 或 ImportError，说明 seed 不完整，
先修到通过再推广。若隐式导入（只把 `'output/renderers'` 加进 SUBPACKAGES、不列 10 个模块）也能通过，
可以改用更短的形式，但必须先在此脚本上验证。

- [ ] **Step 3: 批量套用到其余 19 个**

对每个 `scripts/*.py` 套用完全相同的三处改动（`grep -l SEED_ORDER scripts/*.py` 列表），逐个跑
Task 5 的代表脚本集合里对应的那一个。

---

### Task 5: 版本、CHANGELOG、验收

**Files:**
- Modify: `plugin/Markdown/__init__.py:26-27`、`plugin/Markdown/input/input_plugin.py:370`、`plugin/Markdown/output/output_plugin.py:33`、`plugin/tests/test_plugin_entry.py`（断言 + 注释块新增一行 3.20.8）
- Modify: `CHANGELOG.md`

- [ ] **Step 1: 四处版本号 → 3.20.8**，并在 `test_plugin_entry.py` 的注释块顶部按既有格式加：

```python
    # 3.20.8: the output renderer is split into one mixin per rendering domain
    # (output/renderers/); the generated Markdown is unchanged.
```

- [ ] **Step 2: CHANGELOG「改进」条目**

```markdown
## 3.20.8 (2026-09-26)
### 改进
- 输出渲染器按渲染域拆分为 `output/renderers/` 子包（列表、块级、标题、脚注、表格、链接与图片、
  目录与文首、行内标记、文本转义九个 mixin + 共享纯函数），`markdownml_enhanced.py` 从 1446 行
  降到约 380 行，只保留类状态、生命周期与 `dump_text` 分派。生成的 Markdown 与旧版逐字节一致。
```

- [ ] **Step 3: AST 源码等价证明（临时脚本，跑完即删）**

```python
# /tmp/equiv_check.py: HEAD 版与工作区版各抽「方法源码」逐字比对
import ast, pathlib, subprocess

def methods(source, path):
    tree = ast.parse(source)
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out['%s.%s' % (node.name, item.name)] = ast.get_source_segment(source, item)
    return out

old_src = subprocess.run(['git', 'show', 'HEAD:plugin/Markdown/output/markdownml_enhanced.py'],
                         capture_output=True, text=True, check=True).stdout
old = methods(old_src, 'old')
new = {}
root = pathlib.Path('plugin/Markdown/output')
for path in [root / 'markdownml_enhanced.py', *sorted((root / 'renderers').glob('*.py'))]:
    new.update(methods(path.read_text(), str(path)))

missing = sorted(set(old) - set(new))
extra = sorted(set(new) - set(old))
differ = sorted(k for k in set(old) & set(new) if old[k] != new[k])
print('missing:', missing)
print('extra:', extra)
print('differ:', differ)
assert not missing and not extra and not differ, 'source is not a pure move'
print('OK: %d methods moved verbatim' % len(old))
```

Run: `cd /Users/lachang/Project/calibreMarkdown && .venv/bin/python /tmp/equiv_check.py`
Expected: `OK: 60 methods moved verbatim`；随后 `rm /tmp/equiv_check.py`。

- [ ] **Step 4: 全量单测 + 打包**

```bash
cd /Users/lachang/Project/calibreMarkdown && .venv/bin/python -m pytest plugin/tests -q && python3 plugin/build.py
```

Expected: 489 passed；zip 条目数比拆分前多 11（`renderers/__init__.py` + 10 个模块）。

- [ ] **Step 5: 代表真机脚本**

依次跑（每个都要求全 PASS）：`verify_list_items.py`、`verify_blockquote.py`、`verify_escape_chars.py`、
`verify_heading_141.py`、`verify_no_broken_css_margin.py`、`verify_image_no_alt.py`、
`verify_keep_image_sizes.py`、`verify_webp_export.py`、`verify_ui_language.py`。

- [ ] **Step 6: 交给用户决定是否安装/提交**

`./install.sh` 与 `git commit` 都等用户明确要求再执行。
