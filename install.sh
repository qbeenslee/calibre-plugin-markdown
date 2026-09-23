#!/bin/bash
# 打包并安装到 calibre 插件目录（macOS）。
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DIR="$HOME/Library/Preferences/calibre/plugins"
SRC="$HERE/plugin/Markdown.zip"
DEST="$PLUGIN_DIR/Markdown.zip"

if [ ! -d "$PLUGIN_DIR" ]; then
  echo "✗ 找不到 calibre 插件目录：$PLUGIN_DIR" >&2
  echo "  请确认已安装 calibre 并至少启动过一次。" >&2
  exit 1
fi

echo "→ 打包插件"
python3 "$HERE/plugin/build.py"

if [ ! -f "$SRC" ]; then
  echo "✗ 打包失败：$SRC 不存在" >&2
  exit 1
fi

echo "→ 安装到 $DEST"
cp "$SRC" "$DEST"

src_size=$(stat -f%z "$SRC")
dest_size=$(stat -f%z "$DEST")
if [ "$src_size" != "$dest_size" ]; then
  echo "✗ 复制校验失败：$src_size != $dest_size" >&2
  exit 1
fi

echo "✓ 安装完成（$dest_size 字节）"
echo "  重启 calibre 后在「转换书籍」的输出格式中选择 Markdown 即可使用。"
