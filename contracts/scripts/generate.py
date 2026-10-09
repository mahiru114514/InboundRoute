"""从 schema 生成全部产物（generated/ 下的东西一律由本脚本产出，不许手改）。

用法：
    python scripts/generate.py          # 生成
    python scripts/generate.py --check  # CI：确认 generated/ 与 schema 同步

产物：
    generated/domain.ts        前端 TypeScript 类型（零依赖）
    generated/README.md        字段表文档（人读）
    generated/models.py        后端 Python dataclass 模型（R-1，纯标准库）
    generated/schema_store.py  内联后的自包含 schema + validate()（离线校验用）

注意：不要把这些产物手动拷进模块再改。模块通过 sys.path 引用契约包。
"""
import json
import keyword
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _bundle import Contracts  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "generated"
SCHEMAS_FOR_CODE = ["poi.schema.json", "trip.schema.json", "route.schema.json", "station.schema.json", "recommendation.schema.json"]
TIME_NOTE = "所有 *_at 为 UTC 秒；date 为 Asia/Shanghai 日期；*_local 为同日时刻。见 contracts/TIME_BASELINE.md"
HEADER = "本文件由 contracts/scripts/generate.py 从 schemas/*.schema.json 生成，请勿手改。"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def pascal(name):
    return "".join(part.capitalize() for part in re.split(r"[_\-\s]+", name) if part)


def py_literal(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return repr(value)
    return json.dumps(value, ensure_ascii=False)


# ---------------------------------------------------------------- TypeScript

def ts_type(node, enums):
    if not isinstance(node, dict):
        return "unknown"
    if "const" in node:
        return json.dumps(node["const"], ensure_ascii=False)
    if "enum" in node:
        return " | ".join(json.dumps(value, ensure_ascii=False) for value in node["enum"])
    if "$ref" in node:
        ref = node["$ref"]
        if ref.startswith("#/$defs/"):
            return pascal(ref.rsplit("/", 1)[-1])
        if "enums.json#/" in ref:
            node_enum = enum_node(enums, ref.split("#/", 1)[1])
            if "enum" in node_enum:
                values = node_enum["enum"]
                if all(isinstance(v, int) for v in values):
                    return " | ".join(str(v) for v in values)
                return " | ".join(json.dumps(v) for v in values)
            return "unknown"
        if ".schema.json#/$defs/" in ref:
            return pascal(ref.rsplit("/", 1)[-1])
        if ".schema.json" in ref:
            return pascal(ref.split(".schema.json")[0].split("/")[-1])
        return "unknown"
    if "anyOf" in node:
        return " | ".join(ts_type(item, enums) for item in node["anyOf"])
    node_type = node.get("type")
    if isinstance(node_type, list):
        return " | ".join({"null": "null", "object": "Record<string, unknown>", "array": "unknown[]",
                           "string": "string", "integer": "number", "number": "number",
                           "boolean": "boolean"}.get(item, "unknown") for item in node_type)
    if node_type == "object" or "properties" in node:
        if "properties" not in node:
            return "Record<string, unknown>"
        body = "\n".join(
            f"    {key}{'?' if key not in node.get('required', []) else ''}: {ts_type(value, enums)};"
            for key, value in node["properties"].items())
        return "{\n" + body + "\n  }"
    if node_type == "array":
        return f"{ts_type(node.get('items', {}), enums)}[]"
    return {"string": "string", "integer": "number", "number": "number", "boolean": "boolean",
            "null": "null"}.get(node_type, "unknown")


def enum_node(enums, pointer):
    node = enums
    for token in pointer.split("/"):
        if token:
            node = node.get(token, {})
    return node


def ts_declarations(schema_name, schema, enums):
    lines = []
    for def_name, node in (schema.get("$defs") or {}).items():
        lines.append(f"export interface {pascal(def_name)} {{")
        for key, value in (node.get("properties") or {}).items():
            optional = "?" if key not in node.get("required", []) else ""
            lines.append(f"  {key}{optional}: {ts_type(value, enums)};")
        lines.append("}")
        lines.append("")
    lines.append(f"export interface {pascal(schema_name.replace('.schema.json', ''))} {{")
    for key, value in (schema.get("properties") or {}).items():
        optional = "?" if key not in schema.get("required", []) else ""
        lines.append(f"  {key}{optional}: {ts_type(value, enums)};")
    lines.append("}")
    lines.append("")
    return lines


def ts_enum_constants(enums):
    lines = ["// 枚举唯一取值域：需要使用枚举值时从这里取，不要在业务代码里硬编码字符串。", ""]
    for name, node in enums.items():
        if name.startswith("$") or not isinstance(node, dict) or "enum" not in node:
            continue
        values = node["enum"]
        if all(isinstance(v, str) for v in values):
            lines.append(f"export type {pascal(name)} = " +
                         " | ".join(json.dumps(v) for v in values) + ";")
            lines.append(f"export const {name.upper()} = [" +
                         ", ".join(json.dumps(v) for v in values) + "] as const;")
            lines.append("")
    return lines


# ---------------------------------------------------------------- Python 模型

def collect_inline_types(schema_name, schema, type_map):
    """收集内联对象字段（dict[str, Any] 的那些），为它们生成具名 dataclass。

    背景：契约里 route.segments[].transfer 是内联对象。若退化成 dict，业务代码就只能按字符串取字段，
    契约价值大打折扣。所以这里把内联对象也生成类，命名规则 <父类><字段名>。
    """
    results: dict[tuple[str, str], str] = {}   # (owner_class, field) -> class name
    definitions: list[tuple[str, dict]] = []   # (class name, schema node)

    def walk(owner, properties):
        for field, node in (properties or {}).items():
            inline = _unwrap_to_inline_object(node)
            if inline is None:
                continue
            class_name = f"{owner}{pascal(field)}"
            if (owner, field) in results:
                continue
            results[(owner, field)] = class_name
            definitions.append((class_name, inline))
            walk(class_name, inline.get("properties"))

    root_owner = pascal(schema_name.replace(".schema.json", ""))
    walk(root_owner, schema.get("properties"))
    for def_name, def_node in (schema.get("$defs") or {}).items():
        walk(pascal(def_name), def_node.get("properties"))
    return results, definitions
    return results, definitions


def _type_includes(node, kind: str) -> bool:
    node_type = node.get("type")
    if isinstance(node_type, list):
        return kind in node_type
    return node_type == kind


def _unwrap_to_inline_object(node):
    """把数组/anyOf/可空联合包裹剥掉，返回内联对象节点；不是内联对象则 None。"""
    if not isinstance(node, dict):
        return None
    if _type_includes(node, "array"):
        return _unwrap_to_inline_object(node.get("items") or {})
    if "anyOf" in node:
        for item in node["anyOf"]:
            found = _unwrap_to_inline_object(item)
            if found is not None:
                return found
        return None
    if _type_includes(node, "object") and node.get("properties"):
        return node
    return None


def _is_array_field(node) -> bool:
    """字段本身（或 anyOf 分支之一）是否为数组类型。"""
    if not isinstance(node, dict):
        return False
    if _type_includes(node, "array"):
        return True
    if "anyOf" in node:
        return any(_is_array_field(item) for item in node["anyOf"])
    return False


def _is_nullable(node) -> bool:
    if not isinstance(node, dict):
        return False
    node_type = node.get("type")
    if isinstance(node_type, list) and "null" in node_type:
        return True
    if "anyOf" in node:
        return any(_unwrap_to_inline_object(item) is None and item.get("type") == "null"
                   for item in node["anyOf"])
    return False


def node_is_array_of_object(node) -> bool:
    """字段是否为「对象数组」（内联对象数组或 $ref 到对象的数组）。"""
    if not isinstance(node, dict):
        return False
    if _type_includes(node, "array"):
        inner = node.get("items") or {}
        return _unwrap_to_inline_object(inner) is not None or "$ref" in inner
    if "anyOf" in node:
        return any(node_is_array_of_object(item) for item in node["anyOf"])
    return False


def nested_class_name(node, type_map):
    """返回数组元素或嵌套对象应该构造的类名；无法确定时返回 None。"""
    if not isinstance(node, dict):
        return None
    if _type_includes(node, "array"):
        return nested_class_name(node.get("items") or {}, type_map)
    if "$ref" in node:
        ref = node["$ref"]
        if ref.startswith("#/$defs/"):
            return type_map.get(pascal(ref.rsplit("/", 1)[-1]))
        if ".schema.json" in ref:
            if "#/$defs/" in ref:
                return type_map.get(pascal(ref.rsplit("/", 1)[-1]))
            return type_map.get(pascal(ref.split("#")[0].split("/")[-1].replace(".schema.json", "")))
        return None
    if "anyOf" in node:
        for item in node["anyOf"]:
            found = nested_class_name(item, type_map)
            if found and found != "dict[str, Any]":
                return found
        return None
    if _type_includes(node, "object") and node.get("properties"):
        return "dict[str, Any]"
    return None


def py_hint(node, enums, type_map, owner=None, field=None, inline_map=None):
    """返回 (类型注解, 默认值)。inline_map 用于把内联对象/数组指向生成的具名类。"""
    if not isinstance(node, dict):
        return ("object", "None")
    if inline_map and owner and field and (owner, field) in inline_map:
        name = inline_map[(owner, field)]
        if _is_array_field(node):
            return (f"list[{name}]", "field(default_factory=list)")
        # 内联对象：契约里通常是 ["object","null"]，统一用 Optional 表达
        return (f"{name} | None", "None")
    if "enum" in node:
        values = node["enum"]
        if len(values) == 1:
            return (f"Literal[{py_literal(values[0])}]", py_literal(values[0]))
        return ("Literal[" + ", ".join(py_literal(v) for v in values) + "]", "None")
    if "const" in node:
        return (f"Literal[{py_literal(node['const'])}]", py_literal(node["const"]))
    if "$ref" in node:
        ref = node["$ref"]
        if ref.startswith("#/$defs/"):
            name = pascal(ref.rsplit("/", 1)[-1])
            return (type_map.get(name, name), "None")
        if "enums.json#/" in ref:
            node_enum = enum_node(enums, ref.split("#/", 1)[1])
            if "enum" in node_enum:
                values = node_enum["enum"]
                return ("Literal[" + ", ".join(py_literal(v) for v in values) + "]", "None")
            return ("str", "None")
        if ".schema.json" in ref:
            if "#/$defs/" in ref:
                name = pascal(ref.rsplit("/", 1)[-1])
                return (type_map.get(name, name), "None")
            name = pascal(ref.split("#")[0].split("/")[-1].replace(".schema.json", ""))
            return (type_map.get(name, name), "None")
        return ("object", "None")
    if "anyOf" in node:
        hints = [py_hint(item, enums, type_map, owner, field, inline_map)[0] for item in node["anyOf"]]
        real = [hint for hint in hints if hint not in ("None", "NoneType")]
        if len(real) == 1:
            return (f"{real[0]} | None", "None")
        if real:
            return (" | ".join(dict.fromkeys(real)), "None")
        return ("object", "None")
    node_type = node.get("type")
    if isinstance(node_type, list):
        real = [item for item in node_type if item != "null"]
        hint = py_hint({**node, "type": real[0]}, enums, type_map, owner, field, inline_map)[0] if real else "object"
        return (f"{hint} | None", "None")
    if node_type == "array":
        item_node = node.get("items", {})
        item_hint = py_hint(item_node, enums, type_map, owner, field, inline_map)[0] if item_node else "object"
        return (f"list[{item_hint}]", "field(default_factory=list)")
    if node_type == "object" or "properties" in node:
        return ("dict[str, Any]", "field(default_factory=dict)")
    return ({"string": "str", "integer": "int", "number": "float", "boolean": "bool"}.get(node_type, "object"), "None")


def py_models(contracts: Contracts) -> str:
    lines = [
        '"""领域模型（从 schemas/*.schema.json 生成，请勿手改）。',
        "",
        f"{TIME_NOTE}",
        "",
        "用法：",
        "    from contracts.generated.models import Trip",
        "    trip = Trip.from_dict(payload)     # 未知字段被忽略，嵌套对象自动转换",
        "    payload = trip.to_dict()           # 只输出已知字段，JSON 名自动还原",
        "",
        "严格校验（类型/必填/正则）请用 generated/schema_store.py 的 validate()。",
        "注意：所有 dataclass 都是 kw_only，因此可以按契约顺序声明字段（必填与选填混排）。",
        "JSON 里非法的 Python 标识符会在属性名上转义：from → from_、zh-Hans → zh_Hans，",
        "to_dict()/from_dict() 会自动做双向映射，业务代码里请使用属性名。",
        "需要 Python 3.10+（dataclass kw_only 与 PEP 604 联合类型）。",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "from dataclasses import asdict, dataclass, field, fields, is_dataclass",
        "from typing import Any, Literal",
        "",
        "",
        "def _build(cls, value):",
        '    """把 dict 构造为 dataclass；**必须优先走 cls.from_dict**，否则嵌套对象不会被递归转换。"""',
        "    if value is None or not isinstance(value, dict):",
        "        return value",
        "    if not (is_dataclass(cls) and isinstance(cls, type)):",
        "        return value",
        "    builder = getattr(cls, \"from_dict\", None)",
        "    if callable(builder):",
        "        return builder(value)",
        "    known = {item.name for item in fields(cls)}",
        "    return cls(**{key: val for key, val in value.items() if key in known})",
        "",
        "",
        "def _build_list(cls, value):",
        "    if value is None:",
        "        return []",
        "    return [_build(cls, item) for item in value]",
        "",
        "",
        "def _dump(value):",
        '    """递归导出为 JSON 友好结构；dataclass 一律走它自己的 to_dict（保证别名还原）。"""',
        "    if is_dataclass(value) and not isinstance(value, type):",
        "        exporter = getattr(value, \"to_dict\", None)",
        "        if callable(exporter):",
        "            return exporter()",
        '        return {key: _dump(val) for key, val in asdict(value).items()}',
        "    if isinstance(value, list):",
        "        return [_dump(item) for item in value]",
        "    if isinstance(value, dict):",
        "        return {key: _dump(val) for key, val in value.items()}",
        "    return value",
        "",
        "",
    ]

    type_map: dict[str, str] = {}
    inline_map: dict[tuple[str, str], str] = {}
    inline_defs: dict[str, list[tuple[str, dict]]] = {}
    for schema_name in SCHEMAS_FOR_CODE:
        schema = contracts.schemas[schema_name]
        root = pascal(schema_name.replace(".schema.json", ""))
        type_map[root] = root
        for def_name in (schema.get("$defs") or {}):
            type_map[pascal(def_name)] = pascal(def_name)
        found, definitions = collect_inline_types(schema_name, schema, type_map)
        inline_map.update(found)
        inline_defs[schema_name] = definitions
        for class_name, _ in definitions:
            type_map[class_name] = class_name

    for schema_name in SCHEMAS_FOR_CODE:
        schema = contracts.schemas[schema_name]
        lines.append(f"# {'-' * 70}")
        lines.append(f"# {schema['title']}  ({schema_name})")
        lines.append(f"# {'-' * 70}")
        lines.append("")
        for def_name, node in (schema.get("$defs") or {}).items():
            lines.extend(py_class(pascal(def_name), node, enums=contracts.enums, type_map=type_map,
                                  inline_map=inline_map))
        for class_name, node in inline_defs[schema_name]:
            lines.extend(py_class(class_name, node, enums=contracts.enums, type_map=type_map,
                                  inline_map=inline_map))
        lines.extend(py_class(pascal(schema_name.replace(".schema.json", "")), schema,
                              enums=contracts.enums, type_map=type_map, inline_map=inline_map))

    lines.extend([
        "# ---------------------------------------------------------------- 便捷入口",
        "",
        "MODEL_BY_SCHEMA = {",
        '    "poi.schema.json": Poi,',
        '    "trip.schema.json": Trip,',
        '    "route.schema.json": Route,',
        '    "station.schema.json": Station,',
        '    "recommendation.schema.json": Recommendation,',
        "}",
        "",
        "",
        "def build(schema_name: str, payload: dict):",
        '    """按 schema 名构造模型；未知 schema 抛 KeyError。"""',
        "    return MODEL_BY_SCHEMA[schema_name].from_dict(payload)",
        "",
    ])
    return "\n".join(lines) + "\n"


def py_class(class_name, node, enums, type_map, inline_map=None) -> list[str]:
    required = set(node.get("required", []))
    properties = node.get("properties") or {}
    doc = (node.get("description") or node.get("$comment") or "").strip().replace('"""', "'''")

    def attr_name(wire):
        """Python 标识符化：关键字加下划线，非法字符（如 zh-Hans 的连字符）转下划线。"""
        name = re.sub(r"\W", "_", wire)
        if not name or name[0].isdigit():
            name = "_" + name
        if keyword.iskeyword(name) or name in {"self", "cls"}:
            name += "_"
        return name

    def nested_of(key, value):
        """返回 (类名, 是否列表)；无法确定返回 (None, False)。"""
        as_list = _is_array_field(value)
        if inline_map and (class_name, key) in inline_map:
            return inline_map[(class_name, key)], as_list
        element = nested_class_name(value.get("items") or {} if as_list else value, type_map)
        if element and element != "dict[str, Any]":
            return element, as_list
        return None, False

    lines = ["@dataclass(kw_only=True)", f"class {class_name}:"]
    if doc:
        lines.append(f'    """{doc[:150]}"""')
        lines.append("")
    if not properties:
        lines.append("    pass")
        lines.append("")
    for key, value in properties.items():
        hint, hint_default = py_hint(value, enums, type_map, class_name, key, inline_map)
        # 优先用 schema 里的 default（如 congestion_level="unknown"、crs="WGS84"），
        # 否则选填字段用类型默认值；必填字段一律不给默认值（强制调用方显式传）。
        schema_default = value.get("default") if isinstance(value, dict) else None
        if schema_default is not None and not isinstance(schema_default, (dict, list)):
            default = py_literal(schema_default)
        elif key in required:
            default = hint_default if hint_default.startswith("field(") else None
        else:
            default = hint_default
        comment = (value.get("description") or value.get("$comment") or "").strip().replace("\n", " ")
        alias = attr_name(key)
        note = f"（JSON 字段名：{key}）" if alias != key else ""
        suffix = f"  # {note}{comment[:100]}" if (comment or note) else ""
        if default is None:
            lines.append(f"    {alias}: {hint}{suffix}")
        else:
            lines.append(f"    {alias}: {hint} = {default}{suffix}")
    lines.append("")
    lines.append("    @classmethod")
    lines.append(f'    def from_dict(cls, value: dict) -> "{class_name}":')
    lines.append('        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""')
    lines.append("        if not isinstance(value, dict):")
    lines.append("            raise TypeError(f\"{cls.__name__} 需要 dict，收到 {type(value).__name__}\")")
    if properties:
        lines.append("        return cls(")
        for key, value in properties.items():
            nested, as_list = nested_of(key, value)
            alias = attr_name(key)
            if nested and as_list:
                lines.append(f'            {alias}=_build_list({nested}, value.get("{key}")),')
            elif nested:
                lines.append(f'            {alias}=_build({nested}, value.get("{key}")),')
            else:
                lines.append(f'            {alias}=value.get("{key}"),')
        lines.append("        )")
    else:
        lines.append("        return cls()")
    lines.append("")
    lines.append("    def to_dict(self) -> dict:")
    lines.append('        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""')
    if properties:
        lines.append("        return {")
        for key in properties:
            alias = attr_name(key)
            if key in required:
                lines.append(f'            "{key}": _dump(self.{alias}),')
            else:
                lines.append(f'            **({{}} if self.{alias} is None else {{"{key}": _dump(self.{alias})}}),')
        lines.append("        }")
    else:
        lines.append("        return {}")
    lines.append("")
    lines.append("")
    return lines


# ---------------------------------------------------------------- schema_store

def schema_store(contracts: Contracts) -> str:
    payload = json.dumps(contracts.bundled, ensure_ascii=False, indent=2)
    if "'''" in payload:
        raise ValueError("schema 内容包含三引号，无法内嵌（请改用 base64 或拆分）")
    return "\n".join([
        '"""内联后的自包含 schema 与校验入口（生成物，请勿手改）。',
        "",
        "用途：模块在自己的进程里校验请求/响应，不依赖仓库根目录的 contracts/schemas/",
        "（模块被安装到 modules/<id>/ 后，仓库结构不保证存在）。",
        "",
        "校验需要 jsonschema（可选依赖）：",
        "    from contracts.generated.schema_store import validate",
        "    errors = validate(payload, \"route.schema.json\")",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "import json",
        "",
        "_RAW = r'''" + payload + "'''",
        "",
        "SCHEMAS = json.loads(_RAW)",
        "",
        "",
        "def get(schema_name: str) -> dict:",
        '    """取内联后的 schema（自包含，可直接交给标准校验器）。"""',
        "    return SCHEMAS[schema_name]",
        "",
        "",
        "def validate(instance, schema_name: str) -> list:",
        '    """返回错误列表（空表示通过）。未安装 jsonschema 时抛 RuntimeError。"""',
        "    try:",
        "        from jsonschema import Draft202012Validator",
        "    except ImportError as exc:  # pragma: no cover",
        '        raise RuntimeError("校验需要 jsonschema：pip install jsonschema") from exc',
        "    validator = Draft202012Validator(SCHEMAS[schema_name])",
        "    return sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))",
        "",
        "",
        "def is_valid(instance, schema_name: str) -> bool:",
        "    return not validate(instance, schema_name)",
        "",
    ])


# ---------------------------------------------------------------- 字段表

def field_table(schema_name, schema):
    rows = ["| 字段 | 类型 | 必填 | 默认 | 取值域/枚举 | 说明 |", "| --- | --- | --- | --- | --- | --- |"]

    def walk(props, required, prefix=""):
        for key, node in props.items():
            name = f"{prefix}{key}"
            node_type = node.get("type")
            if isinstance(node_type, list):
                node_type = " / ".join(node_type)
            enum = node.get("enum")
            domain = ", ".join(str(v) for v in enum) if enum else node.get("pattern", "") or ""
            desc = (node.get("description") or node.get("$comment") or "").replace("\n", " ")
            rows.append(f"| `{name}` | {node_type or ''} | {'是' if key in required else '否'} | "
                        f"{json.dumps(node.get('default'), ensure_ascii=False) if 'default' in node else ''} | {domain} | {desc} |")
            if node.get("properties"):
                walk(node["properties"], node.get("required", []), prefix=f"{name}.")
            if node.get("items", {}).get("properties"):
                walk(node["items"]["properties"], node["items"].get("required", []), prefix=f"{name}[].")
    walk(schema.get("properties", {}), schema.get("required", []))
    return "\n".join(rows)


# ---------------------------------------------------------------- 主流程

def build_products() -> dict[Path, str]:
    contracts = Contracts(ROOT)
    enums = contracts.enums

    ts_lines = [f"// {HEADER}", f"// {TIME_NOTE}", ""]
    ts_lines.extend(ts_enum_constants(enums))
    for name in SCHEMAS_FOR_CODE:
        ts_lines.extend(ts_declarations(name, contracts.schemas[name], enums))
    ts = "\n".join(ts_lines) + "\n"

    doc_lines = ["# 字段表（自动生成）", "", f"> {TIME_NOTE}", ">",
                 f"> {HEADER}", ""]
    for name in SCHEMAS_FOR_CODE:
        doc_lines.extend([f"## {contracts.schemas[name]['title']}（`schemas/{name}`）", "",
                          field_table(name, contracts.schemas[name]), ""])
    doc = "\n".join(doc_lines) + "\n"

    return {
        OUT / "domain.ts": ts,
        OUT / "README.md": doc,
        OUT / "models.py": py_models(contracts),
        OUT / "schema_store.py": schema_store(contracts),
    }


def main():
    check_only = "--check" in sys.argv
    products = build_products()
    if check_only:
        stale = [str(path.relative_to(ROOT)) for path, content in products.items()
                 if not path.exists() or path.read_text(encoding="utf-8") != content]
        print("不同步：" + (", ".join(stale) if stale else "无"))
        sys.exit(1 if stale else 0)
    OUT.mkdir(exist_ok=True)
    for path, content in products.items():
        path.write_text(content, encoding="utf-8")
        print("写入", path.relative_to(ROOT), f"({len(content)} 字符)")
    print("完成。前端 import generated/domain.ts；后端 import contracts.generated.models / schema_store。")


if __name__ == "__main__":
    main()
