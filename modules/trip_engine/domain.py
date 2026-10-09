"""行程领域定义：枚举、时间单位、输入断言与事务锁。无 HTTP 依赖。"""
from __future__ import annotations

import re
import time
from datetime import datetime, timedelta, timezone
from functools import wraps

from .errors import EngineError

SHANGHAI = timezone(timedelta(hours=8))

MAX_BODY = 64 * 1024

CONTRACT_VERSION = "0.3.3"

MODULE_ID = "trip_engine"

PACING_CAP = {"relaxed": 2, "balanced": 4, "packed": 6}

PARTY_WALK_MULTIPLIER = {"solo": 1.0, "couple": 1.0, "family_kids": 1.3, "senior": 1.3}

PARTY_COMPOSITIONS = set(PARTY_WALK_MULTIPLIER)

PACINGS = set(PACING_CAP)

INTERESTS = {"modern_skyline", "history_culture", "local_life", "nature"}

CURRENCIES = {"CNY"}

TRIP_STATUSES = {"draft", "confirmed", "in_progress", "completed", "archived"}

DAY_STATUSES = {"empty", "arrival_only", "partial", "fulfilled", "locked"}

STOP_TYPES = {"poi", "hotel", "arrival_anchor", "departure_anchor"}

BORDER_BUFFER_DEFAULT = 90

DEFAULT_DAILY_START = "09:00"

POI_ID_PATTERN = re.compile(r"^[a-z]{2}_poi_[0-9]{5,8}$")

def now_seconds() -> int:
    return int(time.time())

def local_date_of(seconds: int) -> str:
    return datetime.fromtimestamp(seconds, SHANGHAI).strftime("%Y-%m-%d")

def today_local() -> str:
    return datetime.now(SHANGHAI).strftime("%Y-%m-%d")

def minutes_to_seconds(value) -> int:
    """把「整数分钟」或「HH:mm」统一成秒；非法输入抛 EngineError。"""
    if isinstance(value, bool):
        raise EngineError(400, "BAD_REQUEST", "停留时长必须是整数分钟或 HH:mm 格式")
    if isinstance(value, int):
        return value * 60
    if isinstance(value, str) and re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", value.strip()):
        hour, minute = value.strip().split(":")
        return (int(hour) * 60 + int(minute)) * 60
    raise EngineError(400, "BAD_REQUEST", "停留时长必须是整数分钟或 HH:mm 格式")

def dwell_minutes_of(poi: dict) -> int:
    """POI 的建议停留时长；契约允许点值与区间，这里取区间下界。"""
    dwell = (poi.get("operating_rules") or {}).get("dwell_time") or {}
    if dwell.get("kind") == "range":
        return int(dwell.get("minutes_min") or 90)
    return int(dwell.get("minutes") or 90)

def _require(condition, message):
    if not condition:
        raise EngineError(400, "BAD_REQUEST", message)

def _as_float(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EngineError(400, "BAD_REQUEST", f"{field} 必须是数字")
    return float(value)

def _trip_transaction(method):
    """同一行程的读取、版本检查与提交必须作为一个事务执行。"""
    @wraps(method)
    def transaction(self, trip_id, *args, **kwargs):
        # 固定数量的锁避免删除行程后积累锁；哈希冲突仅让不同的行程串行。
        with self._trip_locks[hash(trip_id) % len(self._trip_locks)]:
            return method(self, trip_id, *args, **kwargs)
    return transaction
