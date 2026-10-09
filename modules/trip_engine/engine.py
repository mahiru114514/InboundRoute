"""行程引擎兼容入口；新代码请直接从 service / http_api 导入。"""
try:
    from .service import TripService
    from .errors import EngineError
    from .store import TripStore
    from .anchors_seed import load_anchors
    from .http_api import build_handler, build_server, serve
    from .domain import (
        SHANGHAI,
        MAX_BODY,
        CONTRACT_VERSION,
        MODULE_ID,
        PACING_CAP,
        PARTY_WALK_MULTIPLIER,
        PARTY_COMPOSITIONS,
        PACINGS,
        INTERESTS,
        CURRENCIES,
        TRIP_STATUSES,
        DAY_STATUSES,
        STOP_TYPES,
        BORDER_BUFFER_DEFAULT,
        DEFAULT_DAILY_START,
        POI_ID_PATTERN,
        now_seconds,
        local_date_of,
        today_local,
        minutes_to_seconds,
        dwell_minutes_of,
        _require,
        _as_float,
        _trip_transaction,
    )
except ImportError:  # 兼容旧的 from engine import ... 脚本入口
    from modules.trip_engine.service import TripService
    from modules.trip_engine.errors import EngineError
    from modules.trip_engine.store import TripStore
    from modules.trip_engine.anchors_seed import load_anchors
    from modules.trip_engine.http_api import build_handler, build_server, serve
    from modules.trip_engine.domain import (
        SHANGHAI,
        MAX_BODY,
        CONTRACT_VERSION,
        MODULE_ID,
        PACING_CAP,
        PARTY_WALK_MULTIPLIER,
        PARTY_COMPOSITIONS,
        PACINGS,
        INTERESTS,
        CURRENCIES,
        TRIP_STATUSES,
        DAY_STATUSES,
        STOP_TYPES,
        BORDER_BUFFER_DEFAULT,
        DEFAULT_DAILY_START,
        POI_ID_PATTERN,
        now_seconds,
        local_date_of,
        today_local,
        minutes_to_seconds,
        dwell_minutes_of,
        _require,
        _as_float,
        _trip_transaction,
    )

__all__ = [
    'TripService',
    'EngineError',
    'TripStore',
    'load_anchors',
    'build_handler',
    'build_server',
    'serve',
    'SHANGHAI',
    'MAX_BODY',
    'CONTRACT_VERSION',
    'MODULE_ID',
    'PACING_CAP',
    'PARTY_WALK_MULTIPLIER',
    'PARTY_COMPOSITIONS',
    'PACINGS',
    'INTERESTS',
    'CURRENCIES',
    'TRIP_STATUSES',
    'DAY_STATUSES',
    'STOP_TYPES',
    'BORDER_BUFFER_DEFAULT',
    'DEFAULT_DAILY_START',
    'POI_ID_PATTERN',
    'now_seconds',
    'local_date_of',
    'today_local',
    'minutes_to_seconds',
    'dwell_minutes_of',
    '_require',
    '_as_float',
    '_trip_transaction',
]
