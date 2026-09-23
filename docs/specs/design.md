# Markdown 输出插件重定位设计（v3.0.0）

日期：2026-09-17
状态：调研 + 实证完成，待实现

## 1. 背景与要解决的问题

当前插件以 `InterfaceActionBase`（GUI 工具栏入口）为主入口，输出插件 `MarkdownOutput`
只是内部实现（由 `convert_flow.convert_book_to_markdown()` 手工注入 Plumber）。后果：

1. **不能被 calibre 原生通道复用**：转换对话框的输出格式下拉、批量转换、命令行
   `ebook-convert`、保存/发送模板里都拿不到 Markdown。
2. **不走 calibre 的 job 机制**：`convert_flow` 自己拼临时文件 `.calibre_converting.txt`
   再 `os.replace()` 回 `.md`（因为 Plumber 要求 `.txt` 输出路径），绕开框架。
3. 用户心智成本高：要先点插件按钮、选书、选目录，而不是用 calibre 自带的「转换书籍」。

目标：把插件**重定位为单一 OutputFormatPlugin**（转换输出），删除 GUI 入口，
复用 calibre 全部原生通道；设置入口保留两处；图片按场景落地。

非目标（本次不动）：Markdown 文本质量（表格/TOC/代码围栏/YAML）、转换管线内部实现、
`markdownml_enhanced.py` 的排版规则、EPUB 等其他输出格式。

## 2. 决策摘要

| 主题 | 决策 |
|---|---|
| 插件类型 | 单一 `OutputFormatPlugin`（`file_type = 'md'`），删除 `InterfaceAction` 入口 |
| 版本 | 2.2.1 → **3.0.0**（破坏性变更：GUI 入口消失） |
| 设置入口 | 两处：①转换对话框「Markdown 输出」面板（逐本/默认，calibre 原生）；②首选项→插件→自定义插件（全局默认，**只对显式改过的项覆盖①**） |
| 图片落地 | 分场景：输出目标是真实路径 → md 旁边 `<md 名>.images/`；输出目标是 calibre 临时文件（库内转换）→ 反查书库，写进该书目录 `images/`；反查失败 → 跳过 + 日志告警 |
| 反查方式 | uuid 优先（`oeb.metadata.identifier` + `new_api.lookup_by_uuid`），书名+作者搜索回退 |
| 全局覆盖开关 | 自定义界面提供 `image_output_mode`：`sidecar`（默认）/ `inline`（base64 内联）/ `none`（不导出） |

## 3. 实证依据（已验证，不是推测）

探针脚本：`scripts/probe_output_ctx.py`（calibre-debug 运行，真实书库
`/Users/lachang/Documents/Books/calibre`，样本书 id 830）。

| 结论 | 证据 |
|---|---|
| 输出插件拿不到 book_id | `convert(self, oeb_book, output_path, input_plugin, opts, log)`；`gui2/convert/gui_conversion.py:60` 的 `gui_convert_override` 也无 book_id 参数 |
| GUI 单本/批量转换都注入含 calibre uuid 的 opf | `gui2/tools.py:87-88`（单本）、`gui2/tools.py:205,238`（批量 `create_opf_file`）；`gui2/convert/metadata.py:26` `mi.application_id = mi.uuid` |
| CLI 不注入 opf | 探针实测 `opts.read_metadata_from_opf is None` |
| **epub 内 `dc:identifier` ≠ calibre uuid** | 探针：epub 自带 `0347673a-...`，库里该书 uuid `994189ad-...` → 读 OEB identifier 查不到，必须靠注入 opf 或书名回退 |
| 书库路径可读 | `calibre.library.current_library_path()` → `/Users/lachang/Documents/Books/calibre` |
| 只读打开书库可行且快 | `LibraryDatabase(path, read_only=True)`；877 本书 **0.04s** |
| uuid → book_id 可行 | `db.new_api.lookup_by_uuid(uuid)` 往返自检通过 |
| 书名回退可行 | `db.new_api.search('title:"灰雾：余火重燃"')` → `{830}`（**返回 set**，需 `sorted()`） |
| book_id → 路径的坑 | legacy `db.format_abspath(id, fmt)` 默认 `index_is_id=False`，把 id 当**行索引**（实测 830 返回了第 830 条记录的书）。必须用 `db.new_api.format_abspath(book_id, fmt)` |
| 库内转换输出是临时文件 | `gui2/tools.py:71,210` `PersistentTemporaryFile('.' + fmt)`；判定基准 `calibre.ptempfile.base_dir()` |
| 自定义界面保存链路（坑） | `customize/__init__.py:191-214`：插件自己实现 `config_widget()` 时，OK 后**只**调 `save_settings()`，不像默认分支那样调 `customize_plugin()` → **`save_settings()` 必须自己持久化** |
| 插件列表 Customize 按钮 | `gui2/preferences/plugins.py:398` `plugin.do_user_config()`，依赖 `plugin.is_customizable()` |

## 4. 架构

### 4.1 插件入口（`plugin/Markdown/__init__.py`）

zip 顶层即本文件（build.py 以 `plugin/Markdown` 为包根打包）。重定位后 zip 内
**只暴露一个 Plugin 子类**：`MarkdownOutput`。

- 删除 `InterfaceActionBase` 子类、`actual_plugin`、`icon`（输出插件无 UI 图标）。
- 删除 `is_customizable()` 返回 False 的旧覆写（改由 `MarkdownOutput` 自己返回 True）。
- 版本同步 3 处：`PLUGIN_VERSION_TUPLE`、`PLUGIN_VERSION`（本文件）+
  `MarkdownOutput.version`（`markdown_output.py`）。
- 待验证假设（实施第 1 步冒烟）：calibre 通过扫描插件模块的 `__dict__` 收集 `Plugin`
  子类，模块级 `from ... import MarkdownOutput` 应能被识别为「转换输出」插件。
  若不能，则改为在 `__init__.py` 内直接 `class MarkdownOutput(...)` 定义。

### 4.2 设置：两处入口 + 优先级

**① 转换对话框**（`ui.py` 的 `PluginWidget`）保持现状，值走 calibre 的 recommendations
（`OptionRecommendation.LOW`），随「转换设置」保存/复用；CLI 同源（选项名即 `--xxx`）。

**② 自定义插件界面**（`dialogs.py` 改造）：

- `MarkdownOutput.is_customizable()` → `True`
- `config_widget()` → 返回由 `MarkdownExportDialog` 改造的 `ConfigWidget(QWidget)`
- `save_settings(config_widget)` → 序列化后调 `calibre.customize.ui.customize_plugin(self, json)`
  （**必须自己持久化**，见 §3 坑）
- 读取一律用 `calibre.customize.ui.plugin_customization(self)`，不依赖
  `self.site_customization` 是否已被填充（preferences 进程里不一定有值）
- JSON 结构：`{"version": 1, "overrides": {"yaml_front_matter": false, "image_output_mode": "inline"}}`
  （**不含** `ui_language`：界面语言继续用插件私有 `prefs.json`，避免双写）
- 语义：`overrides` **只存用户显式勾选「覆盖」的项**。每项 UI = 「启用全局覆盖」复选框 +
  值控件（默认不勾选 → 不进 overrides → 跟随转换对话框/CLI）。
- 生效点：`MarkdownOutput.convert()` 开头，把 `overrides` 逐键 `setattr` 到最终 `opts`。
  理由：此时 opts 已由 plumber 定型（含 GUI recommendations、CLI 参数），覆盖即最终值；
  且 CLI/GUI/批量/服务器全场景都经过 `convert()`。不用 `specialize_options`
  （`plumber.py:1256` 只调一次，语义是「按输入格式给推荐值」，不适合做用户覆盖）。

### 4.3 图片落地：分场景

```
convert():
    final_md = opts.markdown_output_path 或 output_path
    if not (keep_image_references and export_image_files): 跳过
    mode = opts.image_output_mode            # sidecar(默认) / inline / none
    if mode == 'none':   跳过 + log 提示
    if mode == 'inline': 生成 data URI 内联，不落盘
    # mode == 'sidecar'
    if is_temporary_output(output_path):     # 库内转换
        book_dir = resolve_book_dir(oeb)     # uuid → 书名+作者回退；失败 → None
        if book_dir: 写入 os.path.join(book_dir, 'images')
        else:        跳过 + log.warn（不抛异常）
    else:                                    # CLI / 用户指定路径
        写入 <md 名>.images/（现状），并把 md 内 'images/' 重写为该目录名
```

要点：

- **库内模式不需要重写 md 里的路径**：`markdownml_enhanced` 生成的就是相对
  `images/xxx.png`，而书库目录里我们建的正是 `images/` → 直接可用。
- 非库内模式沿用现状 `rewrite_markdown_image_dir()`（改成 sidecar 名）。
- 目录名常量：`DEFAULT_IMAGE_DIR = 'images'`（已在 `markdown_helpers.py:12`）。

### 4.4 书库反查（新模块 `plugin/Markdown/markdown_library.py`）

```python
def is_temporary_output(output_path):
    """输出目标是否 calibre 临时文件（=> 库内/批量转换）。比对 ptempfile.base_dir()。"""

def resolve_book_dir(oeb_book, log):
    """返回书籍所在目录（绝对）或 None。只读打开书库，绝不写。"""
    # 1) uuid：遍历 oeb_book.metadata.identifier，strip 'urn:uuid:'
    #    → db.new_api.lookup_by_uuid(uuid)；首个命中即用
    # 2) 回退：new_api.search('title:"..."') ∩ authors 匹配，且必须唯一命中
    # 3) 目录 = dirname(db.new_api.format_abspath(book_id, fmt))
```

约束：

- 一律 `LibraryDatabase(path, read_only=True)`，**不写、不加格式、不改元数据**。
- 全部包在 `try/except`：任何异常 → None + 日志，转换照常产 md。
- 只在**确实需要落盘时**才打开书库（无图片 / mode != sidecar / 非库内场景都不打开）。
- 库路径取 `current_library_path()`；多库/服务端场景可能与正在转换的库不一致 →
  命中后**再用书名校验一次**（db 里的 title 与 oeb title 一致），不一致则放弃。

## 5. 文件级变更清单

| 文件 | 动作 | 说明 |
|---|---|---|
| `plugin/Markdown/__init__.py` | 改 | 改为输出插件入口，3.0.0，删 InterfaceAction/icon |
| `plugin/Markdown/markdown_output.py` | 改 | 新增 `image_output_mode` 选项；`is_customizable/config_widget/save_settings`；`convert()` 应用 overrides + 分场景图片 |
| `plugin/Markdown/markdown_library.py` | **新增** | `is_temporary_output()` / `resolve_book_dir()` |
| `plugin/Markdown/markdown_helpers.py` | 改 | `export_mapped_images()` 接受目标目录；新增 `inline_image_references()` |
| `plugin/Markdown/dialogs.py` | 改 | `MarkdownExportDialog` → `ConfigWidget(QWidget)`（保留 About/语法说明）；删 `ExportStatusDialog` |
| `plugin/Markdown/convert_flow.py` | 改 | 精简为薄封装（去掉 `.calibre_converting.txt` + `os.replace` hack、output guard、progress 回调），仅给脚本/测试用 |
| `plugin/Markdown/prefs.py` | 改 | site_customization 序列化/反序列化 helper；`ui_language` 仍存这里；导出选项值不再写 prefs.json（改由 site_customization 存），旧键保留只读兼容 |
| `plugin/Markdown/ui.py` | 改 | 转换面板保持原选项；`image_output_mode` 属全局偏好，不加到面板 |
| `plugin/Markdown/action.py` | **删** | InterfaceAction 入口 |
| `plugin/Markdown/markdown_stats.py` | **删** | 批量统计报告依赖插件 UI |
| `plugin/Markdown/conversion_log.py` | **删** | log→UI 转发依赖插件 UI |
| `plugin/Markdown/icons.py`、`images/` | **删** | 输出插件无图标需求 |
| `plugin/Markdown/i18n.py` | 改 | 补充新文案（图片模式、覆盖勾选、反查提示） |
| `plugin/build.py` | 不改 | `PLUGINS = [("Markdown", "Markdown.zip")]` 已正确 |
| `install.sh` | 不改 | 安装产物名不变 |

## 6. 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| calibre「检查库」把书目录里的 `images/` 列为 *Unknown files in books*，用户点「修复」会删除 | 图片丢失 | 自定义界面 + 转换日志明确提示；`image_output_mode` 提供 `inline`/`none` 逃生开关 |
| 保存到磁盘 / 拷贝 md 出去不带图 | 引用失效 | 同上的 `inline`（自包含） |
| 多库 / 服务端场景 `current_library_path()` 指向的不是正在转换的库 | 反查落空或错配 | 命中后书名二次校验；不唯一/不一致 → 放弃并记日志 |
| 反查走书名在同名书上误配 | 图片写进别人的目录 | 书名回退只在 uuid 全部 miss 时用，且要求**唯一命中** + 作者匹配 |
| job 进程只读打开书库与主库写操作并发 | 理论上的 sqlite 争用 | 只读打开、用完即关、异常即放弃；实测打开 0.04s，窗口极小 |
| 用户对「GUI 入口消失」不适应 | 找不到插件按钮 | 版本号 3.0.0 + 更新说明里写明新入口（转换书籍 / 批量转换 / 命令行） |

## 7. 验收标准（可测）

1. 首选项 → 插件 → **转换输出** 分类里能看到 Markdown；「自定义插件」按钮可用。
2. 转换对话框输出格式下拉含 Markdown → 选中后出现「Markdown 输出」面板。
3. 自定义界面改一项 + 重启 calibre → 值仍在（证明 `customize_plugin()` 持久化生效）。
4. GUI 单本转换（书库内）→ 图片出现在该书目录 `images/`；md 内引用为 `images/x.png`。
5. GUI 批量转换 → 同上。
6. `ebook-convert in.epub out.md` → 图片在 `out.images/`，md 引用已重写。
7. 自定义界面切 `inline` → md 自包含 data URI，无外部目录。
8. 切 `none` → 不落盘，日志有提示。
9. 反查失败场景（转换一个不在库里的文件，且输出为临时文件）→ 不写盘、不抛异常、日志告警。
10. 只读打开书库不改动 db：`metadata.db` 大小/mtime 不变（转换前后比对）。
11. 删除文件后 zip 仍能安装（`python plugin/build.py` → `calibre-customize -a`）。

## 8. 实施顺序

1. `__init__.py` 改入口 → 打 zip 冒烟：calibre 能识别为「转换输出」插件（单输出格式可见）。
2. `markdown_output.py`：加 `image_output_mode` 选项 + `is_customizable/config_widget/save_settings`
   （先复用现有对话框内容）→ 冒烟：自定义界面可开可存。
3. `markdown_library.py` 新增 + `markdown_helpers.py` 改造 → 冒烟：CLI 与库内两种落地。
4. `convert()` 串起来（overrides 生效 + 分场景）→ 冒烟 4/5/6/9/10。
5. 删除废弃文件（action/conversion_log/markdown_stats/icons/images）→ 精简 `convert_flow` → 重新打包验收。
6. 版本号 3.0.0 三处同步 + i18n 文案。
