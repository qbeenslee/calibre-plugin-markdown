# calibre Markdown 插件

让 Markdown 成为 calibre 的一等公民：**电子书 → Markdown**（输出格式 `md`），以及 **Markdown → 电子书**（输入格式 `md` / `markdown`，自动回填书库图片）。

- 当前版本：`3.20.7`（以 `plugin/Markdown/__init__.py` 的 `PLUGIN_VERSION` 为准）
- 依赖：calibre ≥ 6.0.0（macOS / Windows / Linux）
- 许可：GPLv3

## 用途

calibre 自带的 TXT 输出只能写出 Markdown 的骨架：图片要自己收拾、目录链接点不开、元数据得手写；反过来把 `.md` 转回 EPUB 时，内置的 TXT 输入既找不到 `.md` 旁边的插图，也不认 YAML 文首元数据。

本插件补齐这两条路，并且不比 calibre 多出一套入口——输出侧就是一个普通的 `OutputFormatPlugin`，转换对话框、批量转换、`ebook-convert`、保存/发送模板全部原生可用。

| 方向 | 插件 | 说明 |
|---|---|---|
| 电子书 → Markdown | `Markdown Output`（输出格式 `md`） | 走 calibre 原生转换通道，含图片、目录锚点、YAML 元数据、段落风格等治理 |
| Markdown → 电子书 | `Markdown Input`（输入格式 `md` / `markdown`） | 覆盖内置 TXT Input（priority 2），解析 YAML 元数据并回填书库里的图片 |

## 特性

### 输出：电子书 → Markdown

<img src="https://github.com/qbeenslee/calibre-plugin-markdown/blob/master/docs/assets/markdown-output-conversion-zh-CN.png?raw=true" width="800px" height="auto">

<img src="https://github.com/qbeenslee/calibre-plugin-markdown/blob/master/docs/assets/markdown-output-diy-plugin-zh-CN.png?raw=true" width="500px" height="auto">

**Markdown 文本**

- 文首目录（`inline_toc`）与标题锚点 `{#slug}`（`heading_anchors`）默认打开，目录里的链接可直接跳转。
- 段落风格（`paragraph_style`）：`block`（标准 Markdown，空行分段）或 `single`（每行一段，不写空行，适合网文/逐行素材）；`single` 下可选择标题前补空行（`blank_line_before_heading`）。
- 代码围栏与语言标注、表格、定义列表、引用块等结构保持原样，不因段落重排被拆散。
- 列表项的文字接在 `- ` 后面（书里用 `<p>` 包住条目文字也一样），条目里的第二个段落、引用或嵌套列表各占一行、缩进在条目下。
- 转义 Markdown 特殊字符（`escape_markdown_chars`）默认关闭：`第1卷 原版(By:苏梦枕)` 这类书名按原样写出；表格与 YAML 内部照常转义。
- 可选清除 PDF 页码行（`strip_pdf_page_markers`，如 `Page-12`）。
- 行宽（`max_line_length` / `force_max_line_length`，默认 0 即不折行）、换行符（`newline`，默认 unix）、输出编码（`txt_output_encoding`，默认 utf-8）。

**元数据**

- YAML 文首元数据（`yaml_front_matter`，默认开）：`title`、`authors`、`language`、`publisher`、`tags`、`series`、`series_index`、`isbn`、`pubdate`、`description`、`calibre_id`。
- GUI 转换只交回 EPUB 自身的 OEB 元数据，缺失的 calibre 字段（书号、系列等）通过一次只读书库反查补齐。

**图片**

- 保留图片引用（`keep_image_references`）、保留图片声明尺寸（`keep_image_sizes`，写出为 `<img ... width height>`）、用 alt 文本替换图片（`use_alt_text_for_images`）、导出封面页（`export_cover_page`）。
- 图片落地模式（`image_output_mode`）三选一：
  - `sidecar`（默认）：库内转换写进书籍目录 `images/`（Markdown 里的 `images/x.png` 直接可用）；CLI / 指定路径时写到 `<md 名>.images/` 并把引用重写过去。
  - `inline`：转成 base64 data URI 内联，Markdown 自包含、可单文件搬走。
  - `none`：不导出图片。
- 下载远程图片（`download_remote_images`）：Markdown 引用的 http(s) 图片在导出时一并落地/内联，失败的保留原 URL 并在转换报告里告警。
- 只写出 Markdown 真正引用到的图片，未被引用的图片不会落盘，也不会凭空建目录。

### 输入：Markdown → 电子书

<img src="https://github.com/qbeenslee/calibre-plugin-markdown/blob/master/docs/assets/markdown-input-conversion-zh-CN.png?raw=true" width="800px" height="auto">

<img src="https://github.com/qbeenslee/calibre-plugin-markdown/blob/master/docs/assets/markdown-input-diy-plugin-zh-CN.png?raw=true" width="600px" height="auto">


- **书库图片回填**：GUI 与批量转换会把书复制到临时目录再转换，`.md` 旁边的插图因而失联。插件用注入的元数据 opf 取 calibre uuid，只读反查书库中的书籍目录，把图片复制到输入目录，交回内置资源处理嵌入；`images/`、`assets/`、`media/` 等任意同级目录都算数。
- **URL 转义文件名**：`assets/%E3%80%90.jpg` 这类写法会先解码再查找，并把引用重写为解码后的路径；找不到的引用写入转换报告告警，不会静默丢失。
- **YAML 文首元数据**（`read_yaml_metadata`，默认开）：读取 `title` / `authors` / `language` / `tags` / `description`；列表形式归一化成 calibre 能读的写法，`description` 映射为 `comments`，`language` 覆盖 calibre 补的界面语言。
- **段落风格**（`paragraph_type`）：`auto`（默认，从文本自动识别）、`block`、`single`、`print`（缩进起段）。重排是 Markdown 感知的：不拆代码块、列表、表格，引用块保持为一块，其内部各行成为引用里的段落。
- **单行换行**（`md_line_break`）：`fold`（默认，标准 Markdown 折行）或 `hard`（每个换行变成 `<br>`，nl2br）。
- **图片开关**：保留图片（主开关）→ 图片尺寸 / 嵌入本地图片 → 下载远程图片（逐级门控，关闭上层则下层置灰，置灰只是提示、不锁值）。
- **python-markdown 扩展**复选框（`abbr`、`admonition`、`attr_list`、`codehilite`、`def_list`、`extra`、`fenced_code`、`footnotes`、`legacy_attrs`、`legacy_em`、`sane_lists`、`smarty`、`tables`、`toc`、`wikilinks`）；默认值与输出侧写出的语法对齐（`footnotes, tables, fenced_code, def_list, attr_list, toc`），自己产出的 `.md` 能原样读回。
- **输入编码**（`input_encoding`）默认自动检测（GB2312 系归一成 gbk）。

### 界面

- 插件自己的文案跟随 calibre 界面语言（中文 / 英文两套表），选项的 tooltip 一并翻译。
- 转换面板按选项分组（General / Markdown / Images / Extensions），逐项都有帮助说明。

## 安装

### 方式一：安装 `Markdown.zip`

取得 `Markdown.zip`：从本仓库的 Releases 下载，或按下方「构建」一节自行打包（仓库不提交构建产物）。

```bash
# 命令行安装
calibre-customize -a Markdown.zip

# macOS 的 calibre 命令行工具位于
# /Applications/calibre.app/Contents/MacOS/calibre-customize
```

也可以走图形界面：**首选项 → 插件 → 从文件加载插件**，选择 `Markdown.zip`，然后**重启 calibre**。

### 方式二：源码一键安装（macOS）

```bash
git clone https://github.com/qbeenslee/calibre-plugin-markdown.git
cd calibre-plugin-markdown
./install.sh
```

`install.sh` 依次做三件事：调用 `python3 plugin/build.py` 打包、把 `plugin/Markdown.zip` 复制到 `~/Library/Preferences/calibre/plugins/Markdown.zip`、按字节数校验复制结果。完成后重启 calibre。

其他平台手工安装（把 zip 放进 calibre 的插件目录）：

```bash
python3 plugin/build.py
cp plugin/Markdown.zip ~/.config/calibre/plugins/          # Linux
# Windows: %APPDATA%\calibre\plugins\
```

### 验证安装

- **首选项 → 插件**中搜索 `Markdown`，可见 `Markdown Output` 与 `Markdown Input` 两项，选中后**自定义插件**按钮可用。
- 打开**转换书籍**，输出格式下拉中出现 `Markdown`，选中后左侧出现 **Markdown output** 面板；输入 `.md` 文件时出现 **Markdown input** 面板。

## 构建

```bash
python3 plugin/build.py              # 打包 plugin/Markdown -> plugin/Markdown.zip
python3 plugin/build.py Markdown     # 只打包指定包（可接多个包名）
```

打包规则（`plugin/build.py`）：

- zip 顶层直接是 `__init__.py`，不带包名前缀；
- 必须包含内容为空的 `plugin-import-name-markdown.txt`，它决定插件模块导入名 `calibre_plugins.markdown`；
- 跳过 `__pycache__`、`*.pyc`、`*.pyo`、`.DS_Store`；
- 固定时间戳 + 临时文件原子替换，同样的源码产出同样的 zip。

维护须知：插件 zip 只能暴露一个 `Plugin` 子类（calibre 的 zipplugin 加载器只取第一个），因此 `__init__.py` 只导入 `MarkdownOutput`，输入插件 `MarkdownInput` 由 `MarkdownOutput.initialize()` 在运行时注册。

### 测试

```bash
python3 -m pytest plugin/tests -q              # 需自备 pytest
.venv/bin/python -m pytest plugin/tests -q     # 可选：本机虚拟环境
# 当前基线：450 passed
```

测试在纯 Python 下运行：`plugin/tests/conftest.py` 为 calibre 与 `qt.core` 注入桩，无需打开 calibre 桌面端。

## 更新

```bash
git pull
./install.sh            # 重新打包并覆盖安装（macOS）
```

其他平台：

```bash
git pull && python3 plugin/build.py
calibre-customize -a plugin/Markdown.zip    # 同名插件会被覆盖
```

或走图形界面：**首选项 → 插件 → 从文件加载插件**，再次选择 `Markdown.zip` 覆盖旧版。

覆盖安装后必须**重启 calibre**，插件代码与界面才会刷新；版本号可在**首选项 → 插件**里查看。

发布新版本时版本号需同步四处：`plugin/Markdown/__init__.py` 的 `PLUGIN_VERSION` / `PLUGIN_VERSION_TUPLE`、`output/output_plugin.py` 的 `MarkdownOutput.version`、`input/input_plugin.py` 的 `MarkdownInput.version`，以及 `plugin/tests/test_plugin_entry.py` 中的对应断言。

## 使用

**单本转换**：选中书籍 → **转换书籍** → 输出格式选 `Markdown` → 在左侧 **Markdown output** 面板按需调整 → 确定。

**批量转换**：选中多本书 → 批量转换 → 输出格式 `Markdown`（面板中的值即为本次使用的值）。

**命令行**：

```bash
ebook-convert book.epub book.md --image-output-mode sidecar
ebook-convert book.epub book.md --image-output-mode inline --paragraph-style single
ebook-convert book.md book.epub --paragraph-type auto --read-yaml-metadata
```

选项名即转换面板里的选项名（`--image-output-mode`、`--paragraph-style`、`--yaml-front-matter`、`--paragraph-type`、`--md-line-break` 等），
用 `ebook-convert in.epub out.md -h` 可列出某条转换路径的全部可用选项。

**设置分两层**：

1. **每本书**：转换对话框里的面板，值随该书的转换设置一起保存，下次转换同一本书时沿用。
2. **全局默认**：**首选项 → 插件 → Markdown Output → 自定义插件**（输入侧对应 `Markdown Input`）。勾选「覆盖」的项会成为各本书转换面板的初始值；面板里再改的值优先，不会被全局设置反压。

**图片落地提醒**：库内转换（GUI / 批量）在书籍目录下写 `images/`，calibre 的「检查书库」可能把这些文件列为 *Unknown files in books*，若执行「修复」会被删除。需要长期自包含的 Markdown 请改用 `inline` 模式，或转换后及时把 `.md` 与图片一起另存。

**`.md` → EPUB**：把 `.md` 与它的图片目录（`images/`、`assets/`…）放进书库书籍目录，或直接选择本地 `.md` 文件转换；插件会按 calibre uuid 只读回查书库补齐图片。

## 目录结构

```
plugin/
├── Markdown/                  插件包（= 安装 zip 的顶层）
│   ├── __init__.py            入口，只暴露 MarkdownOutput
│   ├── input/                 .md 输入插件、输入转换面板、段落重排
│   ├── output/                输出插件、输出转换面板、自定义界面、增强的 Markdown 生成
│   ├── utils/                 偏好读写、书库只读反查、图片与 Markdown 工具
│   ├── translations/          中英文文案表与界面语言检测
│   └── images/                转换面板图标
├── build.py                   打包脚本
├── tests/                     单元测试（calibre/Qt 桩）
└── Markdown.zip               构建产物（不入库）
install.sh                     打包 + 安装（macOS）
docs/specs/design.md           设计文档与实证记录
docs/reports/                  单项调研报告
```

## 文档

- `docs/specs/design.md`：插件从 GUI 工具栏入口重定位为输出格式插件的设计、实证依据与验收标准。
- `docs/reports/`：单项调研笔记，例如 Markdown → EPUB 的书库图片回填、TXT/Markdown 标题层级、输入转换面板、段落风格自动识别、界面语言跟随 calibre。

## 许可

GPLv3。输出实现基于 calibre 上游 `markdownml.py`（TXT Output）扩展，输入实现继承 calibre 的 TXT Input；转换面板、图片与元数据处理、书库反查等为本项目新增。
