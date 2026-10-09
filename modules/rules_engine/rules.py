"""rules_engine 的纯规则层：时序推演 + Rule-01~04，无 HTTP、无 IO 副作用。

设计约束（见 contracts/devdocs/开发者B-开发需求文档.md）：
    · 方案 A 铁律：evaluate() 内绝不修改 days[].ordered_stops（本文件所有函数都只读输入，
      对 ordered_stops 的改动只能由用户显式触发的入口完成）；
    · 缺数据一律进 skipped_rules，禁止静默返回「通过」；
    · 文案只产出 message_key + message_args，不在这里拼中文；
    · 时间一律 Asia/Shanghai（UTC+8，无夏令时），存储用 UTC 秒。

时间轴公式以 contracts/TIME_BASELINE.md 与 contracts/scripts/validate.py 为准：
    arrival_at = 上一停靠点 departure_at + transit_from_previous.duration_seconds。
transfer_overhead 只存系数、不改写 duration_seconds（幂等），此处直接使用原 duration_seconds。
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.poi_availability import closure_hit, closure_rule_covers

SHANGHAI = timezone(timedelta(hours=8))

SEVERITY_ORDER = {"hard": 0, "soft_warning": 1, "soft_hint": 2}
CHANNEL_CAPACITY = {
    "modal_confirm": 1,
    "toast": 3,
    "inline_bubble": 3,
    "list_banner": 2,
    "card_badge": 3,
    "pin_badge": 1,
}
WEEKDAY_EN = {
    1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday",
    5: "Friday", 6: "Saturday", 7: "Sunday",
}
RULE_IDS = ["rule_01_closure", "rule_02_lightup", "rule_03_spread", "rule_04_homogeneous"]
RULE_SEVERITY = {
    "rule_01_closure": "hard",
    "rule_02_lightup": "soft_warning",
    "rule_03_spread": "soft_hint",
    "rule_04_homogeneous": "soft_hint",
}
RULE_CHANNEL = {
    "rule_01_closure": "modal_confirm",
    "rule_02_lightup": "inline_bubble",
    "rule_03_spread": "inline_bubble",
    "rule_04_homogeneous": "list_banner",
}


def load_contracts(workspace: str | Path) -> tuple[dict, dict]:
    """读取 contracts/rules.json 与 contracts/mappings.json（规则唯一来源）。"""
    root = Path(workspace)
    rules = json.loads((root / "contracts" / "rules.json").read_text(encoding="utf-8"))
    mappings = json.loads((root / "contracts" / "mappings.json").read_text(encoding="utf-8"))
    return rules, mappings


# ---------------------------------------------------------------- 时间工具

def to_shanghai(seconds: int) -> datetime:
    return datetime.fromtimestamp(seconds, SHANGHAI)


def local_hhmm(seconds: int) -> str:
    return datetime.fromtimestamp(seconds, SHANGHAI).strftime("%H:%M")


def local_date_of(seconds: int) -> str:
    return datetime.fromtimestamp(seconds, SHANGHAI).strftime("%Y-%m-%d")


def date_to_weekday(date_str: str) -> int:
    """ISO 8601：1=周一 … 7=周日。"""
    return datetime.strptime(date_str, "%Y-%m-%d").weekday() + 1


def weekday_en(iso: int) -> str:
    return WEEKDAY_EN[iso]


def hhmm_to_seconds(hhmm: str) -> int:
    hour, minute = hhmm.split(":")
    return int(hour) * 3600 + int(minute) * 60


def subtract_minutes(hhmm: str, minutes: int) -> str:
    total = hhmm_to_seconds(hhmm) - minutes * 60
    total %= 24 * 3600
    hour, remainder = divmod(total, 3600)
    minute = remainder // 60
    return f"{hour:02d}:{minute:02d}"


def date_hhmm_to_utc(date_str: str, hhmm: str) -> int:
    day = datetime.strptime(date_str, "%Y-%m-%d")
    hour, minute = hhmm.split(":")
    local = datetime(day.year, day.month, day.day, int(hour), int(minute), tzinfo=SHANGHAI)
    return int(local.timestamp())


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


# ---------------------------------------------------------------- 时间轴

def day_start_utc(trip: dict, day: dict) -> int:
    """每天用独立出发时刻；Day 1 不得早于抵达缓冲结束。"""
    if day.get("day_index") == 1:
        anchor = trip.get("anchor_arrival") or {}
        activity = anchor.get("activity_start_at")
        if not isinstance(activity, int):
            activity = int(anchor.get("at", anchor.get("arrival_at", 0))) + int(anchor.get("border_buffer_minutes", 90)) * 60
        configured = date_hhmm_to_utc(day["date"], day.get("daily_start_local") or "09:00")
        return max(activity, configured)
    return date_hhmm_to_utc(day["date"], day.get("daily_start_local") or "09:00")


def effective_transit_seconds(transit: dict | None) -> int | None:
    """区段有效耗时（秒），计入 transfer_overhead 的 30% 上浮（幂等，不回写 duration_seconds）。

    契约（C5，C 拍板）：duration_seconds 始终是原始值；
    transfer_overhead.counts_in_timeline=true 时按 applies_to 上浮：
      · walking_segment -> duration_seconds + walking_duration_seconds * (factor - 1)
      · whole_transit   -> duration_seconds * factor
      · none            -> duration_seconds
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


def build_timeline(trip: dict, day: dict) -> list[dict]:
    """只读地推算当日每个停靠点的 arrival_at / departure_at；绝不改动 ordered_stops。"""
    timeline: list[dict] = []
    previous_departure = day_start_utc(trip, day)
    for index, stop in enumerate(day["ordered_stops"]):
        transit_seconds = effective_transit_seconds(stop.get("transit_from_previous"))
        anchor = trip.get('anchor_arrival') or {}
        if (index == 0 and day.get('day_index') == 1 and stop.get('stop_type') == 'arrival_anchor'
                and stop.get('coordinate') == anchor.get('coordinate') and anchor.get('at') is not None):
            arrival_at = anchor['at']
        elif transit_seconds is None:
            arrival_at = previous_departure
        else:
            arrival_at = previous_departure + transit_seconds
        dwell_minutes = int(stop.get("planned_dwell_minutes") or 0)
        departure_at = arrival_at + dwell_minutes * 60
        timeline.append({
            "arrival_at": arrival_at,
            "departure_at": departure_at,
            "arrival_local": local_hhmm(arrival_at),
        })
        previous_departure = departure_at
    return timeline


# ---------------------------------------------------------------- notice

def make_notice(rule_id: str, severity: str, channel: str, message_key: str,
                message_args: dict, now: int, outcome: str = "pending",
                notice_id: str | None = None) -> dict:
    args = dict(message_args)
    if notice_id:
        args["notice_id"] = notice_id
    return {
        "rule_id": rule_id,
        "severity": severity,
        "outcome": outcome,
        "channel": channel,
        "message_key": message_key,
        "message_args": args,
        "confirmed_at": None,
        "raised_at": now,
        "expires_on_reorder": True,
    }


def notice_id_for(rule_id: str, day_index: int, poi_id: str | None) -> str:
    return f"{rule_id}:{day_index}:{poi_id or ''}"


def parse_notice_id(notice_id: str) -> tuple[str, int, str]:
    parts = notice_id.split(":", 2)
    if len(parts) != 3 or not parts[1].isdigit():
        raise ValueError(f"notice_id 格式非法：{notice_id}")
    return parts[0], int(parts[1]), parts[2]


# ---------------------------------------------------------------- Rule-01 闭馆

def rule_01_closure(day: dict, poi: dict, now: int) -> tuple[list[dict], list[tuple[str, str]]]:
    notices: list[dict] = []
    skips: list[tuple[str, str]] = []
    operating = poi.get("operating_rules") or {}
    status = operating.get("closure_data_status", "unknown")
    name_en = (poi.get("names") or {}).get("en", "")

    if status == "unknown":
        notices.append(make_notice(
            "rule_01_closure", "soft_hint", "toast", "rule.closure.data_unknown",
            {"poi_name": name_en}, now))
        return notices, skips
    if status == "unverified":
        notices.append(make_notice(
            "rule_01_closure", "soft_hint", "toast", "rule.closure.data_unverified",
            {"poi_name": name_en}, now))
        return notices, skips

    enclosed = operating.get("is_enclosed_attraction")
    if enclosed is None:
        notices.append(make_notice(
            "rule_01_closure", "soft_hint", "toast", "rule.closure.data_unknown",
            {"poi_name": name_en}, now))
        return notices, skips
    if enclosed is False:
        return notices, skips

    weekday = date_to_weekday(day["date"])
    hit, hit_rule = closure_hit(operating.get("closure_rules", []), day["date"], weekday)
    if hit is None or hit == "holiday_exception_open":
        return notices, skips
    notice_id = notice_id_for("rule_01_closure", day["day_index"], poi.get("poi_id"))
    if hit == "weekly":
        message_key = "rule.closure.confirm"
        message_args = {"poi_name": name_en, "weekday": weekday_en(weekday)}
    else:
        # special_period / maintenance / holiday_exception_closed 使用原因文案，而非硬编码 weekday。
        reason = ((hit_rule or {}).get("reason_en") or (hit_rule or {}).get("reason_zh")
                  or hit)
        message_key = "rule.closure.reason"
        message_args = {"poi_name": name_en, "reason": reason}
    notices.append(make_notice(
        "rule_01_closure", "hard", "modal_confirm", message_key,
        message_args, now, notice_id=notice_id))
    return notices, skips


# ---------------------------------------------------------------- Rule-02 亮灯

def match_lightup_window(windows: list[dict], mmdd: str) -> dict | None:
    for window in windows or []:
        date_from = window.get("date_from")
        date_to = window.get("date_to")
        if not date_from or not date_to:
            continue
        if date_from <= date_to:
            if date_from <= mmdd <= date_to:
                return window
        else:
            if mmdd >= date_from or mmdd <= date_to:
                return window
    return None


def compute_t_light(light_up: dict, window: dict) -> str | None:
    rule = light_up.get("T_light_rule", "window_start_minus_30")
    if rule == "window_start":
        return window.get("start")
    if rule == "window_start_minus_30":
        start = window.get("start")
        return subtract_minutes(start, 30) if start else None
    if rule == "sunset":
        # 需要日落数据源；契约缺失时按 skip 处理，禁止用默认值蒙。
        return None
    return None


def rule_02_lightup(day: dict, poi: dict, arrival_local: str | None, now: int,
                    ) -> tuple[list[dict], list[tuple[str, str]]]:
    notices: list[dict] = []
    skips: list[tuple[str, str]] = []
    light_up = (poi.get("operating_rules") or {}).get("light_up")
    if not light_up or not light_up.get("required"):
        return notices, skips
    windows = light_up.get("windows") or []
    if not windows:
        skips.append(("rule_02_lightup", "missing_data"))
        return notices, skips

    window = match_lightup_window(windows, day["date"][5:])
    if window is None:
        skips.append(("rule_02_lightup", "no_match"))
        return notices, skips
    if arrival_local is None:
        skips.append(("rule_02_lightup", "missing_data"))
        return notices, skips

    t_light = compute_t_light(light_up, window)
    if t_light is None:
        skips.append(("rule_02_lightup", "missing_data"))
        return notices, skips

    if arrival_local < t_light:
        notices.append(make_notice(
            "rule_02_lightup", "soft_warning", "inline_bubble", "rule.lightup.too_early",
            {"T_light": t_light, "light_start": window.get("start"), "light_close": window.get("close")}, now))
    elif arrival_local >= window.get("close", "23:59"):
        notices.append(make_notice(
            "rule_02_lightup", "soft_warning", "inline_bubble", "rule.lightup.too_late",
            {"window_close": window.get("close")}, now))
    return notices, skips


# ---------------------------------------------------------------- Rule-03 跨度

def _rule_by_id(rules: dict, rule_id: str) -> dict:
    for rule in rules["rules"]:
        if rule["rule_id"] == rule_id:
            return rule
    return {}


def rule_03_spread(day: dict, stops: list[dict], poi_lookup: dict[str, dict | None],
                   rules: dict, now: int) -> tuple[list[dict], list[tuple[str, str]]]:
    notices: list[dict] = []
    skips: list[tuple[str, str]] = []
    rule_def = _rule_by_id(rules, "rule_03_spread")
    city_config = (rule_def.get("city_config") or {}).get("shanghai") or {}
    straight_km = city_config.get("spread_straight_km")
    duration_minutes = city_config.get("spread_duration_minutes")
    config_missing = straight_km is None or duration_minutes is None

    poi_stops = [stop for stop in stops if stop.get("stop_type") == "poi" and stop.get("poi_id")]
    for previous, current in zip(poi_stops, poi_stops[1:]):
        if config_missing:
            skips.append(("rule_03_spread", "missing_data"))
            continue
        poi_prev = poi_lookup.get(previous["poi_id"])
        poi_curr = poi_lookup.get(current["poi_id"])
        if not poi_prev or not poi_curr:
            skips.append(("rule_03_spread", "missing_data"))
            continue
        core_prev = (poi_prev.get("city") or {}).get("is_core_urban")
        core_curr = (poi_curr.get("city") or {}).get("is_core_urban")
        if core_prev is None or core_curr is None:
            skips.append(("rule_03_spread", "missing_data"))
            continue
        if not (core_prev and core_curr):
            continue
        coord_prev = poi_prev.get("coordinate") or {}
        coord_curr = poi_curr.get("coordinate") or {}
        if not all(key in coord_prev and key in coord_curr for key in ("lat", "lng")):
            skips.append(("rule_03_spread", "missing_data"))
            continue
        distance_km = haversine_km(coord_prev["lat"], coord_prev["lng"],
                                   coord_curr["lat"], coord_curr["lng"])
        duration_seconds = effective_transit_seconds(current.get("transit_from_previous"))
        if duration_seconds is None:
            skips.append(("rule_03_spread", "missing_data"))
            continue
        duration_min = duration_seconds / 60
        if distance_km > straight_km and duration_min > duration_minutes:
            notices.append(make_notice(
                "rule_03_spread", "soft_hint", "inline_bubble", "rule.spread.long_transit",
                {"distance_km": round(distance_km, 1), "duration_minutes": round(duration_min),
                 "from_name_zh": (poi_prev.get("names") or {}).get("zh-Hans"),
                 "to_name_zh": (poi_curr.get("names") or {}).get("zh-Hans")},
                now))
    return notices, skips


# ---------------------------------------------------------------- Rule-04 同质化

def _category_level2_labels(mappings: dict) -> dict[str, str]:
    labels: dict[str, str] = {}
    for level1_key, level1 in mappings.get("category_taxonomy", {}).items():
        if level1_key.startswith("$") or not isinstance(level1, dict):
            continue
        for level2, meta in (level1.get("level2") or {}).items():
            labels[level2] = (meta or {}).get("en", level2)
    return labels


def rule_04_homogeneous(day: dict, stops: list[dict], poi_lookup: dict[str, dict | None],
                        rules: dict, mappings: dict, now: int) -> tuple[list[dict], list[tuple[str, str]]]:
    notices: list[dict] = []
    rule_def = _rule_by_id(rules, "rule_04_homogeneous")
    try:
        threshold = int((rule_def.get("trigger") or {}).get("value"))
    except (TypeError, ValueError):
        threshold = None
    if threshold is None:
        return [], [("rule_04_homogeneous", "missing_data")]
    labels = _category_level2_labels(mappings)
    counts: dict[str, int] = {}
    for stop in stops:
        if stop.get("stop_type") != "poi":
            continue
        poi = poi_lookup.get(stop.get("poi_id"))
        if not poi:
            continue
        level2 = (poi.get("category") or {}).get("level2")
        if not level2 or level2 not in labels:
            continue
        counts[level2] = counts.get(level2, 0) + 1
    for level2, count in counts.items():
        if count >= threshold:
            notices.append(make_notice(
                "rule_04_homogeneous", "soft_hint", "list_banner", "rule.homogeneous.banner",
                {"count": count, "category": labels[level2],
                 "category_zh": next(((p.get("category") or {}).get("label_zh") for p in poi_lookup.values()
                                      if p and (p.get("category") or {}).get("level2") == level2), None)}, now))
    return notices, []


# ---------------------------------------------------------------- 执行框架（方案 A）

def _dedupe_skips(skips: list[tuple[str, str]]) -> list[dict]:
    seen: set[tuple[str, str]] = set()
    result: list[dict] = []
    for rule_id, reason in skips:
        key = (rule_id, reason)
        if key not in seen:
            seen.add(key)
            result.append({"rule_id": rule_id, "reason": reason})
    return result


def evaluate_day(trip: dict, day: dict, poi_lookup: dict[str, dict | None],
                 rules: dict, mappings: dict, now: int) -> dict:
    """四步顺序：时序推演 → 硬规则 → 软规则 → 汇总排序。绝不修改 day。"""
    timeline = build_timeline(trip, day)
    notices: list[dict] = []
    skips: list[tuple[str, str]] = []

    stops = day["ordered_stops"]
    def context(items, poi=None, arrival=None):
        for notice in items:
            # Keep persisted hard-conflict arguments compatible with confirmations.
            if notice["severity"] == "hard":
                continue
            args = notice["message_args"]
            args.update(day_index=day["day_index"], date=day["date"])
            if poi:
                args.update(poi_id=poi.get("poi_id"), poi_name_zh=(poi.get("names") or {}).get("zh-Hans"))
            if arrival is not None:
                args["arrival_local"] = arrival
        return items
    for index, stop in enumerate(stops):
        if stop.get("stop_type") != "poi":
            continue
        poi = poi_lookup.get(stop.get("poi_id"))
        if not poi:
            skips.append(("rule_01_closure", "missing_data"))
            continue
        hard_notices, hard_skips = rule_01_closure(day, poi, now)
        notices.extend(context(hard_notices, poi))
        skips.extend(hard_skips)

    for index, stop in enumerate(stops):
        if stop.get("stop_type") != "poi":
            continue
        poi = poi_lookup.get(stop.get("poi_id"))
        if not poi:
            continue
        arrival_local = timeline[index].get("arrival_local") if index < len(timeline) else None
        soft_notices, soft_skips = rule_02_lightup(day, poi, arrival_local, now)
        notices.extend(context(soft_notices, poi, arrival_local))
        skips.extend(soft_skips)

    spread_notices, spread_skips = rule_03_spread(day, stops, poi_lookup, rules, now)
    notices.extend(context(spread_notices))
    skips.extend(spread_skips)

    homogeneous_notices, homogeneous_skips = rule_04_homogeneous(
        day, stops, poi_lookup, rules, mappings, now)
    notices.extend(context(homogeneous_notices))
    skips.extend(homogeneous_skips)

    notices.sort(key=lambda notice: SEVERITY_ORDER.get(notice["severity"], 9))
    return {
        "notices": notices,
        "evaluated_rules": list(RULE_IDS),
        "skipped_rules": _dedupe_skips(skips),
    }


def split_render(notices: list[dict], capacity: dict | None = None) -> tuple[list[dict], list[dict]]:
    """按 channel 承载位拆分：返回（就地展示的, 被裁掉的）。

    「还有 N 条建议」不该是信息终点：被裁掉的条目仍然要交回调用方，
    前端才能提供「展开全部」。硬冲突一如既往全部透传，不参与裁剪。
    """
    capacity = capacity or CHANNEL_CAPACITY
    used: dict[str, int] = {}
    rendered: list[dict] = []
    overflow_items: list[dict] = []
    for notice in notices:
        # 硬冲突必须全部透传，不能被「还有 N 条建议」吞掉。
        if notice.get("severity") == "hard":
            rendered.append(notice)
            continue
        channel = notice.get("channel")
        limit = capacity.get(channel)
        if limit is None:
            rendered.append(notice)
            continue
        if used.get(channel, 0) < limit:
            rendered.append(notice)
            used[channel] = used.get(channel, 0) + 1
        else:
            overflow_items.append(notice)
    return rendered, overflow_items


def summarize_render(notices: list[dict], capacity: dict | None = None) -> tuple[list[dict], int]:
    """按 channel 承载位裁剪，溢出数量合并为「还有 N 条建议」（纯函数，便于单测 TC-X-03）。"""
    rendered, overflow_items = split_render(notices, capacity)
    return rendered, len(overflow_items)
