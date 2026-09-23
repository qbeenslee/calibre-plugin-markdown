# MD 输入「段落样式：自动检测」失效的排查与修复（v3.4.0）

日期：2026-09-18
插件版本：3.3.0 → 3.4.0
触发：书库《尘缘》(id 919) 的 `尘缘 - 烟雨江南.md` 是「每行一段」(single)，
面板「段落样式」设为「自动检测段落类型」后转出的 EPUB 段落被拼合。

## 1. 根因

「自动检测」= `paragraph_type='auto'`，但 **calibre 的 TXT Input 对 `.md` 强制
把它改成 `'off'`**，检测分支从不会执行：

```226:226:calibre/ebooks/conversion/plugins/txt_input.py
                options.paragraph_type = 'off'
```

```276:282:calibre/ebooks/conversion/plugins/txt_input.py
        if options.paragraph_type == 'auto':
            options.paragraph_type = detect_paragraph_type(txt)
```

于是：
- `detect_paragraph_type()` 只对 `.txt` 生效，`.md` 从不检测（v3.3.0 的
  「段落代理」只救回了显式选择，auto 的语义是「保持 calibre 的 off」）；
- 文本原样交给 python-markdown，而 Markdown 只在**空行**处断段。
  《尘缘》18046 行只有 95 个空行 → 整本书只剩 90 个 `<p>`（每章一个），
  正文全部被拼合。

## 2. 修复设计

新增 `plugin/Markdown/markdown_paragraphs.py`（calibre-free，可独立单测）：

**行分类** `classify_lines()` → `BLANK` / `BODY` / `BLOCK`

- `BLOCK` 是「跨行才有意义」的结构，**永不拆散**：围栏代码块（含未闭合）、
  缩进代码块、列表（含缩进续行）、引用、表格（表头+分隔行+行）、ATX 标题、
  水平线、行首 HTML、脚注定义，以及 setext 下划线 / 定义列表 `:` 行
  「连同上一行一起」保护（`_protect_previous`）。
- 其余非空行为 `BODY` —— 只有它们会被重排。

**自动检测** `detect_paragraph_type()`：

| 样式 | 判据 |
|---|---|
| `print` | body 行中以「全角空格 / 2–3 个半角空格」开头的 ≥2 行且占比 ≥20% |
| `single` | 相邻两行都是 body（中间无空行）的 body 行占比 ≥50% |
| `block` | 其余，以及 body 行不足 10 行（样本太小，不改写） |

**重排** `restructure_paragraphs()`（幂等）：

- `single`：每个 body 行后补空行（标题行同样补，让后续内容不与标题粘连）；
- `print`：每个缩进 body 行前补空行（段内软换行留在同一段）；
- 其它样式原样返回 = Markdown 原生语义。

接入点在 `MarkdownInput._prepare_stream()`：读字节 → 处理/剥离 YAML →
**解码（按 input_encoding，缺省用 calibre 的 chardet 探测，含 gb2312→gbk 与 BOM 剥离）**
→ 检测 → 重排 → 以 UTF-8 交回并设置 `options.input_encoding='utf-8'`。
无需改写的路径**原字节返回**，行为与既有完全一致；任何异常都退回原字节。

**显式选择一并改为 Markdown 感知**：single / print / unformatted 直接按上表重排
（`unformatted` = 无空行无缩进的每行一段），block / off 不改写。原先为「钉住被
父类丢弃的显式值」而设的 `_ParagraphTypeOverride` 代理随之删除——重排在
TXT Input 之前完成，父类强制 `off` 恰好不再动文本。

## 3. 实证

### 3.1 检测算法在真实书库上的表现（8 本 MD）

| 书 | body 行 | tight 占比 | 缩进行占比 | 判定 |
|---|---|---|---|---|
| 尘缘 (919) | 17853 | 0.99 | 0.00 | single |
| 异界猎妈人 (1007) | 45372 | 0.99 | 0.00 | single |
| 献祭辣条… (793) | 26936 | 0.99 | 0.00 | single |
| 大学门卫老董 (17) | 11497 | 0.99 | 0.00 | single |
| 小镇上的熟母… (999) | 7607 | 1.00 | 0.00 | single |
| 一诺千精 (1005) | 5526 | 0.99 | 0.00 | single |
| 神明少女 (1017) | 4319 | 1.00 | 0.00 | single |
| 伊万卡… (246) | 127 | 0.99 | 0.00 | single |

合成样本：single→single、block→block、print→print；空行分段的标准 Markdown
（块间空行、段内换行）稳定判为 block。

### 3.2 修复前后对照（《尘缘》真实转换，calibre-debug）

| 场景 | `<p>` 数 | 说明 |
|---|---|---|
| 修复前（段落不改写） | **90** | 每章一个段落，正文全被拼合 |
| 修复后（auto 检测） | **17847** | 每行一段；`<h1..6>`=96、`<img>`=2、`dc:title=尘缘` |

抽查「青石不知从何而来，自亘古时起就已立于不二河畔。……」一句：修复后独占一个
`<p>`。转换日志可观测：

```
Markdown: paragraph style: single (auto detected), 17847 blank line(s) inserted
```

### 3.3 结构保护（auto 检测为 single 时）

代码块 / 表格 / 列表 / 引用 / 定义列表在重排后全部解析正常（`<pre>`、`<table>`、
`<li>`×2、`<blockquote>`、`<dl>/<dd>` 均出现），正文行照常独立成段。

## 4. 验收

- 单元测试：`.venv/bin/python -m pytest plugin/tests -q` → **215 passed**
  （新增 `test_markdown_paragraphs.py` 23 项；`test_markdown_input.py` 改/增
  auto 检测、显式样式、编码、GBK→UTF-8 等用例）。
- 真机 `scripts/verify_md_paragraph_auto.py`（calibre-debug，4 项全 PASS）：
  book-919 / standard-markdown / structure-protected / print-style。
- 回归 `scripts/verify_md_input_pane.py` → 8 项全 PASS。
- 安装：`./install.sh`（`plugin/Markdown.zip` 16 条目，含新模块）。

## 5. 已知边界

- **段内软换行 + 段间空行**的 Markdown（英文小说常见的「一段 3 行」）会因
  tight 占比高被判为 single，段落被拆得更碎；需要原样时应显式选「块」。
- 行首缩进字符（全角空格）在 EPUB 中不保留——**对照实验**：标准 block 布局、
  不做任何重排时同样不保留，属 calibre 下游管线行为，与本次改动无关；
  print 检测保证的是分段正确。
- body 行不足 10 行不做检测（短文档维持原状）；4 空格/tab 行首是缩进代码块，
  不参与 print 判定。
- YAML 文首块不参与重排（只处理正文），关闭「读取 YAML 文首元数据」时按既有
  行为剥离。

## 6. 文件清单

| 文件 | 动作 |
|---|---|
| `plugin/Markdown/markdown_paragraphs.py` | **新增**：Markdown 感知的行分类 + 段落样式检测 + 重排 |
| `plugin/Markdown/markdown_input.py` | 接入检测（`_restructure_paragraphs`、`decode_body`）、删除段落代理、帮助文本；3.4.0 |
| `plugin/Markdown/i18n.py` | 段落样式选项帮助（中英）更新 |
| `plugin/Markdown/__init__.py`、`markdown_output.py` | 版本 3.4.0 |
| `plugin/tests/test_markdown_paragraphs.py` | **新增** 23 项 |
| `plugin/tests/test_markdown_input.py`、`conftest.py`、`test_plugin_entry.py` | 流程用例改写、chardet 桩、版本断言 |
| `scripts/verify_md_paragraph_auto.py` | **新增**：真机验收（含 919 真实书） |
