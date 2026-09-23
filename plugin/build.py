"""打包插件为 calibre 可安装的 zip。

硬性要求：
- zip 顶层必须直接是 `__init__.py`（归档名以包目录为基准，不加包名前缀）；
- zip 内必须包含内容为空的 `plugin-import-name-<name>.txt`（决定 calibre_plugins.<name>）。
"""

import os
import stat
import sys
import zipfile

PLUGINS = [("Markdown", "Markdown.zip")]
SKIP_DIRS = {"__pycache__"}
SKIP_SUFFIX = (".pyc", ".pyo")
SKIP_FILES = {".DS_Store"}
FIXED_DATE = (2024, 1, 1, 0, 0, 0)


def _iter_entries(pkg_dir: str):
    for root, dirs, files in os.walk(pkg_dir):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(files):
            if name in SKIP_FILES or name.endswith(SKIP_SUFFIX):
                continue
            full = os.path.join(root, name)
            yield full, os.path.relpath(full, pkg_dir).replace(os.sep, "/")


def build_plugin(pkg_dir: str, out_zip: str) -> str:
    """把包目录打成 zip（临时文件 + 原子替换），返回产物绝对路径。"""
    out_zip = os.path.abspath(out_zip)
    tmp_zip = out_zip + ".tmp"
    count = 0
    with zipfile.ZipFile(tmp_zip, "w", zipfile.ZIP_DEFLATED) as archive:
        for full, arc in _iter_entries(pkg_dir):
            info = zipfile.ZipInfo(arc, date_time=FIXED_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = stat.S_IMODE(os.stat(full).st_mode) << 16
            with open(full, "rb") as handle:
                archive.writestr(info, handle.read())
            count += 1
    os.replace(tmp_zip, out_zip)
    print(
        "已生成 {0}（{1} 个条目，{2} 字节）".format(
            os.path.basename(out_zip), count, os.path.getsize(out_zip)
        )
    )
    return out_zip


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    here = os.path.dirname(os.path.abspath(__file__))
    targets = PLUGINS
    if argv:
        keep = set(argv)
        targets = [item for item in PLUGINS if item[0] in keep]
    for pkg_name, zip_name in targets:
        pkg_dir = os.path.join(here, pkg_name)
        if not os.path.isdir(pkg_dir):
            print("找不到包目录：{0}".format(pkg_dir), file=sys.stderr)
            return 1
        out = build_plugin(pkg_dir, os.path.join(here, zip_name))
        print("产物：{0}".format(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
