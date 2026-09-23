# MD → EPUB 图片丢失：根因与修复（输入插件方案）

日期：2026-09-17
插件版本：3.1.0 → 3.2.0
实证样本：calibre 书库《尘缘》（book id 919，烟雨江南；EPUB/MD/TXT 三格式，
书目录内含 `images/1.jpg`，MD 第 2 行为 `![背景图](images/1.jpg)`）
环境：calibre 9.14.0 (macOS)、Markdown 插件（输出 + 新增输入）

## 1. 结论摘要（TL;DR）

1. **markdown 语法本身解析正常**。实测 EPUB 内是
   `<p><img alt="背景图" src="images/1.jpg"/></p>`（不是原文文本）；
   丢失的是**图片文件本身**——EPUB 里没有任何 `images/` 条目。
2. **根因是「转换现场」与「图片现场」分离**：calibre 的 GUI 单本/批量转换先把
   书格式文件**复制到一个孤立临时目录**再转换
   （`gui2/tools.py`：`PersistentTemporaryFile('.' + fmt)` + `copy_format_to`），
   于是 `.md` 离开了书目录里的 `images/`。calibre 的文本输入管线只会在
   **输入文件所在目录**里解析相对图片引用，找不到就原样保留路径；随后的
   HTML→OEB 阶段又只允许引用转换工作目录（cwd）内的文件，图片因此进不了
   manifest，最后被 "Trimming unused files from manifest" 清掉。
3. **修复**：新增 **`MarkdownInput` 输入插件**（`file_types = {'md','markdown'}`），
   继承内置 TXT Input 的全部 markdown 处理，只在资源解析前多做一件事——用
   GUI/批量转换注入的 metadata opf（含 calibre uuid）**反查书库书目录**，把
   书目录里存在、输入目录里缺失的图片补齐到输入目录，交给内置逻辑正常打包。
4. **一个 zip 只能暴露一个插件类**（calibre `customize/zipplugin.py` 取
   `plugin_classes[0]`），所以输入插件不能在包 `__init__.py` 里作为第二个
   Plugin 子类出现；改为 `MarkdownOutput.initialize()` 在插件初始化时
   **运行时注册**（并让它在输入插件表里排到内置 TXT Input 之前）。
5. **无法解析的图片引用不再静默丢失**：转换日志给出 WARNING（数量 + 示例），
   便于用户/开发者定位。
6. 验收：单元测试 133 passed；真实书库端到端 6 项全 PASS（见 §5）。

## 2. 复现与证据（书 919）

| 场景 | 输入现场 | 转换结果（EPUB 内部） |
|---|---|---|
| `isolated`（模拟 GUI：单文件复制到临时目录） | 临时目录里只有 `.md`，书目录 `images/` 不在 | **0 个图片条目**；XHTML 为 `<img alt="背景图" src="images/1.jpg"/>`（死链） |
| `inplace`（CLI：md 留在书目录） | `.md` 与 `images/` 同目录 | `1.jpg`（1.38 MB）正常打包；XHTML 为 `<img alt="背景图" src="1.jpg"/>` |

两种场景的差异只在「图片能不能被输入阶段找到」，markdown 解析行为完全一致。

### 管线四段（calibre 9.x 源码）

1. **GUI/批量复制单文件**：`gui2/tools.py:65-69`（单本）、`:206-208`（批量）
   ```python
   in_file = PersistentTemporaryFile('.' + d.input_format)   # 随机名 .MD
   db.copy_format_to(book_id, input_fmt, in_file, index_is_id=True)
   ```
   只复制格式文件本身，**书目录里的 `images/` 不跟随**。
2. **TXT Input 的 markdown 路径**（`ebooks/conversion/plugins/txt_input.py`）：
   扩展名 `.md` 强制 `formatting_type='markdown'`、`paragraph_type='off'`，
   python-markdown 解析成 HTML 后调用
   `fix_resources(html, base_dir)`（`base_dir = dirname(stream.name)` = 临时目录）
   尝试把相对图片 shift 到 cwd；**图片不存在 → 不改写、不报错**，`src` 保持
   `images/1.jpg`。
3. **HTML Input 的资源收集**（`ebooks/conversion/plugins/html_input.py`）：
   `index.html` 被 shift 到 cwd，`root_dir_of_input = cwd`；
   `resource_adder` 对 `images/1.jpg` 找不到可读文件，直接保留原链接。
4. **manifest 清理**：没有任何 manifest 项指向图片 →
   `Trimming unused files from manifest` → EPUB 无图片。

### 为什么 CLI 正常、GUI 不正常

CLI（`ebook-convert`）直接以书目录里的 `.md` 为输入，`base_dir` 就是书目录，
第 2 步立刻命中并打包。GUI/批量走第 1 步的「复制单文件」，第 2 步必然落空。

## 3. 修复设计

### 3.1 书库反查（`markdown_library.py`）

- 抽出 `_identify_by_uuid_and_title(api, uuids, title)`（uuid 优先、唯一书名回退、
  uuid 命中但标题不符即放弃——沿用输出侧既有裁定）。
- 新增 `resolve_book_dir_for_options(opts, log)`：输入插件拿得到、但输出插件
  拿不到的入口是 **`opts.read_metadata_from_opf`**（GUI/批量转换注入，含 calibre
  uuid 与书名）；用 `_opf_identity()` 解析后走与输出侧相同的只读开库 → 书目录。
  CLI 不注入 opf，此时输入文件就在书目录里，返回 None 是正确结果。

### 3.2 输入插件（新文件 `markdown_input.py`）

```python
class MarkdownInput(TXTInput):          # 内置 TXT Input 的子类
    file_types = {'md', 'markdown'}     # 不碰 txt/textile/txtz
    priority = 2                        # 高于内置（默认 1）

    def convert(...):                   # 先反查书目录，再交给内置实现
        self._book_dir = resolve_book_dir_for_options(options, log)
        return super().convert(...)

    def fix_resources(self, html, base_dir):
        self._stage_library_images(html, base_dir)   # 补齐缺失图片
        return super().fix_resources(html, base_dir)
```

`_stage_library_images` 的边界规则：

- 只处理**本地相对引用**；远端 URL / `data:` / 绝对路径 / 含 `..` 的路径一律不碰
  （不由本插件判断，交回内置逻辑）。
- 输入目录里已存在同名文件 → 不动（保留内置的路径安全检查与命名行为）。
- 书目录里按 `book_dir/引用路径`、`book_dir/basename(引用)` 两个候选查找；
  找到则 `copy2` 到输入目录对应相对位置。
- 两边都找不到 → 汇总一条 WARNING（去重，最多列 5 个示例）。

### 3.3 插件注册（一个 zip 只能有一个插件类）

calibre 的 `customize/zipplugin.py` 只取包模块 `plugin_classes[0]`——同一 zip 里
第二个 Plugin 子类会**遮蔽**输出插件。因此：

- 包 `__init__.py` 仍然只暴露 `MarkdownOutput`（顶层的 Plugin 子类唯一）；
- `MarkdownOutput.initialize()`（calibre 插件的标准初始化钩子）调用
  `register_markdown_input_plugin()`：
  - 幂等（已注册则跳过）；
  - `is_disabled()` 判断 → 用户禁用「Markdown Input」后回落内置 TXT Input；
  - 注册时**前插**到插件表，且 `priority = 2`，确保
    `plugin_for_input_format('md')` 返回本插件（内置 TXT Input 也声明 `.md`）。

## 4. 行为变化

- 安装后（重启 calibre）：**GUI/批量转换 `.md` → EPUB 时，书库书目录里的
  `images/` 会被带入 EPUB**；CLI/`inplace` 场景行为不变（本来就正常）。
- 首选项 → 插件里新增「Markdown Input」条目（安装类型：外部），可禁用。
- 转换日志：图片在输入目录与书库中均找不到时输出 WARNING
  （英文界面：`Markdown: N image reference(s) could not be found ...`；
  中文界面：`Markdown：有 N 个图片引用……输出将不包含这些图片：…`）。
- 输出方向（EPUB → MD）与 `.txt` 输入完全不受影响（验收已覆盖）。

## 5. 验收

单元测试：`.venv/bin/python -m pytest plugin/tests -q` → **133 passed**
（新增 `test_markdown_input.py` 19 项、`test_markdown_library.py` 新增反查/opf 解析
8 项、`test_plugin_entry.py` 更新版本与「单插件类」守护断言）。

真实书库端到端（`scripts/verify_md_to_epub_images.py`，calibre-debug 运行）：

| 检查项 | 内容 | 结果 |
|---|---|---|
| `registry` | `plugin_for_input_format('md')` → `MarkdownInput` | PASS |
| `txt-plugin` | `plugin_for_input_format('txt')` → 仍是内置 `TXTInput` | PASS |
| `gui` | 复刻 GUI（孤立临时目录 + 注入 opf）转换书 919 → EPUB 内 `1.jpg` 打包、无死链 | PASS |
| `inplace` | CLI 场景（md 与 images 同目录）→ 图片正常 | PASS |
| `md-output` | `plugin_for_output_format('md')` 仍是 `MarkdownOutput`；EPUB→MD 正常出 sidecar | PASS |
| `missing-warn` | 引用不存在的图片 → 日志出现 WARNING（不再是静默丢失） | PASS |

修复前后对照（书 919，同一 isolated 场景）：修复前 `0` 个图片条目；
修复后 `['cover_image.jpg', '1.jpg']`。

## 6. 附录：本次踩到的坑

1. **calibre `Log.warn` 是实例属性**：`Log.__init__` 里
   `self.warn = self.warning = partial(self.print_with_flush, WARN)`，
   且 `print_with_flush` 直接遍历 `self.outputs`（不经过 `self.prints`）。
   后果：**子类覆写 `warn()` 或 `prints()` 都抓不到日志**；要捕获请给
   `log.outputs` 追加一个带 `prints(level, *args)` 的 sink 对象，或覆写
   `print_with_flush`（partial 在 `__init__` 时已绑定到覆写后的方法）。
2. **一个 zip 一个插件类**（`customize/zipplugin.py:322-331`）：第二个 Plugin
   子类会遮蔽原插件（按 `__module__` 点数排序取第一个）。多插件必须运行时注册
   或拆成多个 zip。
3. **输入插件拿不到 `book_id`/db**：GUI/批量转换唯一的书身份线索是注入的
   metadata opf（`opts.read_metadata_from_opf`），CLI 连它都没有——所以反查
   失败时的兜底只有「原行为 + 明确警告」。
4. **`Plugin.__call__` 会 chdir 并清空 plumber 的 tdir**
   （`customize/conversion.py:238-242`），所以 `fix_resources` 里
   `os.getcwd()` 是 plumber 临时目录，不是调用方的 cwd——图片 shift/打包都以
   该目录为根，反向验证脚本的 `os.chdir(work)` 对图片落地位置没有决定作用。
5. 书库反查沿用既有的**只读打开**（`LibraryDatabase(path, read_only=True)`）与
   「uuid 命中但标题不符即放弃」的裁定，避免把图片写错书。

## 7. 附：涉及文件

| 文件 | 动作 |
|---|---|
| `plugin/Markdown/markdown_input.py` | **新增**：`MarkdownInput` + `register_markdown_input_plugin()` |
| `plugin/Markdown/markdown_library.py` | 新增 `_opf_identity` / `resolve_book_dir_for_options`，抽出 `_identify_by_uuid_and_title` |
| `plugin/Markdown/markdown_output.py` | 新增 `initialize()`（注册输入插件）；版本 3.2.0 |
| `plugin/Markdown/__init__.py` | 保持只暴露 `MarkdownOutput`（注释说明约束）；3.2.0 |
| `plugin/Markdown/i18n.py` | 新增「图片未找到」中英文案 |
| `plugin/tests/test_markdown_input.py` | **新增** 19 项单测 |
| `plugin/tests/test_markdown_library.py` / `test_plugin_entry.py` / `conftest.py` | 补反查与注册单测、桩扩展、版本与单插件类断言 |
| `scripts/verify_md_to_epub_images.py` | **新增**：端到端验收（6 项） |
| `scripts/probe_book_919.py` | **新增**：书库/书目录探查 |
