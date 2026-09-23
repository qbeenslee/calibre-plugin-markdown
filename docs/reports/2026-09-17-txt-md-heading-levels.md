# TXT → Markdown 转换中标题生成等级的决策研究报告

日期：2026-09-17
研究对象：calibre TXT → MD 转换管线中标题（h1–h6 → `#`–`######`）的产生机制
实证样本：calibre 书库《尘缘》（book id 919，烟雨江南，TXT 3.6 MB / 18033 行 / 92 个卷章行）
环境：calibre 9.14.0 (macOS)、Markdown Output 插件 3.1.0

## 1. 结论摘要（TL;DR）

1. **输出侧不做任何标题判断**。Markdown 输出插件只做固定映射：中间 XHTML 的
   `h1→#`、`h2→##` … `h6→######`（叠加可选 `{#slug}` 锚点、段落样式等）。
   「这一行是不是标题、是几级」完全由**输入侧与转换管线**决定。
2. **calibre 原生能力对中文 TXT 无效**。TXT 输入插件的内建启发式
   （`markup_chapters`）章节模式全部是英文/数字（`CHAPTER/Volume/Part`、
   `1.`/裸数字、大写字母行），**没有任何中文章节模式**；实测对
   「第1卷」「第一部 人界篇」「第1章 断肠」全部不命中。
3. 《尘缘》`## 第1卷` 的真正来源是**用户自己配置的「HTML 转换规则」**
   （`transform_html_rules`，逐书保存）：规则把 `<p>第1卷</p>` 的标签
   **改名成 `<h2>`**，再由输出插件映射为 `## 第1卷`。
4. 因此「第1卷 → `##`」的决策依据 = 规则 2 的正则
   `第[数字/中文数字]{1,9}[卷篇]`；「第一部 人界篇」命中规则 1 → `#`；
   「第1章 断肠」命中规则 3 → `###`。

## 2. 转换管线与标题决策链

```
TXT 文件
  │  ① TXT Input 插件（编码探测/BOM/段落类型/格式探测）
  │     · formatting_type=auto → detect_formatting_type()
  │     · markdown 证据 >5 处 → markdown 路径（python-markdown，# 即 h1-h6）
  │     · 否则 → heuristic 路径 → convert_basic() → 全部 <p>，无标题
  ▼
中间 XHTML（OEB）
  │  ② 启发式阶段（enable_heuristics，heuristic 路径自动置位）
  │     · markup_chapter_headings（默认开）→ markup_chapters()
  │       英文/数字章节模式表 → 命中行标 <h2>（副标题行 <h3>）
  │       【无中文模式，对中文小说无效——实测】
  │  ③ HTML 转换规则阶段（transform_html_rules，plumber「Running transforms」）
  │     · 用户配置的规则按 xpath 匹配段落文本 → 改标签名（p → h1/h2/h3）
  │       【《尘缘》## 第1卷 的实际来源】
  ▼
OEB（含 h1-h6）
  │  ④ Markdown Output 插件（本插件）
  │     · h1→# … h6→######（固定映射）
  │     · heading_anchors 开 → 追加 {#slug}
  ▼
MD 文件
```

## 3. 各来源详解

### 3.1 TXT Input 的格式探测（决定走哪条路径）

`detect_formatting_type()`（`calibre/ebooks/txt/processor.py`）统计证据计数：

- Markdown 证据：行首 `#+`、`===`/`---` 下划线标题、`![..](`、`[..](` 链接
- Textile 证据：`h1.`~`h6.`、`bq.`、`"…":url` 等
- 判定：**任一计数 > 5** 且 markdown > textile → `markdown`；否则 → `heuristic`

普通中文小说 TXT 无任何 Markdown/Textile 标记 → 判为 `heuristic`。
（实测《尘缘》TXT：`paragraph_type=unformatted`、`formatting_type=heuristic`）

- `markdown` 路径：python-markdown 解析，`#` 的个数直接决定 h1–h6。
  适合「先预处理 TXT 成 Markdown，再让 calibre 直通」的做法。
- `heuristic` 路径：自动设置 `enable_heuristics=True`、`unwrap_lines=False`、
  `smarten_punctuation=True`，然后 `convert_basic()` 只产 `<p>`，输入阶段无标题。

### 3.2 内建启发式 `markup_chapters`（对中文无效）

位置：`calibre/ebooks/conversion/utils.py`（`HeuristicProcessor.markup_chapters`），
由 `markup_chapter_headings` 选项（默认开）启用。

- **数量门槛**：`min_chapters = ceil(词数/7000)`（>20 万字时 /15000），
  `max_chapters = 150`；先「分析」一轮统计命中数，达标才实际标注；
  已有 h1–h3 数量 ≥ min_chapters 时跳过。
- **模式表**（按命中率试探）：common（`Introduction|…|CHAPTER|Kapitel|Volume|
  Prologue|Book|Part|…`）→ `CHAPTER+编号` → `<b>` 强调行 → `数字.`/`数字:` →
  字距标题 → 数字+标题 → 裸数字 → 大写字母行。
- **标注结果**：`chapter_head()` 把章节行包成 **`<h2>`**（永远不是 h1）；
  若紧随其后的行被识别为标题行 → `<h2>` + `<h3 class="sigilNotInTOC">`。
- **中文覆盖**：无。`第X章/卷/部/回`（无论中文数字还是阿拉伯数字）实测均不命中。

### 3.3 HTML 转换规则 `transform_html_rules`（《尘缘》的实际来源）

- GUI 入口：转换书籍 → **外观（Look & feel）→ 转换 HTML**（HtmlRulesWidget 规则向导）
- CLI：`--transform-html-rules <规则文件>`
- 执行点：`plumber.py` 的 "Running transforms on e-book" 阶段
  （`transform_conversion_book(oeb, opts, rules)`），对每个 spine 文档应用
- **保存位置**：逐书转换设置（转换对话框每次 OK 后按书保存一份快照）+
  全局默认。旧书的快照与全局默认可能不一致

《尘缘》(id 919) 逐书设置中实际保存的 5 条规则（从 `transform_html_rules` JSON 解码）：

| # | 目标标签 | 匹配正则（行级，允许首部空白/全角空格，尾部可有分隔符+≤100 字符标题） |
|---|---|---|
| 1 | **h1**（加类 section） | `作品相关` 或 `第[.0-9０-９一二三四五六七八九十零〇百千壹贰叁肆伍陆柒捌玖拾佰仟]{1,9}部` |
| 2 | **h2**（加类 volume） | `番外篇`、`序卷`、`第[同上数字集]{1,9}[卷篇]` |
| 3 | **h3**（加类 chapter） | `楔子/前传/正文/引子/序章/序幕/序言/序/角色介绍/人物介绍/简介/【内容简介】/上篇/中篇/下篇/尾声/终章/后记/后传/特典/附录/番外` 或 `第[数字集]{1,9}[章节回集讲话幕]` |
| 4 | **h4** | `前言`、`[Cc]hapter/[Ss]ection/[Pp]art/ＰＡＲＴ`、`No[分隔符]数字` |
| 5 | 加类 chapter-intro（不改标签） | `楔子/前传/引子/序章/序幕/序言/序/角色介绍/人物设定/人物介绍/简介` |

由此：`第1卷` → h2 → `## 第1卷`；`第1章 断肠` → h3 → `### 第1章 断肠`；
`第一部 人界篇` → h1 → `# 第一部 人界篇`。

### 3.4 输出插件（本插件）

- 固定映射 h1–h6 → `#`–`######`（`EnhancedMarkdownMLizer._dump_heading`）
- `heading_anchors`（默认开）：标题尾追加 `{#slug}`，供文首目录跳转
- `paragraph_style` / `blank_line_before_heading`：段落与标题的空行排版
- 输出插件**不参与**「是不是标题」的判断

## 4. 实证记录（《尘缘》id 919）

| 实验 | 操作 | 结果 |
|---|---|---|
| E1 | 合成文本 + `markup_chapters`（wordcount=8000） | `Volume 2 The New Realm` → `<h2>`；`第1章 起点`、`第一部 人界篇` 不命中 |
| E2 | 书 919 TXT 原文扫描 | 3.6 MB / 18033 行 / 92 个卷章行（`第1卷`…`第4卷 忽闻海外有仙山`） |
| E3 | TXTInput 单跑（真实 opts） | 产出 XHTML **无任何 h 标签**，`第1卷` 在 `<p>` 中 |
| E4 | 完整启发式阶段跑真实 XHTML | `第1卷`/`第1章 断肠` 仍为 `<p>`（**0 个 h 标签**） |
| E5 | 裸默认全管线 TXT→MD | MD 标题数 = **0** |
| E6 | EPUB→MD | `## 第1卷 {#第1卷}`、`### 第1章 断肠 {#…}`（EPUB 内部自带 h2/h3） |
| E7 | 读取书 919 逐书设置 | 发现 `transform_html_rules` 中文 5 规则；`paragraph_type=off`、`preserve_spaces=True`、`inline_toc=False`、`heading_anchors=False` 等 |
| E8 | 用户删除 EPUB/MD 后仅 TXT 转换 | 仍输出 `## 第1卷`（规则来自逐书设置，与 EPUB 无关）——证伪「EPUB 输入优先级」假设 |

### 研究过程中的两个错误假设（记录备查）

1. **假设「EPUB 输入优先级导致」**：书 919 同时有 EPUB/TXT/MD，曾判断
   calibre 默认选 EPUB 作为输入。E8（删 EPUB 后 TXT 依旧出 `##`）证伪。
2. **假设「calibre 内建启发式不支持中文 ⇒ TXT 必无标题」**：结论方向正确
   （内建启发式确实无中文模式、E4/E5 实测 0 标题），但忽略了用户侧
   `transform_html_rules` 的存在——「整条链路」上标题可来自用户规则。
   教训：分析完整管线时必须核对**逐书转换设置**（`load_specifics`），
   转换对话框 OK 即按书保存快照。

## 5. 实用指南

- **查看/编辑规则**：转换书籍 → 外观（Look & feel）→ 转换 HTML。
  注意规则快照按书保存：改全局默认不会自动改旧书的快照。
- **想要自定义层级**（部→#、卷→##、章→###）：维护对应规则即可，无需改输出插件。
- **CLI**：`--transform-html-rules <file>`、`--formatting-type heuristic/markdown`、
  `--enable-heuristics`、`--markup-chapter-headings`。
- **想要 TXT 自动识别中文标题**：calibre 原生做不到；可行方向是预处理 TXT 为
  Markdown（`#` 数量即级别），或在输入侧增加中文标题识别辅助。

## 6. 附录：源码索引（calibre 9.x）

| 位置 | 内容 |
|---|---|
| `calibre/ebooks/conversion/plugins/txt_input.py` | TXT 输入插件：格式/段落探测、heuristic 选项置位 |
| `calibre/ebooks/txt/processor.py` | `detect_formatting_type`（阈值 >5）、`convert_basic`（全 `<p>`） |
| `calibre/ebooks/conversion/utils.py` | `HeuristicProcessor.markup_chapters`（英文模式表、min/max 门槛）、`chapter_head`（h2/h3 固定标注） |
| `calibre/ebooks/conversion/preprocess.py` | 启发式阶段入口（`enable_heuristics` → `HeuristicProcessor(html)`） |
| `calibre/ebooks/conversion/plumber.py` | `markup_chapter_headings` 选项、`transform_html_rules` 执行点（Running transforms 阶段） |
| `calibre/ebooks/html_transform_rules.py` | `transform_conversion_book`：规则对 OEB 的应用 |
| `calibre/gui2/convert/look_and_feel.*` | 转换对话框「转换 HTML」规则编辑器 |
| `calibre/ebooks/conversion/config.py` | 逐书设置 `load_specifics` / 保存分组 |

本插件侧：`plugin/Markdown/markdownml_enhanced.py`（`_dump_heading` 的 h1-h6 映射
与 `heading_anchors`）、`plugin/Markdown/markdown_helpers.py`（`apply_paragraph_style`
的标题前空行/围栏保护）。
