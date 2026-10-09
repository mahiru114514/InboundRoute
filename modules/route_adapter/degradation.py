"""五类依赖逐项降级（C5）。严格按 contracts/mappings.json#/degradation_matrix。"""
from __future__ import annotations

# 冻结自 mappings.json#/degradation_matrix
DEGRADATION_MATRIX = {
    "route_api": {
        "failure": ["timeout", "rate_limited", "no_route"],
        "fallback": "直线距离粗算",
        "null_fields": ["cost", "transfer_count", "congestion_level", "segments"],
        "notice_key": "degraded.direct_orientation",
        "must_notify": True,
    },
    "reverse_geo": {
        "failure": ["timeout", "no_result"],
        "fallback": "要求用户手动打点确认坐标",
        "null_fields": ["coordinate"],
        "notice_key": "degraded.partial_data",
        "must_notify": True,
    },
    "realtime_transit": {
        "failure": ["unsupported_city", "timeout"],
        "fallback": "使用计划时刻表；换乘预警不可用",
        "null_fields": ["realtime_arrival", "transfer_warning"],
        "notice_key": "degraded.partial_data",
        "must_notify": True,
    },
    "rules_data": {
        "failure": ["closure_data_status=unknown"],
        "fallback": "软提示，禁止静默放行",
        "null_fields": ["closure_rules"],
        "notice_key": "rule.closure.data_unknown",
        "must_notify": True,
    },
    "tiles": {
        "failure": ["load_error"],
        "fallback": "保留纯文字流程树",
        "null_fields": ["map_tiles"],
        "notice_key": "offline.mode",
        "must_notify": True,
    },
}


def degrade(dependency: str, reason: str) -> dict:
    """按依赖返回降级产物：fallback 文案、notice_key、null_fields、must_notify。"""
    if dependency not in DEGRADATION_MATRIX:
        raise ValueError("未知依赖：" + str(dependency))
    entry = DEGRADATION_MATRIX[dependency]
    return {
        "dependency": dependency,
        "reason": reason,
        "fallback": entry["fallback"],
        "notice_key": entry["notice_key"],
        "must_notify": entry["must_notify"],
        "null_fields": list(entry.get("null_fields", [])),
        "data_source": "degraded",
    }


def null_out(payload: dict, fields) -> dict:
    """把数值字段置为 null（不是 0），保留结构。"""
    for field in fields:
        if field in payload:
            payload[field] = None
    return payload