# Markdown 输出渲染器拆分设计（`markdownml_enhanced` → `renderers/`）

日期：2026-09-26
状态：设计已确认，待实现
版本：3.20.7 → 3.20.8（纯内部重构，用户可见行为不变）

## 1. 背景与问题

`plugin/Markdown/output/markdownml_enhanced.py` 现有 **1446 行**：模块级常量与纯函数约 186 行，
`EnhancedMarkdownMLizer` 一个类约 1258 行、**60 个方法**。文件内虽有清晰的方法簇（列表、块级、
脚注、表格、链接图片、TOC/文首、转义与片段、生命周期与分派），但没有任何物理边界：

- 想改一处列表渲染要在一个 1400 行的文件里定位；一次 Read 装不下，review diff 也是同一团。
- 新读者无法从文件结构看出渲染器由哪几个域组成（只能靠 docstring 里的 `see _xxx` 反推）。

目标：把 60 个方法按渲染域搬到物理模块里，**主文件只留类状态、生命周期与 `dump_text` 分派**，
使每个文件都能被完整读进上下文、职责一眼可见。

非目标（本次不动）：

- 任何渲染行为（输出 Markdown 必须逐字节不变）；
- 渲染状态的组织方式（不引入 `RenderState` 之类的新状态对象，不改成组合式）；
- `output_plugin.py`、`conversion_ui.py`、`preference_ui.py`、`convert_flow.py` 的内部结构；
- 打包与安装通道（`build.py` 按目录遍历，新文件自动进 zip）。

## 2. 硬不变量

1. `calibre_plugins.markdown.output.markdownml_enhanced.EnhancedMarkdownMLizer` 仍是唯一入口类，
   **导入路径与类名不变**（`output/output_plugin.py:279`、9 个测试文件、verify 脚本都按此导入）。
2. **方法体逐字照搬**：不改逻辑、不重排语句、不改注释与 docstring；`self.` 调用一律照旧。
3. 状态仍全部挂在类实例上（`opts / oeb_book / list / blockquotes / in_code / in_pre /
   remove_space_after_newline / _in_table_cell / _in_figure / _in_heading / _item_line /
   _fenced_pre / style_strike / style_bold / style_italic / toc_entries / _heading_slugs /
   base_hrefs / images / _footnote_* / _repaired_margins`），不新增状态对象，不改方法名。
4. 类外契约不变：`repair_margin_lengths`、`margin_repair_summary` 等纯函数仍然可导入
   （新位置 `renderers/primitives.py`，测试同步改导入）。

## 3. 模块边界

```
plugin/Markdown/output/
├── markdownml_enhanced.py      ~380 行  类定义 + 状态 + 生命周期 + dump_text 分派
└── renderers/
    ├── __init__.py              ~10   只放 docstring（说明拆分与依赖规则），不 import 任何东西
    ├── primitives.py           ~185   共享常量 + 纯函数（含 margin 修复）
    ├── text.py                  138   转义/片段/wikilink/文本收集
    ├── footnotes.py             152   脚注
    ├── tables.py                101   表格 + 定义列表
    ├── blocks.py                161   引用块 + 图
    ├── headings.py               99   标题
    ├── inline.py                 83   行内分隔符 + 围栏代码
    ├── lists.py                 233   列表项 + 强调开闭
    ├── media.py                 123   链接 + 图片
    └── document.py              111   目录 + 文首 + 封面
```

（上表为实测行数。）总行数从 1446 升到 1673（各模块的 docstring 与 import 开销，约 +230），这是可接受的代价。

### 3.1 方法到模块的精确映射（60 个方法，一一对应，不多不少）

| 模块 | 内容 |
|---|---|
| `markdownml_enhanced.py`（留在主文件） | 常量 `USE_FENCED_CODE_BLOCKS`；类属性 `_in_heading`、`_item_line`（含其 docstring）；方法 `extract_content`、`map_resources`、`_map_remaining_images`、`mlize_spine`、`apply_max_line_length`、`_repair_margins`、`dump_text`（共 7 个） |
| `renderers/primitives.py` | 常量 `BLOCK_LEVEL_TAGS`、`ITEM_LINE_BLOCKS`、`ITEM_LINE_OPEN`、`ITEM_LINE_STARTED`、`ITEM_TEXT_WRAPPERS`、`HEADING_INLINE_TAGS`、`_CSS_LENGTH_RE`、`_MARGIN_KEYWORDS`、`MARGIN_LENGTH_KEYS`；函数 `_ends_with_blank_line`、`_has_visible_text`、`_drop_leading_blank_fragments`、`_css_margin_break`、`_is_readable_length`、`repair_margin_lengths`、`margin_repair_summary`（无方法） |
| `renderers/text.py` | 常量 `MARKDOWN_ESCAPE_RE`、`MARKDOWN_UNESCAPE_RE`；方法 `_escaping_enabled`、`prepare_string_for_markdown`、`_plain_heading_text`、`prepare_string_for_table_cell`、`_format_fragment`、`_tail_fragment`、`_contains_token`、`_should_keep_link`、`_looks_like_external_href`、`_looks_like_internal_href`、`_sanitize_wikilink_target`、`_wikilink_target_from_href`、`_collect_element_text_parts`、`_dump_inline_block`（14 个） |
| `renderers/footnotes.py` | `_looks_like_footnote_id`、`_extract_footnote_target`、`_is_footnote_reference`、`_is_footnote_backlink`、`_next_available_footnote_label`、`_footnote_label_for_target`、`_collect_footnote_definition`、`_is_footnote_definition`、`_capture_footnote_definition`、`_render_footnotes`（10 个） |
| `renderers/tables.py` | `_cell_alignment`、`_render_table`、`_dump_definition_list`（3 个） |
| `renderers/blocks.py` | `_starts_with_block`、`_dump_blockquote`、`_dump_figure`（3 个） |
| `renderers/headings.py` | `_heading_level`、`_dump_heading_inline`、`_dump_heading`（3 个） |
| `renderers/inline.py` | `_wrap_delimiters`、`_wrap_html_tag`、`_code_language_from`、`_dump_fenced_pre`（4 个） |
| `renderers/lists.py` | `_extract_task_checkbox`、`_dump_list_item`、`_dump_item_block`、`_dump_item_paragraph`、`_item_indent`、`_open_emphasis`、`_close_emphasis`（7 个） |
| `renderers/media.py` | `_dump_link`、`_html_image`、`_markdown_image`（3 个） |
| `renderers/document.py` | `create_toc_entries`、`_toc_heading`、`get_toc`、`get_front_matter`、`_find_cover_href`、`_cover_markdown`（6 个） |

每个 mixin 类名 = `模块名首字母大写 + Mixin`：`TextMixin`、`FootnotesMixin`、`TablesMixin`、
`BlocksMixin`、`HeadingsMixin`、`InlineMixin`、`ListsMixin`、`MediaMixin`、`DocumentMixin`。

### 3.2 继承结构与依赖规则

```python
class EnhancedMarkdownMLizer(
        ListsMixin, DocumentMixin, MediaMixin, TablesMixin, BlocksMixin,
        HeadingsMixin, InlineMixin, FootnotesMixin, TextMixin,
        MarkdownMLizer):
```

- 类内**无同名方法**（已用 `grep -d` 核对，60 个名字唯一）⇒ mixin 顺序无语义；测试固化这一点。
- 三个 `super()` 调用点（`dump_text`、`map_resources`、`mlize_spine`）**全部留在具体类**，
  mixin 内不写 `super()`：`super()` 的下一站必须是 calibre 的 `MarkdownMLizer`，不依赖 mixin 顺序。
- **import 一律写绝对路径**（`from calibre_plugins.markdown.output.renderers.primitives import ...`），
  与仓库既有风格一致；相对导入在这里容易写错——从 `renderers` 出发 `..utils` 解析到 `output.utils`，
  要回到包根得写 `...utils`。
- **依赖规则**：`renderers/*.py` 互不 import，只允许 import `renderers.primitives` 与
  `utils.helpers`（以及 calibre 与标准库）；所有跨域调用走 `self.`。这条规则同时是
  20 个 verify 脚本的 seed 顺序依据（primitives 必须先 seed）。
- `renderers/__init__.py` 保持空壳（只有 docstring），不 import 子模块——避免在
  calibre 冻结点解释器的脚本 seed 流程里引入对导入查找器的依赖。

## 4. 连带改动

| 位置 | 改动 |
|---|---|
| `output/output_plugin.py` | 不动 |
| `plugin/build.py` | 不动（按目录遍历，新文件自动进 zip） |
| `plugin/tests/test_broken_css_margins.py` | 11 处导入改为从 `renderers.primitives` 取 `repair_margin_lengths`、`margin_repair_summary` |
| `plugin/tests/test_list_items.py:35` | `STUB_BASE = EnhancedMarkdownMLizer.__mro__[1]` → 显式 `from calibre.ebooks.txt.markdownml import MarkdownMLizer as STUB_BASE`（conftest 已打桩），不再依赖 MRO 位置 |
| 新增 `plugin/tests/test_renderer_layout.py` | 结构守卫五断言：① 10 个模块齐备；② 9 个 mixin 都真的混入；③ mixin 之间无同名方法（无遮蔽）且方法可从主类取到；④ `__mro__[-2] is MarkdownMLizer`（`super()` 链末端正确）；⑤ `renderers/*.py` 除 `primitives`/`utils`/`translations` 外不 import 插件内其它模块，且每模块只定义一个类（`primitives` 零个） |
| 20 个 `scripts/*.py` | seed 样板：`SUBPACKAGES` 加 `'output/renderers'`，`SEED_ORDER` 在 `('output', 'markdownml_enhanced')` 之前插入 10 个 renderer 模块（`primitives` 第一），`full_name` 拼接加 `.replace('/', '.')`（四类写法各自套用）；改完先跑通 `verify_blockquote.py` 再批量套用 |
| `scripts/verify_no_broken_css_margin.py` | 其 `_is_readable_length` 导入从主模块改到 `renderers.primitives`（脚本清单里唯一引用了已迁移私有函数的脚本） |
| `plugin/Markdown/__init__.py`、`input/input_plugin.py`、`output/output_plugin.py`、`tests/test_plugin_entry.py` | 3.20.7 → 3.20.8（四处同步，另更新 `PLUGIN_RELEASED`/`PLUGIN_ABOUT_LAST_UPDATED`） |
| `CHANGELOG.md` | 「改进」一条：输出渲染器按渲染域拆分为 `output/renderers/` 子包，行为不变 |

## 5. 验证与实测结果

1. **源码级等价证明**（代替金标准，零成本、不需要 calibre）：用 `ast` 从 `HEAD` 与拆分后两处各抽出
   「方法名 → 方法源码文本」映射，逐字比对。实测 `missing: [] extra: [] differ: []`，
   **60 个方法全部逐字搬运**（53 个迁入 mixin、7 个留在主文件）。
2. **未定义名字静态检查**（在没有 pyflakes 的 venv 里自写的 AST 检查器，含反向自测）：11 个模块
   0 处未定义名字。此项抓到了一个测试没覆盖的真实遗漏——`extract_content` 用的
   `margin_repair_summary` 一度没被导入。
3. `.venv/bin/python -m pytest plugin/tests -q`：484 → **489 passed**（新增 5 个结构守卫断言）。
4. **双树对照**（比金标准更省事、比单跑更可信）：`git clone` 出 HEAD 纯净副本 + 改前的 scripts，
   同一脚本在两棵树上各跑一遍，逐行比对 `PASS/FAIL`。实测 13 个脚本**输出完全一致**：
   `verify_blockquote`(3 项既有失败)、`verify_list_items`(23/0)、`verify_escape_chars`(19/0)、
   `verify_heading_141`(9/4 既有)、`verify_no_broken_css_margin`(5/0)、`verify_image_no_alt`(10/0)、
   `verify_keep_image_sizes`(19/1 既有)、`verify_webp_export`(9/1 既有)、`verify_ui_language`(9/0)、
   `verify_quote_paragraphs`(17/1 既有)、`verify_md_image_dedupe`(4/0)、
   `verify_yaml_front_matter_pane`(12/1 既有)、`verify_md_library_images`(全 PASS)。
   其余脚本在改后树上单跑，均无 `ImportError`/`Traceback`：`verify_pane_icons`(8/0)、
   `verify_image_output_pane`(42/0)、`verify_md_input_pane`(8/0)、`verify_md_to_epub_images`(3/0)、
   三个探针(`probe_margin_crash`/`probe_list_render`/`probe_book_folder_resolution`)退出码 0。
   失败项一律在 HEAD 上复现，属既有现象（样本书自带的 `*` 场景分隔行等），与本次拆分无关。
   另有两个**既有**故障（HEAD 同样）：`smoke_markdown_output.py` 触发自身的
   `installed zip shadows the source tree` 守卫；`probe_output_ctx.py` 调用
   `convert_book_to_markdown(..., emit=...)`，而该参数早已从 convert_flow 移除。
5. `python3 plugin/build.py`：zip 37 个条目（较拆分前 +11），`output/renderers/*.py` 全部在包内。

## 6. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 脚本 seed 不全 → 静默跑旧插件、假通过 | 先在一个脚本上跑通再批量套用；利用脚本自带的 zip 影子守卫；逐个真跑 |
| mixin 遮蔽（两个模块定义同名方法，前者被覆盖） | 60 个名字已核对唯一；新增结构守卫测试永久固化 |
| 迁移过程中手滑改到方法体 | §5.2 的 AST 逐字比对；迁移按"整块剪切-粘贴"进行，不做格式化 |
| 导入遗漏（某方法用到 `barename`/`unquote`/`DEFAULT_IMAGE_DIR` 而新模块没 import） | 每个模块按实际用量收敛 import；测试 484 项与真机脚本会立刻暴露 NameError |

## 7. 实施顺序

1. 建 `renderers/` 包与 `primitives.py`、`text.py`（被最多模块依赖，先落地）。
2. 迁 `footnotes` → `tables` → `blocks` → `headings` → `inline` → `lists` → `media` → `document`。
3. 主文件收口：继承 mixin、删除已迁代码、清 import。
4. 测试改造（2 处导入 + 结构守卫），跑 484+3。
5. 20 个脚本 seed 样板批量更新，跑代表脚本。
6. 版本号与 CHANGELOG，AST 等价证明，收尾。
