# 「Markdown 输入」转换面板：设计、实证与验收（v3.3.0）

日期：2026-09-18
插件版本：3.2.0 → 3.3.0
交付：转换对话框（输入格式为 MD 时）新增「Markdown 输入」面板 + 4 个输入侧新行为

## 1. 目标与结论

| 需求 | 落地 |
|---|---|
| 输入源为 MD 时出现「Markdown 输入」面板 | `MarkdownInput.gui_configuration_widget()` 返回 `input_ui.PluginWidget`（此前返回 None：输入格式选 MD 时其实**没有任何面板**） |
| 常规：输入字符编码（含自动） | 绑定 calibre 既有选项 `input_encoding`，用 `EncodingComboBox`（第 0 项空 = 自动探测） |
| 常规：换行符样式 | **改为「单换行处理方式」**：折叠为空格（默认）/ 硬换行 `<br>`；原因是「读取时统一换行」实测对输出零影响（§3.1） |
| markdown：段落样式 auto/block/single/print | 绑定 `paragraph_type`；**显式选择会生效**（auto 保持 calibre 对 .md 的 `off`） |
| markdown：读取 YAML 文首元数据 | 新增 `read_yaml_metadata`（默认开）；开 = 读入元数据（含 language），关 = 从正文剥离 |
| 扩展：勾选网格 | 绑定 `markdown_extensions`；15 项 = calibre 的 17 项去掉 `meta`（归 YAML 开关）与 `nl2br`（归单换行） |

面板提交名 `markdown_input`，与内置 TXT 面板的 `txt_input` 分开存储，互不覆盖。

## 2. 面板结构与绑定

```
Markdown 输入（页签标题，ICON = mimetypes/txt.png）
├─ 常规
│   ├─ 输入字符编码：  EncodingComboBox      → input_encoding（calibre common option）
│   └─ 单换行处理：    下拉（折叠/硬换行）    → md_line_break（新增）
├─ Markdown
│   ├─ 段落样式：      下拉 auto/block/single/print → paragraph_type
│   └─ ☑ 读取 YAML 文首元数据                → read_yaml_metadata（新增）
└─ 扩展
    └─ 勾选列表（15 项）                      → markdown_extensions
```

三个实现要点：

1. **面板挂载**：calibre 的转换对话框会问输入插件要面板（`gui2/convert/single.py:244`），而基类实现按 `name` 去找 `calibre.gui2.convert.markdown_input`（不存在）→ 返回 None。我们覆写 `gui_configuration_widget()` 直接返回自建面板（与输出侧同一套路）。面板用纯 Qt 从零搭（3 个 QGroupBox），不依赖 calibre 的 `.ui`，避免输出面板那种"删行/插行"的脆弱做法。
2. **段落样式显式生效**：TXT Input 对 `.md` 会强制 `paragraph_type='off'`（`txt_input.py:226`），会静默丢弃面板选择。用一个 options 代理在 `super().convert()` 期间只把 `paragraph_type` 的写入钉回用户选择，其余读写全部转发真实 opts——管线其它阶段看到的仍是真实对象。
3. **输入流前处理**：`convert()` 先读原始字节 → （按需）归一化/剥离 YAML 块 → 包装成带 `.name` 的 `_ReplayStream` 交给父类；既有的图片兜底与 calibre 原有行为不变。

## 3. 实证发现（都改了实现，不是猜测）

### 3.1 「读取时统一换行」是空操作 → 换成单换行控制

同一内容分别以 LF / CRLF / CR / 混合换行写四份 .md，各自转 EPUB，正文**逐字节相同**
（探针 `scripts/probe_input_newline_effect.py`）。原因：TXT Input 解码后必定调用
`normalize_line_endings()`，把换行统一成 `\n` 再解析。因此该控件改为真正有可见效果的
「单换行处理方式」，映射 python-markdown 的 `nl2br` 扩展（扩展网格里不再重复出现 nl2br）。

### 3.2 python-markdown 的 meta 扩展读不了 YAML 列表

你给的标准 YAML：

```yaml
tags:
  - 出版
  - 玄幻
description: 简介
```

实测（`probe_meta.py`）会**漏进正文**：`<ul><li>出版</li><li>玄幻 description: 简介</li></ul><hr/>`，
同时 `tags` 得到空值。原因是 meta 扩展只认 `key: value` 行与 **4 空格**续行，2 空格列表
不是续行 → 解析提前结束，剩余文本按 Markdown 渲染。而**重复 key 是有效的**：

```
tags: 出版
tags: 玄幻        →  mi.tags == ['出版', '玄幻']
```

所以输入时把 YAML 列表归一化成重复 key（`normalize_yaml_front_matter()`）：
- `tags:` + `  - x` → `tags: x`（首项替换掉那个空值行，避免产生空 `<dc:subject>`）
- 该归一化同时修好了**本插件自身导出的 MD 的往返**（输出侧写的就是这种列表形式）

### 3.3 meta 扩展不认 `description`，calibre 只映射 `comments`/`summary`

`convert_markdown_with_metadata()` 的映射键是 `title authors series tags pubdate
comments publisher rating`——`description` 会被静默丢弃（而本插件输出侧写的正是
`description`）。归一化时把 `description` **别名成 `comments`**，往返即可带上简介。

### 3.4 语言：calibre 会先补一个界面语言兜底，YAML 必须覆盖它

HTML Input 在语言缺失时会写入 `get_lang()`（实测 `zh-CN`）。若沿用"仅当没有语言时才补"
的策略，YAML 里的 `language:` 永远不会生效。改为：YAML 声明了语言就 `clear + add` 覆盖；
**书库元数据在管线更晚的阶段合并，仍然优先**（GUI 单本转换时以书库为准）。

另注：calibre 写 OPF 时会把 `zho` 归一成 `zh`（抽查库内 879 本 EPUB 全是 `zh`），
所以验收用 `language: eng` 这种与界面语言不同的值来证明「语言确实来自 YAML」。

### 3.5 默认扩展值调整（行为变更）

calibre 默认 `footnotes, tables, toc`，但本插件导出的 MD 还会写围栏代码块、定义列表与
`{#slug}` 标题锚点；缺 `fenced_code` / `def_list` / `attr_list` 时这些会以**字面文本**进入
EPUB。新默认：`footnotes, tables, fenced_code, def_list, attr_list, toc`。
已保存的逐书转换设置（旧默认）仍会覆盖该默认值，需要用户在面板里重新勾选一次。

## 4. 验收

单元测试：`.venv/bin/python -m pytest plugin/tests -q` → **190 passed**
（新增 `test_input_pane.py` 15 项；`test_markdown_input.py` 扩到 47 项，覆盖 YAML 解析/归一化/
代理/换行调和/convert 流程）。

真机验收 `scripts/verify_md_input_pane.py`（calibre-debug）：

| 项 | 结果 |
|---|---|
| 面板实例化（真实 QApplication + Plumber）：标题/提交名/选项清单/控件齐全 | PASS |
| YAML 开：title=尘缘测试、subjects=[出版, 玄幻]、description、正文无 YAML 残留 | PASS |
| YAML 关：不写元数据、正文无残留 | PASS |
| YAML 语言：`language: eng` → OPF `en`；关闭时回落界面语言 `zh` | PASS |
| 单换行：fold 无 `<br>`、hard 有 `<br>` | PASS |
| 段落样式：auto 1 个 `<p>` vs single 8 个 `<p>` | PASS |
| 输入编码：gbk 正确、latin1 乱码（证明选项生效） | PASS |
| 往返：锚点/围栏代码/表格/定义列表默认可读，`{#第一章}` 无字面残留 | PASS |

回归 `scripts/verify_md_to_epub_images.py`（图片打包 + 输出方向）→ 6 项 PASS。
该脚本已改为自包含样本：书目录的 MD/图片是用户数据（本次就跑出一次假回归——用户重新
导出后 MD 不再含图片引用），现在脚本自己从书目录 `images/` 挑一张图、自己搭 CLI 样本、
自建 md→epub→md 验证输出方向。

## 5. 已知边界

- **批量转换（bulk）不读取该面板保存的"默认值"**：calibre 对外部插件的回退查找要求
  `calibre_plugins.<pkg>.<name>.<name>` 子包形式的模块路径，我们是扁平模块（实测
  `config_widget_for_input_plugin` 返回 None）。单本转换、按书保存的设置、CLI 都正常。
- YAML 只处理**文首块**（首个 `---` 到下一个 `---`/`...`）；块标量（`description: |`）与
  更复杂结构仍会按原样交给 meta 扩展（可能漏进正文），需要时再扩。
- 非 ASCII 兼容编码（UTF-16）的 YAML 块：归一化按字节做，识别不到分隔行时不处理（保持原行为）。

## 6. 文件清单

| 文件 | 动作 |
|---|---|
| `plugin/Markdown/markdown_input.py` | 新增 4 个选项、YAML 归一化/剥离/语言、段落代理、流包装、`gui_configuration_widget()`；3.3.0 |
| `plugin/Markdown/input_ui.py` | **新增**：转换对话框面板（纯 Qt，三组控件） |
| `plugin/Markdown/i18n.py` | 面板标题/组名/字段/15 个扩展描述与 4 条选项帮助（中英） |
| `plugin/Markdown/markdown_output.py`、`__init__.py` | 版本 3.3.0、发布日 2026-09-18 |
| `plugin/tests/test_input_pane.py` | **新增** 15 项（取值联动 + 面板/选项/扩展清单守护 + i18n） |
| `plugin/tests/test_markdown_input.py`、`test_plugin_entry.py`、`conftest.py` | YAML/代理/换行/流程单测与桩扩展、版本断言 |
| `scripts/verify_md_input_pane.py` | **新增**：面板与新选项真机验收 |
| `scripts/probe_input_newline_effect.py` | **新增**：换行影响探针（证明统一换行是空操作） |
| `scripts/verify_md_to_epub_images.py` | 改为自包含样本（不再依赖库里书的内容） |
