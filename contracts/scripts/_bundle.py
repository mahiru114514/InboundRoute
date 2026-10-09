"""schema 加载与内联（scripts/validate.py 与 scripts/generate.py 共用）。

为什么不直接用 jsonschema 的 RefResolver：该类已废弃，且对内部 #/$defs/... 指针解析不可靠。
这里的做法是**加载时把跨文件 $ref 内联**，并把内联进来的 $defs 提升到根作用域，
使每个 schema 成为自包含文档，于是任何标准校验器都能直接用。
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

SCHEMA_NAMES = ["poi.schema.json", "trip.schema.json", "route.schema.json",
                "station.schema.json", "api.schema.json", "recommendation.schema.json"]
EXTERNAL_REF = re.compile(r"^(?P<file>[a-z_]+\.schema\.json|enums\.json)(#(?P<pointer>.*))?$")


def contracts_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def json_pointer(document, pointer: str):
    node = document
    for token in [t for t in pointer.split("/") if t]:
        token = token.replace("~1", "/").replace("~0", "~")
        node = node[token]
    return node


class Contracts:
    """契约包的内存视图：原始 schema、枚举表，以及内联后的自包含 schema。"""

    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else contracts_root()
        self.schemas = {name: load_json(self.root / "schemas" / name) for name in SCHEMA_NAMES}
        self.enums = load_json(self.root / "enums.json")
        self.rules = load_json(self.root / "rules.json")
        self.mappings = load_json(self.root / "mappings.json")
        self.errors = load_json(self.root / "errors.json")
        self.bundled = {name: self._bundle(name) for name in SCHEMA_NAMES}

    # ------------------------------------------------------------ 内联

    def _document(self, file_name: str):
        if file_name == "enums.json":
            return self.enums
        return self.schemas.get(file_name)

    def _inline(self, node):
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and EXTERNAL_REF.match(ref):
                match = EXTERNAL_REF.match(ref)
                document = self._document(match.group("file"))
                if document is None:
                    raise KeyError(f"未知引用文件：{match.group('file')}")
                pointer = match.group("pointer") or ""
                target = copy.deepcopy(json_pointer(document, pointer) if pointer else document)
                target.pop("$id", None)
                target.pop("$schema", None)
                return self._inline(target)
            return {key: self._inline(value) for key, value in node.items()}
        if isinstance(node, list):
            return [self._inline(item) for item in node]
        return node

    def _bundle(self, schema_name: str):
        bundled = self._inline(copy.deepcopy(self.schemas[schema_name]))
        bundled = self._strip_comments(bundled)
        bundled = self._flatten_defs(bundled)
        # 去掉 $id/$schema：否则内联后的文档会改变 base URI，使 #/$defs/... 解析到错误作用域
        bundled.pop("$id", None)
        bundled.pop("$schema", None)
        return bundled

    @staticmethod
    def _strip_comments(node):
        """去掉 $comment（人读注释）。内联后它们会混进被校验的数据里，导致 additionalProperties 报错。"""
        if isinstance(node, dict):
            node.pop("$comment", None)
            for value in node.values():
                Contracts._strip_comments(value)
        elif isinstance(node, list):
            for item in node:
                Contracts._strip_comments(item)
        return node

    @staticmethod
    def _flatten_defs(document: dict):
        """把内联进来的子 schema 的 $defs 提升到根 $defs，并重写内部指针。"""
        root_defs = document.setdefault("$defs", {})
        for _ in range(10):
            pending: list[tuple[str, dict]] = []

            def collect(node):
                if isinstance(node, dict):
                    found = node.pop("$defs", None)
                    if found:
                        pending.extend(found.items())
                    for value in node.values():
                        collect(value)
                elif isinstance(node, list):
                    for item in node:
                        collect(item)

            for value in list(document.values()):
                collect(value)
            if not pending:
                return document
            for name, definition in pending:
                target = name
                while target in root_defs:
                    target = f"{name}_x" if not target.endswith("_x") else f"{target}_x"
                root_defs[target] = definition
                Contracts._rename_refs(document, f"#/$defs/{name}", f"#/$defs/{target}")
        raise RuntimeError("_flatten_defs 未收敛")

    @staticmethod
    def _rename_refs(node, old: str, new: str):
        if isinstance(node, dict):
            if node.get("$ref") == old:
                node["$ref"] = new
            for value in node.values():
                Contracts._rename_refs(value, old, new)
        elif isinstance(node, list):
            for item in node:
                Contracts._rename_refs(item, old, new)

    # ------------------------------------------------------------ 校验

    def validate(self, instance, schema_name: str) -> list:
        """返回校验错误列表（空列表表示通过）；需要 jsonschema（可选依赖）。"""
        from jsonschema import Draft202012Validator
        validator = Draft202012Validator(self.bundled[schema_name])
        return sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))

    def enum_values(self, pointer: str) -> list:
        node = json_pointer(self.enums, pointer)
        return list(node.get("enum", []))
