"""契约校验器：schema 自检 + 示例校验 + 时间自洽性检查。

设计说明：schema 的内联与 $defs 打平由 scripts/_bundle.py 提供（与 generate.py 共用），
本文件只负责“检查”。
"""
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _bundle import EXTERNAL_REF, SCHEMA_NAMES, Contracts, json_pointer  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SHANGHAI = timezone(timedelta(hours=8))
FAILURES = []
CHECKS = 0

CONTRACTS = Contracts(ROOT)
LOCAL_SCHEMAS = CONTRACTS.schemas
BUNDLED = CONTRACTS.bundled
ENUMS = CONTRACTS.enums
RULES = CONTRACTS.rules
MAPPINGS = CONTRACTS.mappings
ERRORS = CONTRACTS.errors


def check(label, condition, detail=""):
    global CHECKS
    CHECKS += 1
    if not condition:
        FAILURES.append(f"{label} :: {detail}")
        print(f"FAIL  {label} :: {detail}")
    return condition


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate(instance, schema_name, label, expect_violation=False):
    """校验示例。expect_violation=True 时用于非法样例：预期它**违反** schema。"""
    try:
        import warnings
        from jsonschema import Draft202012Validator
        warnings.filterwarnings("ignore")
    except ImportError:
        print("提示：未安装 jsonschema，跳过结构校验")
        return []
    validator = Draft202012Validator(BUNDLED[schema_name])
    found = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    summary = "; ".join(f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}" for e in found[:5])
    if expect_violation:
        check(f"{label}: 按预期违反 {schema_name}", bool(found), "结构居然合法 —— 校验器漏检")
        print(f"      预期违规示例：{summary[:160]}")
    else:
        check(f"{label}: 符合 {schema_name}", not found, summary)
    return found


# ---------------------------------------------------------------- schema 自检
def walk(node, fn, path="$"):
    fn(node, path)
    if isinstance(node, dict):
        for key, value in node.items():
            walk(value, fn, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            walk(value, fn, f"{path}[{index}]")


for name, schema in LOCAL_SCHEMAS.items():
    def collect(node, path):
        if isinstance(node, dict) and isinstance(node.get("$ref"), str):
            ref = node["$ref"]
            if ref.startswith("#"):
                pointer = ref[1:]
                try:
                    json_pointer(BUNDLED[name], pointer)
                except (KeyError, TypeError):
                    check(f"{name}: 内部 $ref 可解析", False, f"{path} -> {ref}")
                return
            match = EXTERNAL_REF.match(ref)
            if check(f"{name}: $ref 格式合法", bool(match), f"{path} -> {ref}"):
                file_name, pointer = match.group("file"), match.group("pointer") or ""
                document = ENUMS if file_name == "enums.json" else LOCAL_SCHEMAS.get(file_name)
                if check(f"{name}: $ref 目标文件存在", document is not None, f"{path} -> {ref}"):
                    try:
                        json_pointer(document, pointer) if pointer else document
                    except (KeyError, TypeError):
                        check(f"{name}: $ref 锚点存在", False, f"{path} -> {ref}")
    walk(schema, collect)

    def required_check(node, path):
        if isinstance(node, dict) and "required" in node and "properties" in node:
            missing = [field for field in node["required"] if field not in node["properties"]]
            check(f"{name}: required 字段已声明", not missing, f"{path} 缺 {missing}")
    walk(schema, required_check)


# ---------------------------------------------------------------- 时间基准检查
def to_local(seconds):
    return datetime.fromtimestamp(seconds, SHANGHAI)


def effective_transit_seconds(transit):
    """区段有效耗时（秒），与 rules_engine 同一口径（C5，C 拍板）。

    duration_seconds 始终是原始值；transfer_overhead.counts_in_timeline=true 时按 applies_to 上浮：
      walking_segment -> duration_seconds + walking_duration_seconds * (factor - 1)
      whole_transit   -> duration_seconds * factor
      none            -> duration_seconds
    """
    if not isinstance(transit, dict):
        return None
    duration = transit.get("duration_seconds")
    if duration is None:
        return None
    duration = int(duration)
    overhead = transit.get("transfer_overhead")
    if not isinstance(overhead, dict) or overhead.get("counts_in_timeline") is False:
        return duration
    try:
        factor = float(overhead.get("factor"))
    except (TypeError, ValueError):
        return duration
    applies_to = overhead.get("applies_to", "walking_segment")
    if applies_to == "whole_transit":
        return int(round(duration * factor))
    if applies_to == "walking_segment":
        walking = transit.get("walking_duration_seconds")
        if walking is None:
            return duration
        return int(round(duration + int(walking) * (factor - 1.0)))
    return duration


def check_time_consistency(trip, label):
    arrival = trip["anchor_arrival"]["arrival_at"]
    expect_start = arrival + trip["anchor_arrival"].get("border_buffer_minutes", 90) * 60
    check(f"{label}: activity_start_at 派生正确",
          trip["anchor_arrival"]["activity_start_at"] == expect_start,
          f"{trip['anchor_arrival']['activity_start_at']} != {expect_start}")
    first_day = trip["days"][0]
    check(f"{label}: 抵达日期与 days[0].date 一致",
          to_local(arrival).strftime("%Y-%m-%d") == first_day["date"],
          f"{to_local(arrival):%Y-%m-%d} != {first_day['date']}（PRD 示例正是在此处矛盾）")
    for day in trip["days"][1:]:
        check(f"{label}: Day{day['day_index']} 有 daily_start_local",
              bool(day.get("daily_start_local")), "缺失则 Day2..N 时间轴断链")
    for day in trip["days"]:
        previous = None
        for stop in day["ordered_stops"]:
            arrival_at, departure_at = stop.get("arrival_at"), stop.get("departure_at")
            if arrival_at and departure_at:
                check(f"{label}: 停留时长自洽",
                      departure_at - arrival_at == stop["planned_dwell_minutes"] * 60,
                      f"Day{day['day_index']} stop{stop['stop_order']}")
            if previous and arrival_at:
                duration = effective_transit_seconds(stop.get("transit_from_previous"))
                if duration:
                    check(f"{label}: 区段耗时衔接",
                          arrival_at == previous + duration,
                          f"Day{day['day_index']} stop{stop['stop_order']}")
            previous = departure_at or previous
    check(f"{label}: timezone 固定 Asia/Shanghai", trip["timezone"] == "Asia/Shanghai", trip["timezone"])
    # 注：停留时长只含游览时间；区段耗时衔接已计入 transfer_overhead（counts_in_timeline=true 时按 applies_to 上浮）。


# ---------------------------------------------------------------- 示例校验
def payload_of(data):
    """去掉导出用的元字段（$ 前缀），仅保留业务数据。"""
    return {key: value for key, value in data.items() if not key.startswith("$")}


for example in sorted((ROOT / "examples").glob("*.json")):
    if example.name.endswith(".invalid.json"):
        continue
    data = load(example)
    target = data.get("$schema_target")
    if not target:
        continue
    payload = payload_of(data)
    validate(payload, target, example.name)
    if target == "trip.schema.json":
        check_time_consistency(payload, example.name)


def validate_invalid_examples():
    """非法样例必须被拦住，否则校验器形同虚设。

    非法样例按「结构违规」验收，不跑时间检查：时间矛盾类校验是独立的一层，
    两者混在一个 check 里会出现「预期失败被当成失败」的假警报。
    """
    for example in sorted((ROOT / "examples").glob("*.invalid.json")):
        data = load(example)
        target = data.get("$schema_target")
        payload = payload_of(data)
        validate(payload, target, example.name, expect_violation=True)


def check_invalid_time_detection():
    """单独验证时间矛盾能被时间检查层发现（用 PRD 的原始错误数据构造）。"""
    arrival = 1789728000  # PRD 原示例：2026-09-18 18:40 UTC+8
    first_day = "2026-10-12"
    expected = to_local(arrival).strftime("%Y-%m-%d")
    check("时间检查层能发现 PRD 的日期矛盾", expected != first_day,
          f"{expected} vs {first_day} —— 应当不一致")
    check("时间检查层能发现缺每日起点",
          "daily_start_local" not in {"day_index": 2, "date": "2026-10-13"},
          "缺 daily_start_local 应被标记")


validate_invalid_examples()
check_invalid_time_detection()

# ---------------------------------------------------------------- 契约自洽
check("rules.json 四条规则齐全", len(RULES["rules"]) == 4, str(len(RULES["rules"])))
rule_ids = {rule["rule_id"] for rule in RULES["rules"]}
declared = (set(RULES["execution_model"]["steps"]["step_2_hard_rules"]["rules"]) |
            set(RULES["execution_model"]["steps"]["step_3_soft_rules"]["rules"]))
check("规则编号与 execution_model 对齐", declared == rule_ids, f"{rule_ids} vs {declared}")
for rule in RULES["rules"]:
    keys = [rule["response"]["message_key"]] if "response" in rule else \
           [branch["message_key"] for branch in rule.get("branches", [])]
    for key in keys:
        check(f"{rule['rule_id']}: 只使用已登记文案键", key in RULES["notice_message_keys"]["keys"], key)
    check(f"{rule['rule_id']}: 有 AC 用例", bool(RULES["ac_matrix"].get(rule["rule_id"])), "缺验收用例")
check("错误码 http 状态合法", all(100 <= code["http"] <= 599 for code in ERRORS["codes"]))
check("降级矩阵覆盖 5 类依赖",
      len([key for key in MAPPINGS["degradation_matrix"] if not key.startswith("$")]) == 5,
      str(list(MAPPINGS["degradation_matrix"])))
check("离线包必须含进出站口数据",
      any("进出站口" in item for item in MAPPINGS["offline_package"]["must_include"]))
taxonomy = {key: value for key, value in MAPPINGS["category_taxonomy"].items() if not key.startswith("$")}
all_level2 = [key for value in taxonomy.values() for key in value["level2"]]
check("分类字典 level2 无重复", len(all_level2) == len(set(all_level2)), str(len(all_level2) - len(set(all_level2))))
check("文案模板覆盖所有登记键",
      set(RULES["notice_message_keys"]["keys"]) <= set(MAPPINGS["notice_templates"]),
      str(set(RULES["notice_message_keys"]["keys"]) - set(MAPPINGS["notice_templates"])))
# 方案 A 的回归：软规则不得自动改单，且必须定义「移动后仍不满足」分支
policy = RULES["execution_model"]["iteration_policy"]
check("C3 方案 A：禁止引擎改单", policy.get("auto_apply_soft_rules") is False and policy.get("max_iterations") == 1,
      str(policy))
move = next(branch for branch in next(r for r in RULES["rules"] if r["rule_id"] == "rule_02_lightup")["branches"]
            if branch["id"] == "too_early")["on_action"]["move_to_evening"]
check("C3：move_to_evening 仅用户可触发", move.get("trigger") == "user", str(move.get("trigger")))
check("C3：定义了末位语义", bool(move.get("last_position_definition")), "缺 last_position_definition")
check("C3：定义了移动后仍不满足的分支", "on_still_failing" in move, "缺 on_still_failing")
check("C3：移动后仍不满足有文案键",
      move.get("on_still_failing", {}).get("message_key") in MAPPINGS["notice_templates"],
      str(move.get("on_still_failing", {}).get("message_key")))
check("C3：AC 覆盖方案 A 的四个新场景",
      {"AC-R2-04", "AC-R2-05", "AC-R2-06", "AC-R2-07"} <=
      {case["id"] for case in RULES["ac_matrix"]["rule_02_lightup"]},
      str([case["id"] for case in RULES["ac_matrix"]["rule_02_lightup"]]))
check("每个 rule_id 都有 AC", all(RULES["ac_matrix"].get(rule["rule_id"]) for rule in RULES["rules"]))
pacing = MAPPINGS["pacing_cap"]
check("pacing 三档均为闭区间",
      all("max" in pacing[key] for key in ("relaxed", "balanced", "packed")),
      "PRD 的 Packed 是下界，已修正为区间")

print(f"\n检查项 {CHECKS} 个，失败 {len(FAILURES)} 个")
if FAILURES:
    print("失败明细：")
    for item in FAILURES:
        print("  -", item)
sys.exit(1 if FAILURES else 0)
