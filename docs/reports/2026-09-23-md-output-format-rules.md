# Markdown 输出插件：输出 .md 的格式规范与修正清单（v3.20.6）

日期：2026-09-23
插件版本：3.20.6
范围：`plugin/Markdown/output/`（输出插件、转换面板、自定义弹窗、MarkdownML 渲染器）及其依赖的 `utils/helpers.py`、`utils/remote_images.py`、`utils/library.py`

本报告回答一个问题：**一本书经过本插件转成 Markdown 后，产出的 .md 为什么长这样**——
每一条格式规范的产出规则、它由哪个选项控制、以及它相对 calibre 上游 `MarkdownMLizer`
修正了什么。规范取自当前源码，不是设计稿。

## 1. 流水线位置：格式在哪一步被决定

`MarkdownOutput.convert()` 拿到的是 calibre 已经解析好的 OEB（XHTML + 样式），
格式规范全部落在 `EnhancedMarkdownMLizer`（继承 calibre `MarkdownMLizer`）里。

```136:178:plugin/Markdown/output/markdownml_enhanced.py
    def extract_content(self, oeb_book, opts):
        self.log.info('Converting XHTML to enhanced Markdown formatted TXT...')
        self.opts = opts
        self.oeb_book = oeb_book
        ...
        body = self.mlize_spine(oeb_book) + self._render_footnotes()
        if self._repaired_margins:
            self.log.info(margin_repair_summary(self._repaired_margins))
        body = self.tidy_up(body)
        body = clean_invisible_chars(body)
        if getattr(self.opts, 'strip_pdf_page_markers', False):
            body = strip_pdf_page_marker_lines(body)
        body = self.apply_max_line_length(body)
        return apply_paragraph_style(
            clean_invisible_chars(self.get_front_matter(oeb_book))
            + self._cover_markdown(oeb_book)
            + self.get_toc()
            + body,
            getattr(self.opts, 'paragraph_style', None) or 'block',
            getattr(self.opts, 'blank_line_before_heading', True),
        )
```

| # | 阶段 | 做什么 | 开关 |
|---|---|---|---|
| 1 | `mlize_spine` | XHTML 块/行内元素 → Markdown 语法（§3、§4） | 各语法开关 |
| 2 | `_render_footnotes` | 正文里收集的脚注定义统一追加到文末（§3.9） | 跟随链接/脚注识别 |
| 3 | `tidy_up`（上游） | 行首空白、tab、空行、收尾换行（§6.1） | 无 |
| 4 | `clean_invisible_chars` | 删除零宽/软连字符/BOM 类字符（§5.3） | 无 |
| 5 | `strip_pdf_page_marker_lines` | 删除独立页码行（§5.4） | `strip_pdf_page_markers`（默认关） |
| 6 | `apply_max_line_length` | 按空格折行（§6.3） | `max_line_length`（默认 0=关） |
| 7 | 骨架拼装 | YAML → 封面 → 目录 → 正文（§2） | `yaml_front_matter` / `export_cover_page` / `inline_toc` |
| 8 | `apply_paragraph_style` | 段落/空行布局重塑（§6.2） | `paragraph_style`（默认 block） |
| 9 | 图片导出 | 写文件 / 内嵌 / 改路径（§7） | `image_output_mode` 等 |
| 10 | 写出字节 | 换行符归一 + 编码（§6.4） | `newline`（unix）/ `txt_output_encoding`（utf-8） |

**顺序要点**：折行（6）只作用于**正文**，YAML/TOC/封面不参与；段落样式（8）作用于**整份文件**，
包括 YAML 与目录（见 §10 边界）。

## 2. 文档骨架

一份输出文件的固定顺序（每个部分为空就整段不出现）：

```
---            ← YAML front matter（§3.1）
key: value
---

![Cover](images/000000.jpg)      ← 封面（§3.2）

## 目录                          ← 内联目录（§3.3）
- [第一章](#第一章)
  - [第一节](#第一节)

# 第一章                         ← 正文（§3.4 起）
...

[^1]: 脚注正文                    ← 脚注定义（§3.9）
```

目录标题跟随 calibre 界面语言：中文界面写「目录」，否则 `Table of Contents`。

```243:253:plugin/Markdown/output/markdownml_enhanced.py
    def _toc_heading(self):
        try:
            from calibre_plugins.markdown.translations.ui_language import (
                UI_LANG_ZH_CN,
                get_ui_language,
            )
            if get_ui_language() == UI_LANG_ZH_CN:
                return '目录'
        except Exception:
            pass
        return 'Table of Contents'
```

## 3. 块级元素 → Markdown 规范

### 3.1 YAML front matter

- 字段顺序固定：`title, authors, language, publisher, tags, series, series_index, isbn, pubdate, description, calibre_id`；空值（None/''/[]）整项跳过。
- 取值优先级：**书库元数据 > OEB 元数据**。书库那部分由 `utils/library.py` 以只读方式查（携带 `calibre_id`、`series`、`description` 等 OEB 里没有的字段）；OEB 只提供 title/authors/language/publisher/tags。
- 列表写法：单值写成 `key: value`；多值写成 `key:` + 每行 `  - value`（这是 python-markdown `meta` 扩展能读回的形式，见输入侧报告 `2026-09-18-md-input-pane.md` §3.2）。
- `series_index` 经 `format_series_index()` 归一（2.0 → `2`）；`pubdate` 归一为 `YYYY-MM-DD`；`description` 由书库 `comments` 经 `html_to_plain()` 转纯文本。
- 引号规则 `yaml_quote()`：含 `:#[]{},&*!|>'"%@`、或以 `-`/`?` 开头、或含换行、或首尾有空白 → 双引号包裹，内部 `\`→`\\`、`"`→`\"`、换行→`\n`；空值写 `''`。**该转义与"转义 Markdown 字符"开关无关，始终生效。**
- 全空则不产生 front matter（不会留下一个空的 `---` 块）。

### 3.2 封面

仅在 `export_cover_page` 与 `keep_image_references` 同时为真、且封面 href 不在 spine 中时输出
`![Cover](images/NNNNNN.ext)`。`export_cover_page` 另有一个作用：关闭时从 spine 中剔除
`titlepage.xhtml/.html`，整页不渲染。

### 3.3 内联目录

`## 目录` + 每个条目 `- [标题](#slug)`，层级缩进 `2 × depth` 个空格；空标题跳过。
slug 由 `slugify()` 生成且全文唯一（重复加 `-2`、`-3`…），与正文标题锚点用同一算法，故目录链接可命中。

`slugify()`：转小写 → 去掉非 `[\w\s-]` 字符 → 空白转 `-` → 合并连续 `-` → 去首尾 `-`；空结果取 `section`。

### 3.4 标题

- `<h1>..<h6>` → `#`×level + 空格 + 标题文本；引用块内的标题仍带 `> ` 前缀（`>` 在 `#` 之前）。
- **标题内容一律按行内文本渲染，一个标题只占一行**（`_dump_heading` 置位 `_in_heading`）：
  - `<br>` → 空格（上游写的 `  \n` 硬换行会截断 ATX 标题，标题后半段掉成正文）；
  - 块级子元素与**嵌套的 `<h1>..<h6>`** 压成纯文本，不再各自写 `#`/换行/前缀；
  - 嵌套标题取**更深**的那一级（`<h2><h3>第0001章</h3><br/>我成了岳不群</h2>` → `### 第0001章 我成了岳不群`）：
    外层是版式容器，内层才带着书或「转换 HTML」规则定出的级别，两边都写就成了 `## ### 第0001章`；
  - 不写 `**`/`*`：子元素继承标题的 `font-weight:bold` 后上游会给它们包 `**`（上游只对标题自身跳过强调），
    而 `#` 已经表达了强调；
  - `a`/`img`/`sup`/`sub`/`code`/`del`/`s`/`strike`/`mark`/`cite` 这些行内语法照旧保留。
- 标题内部空白压成单空格并 strip。
- 标题文本尾部若已带 `{#...}`，先剥离再重新生成，避免重复锚点。
- `heading_anchors`（默认开）追加 ` {#slug}`；关闭则输出纯标题。
- 计算 slug 时用 `_plain_heading_text()` 只回退本模块加过的转义，因此开/关转义对同一本书得到同一个 slug。

### 3.5 列表

| XHTML | 输出 | 说明 |
|---|---|---|
| `ul > li` | `- 项` | **上游写 `+ `**，本插件改用 `- `（CommonMark 主流记号） |
| `ol > li` | `1. ` `2. `… | 每个 `ol` 独立计数，靠 `self.list` 栈维护 |
| 嵌套列表 | 行首 `\t × (深度-1)` | 只缩进嵌套层 |
| 任务项 | `[x] ` / `[ ] ` | 识别文本里的 `[ ]`/`[x]` 前缀，或 `<input type=checkbox>`（`checked`/`aria-checked=true|mixed`/`value=true`） |
| 斜体/粗体 | `*项*` / `**项**` | 由 CSS 或 `i/em/b/strong` 触发，且不在已处于该状态时重复嵌套 |

### 3.6 引用块

规范：**每一行以 `> ` 开头，前缀只写一次**；引用结束靠**空行**，不靠裸 `>` 行。

上游的两个缺陷在此修正：
1. 上游为 `<blockquote>` 与其块级子元素各写一次前缀，于是每段引文上方多出一行孤立的 `>`；
2. 上游把斜体/粗体样式包在整个引用外面（`*` 跨块级子元素非法，且行首 `*` 会被当列表符号）。

现在：若引用的首个内容是块级子元素（`BLOCK_LEVEL_TAGS`），前缀由该子元素自己写；否则本方法为文本/行内子元素写前缀，并把 `*`/`**` 写在文本上 —— 得到 `> *引文*`。
引用后紧跟的 tail 文本会补一个空行（否则会被读成 lazy continuation 行而并进引用）。
引用上下由 CSS margin 换算出的"软场景分隔"（`_css_margin_break()`）被保留。

### 3.7 表格（GFM 管道表）

- 结构：`| a | b |` + 第二行对齐分隔行（`---` / `:---` / `---:` / `:---:`）；对齐取单元格 `align` 属性，其次 CSS `text-align`（`center|middle`→`:---:`，`right|end`→`---:`，`left|start|justify`→`:---`）。
- 支持 `thead/tbody/tfoot` 包裹（递归取 `tr`）。
- 单元格文本：换行→空格、连续空格压缩为一个、`|`→`\|`、去首尾空白；单元格内的 `<p>/<div>` 走 `_dump_inline_block()`，不产生块换行，避免撑破表格行。
- `<caption>` 渲染成表格上方的 `*斜体*` 行。
- 无有效行则整表输出空。

### 3.8 代码块（围栏）

`USE_FENCED_CODE_BLOCKS = True`：`<pre>` 渲染成 ```` ```lang ```` 围栏（上游是 4 空格缩进，且不带语言）。
语言从 `class` / `data-lang` / `data-language` / `data-brush` 依次探测（`<pre>` 与其内部 `<code>` 都看）：
`language-python` 这类 token、`brush: python` 这类写法、以及裸词（但 `preformatted/highlight/code/source/prettyprint/hljs/syntax/listing/pre/blockquote` 这类通用词不算语言）。

### 3.9 脚注

- 识别引用：`class` 含 `noteref`/`footnote-ref`、`role=doc-noteref`、`epub:type` 含 `noteref`，或锚点 id 形如 `fn*`/`footnote*`/`note*` → 正文写 `[^n]`。
- 识别定义：元素 id 已登记、`role=doc-footnote`、`class` 含 `footnote`、`epub:type` 含 `footnote`，或 id 形如上述 → 从正文摘出，文末统一输出 `[^n]: 文本`。
- 编号：优先取 id 尾部的数字，冲突或没有则取自增序号。
- 定义文本：跳过返回链接（`#fnref*`、`backref`、`doc-backlink`），空白压成一个空格，剥掉已有的 `[^x]:` 前缀，避免二次转换时重复。

### 3.10 定义列表 / figure / 分隔线 / 硬换行

| XHTML | 输出 |
|---|---|
| `dl`（含 `div/section` 包裹） | `术语` 行 + `: 释义` 行 + 空行；多个 `dt` 连续则各自成行后接同一条释义 |
| `figure` | 内容原样，`<figcaption>` → 末尾 `*斜体*` 行；孤立的 `figcaption` 也渲染成 `*斜体*` |
| `hr` | `* * *`（继承上游） |
| `br` | 行尾两个空格 + 换行（继承上游） |

## 4. 行内元素 → Markdown 规范

| XHTML | 输出 | 规则 |
|---|---|---|
| `i/em`、CSS `font-style: italic` | `*文本*` | 已在斜体状态内不重复包裹 |
| `b/strong`、CSS `font-weight: bold/bolder` | `**文本**` | 同上 |
| `del/s/strike`、CSS `text-decoration: line-through` | `~~文本~~` | 链接元素不套删除线 |
| `mark` | `==文本==` | 高亮 |
| `cite` | `*文本*` | |
| `sup` / `sub` | `<sup>..</sup>` / `<sub>..</sub>` | Markdown 无对应语法，保留原始 HTML |
| `a`（外部链接） | `[文本](href "title")` | `title` 存在才写引号部分 |
| `a`（站内链接） | `[[目标]]` | 目标是链接文本，没有则从 href 的 basename stem 或锚点取；清理 `[`、`]`、换行，`|`→`-` |
| `a`（`javascript:` 或空 href） | 只保留文本 | 链接整体丢弃 |
| `img` | 见 §7 | |

`keep_links` 关闭时：链接整体降级为纯文本（站内链接不再写成 `[[..]]`）。

## 5. 文本层规范

### 5.1 转义（默认不转义）

- 字符集沿用上游 `MARKDOWN_ESCAPE_RE`：反斜杠、反引号、星号、下划线、花括号、方括号、圆括号、井号、加号、叹号。
- **默认关闭**（`escape_markdown_chars=False`）：`第1卷 原版(By:苏梦枕)` 原样输出，不会被写成
  `第1卷 原版\(By:苏梦枕\)`。代价是把文件再当 Markdown 渲染时，这些字符可能被读成格式。
- 开启时，正文、标题、tail 文本全部经 `prepare_string_for_markdown()` 转义。
- **始终转义**的两处：表格单元格里的 `|`，以及 YAML 的引号转义（§3.1）。

### 5.2 换行折叠（`remove_newlines`，继承上游）

源文本里的换行/CR/tab 一律折成一个空格，连续空格压缩为一个；
`remove_space_after_newline` 标志位会在块开始时吃掉行首多余空格（因此 alt 文本等处会保存/恢复该标志，
避免误吃内容空格）。`<pre>` 内不走这条路径。

### 5.3 不可见字符

`clean_invisible_chars()` 删除 `U+00AD`（软连字符）、`U+200B–U+200D`、`U+2060`、`U+FEFF`。
在正文（tidy 之后）与拼装后的整份文件上各跑一次。

### 5.4 PDF 页码行（可选）

`strip_pdf_page_markers` 开启时删除整行只有页码标记的独立行
（`Page-12`、`Page 12`、`link to page 12`，忽略大小写），并把因此产生的 3 个以上连续换行压成 2 个。
默认关闭，因为正文里可能出现同形文本。

## 6. 文档级整形

### 6.1 `tidy_up()`（继承 calibre 上游）

1. 行首 1–3 个空格删除；剩下的行首空格视为缩进代码，补成 4 空格；
2. 行内（非行首）的 tab 删除，行首 tab 保留；
3. 只含空格的"空行"清成真空行；
4. 7 个以上连续换行压成 6 个；
5. 文件开头空白删除，结尾统一为 `\n\n`。

### 6.2 段落样式

- `block`（默认）：保持标准 Markdown 布局，空行分段，本步直接返回原文。
- `single`：删除所有空行，让每行自成一个段落行。三个例外：
  - **围栏代码块内的空行是内容**，保留；
  - **引用块结束处的空行保留**（它不是段落分隔，而是引用的终止，删掉会让下一行被吞进引用）；
  - `blank_line_before_heading`（默认开）时，在 `#` 标题前补一个空行，**文件第一行的标题不补**。

### 6.3 折行

`max_line_length` > 0 时按空格折行：优先在前 `max_length` 内的最后一个空格处断，
找不到就到后面第一个空格处断（会超限）；`force_max_line_length` 打开时允许硬切并允许小于 25 的值，
否则小于 25 的值被抬到 25。默认 0 = 不折行。

### 6.4 写出

`specified_newlines()` 按 `newline`（unix/windows/old_mac/system，默认 unix）归一换行；
按 `txt_output_encoding`（默认 utf-8，`errors='replace'`）编码写出，写出前经 calibre 的
`clean_ascii_chars()` 清理控制字符。

## 7. 图片与资源路径规范

### 7.1 引用命名与映射

- 所有图片统一映射为 `images/%06d<ext>`（如 `images/000003.webp`）。
- **修正上游**：calibre 的 `map_resources()` 只映射其 `OEB_IMAGES`（gif/jpeg/png/svg），
  webp 这类"光栅图"保留 EPUB 内 href，导出的 .md 里是一个无法解析的路径，且不会被导出。
  `_map_remaining_images()` 在 calibre 之后补齐所有 `image/*`，沿用已有编号，不重排。

### 7.2 两种引用写法

| 情形 | 写法 |
|---|---|
| 未声明尺寸 | `![alt](images/000001.jpg)` |
| 声明了 width/height（属性或 CSS） | `<img src="images/000001.jpg" alt=".." title=".." width=".." height="..">` |

- **修正上游**：上游只在 `<img>` 带 `alt` 时才写 `[]`，无 alt 的图片会输出 `!(images/000001.jpg)`
  —— 括号缺失，图片在每个渲染器里都丢失，输入侧也读不回来。现在无论有无 alt 都写 `![...]`。
- 尺寸：裸数字按像素处理补 `px`（`80` → `80px`），`auto` 保留，未声明的一边写 `auto` 以保持比例；
  两边都没声明就用 Markdown 形式。`keep_image_sizes` 关闭时退化为纯 `![alt](src)`。
- `keep_image_references` 关闭时完全走上游分支（`use_alt_text_for_images` 生效，用 alt 文本替图）。

### 7.3 三种输出模式（`image_output_mode`）

| 模式 | 行为 |
|---|---|
| `sidecar`（默认） | 图片写到 .md 旁边；库内转换写进**书目录 `images/`**（引用前缀不变），CLI/保存到磁盘写进 `<md 名>.images/` 并把引用前缀 `images/` 改写成该目录名（URL 编码） |
| `inline` | 图片以 base64 data URI 内嵌，只改 `src`，保留 alt/width/height |
| `none` | 不导出图片 |

共同规则：**只导出 Markdown 实际引用到的图片**（封面页被跳过时封面图也不会被写出来），
一本书一张图都没引用就不创建目录；远程图片（http/https）在 `download_remote_images` 打开时下载，
续接 `%06d` 编号避免与本地图冲突，下载失败保留原 URL 并在转换报告里给出警告（最多列 5 条）。

## 8. 相对 calibre 上游的修正清单

| # | 上游症状 | 修正 |
|---|---|---|
| 1 | 引用块前缀写两遍，每段引文上方多一个孤立 `>`；斜体/粗体包在引用外 → `*>` 与孤立 `*` 行 | 前缀只写一次；样式写在文本上（§3.6） |
| 2 | 无 alt 的 `<img>` 输出 `!(path)`，括号缺失 | 始终写 `![alt](src)`（§7.2） |
| 3 | webp 等非 `OEB_IMAGES` 图片保留 EPUB 内 href，路径不可解析且不导出 | 补映射所有 `image/*`（§7.1） |
| 4 | CSS margin 写成无法解析的字符串（如 `margin-bottom: olid`）时上游 `float()` 抛异常，**整本书导出失败** | `repair_margin_lengths()` 把它读作 0，并在日志留一行说明（§9） |
| 5 | 无序列表用 `+ ` | 改成 `- `（§3.5） |
| 6 | `<pre>` 用 4 空格缩进，无语言标注 | 围栏 ``` ```lang ```（§3.8） |
| 7 | 一律转义 Markdown 特殊字符 | 默认不转义，可按书/全局开关（§5.1） |
| 8 | 站内链接被丢弃（上游只保留含 `://` 的外部链接） | 站内链接 → `[[wikilink]]`（§4） |
| 9 | 脚注被当成普通链接/正文 | 识别 EPUB3 语义与常见 id 约定，转成 `[^n]` + 文末定义（§3.9） |
| 10 | `table` 没有专门分支：单元格内容连成一片，无对齐行、无 caption | GFM 管道表 + 对齐行 + caption + 单元格内块降级（§3.7） |
| 11 | 无 TOC / YAML / 封面控制 | `inline_toc`、`yaml_front_matter`、`export_cover_page`（§2） |
| 12 | 定义列表 / `mark` / `figure` 无对应处理 | 见 §3.10、§4 |
| 13 | 标题的子元素按块级渲染：嵌套标题再写一遍 `#`（`## ### 第1章`）、`<br>` 写硬换行把标题截断、子元素继承的 bold 又写出 `**` | 标题内容走行内模式，一个标题一行、一个层级标记（§3.4） |

## 9. 容错：坏 CSS 不再中断导出

```100:123:plugin/Markdown/output/markdownml_enhanced.py
def repair_margin_lengths(style):
    ...
    for key in MARGIN_LENGTH_KEYS:
        value = getter(key)
        if value is None or _is_readable_length(value):
            continue
        repaired.append((key, value))
        setter(key, '0')
    return repaired
```

`dump_text()` 在读取任何样式前先调用它（`_repair_margins`），因此上游那句无保护的
`float(style.marginTop)` 只会看到已修好的值。可读值判定：数字、带单位的数值、`auto/inherit/initial/unset`；
其余一律读作 0。修复会在转换日志里汇总成一行，不会静默改掉排版。

## 10. 已知边界

- **`single` 段落样式作用于整份文件**：YAML front matter 与目录块里的空行也会被去掉
  （引用块结尾空行、围栏内空行仍保留）。
- **折行只作用于正文**：YAML、目录、封面不受 `max_line_length` 影响。
- **转义默认关闭**：导出的 .md 里源文本中的 `(`、`#`、`*` 等都是字面量，再次当 Markdown 渲染时
  可能被解释为格式；需要"所见即所得"的场景请打开 `escape_markdown_chars`。
- **目录 slug 与标题锚点由同算法分别计算**：目录条目来自 EPUB 的 TOC 节点，正文锚点来自渲染出的
  标题文本，两者一般一致；书的 TOC 与正文标题不完全相同时（重命名、层数不同）会有个别链接不命中。
- **脚注定义整段压成一行**：多行脚注的换行会变成空格。
- **远程图片**：只下载 http/https，单图上限 50MB、超时 10s；失败的引用保持 URL。
- **库内图片目录依赖只读书库查询**：找不到书目录时不导出图片并在转换报告里警告 .md 仍会生成。
- **`sup`/`sub` 以原始 HTML 输出**，目标渲染器若不开启内联 HTML 会看不到效果。
- **批量转换不读取输入面板保存的默认值**（输入侧限制，见 `2026-09-18-md-input-pane.md` §5）；
  输出侧的全局覆盖（自定义弹窗）作为转换面板的初始默认值生效，面板提交的值按书保存并优先。

## 11. 验证

- 单元测试：`.venv/bin/python -m pytest plugin/tests -q` → **466 passed**（2026-09-23 基线）。
  覆盖本报告各条的测试：`test_blockquote.py`、`test_heading_anchors.py`、`test_heading_inline.py`、`test_escape_chars.py`、
  `test_paragraph_style.py`、`test_keep_image_sizes.py`、`test_image_size.py`、`test_image_formats.py`、
  `test_image_export.py`、`test_remote_images.py`、`test_broken_css_margins.py`、`test_cover_page.py`、
  `test_library_metadata.py`、`test_output_options.py`、`test_helpers_baseline.py`。
- 真机验收（calibre-debug，改源码树即可跑）：`scripts/verify_blockquote.py`、
  `scripts/verify_quote_paragraphs.py`、`scripts/verify_escape_chars.py`、
  `scripts/verify_keep_image_sizes.py`、`scripts/verify_webp_export.py`、
  `scripts/verify_no_broken_css_margin.py`、`scripts/verify_heading_141.py`、`scripts/verify_md_library_images.py`、
  `scripts/verify_yaml_front_matter_pane.py`、`scripts/verify_image_output_pane.py`。
- 用户在 GUI 实际生效仍需 `./install.sh` 装成 `~/Library/Preferences/calibre/plugins/Markdown.zip` 并重启 calibre。

## 12. 文件清单

| 文件 | 承担的格式规范 |
|---|---|
| `output/markdownml_enhanced.py` | §2 骨架、§3 块级、§4 行内、§5.1 转义、§6.3 折行、§7.1/7.2 图片映射与写法、§9 容错 |
| `output/output_plugin.py` | 选项声明与默认值、§7.3 输出模式与导出编排、§6.4 写出 |
| `output/convert_flow.py` | 脚本/冒烟用的转换入口（选项回填），不参与格式决策 |
| `output/conversion_ui.py` | 转换面板（选项绑定、图片行联动置灰） |
| `output/preference_ui.py` | 自定义弹窗（全局覆盖 = 面板初始默认值） |
| `utils/helpers.py` | YAML/TOC/表格/定义列表/图片尺寸与路径改写（§3.1、§3.3、§3.7、§5.3、§5.4、§6.2、§7） |
| `utils/remote_images.py` | 远程图片下载与引用改写（§7.3） |
| `utils/library.py` | 只读书库查询：书目录（图片落点）与书库元数据（YAML） |
| `utils/prefs.py` | 选项清单、默认值、全局覆盖序列化 |
