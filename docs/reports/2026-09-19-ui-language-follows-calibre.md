# 插件界面语言改为跟随 calibre（v3.18.0）

日期：2026-09-19
插件版本：3.17.1 → 3.18.0
触发：插件自己有一个「界面语言」设置（输出侧「自定义插件」弹窗的第一行下拉框），
可以和 calibre 的语言不一致。要求删掉这个设置，改为永远跟随 calibre：
系统语言是中文就显示中文，其他一律英文。

## 1. 变更设计

**语言来源唯一化**（`translations/ui_language.py`）：

- `_current_ui_lang` 初值改为 `None`（= 尚未探测）；`get_ui_language()` 首次被调用时
  执行 `detect_calibre_ui_language()` 并缓存。calibre 改语言要求重启，所以一个进程
  读一次就够；`get_ui_language()` 是消息表 `_()` 每次查表读的东西，缓存后只是读一个
  模块全局。
- 映射沿用并简化：`calibre.utils.localization.get_lang()` 归一化后以 `zh` 开头
  （`zh_CN` / `zh_SG` / `zh_TW` / `zh-HK` / `zh-Hans`）→ 中文表；其余语言、以及取不到
  calibre（测试环境）→ 英文表。**繁体回落到中文**（插件只有中英两套文案）。
- 保留 `set_ui_language()`，但语义收窄为「测试用的钉住开关」：传 `None` 即恢复
  自动探测。测试文件用 autouse fixture 复原模块状态，避免把整轮测试钉在中文。

**删掉的整条链路**：

| 位置 | 删除内容 |
|---|---|
| `utils/prefs.py` | `DEFAULTS['ui_language']`、`stored_ui_language()`、`save_ui_language()`、`ensure_prefs_initialized()`（后者唯一存在理由是首启把探测到的语言落盘） |
| `translations/ui_language.py` | `apply_ui_language_from_prefs()`、`ui_language_combo_items()`、`normalize_ui_language()` |
| `output/preference_ui.py` | `UiLanguageMixin` 与「Interface language:」行；`ConfigWidget` 不再持有 prefs，`PluginAboutDialog` 退回 `get_prefs()` |
| `input/preference_ui.py`、`output/conversion_ui.py`、`input/conversion_ui.py` | 4 处 `apply_ui_language_from_prefs(get_prefs())` 调用与随之失用的 `get_prefs` 导入 |
| `translations/messages.py` | 只服务该下拉框的 3 条键（`Interface language:` / `English` / `Simplified Chinese`） |

**未变**：生成的 Markdown 里目录标题（`output/markdownml_enhanced._toc_heading`）仍读
同一个状态，即「calibre 中文 → `目录`，其他 → `Table of Contents`」，与改动前的默认
行为一致。用户 `prefs.json` 里残留的 `ui_language` 键不读也不删，留着无害。

## 2. 实证

### 2.1 单测

`.venv/bin/python -m pytest plugin/tests -q` → **415 passed**（新增
`tests/test_ui_language.py` 10 项：探测映射、惰性探测驱动消息表、一次读取、钉住优先、
解除钉住复原、旧 prefs 键与旧接口消失、两个弹窗源码无语言行、两侧转换面板不引用旧接口）。

### 2.2 真机验收

`scripts/verify_ui_language.py`（calibre-debug + 真实 Qt，跑源码树并校验未被已安装 zip
遮蔽）：

| 检查项 | 结果 |
|---|---|
| 本机 calibre `get_lang()='en'` → 探测为英文、消息表英文 | PASS |
| `CALIBRE_OVERRIDE_LANG=en_US` → 英文表 | PASS |
| `CALIBRE_OVERRIDE_LANG=zh_TW` → 中文表（繁体回落） | PASS |
| `CALIBRE_OVERRIDE_LANG=zh-Hans` → 中文表 | PASS |
| 输出「自定义插件」弹窗：20 个选项行齐全、**没有语言行**、overrides 仍能存取往返 | PASS |
| 关于对话框标题、转换对话框输出面板各文案随 calibre | PASS |
| 配置默认值里没有 `ui_language`；配置里残留的旧值 `0`（英文）被忽略（calibre 切中文时显示中文）；期间配置文件逐字节未变 | PASS |

## 3. 文件清单

| 文件 | 动作 |
|---|---|
| `plugin/Markdown/translations/ui_language.py` | 惰性跟随 calibre；删 `apply_ui_language_from_prefs` / `ui_language_combo_items` / `normalize_ui_language` |
| `plugin/Markdown/translations/messages.py` | 删 3 条下拉框专用文案键 |
| `plugin/Markdown/translations/__init__.py` | 子包说明改为「如何从 calibre 映射」，去掉「持久化」 |
| `plugin/Markdown/utils/prefs.py` | 删 `ui_language` 键与 `stored_ui_language` / `save_ui_language` / `ensure_prefs_initialized` |
| `plugin/Markdown/output/preference_ui.py` | 删 `UiLanguageMixin` 与语言行；`ConfigWidget` 不再持 prefs |
| `plugin/Markdown/input/preference_ui.py`、`input/conversion_ui.py`、`output/conversion_ui.py` | 删语言同步调用与失用导入 |
| `plugin/Markdown/__init__.py`、`output/output_plugin.py`、`input/input_plugin.py` | 版本 3.18.0 |
| `plugin/tests/test_ui_language.py` | **新增** 10 项 |
| `plugin/tests/test_plugin_entry.py` | 版本断言与说明 |
| `scripts/verify_ui_language.py` | **新增**：真机验收（12 项 PASS） |

注：`docs/specs/2026-09-17-markdown-output-plugin-design.md` 里「界面语言继续用插件私有
prefs.json」的说法已被本次变更取代（历史设计稿，不修改）。
