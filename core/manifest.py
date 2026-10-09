import json
import re
from pathlib import Path

ID_PATTERN = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(10)), *(f"lpt{i}" for i in range(10))}


def validate_id(value):
    if not isinstance(value, str) or not ID_PATTERN.fullmatch(value) or value in RESERVED:
        raise ValueError("模块 ID 必须是小写字母开头的字母、数字或下划线（最长 64 位），且不能是系统保留名")
    return value


def read_manifest(folder: Path):
    if folder.is_symlink() or folder.resolve().parent != folder.parent.resolve():
        raise ValueError("模块目录不能是链接")
    path = folder / "manifest.json"
    if not path.is_file():
        # 空目录 / 半成品目录（例如只建了文件夹就交付）以前会退化成
        # FileNotFoundError 的英文原文，界面上只能显示笼统的「格式异常」。
        # 这里必须说清「缺什么、怎么补」，否则使用者无从下手。
        try:
            empty = not any(folder.iterdir())
        except OSError:
            empty = False
        raise ValueError(
            "模块目录%s：找不到 manifest.json"
            "（示例模块的源码在 examples/ 下，把整个文件夹复制进 modules/ 后点「刷新发现」）"
            % ("是空的" if empty else "不完整"))
    if path.stat().st_size > 65536:
        raise ValueError("模块清单超过 64 KB")
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("模块清单必须是 JSON 对象")
    validate_id(value.get("id"))
    for field in ("name", "version"):
        if not isinstance(value.get(field), str) or not value[field].strip() or len(value[field]) > 120:
            raise ValueError(f"清单字段 {field} 必须是非空字符串（最长 120 字符）")
    deps = value.get("dependencies", [])
    if not isinstance(deps, list) or len(deps) > 100:
        raise ValueError("dependencies 必须是模块 ID 数组（最多 100 项）")
    for dep in deps:
        validate_id(dep)
    if len(set(deps)) != len(deps):
        raise ValueError("依赖不能重复")
    description = value.get("description", "")
    if not isinstance(description, str) or len(description) > 2000:
        raise ValueError("description 必须是字符串（最长 2000 字符）")
    entry = folder / "plugin.py"
    if not entry.is_file() or entry.is_symlink() or entry.resolve().parent != folder.resolve():
        raise ValueError("模块缺少有效的 plugin.py")
    return {"id": value["id"], "name": value["name"], "version": value["version"],
            "description": description, "dependencies": deps}
