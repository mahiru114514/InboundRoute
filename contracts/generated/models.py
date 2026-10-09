"""领域模型（从 schemas/*.schema.json 生成，请勿手改）。

所有 *_at 为 UTC 秒；date 为 Asia/Shanghai 日期；*_local 为同日时刻。见 contracts/TIME_BASELINE.md

用法：
    from contracts.generated.models import Trip
    trip = Trip.from_dict(payload)     # 未知字段被忽略，嵌套对象自动转换
    payload = trip.to_dict()           # 只输出已知字段，JSON 名自动还原

严格校验（类型/必填/正则）请用 generated/schema_store.py 的 validate()。
注意：所有 dataclass 都是 kw_only，因此可以按契约顺序声明字段（必填与选填混排）。
JSON 里非法的 Python 标识符会在属性名上转义：from → from_、zh-Hans → zh_Hans，
to_dict()/from_dict() 会自动做双向映射，业务代码里请使用属性名。
需要 Python 3.10+（dataclass kw_only 与 PEP 604 联合类型）。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, is_dataclass
from typing import Any, Literal


def _build(cls, value):
    """把 dict 构造为 dataclass；**必须优先走 cls.from_dict**，否则嵌套对象不会被递归转换。"""
    if value is None or not isinstance(value, dict):
        return value
    if not (is_dataclass(cls) and isinstance(cls, type)):
        return value
    builder = getattr(cls, "from_dict", None)
    if callable(builder):
        return builder(value)
    known = {item.name for item in fields(cls)}
    return cls(**{key: val for key, val in value.items() if key in known})


def _build_list(cls, value):
    if value is None:
        return []
    return [_build(cls, item) for item in value]


def _dump(value):
    """递归导出为 JSON 友好结构；dataclass 一律走它自己的 to_dict（保证别名还原）。"""
    if is_dataclass(value) and not isinstance(value, type):
        exporter = getattr(value, "to_dict", None)
        if callable(exporter):
            return exporter()
        return {key: _dump(val) for key, val in asdict(value).items()}
    if isinstance(value, list):
        return [_dump(item) for item in value]
    if isinstance(value, dict):
        return {key: _dump(val) for key, val in value.items()}
    return value


# ----------------------------------------------------------------------
# POIMaster  (poi.schema.json)
# ----------------------------------------------------------------------

@dataclass(kw_only=True)
class Point:
    lat: float
    lng: float
    crs: Literal['WGS84', 'GCJ-02', 'BD-09'] = 'WGS84'  # PRD 未标坐标系；内部主数据统一 WGS84，由 Adapter 单向转换。
    precision_m: float = 50  # 入口点级精度（非几何中心）

    @classmethod
    def from_dict(cls, value: dict) -> "Point":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            lat=value.get("lat"),
            lng=value.get("lng"),
            crs=value.get("crs"),
            precision_m=value.get("precision_m"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "lat": _dump(self.lat),
            "lng": _dump(self.lng),
            "crs": _dump(self.crs),
            **({} if self.precision_m is None else {"precision_m": _dump(self.precision_m)}),
        }


@dataclass(kw_only=True)
class PoiNames:
    """多语言名称。PRD 只有 en/zh/pinyin 三件套，日语场景（Sensō-ji）会失效，故改为语言映射。"""

    zh_Hans: str  # （JSON 字段名：zh-Hans）
    zh_Hant: str = None  # （JSON 字段名：zh-Hant）
    en: str
    ja: str = None
    ko: str = None

    @classmethod
    def from_dict(cls, value: dict) -> "PoiNames":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            zh_Hans=value.get("zh-Hans"),
            zh_Hant=value.get("zh-Hant"),
            en=value.get("en"),
            ja=value.get("ja"),
            ko=value.get("ko"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "zh-Hans": _dump(self.zh_Hans),
            **({} if self.zh_Hant is None else {"zh-Hant": _dump(self.zh_Hant)}),
            "en": _dump(self.en),
            **({} if self.ja is None else {"ja": _dump(self.ja)}),
            **({} if self.ko is None else {"ko": _dump(self.ko)}),
        }


@dataclass(kw_only=True)
class PoiRomanization:
    """PRD 的 name_pinyin 带声调（wài tān）无法用于检索匹配，故拆为两套。"""

    pinyin: str  # 带声调，用于现场路牌比对展示
    pinyin_plain: str  # 无声调，用于检索匹配
    ja_romaji: str = None
    ko_rr: str = None

    @classmethod
    def from_dict(cls, value: dict) -> "PoiRomanization":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            pinyin=value.get("pinyin"),
            pinyin_plain=value.get("pinyin_plain"),
            ja_romaji=value.get("ja_romaji"),
            ko_rr=value.get("ko_rr"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "pinyin": _dump(self.pinyin),
            "pinyin_plain": _dump(self.pinyin_plain),
            **({} if self.ja_romaji is None else {"ja_romaji": _dump(self.ja_romaji)}),
            **({} if self.ko_rr is None else {"ko_rr": _dump(self.ko_rr)}),
        }


@dataclass(kw_only=True)
class PoiCategory:
    """三级分类字典。PRD 只有自由字符串，Rule-04 因此无法统计。"""

    level1: Literal['modern_skyline', 'history_culture', 'local_life', 'nature', 'transport_hub', 'other']
    level2: str  # 受 mappings.json 的 category_taxonomy 约束，枚举值以该文件为准（Rule-04 按此计数）。
    label_en: str
    label_zh: str

    @classmethod
    def from_dict(cls, value: dict) -> "PoiCategory":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            level1=value.get("level1"),
            level2=value.get("level2"),
            label_en=value.get("label_en"),
            label_zh=value.get("label_zh"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "level1": _dump(self.level1),
            "level2": _dump(self.level2),
            "label_en": _dump(self.label_en),
            "label_zh": _dump(self.label_zh),
        }


@dataclass(kw_only=True)
class PoiDropOffLocations:
    point: Point
    desc_zh: str
    desc_en: str
    source: Literal['amap', 'tencent', 'baidu', 'curated', 'manual', 'degraded', 'mock']
    priority: int  # 1 最高；人工(curated/manual) 优先于三方(api)
    verified_at: int = None  # UTC 秒
    note_zh: str = None
    note_en: str = None

    @classmethod
    def from_dict(cls, value: dict) -> "PoiDropOffLocations":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            point=_build(Point, value.get("point")),
            desc_zh=value.get("desc_zh"),
            desc_en=value.get("desc_en"),
            source=value.get("source"),
            priority=value.get("priority"),
            verified_at=value.get("verified_at"),
            note_zh=value.get("note_zh"),
            note_en=value.get("note_en"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "point": _dump(self.point),
            "desc_zh": _dump(self.desc_zh),
            "desc_en": _dump(self.desc_en),
            "source": _dump(self.source),
            "priority": _dump(self.priority),
            **({} if self.verified_at is None else {"verified_at": _dump(self.verified_at)}),
            **({} if self.note_zh is None else {"note_zh": _dump(self.note_zh)}),
            **({} if self.note_en is None else {"note_en": _dump(self.note_en)}),
        }


@dataclass(kw_only=True)
class PoiOperatingRules:
    opening_hours: list[PoiOperatingRulesOpeningHours] = field(default_factory=list)  # 结构化时段。PRD 的自由字符串无法表达午休、按星期差异、旺季调整。
    last_entry_time: str | None = None  # 为 null 表示未采集；展示层按 mappings.json 的 null_policy 处理（PRD 承诺展示却给了 null）。
    closure_data_status: Literal['verified', 'unverified', 'unknown'] = 'unknown'  # PRD 的 closure_days: [] 无法区分「不闭馆」和「未采集」，故显式加此字段。unknown 时 Rule-01 不得静默放行。
    closure_rules: list[PoiOperatingRulesClosureRules] = field(default_factory=list)
    is_enclosed_attraction: bool = False  # 人工标注字段：有围合检票边界（博物馆/园林）为 true，开放式街区为 false。维护方=数据运营。
    reservation_required: bool = False  # PRD 完全缺失。故宫/国博类预约制直接决定行程可行性。
    advance_booking_days: int | None = None
    light_up: PoiOperatingRulesLightUp | None = None  # PRD 的 light_up_required + light_up_schedule{summer,winter} 无法推出 T_light（区间不是点，且季节切分未定义）。
    dwell_time: PoiOperatingRulesDwellTime | None = None  # PRD 展示区间（1.5-2 Hours）但字段是单值 90 分钟，故显式表达 kind。

    @classmethod
    def from_dict(cls, value: dict) -> "PoiOperatingRules":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            opening_hours=_build_list(PoiOperatingRulesOpeningHours, value.get("opening_hours")),
            last_entry_time=value.get("last_entry_time"),
            closure_data_status=value.get("closure_data_status"),
            closure_rules=_build_list(PoiOperatingRulesClosureRules, value.get("closure_rules")),
            is_enclosed_attraction=value.get("is_enclosed_attraction"),
            reservation_required=value.get("reservation_required"),
            advance_booking_days=value.get("advance_booking_days"),
            light_up=_build(PoiOperatingRulesLightUp, value.get("light_up")),
            dwell_time=_build(PoiOperatingRulesDwellTime, value.get("dwell_time")),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "opening_hours": _dump(self.opening_hours),
            **({} if self.last_entry_time is None else {"last_entry_time": _dump(self.last_entry_time)}),
            "closure_data_status": _dump(self.closure_data_status),
            **({} if self.closure_rules is None else {"closure_rules": _dump(self.closure_rules)}),
            "is_enclosed_attraction": _dump(self.is_enclosed_attraction),
            **({} if self.reservation_required is None else {"reservation_required": _dump(self.reservation_required)}),
            **({} if self.advance_booking_days is None else {"advance_booking_days": _dump(self.advance_booking_days)}),
            **({} if self.light_up is None else {"light_up": _dump(self.light_up)}),
            **({} if self.dwell_time is None else {"dwell_time": _dump(self.dwell_time)}),
        }


@dataclass(kw_only=True)
class PoiOperatingRulesOpeningHours:
    weekdays: list[Literal[1, 2, 3, 4, 5, 6, 7]] = field(default_factory=list)
    date_from: str = None
    date_to: str = None
    open: str
    close: str
    close_next_day: bool = False  # close 是否落在次日（如夜场 23:00-02:00）

    @classmethod
    def from_dict(cls, value: dict) -> "PoiOperatingRulesOpeningHours":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            weekdays=value.get("weekdays"),
            date_from=value.get("date_from"),
            date_to=value.get("date_to"),
            open=value.get("open"),
            close=value.get("close"),
            close_next_day=value.get("close_next_day"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            **({} if self.weekdays is None else {"weekdays": _dump(self.weekdays)}),
            **({} if self.date_from is None else {"date_from": _dump(self.date_from)}),
            **({} if self.date_to is None else {"date_to": _dump(self.date_to)}),
            "open": _dump(self.open),
            "close": _dump(self.close),
            **({} if self.close_next_day is None else {"close_next_day": _dump(self.close_next_day)}),
        }


@dataclass(kw_only=True)
class PoiOperatingRulesClosureRules:
    kind: Literal['weekly', 'special_period', 'maintenance', 'holiday_exception_open', 'holiday_exception_closed']
    weekday: Literal[1, 2, 3, 4, 5, 6, 7] = None
    date: str = None
    date_from: str = None
    date_to: str = None
    reason_zh: str = None
    reason_en: str = None
    note_zh: str = None

    @classmethod
    def from_dict(cls, value: dict) -> "PoiOperatingRulesClosureRules":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            kind=value.get("kind"),
            weekday=value.get("weekday"),
            date=value.get("date"),
            date_from=value.get("date_from"),
            date_to=value.get("date_to"),
            reason_zh=value.get("reason_zh"),
            reason_en=value.get("reason_en"),
            note_zh=value.get("note_zh"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "kind": _dump(self.kind),
            **({} if self.weekday is None else {"weekday": _dump(self.weekday)}),
            **({} if self.date is None else {"date": _dump(self.date)}),
            **({} if self.date_from is None else {"date_from": _dump(self.date_from)}),
            **({} if self.date_to is None else {"date_to": _dump(self.date_to)}),
            **({} if self.reason_zh is None else {"reason_zh": _dump(self.reason_zh)}),
            **({} if self.reason_en is None else {"reason_en": _dump(self.reason_en)}),
            **({} if self.note_zh is None else {"note_zh": _dump(self.note_zh)}),
        }


@dataclass(kw_only=True)
class PoiOperatingRulesLightUp:
    """PRD 的 light_up_required + light_up_schedule{summer,winter} 无法推出 T_light（区间不是点，且季节切分未定义）。"""

    required: bool = False
    T_light_rule: Literal['window_start_minus_30', 'sunset', 'window_start'] = 'window_start_minus_30'  # T_light 的取点规则；Rule-02 依赖它。
    windows: list[PoiOperatingRulesLightUpWindows] = field(default_factory=list)

    @classmethod
    def from_dict(cls, value: dict) -> "PoiOperatingRulesLightUp":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            required=value.get("required"),
            T_light_rule=value.get("T_light_rule"),
            windows=_build_list(PoiOperatingRulesLightUpWindows, value.get("windows")),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "required": _dump(self.required),
            **({} if self.T_light_rule is None else {"T_light_rule": _dump(self.T_light_rule)}),
            "windows": _dump(self.windows),
        }


@dataclass(kw_only=True)
class PoiOperatingRulesLightUpWindows:
    date_from: str
    date_to: str
    label_zh: str = None
    label_en: str = None
    start: str
    close: str

    @classmethod
    def from_dict(cls, value: dict) -> "PoiOperatingRulesLightUpWindows":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            date_from=value.get("date_from"),
            date_to=value.get("date_to"),
            label_zh=value.get("label_zh"),
            label_en=value.get("label_en"),
            start=value.get("start"),
            close=value.get("close"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "date_from": _dump(self.date_from),
            "date_to": _dump(self.date_to),
            **({} if self.label_zh is None else {"label_zh": _dump(self.label_zh)}),
            **({} if self.label_en is None else {"label_en": _dump(self.label_en)}),
            "start": _dump(self.start),
            "close": _dump(self.close),
        }


@dataclass(kw_only=True)
class PoiOperatingRulesDwellTime:
    """PRD 展示区间（1.5-2 Hours）但字段是单值 90 分钟，故显式表达 kind。"""

    kind: Literal['point', 'range']
    minutes: int = None
    minutes_min: int = None
    minutes_max: int = None

    @classmethod
    def from_dict(cls, value: dict) -> "PoiOperatingRulesDwellTime":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            kind=value.get("kind"),
            minutes=value.get("minutes"),
            minutes_min=value.get("minutes_min"),
            minutes_max=value.get("minutes_max"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "kind": _dump(self.kind),
            **({} if self.minutes is None else {"minutes": _dump(self.minutes)}),
            **({} if self.minutes_min is None else {"minutes_min": _dump(self.minutes_min)}),
            **({} if self.minutes_max is None else {"minutes_max": _dump(self.minutes_max)}),
        }


@dataclass(kw_only=True)
class PoiProviderRefs:
    """缺此映射会无法把三方返回的 POI 关联回内部主数据。"""

    amap: str = None
    tencent: str = None
    baidu: str = None

    @classmethod
    def from_dict(cls, value: dict) -> "PoiProviderRefs":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            amap=value.get("amap"),
            tencent=value.get("tencent"),
            baidu=value.get("baidu"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            **({} if self.amap is None else {"amap": _dump(self.amap)}),
            **({} if self.tencent is None else {"tencent": _dump(self.tencent)}),
            **({} if self.baidu is None else {"baidu": _dump(self.baidu)}),
        }


@dataclass(kw_only=True)
class PoiProvenance:
    source: Literal['amap', 'tencent', 'baidu', 'curated', 'manual', 'degraded', 'mock']
    updated_at: int  # UTC 秒
    reviewed_by: str = None
    confidence: float = 1

    @classmethod
    def from_dict(cls, value: dict) -> "PoiProvenance":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            source=value.get("source"),
            updated_at=value.get("updated_at"),
            reviewed_by=value.get("reviewed_by"),
            confidence=value.get("confidence"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "source": _dump(self.source),
            "updated_at": _dump(self.updated_at),
            **({} if self.reviewed_by is None else {"reviewed_by": _dump(self.reviewed_by)}),
            **({} if self.confidence is None else {"confidence": _dump(self.confidence)}),
        }


@dataclass(kw_only=True)
class Poi:
    """C2 实体表。相对 PRD 4.1 的改动已在 x-changed 标注；PRD 未定义的必填/取值域/默认值/单位在此补齐。"""

    description_zh: str = None  # 简短中文介绍，概述主要看点及游玩方式；可选以兼容旧数据，缺失时由页面提示简介待补充。
    poi_id: str  # 内部 ID，稳定不变；三方映射见 provider_refs。
    names: PoiNames | None  # 多语言名称。PRD 只有 en/zh/pinyin 三件套，日语场景（Sensō-ji）会失效，故改为语言映射。
    romanization: PoiRomanization | None = None  # PRD 的 name_pinyin 带声调（wài tān）无法用于检索匹配，故拆为两套。
    search_aliases: list[str] = field(default_factory=list)
    category: PoiCategory | None  # 三级分类字典。PRD 只有自由字符串，Rule-04 因此无法统计。
    coordinate: Point
    drop_off_locations: list[PoiDropOffLocations] = field(default_factory=list)  # PRD 的 suggested_drop_off_coordinate 单值改为数组，以表达多入口/多停靠点与来源优先级。
    operating_rules: PoiOperatingRules | None
    provider_refs: PoiProviderRefs | None = None  # 缺此映射会无法把三方返回的 POI 关联回内部主数据。
    provenance: PoiProvenance | None
    tags: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, value: dict) -> "Poi":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            description_zh=value.get("description_zh"),
            poi_id=value.get("poi_id"),
            names=_build(PoiNames, value.get("names")),
            romanization=_build(PoiRomanization, value.get("romanization")),
            search_aliases=value.get("search_aliases"),
            category=_build(PoiCategory, value.get("category")),
            coordinate=_build(Point, value.get("coordinate")),
            drop_off_locations=_build_list(PoiDropOffLocations, value.get("drop_off_locations")),
            operating_rules=_build(PoiOperatingRules, value.get("operating_rules")),
            provider_refs=_build(PoiProviderRefs, value.get("provider_refs")),
            provenance=_build(PoiProvenance, value.get("provenance")),
            tags=value.get("tags"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            **({} if self.description_zh is None else {"description_zh": _dump(self.description_zh)}),
            "poi_id": _dump(self.poi_id),
            "names": _dump(self.names),
            **({} if self.romanization is None else {"romanization": _dump(self.romanization)}),
            **({} if self.search_aliases is None else {"search_aliases": _dump(self.search_aliases)}),
            "category": _dump(self.category),
            "coordinate": _dump(self.coordinate),
            **({} if self.drop_off_locations is None else {"drop_off_locations": _dump(self.drop_off_locations)}),
            "operating_rules": _dump(self.operating_rules),
            **({} if self.provider_refs is None else {"provider_refs": _dump(self.provider_refs)}),
            "provenance": _dump(self.provenance),
            **({} if self.tags is None else {"tags": _dump(self.tags)}),
        }


# ----------------------------------------------------------------------
# TripInstance  (trip.schema.json)
# ----------------------------------------------------------------------

@dataclass(kw_only=True)
class DayAnchor:
    type: Literal['poi', 'hotel', 'arrival_anchor', 'departure_anchor']
    name_zh: str
    name_en: str
    name_pinyin: str = None
    poi_id: str | None = None
    coordinate: Point

    @classmethod
    def from_dict(cls, value: dict) -> "DayAnchor":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            type=value.get("type"),
            name_zh=value.get("name_zh"),
            name_en=value.get("name_en"),
            name_pinyin=value.get("name_pinyin"),
            poi_id=value.get("poi_id"),
            coordinate=_build(Point, value.get("coordinate")),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "type": _dump(self.type),
            "name_zh": _dump(self.name_zh),
            "name_en": _dump(self.name_en),
            **({} if self.name_pinyin is None else {"name_pinyin": _dump(self.name_pinyin)}),
            **({} if self.poi_id is None else {"poi_id": _dump(self.poi_id)}),
            "coordinate": _dump(self.coordinate),
        }


@dataclass(kw_only=True)
class Notice:
    rule_id: Literal['rule_01_closure', 'rule_02_lightup', 'rule_03_spread', 'rule_04_homogeneous']
    severity: Literal['hard', 'soft_warning', 'soft_hint']
    outcome: Literal['pending', 'confirmed_proceed', 'rejected', 'auto_dismissed', 'expired_on_reorder']
    channel: Literal['modal_confirm', 'toast', 'inline_bubble', 'list_banner', 'card_badge', 'pin_badge']
    message_key: str = None  # 对应 mappings.json/notice_templates 的键，不存最终文案（便于多语言）
    message_args: dict[str, Any] = field(default_factory=dict)
    confirmed_at: int | None = None
    raised_at: int
    expires_on_reorder: bool = True  # 改期后确认是否失效（PRD 未定义）

    @classmethod
    def from_dict(cls, value: dict) -> "Notice":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            rule_id=value.get("rule_id"),
            severity=value.get("severity"),
            outcome=value.get("outcome"),
            channel=value.get("channel"),
            message_key=value.get("message_key"),
            message_args=value.get("message_args"),
            confirmed_at=value.get("confirmed_at"),
            raised_at=value.get("raised_at"),
            expires_on_reorder=value.get("expires_on_reorder"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "rule_id": _dump(self.rule_id),
            "severity": _dump(self.severity),
            "outcome": _dump(self.outcome),
            "channel": _dump(self.channel),
            **({} if self.message_key is None else {"message_key": _dump(self.message_key)}),
            **({} if self.message_args is None else {"message_args": _dump(self.message_args)}),
            **({} if self.confirmed_at is None else {"confirmed_at": _dump(self.confirmed_at)}),
            "raised_at": _dump(self.raised_at),
            **({} if self.expires_on_reorder is None else {"expires_on_reorder": _dump(self.expires_on_reorder)}),
        }


@dataclass(kw_only=True)
class TripBudget:
    """每人整趟行程预算；null 表示未设置。金额使用整数分。"""

    scope: Literal['per_person']
    currency: Literal['CNY']
    amount_cents: int

    @classmethod
    def from_dict(cls, value: dict) -> "TripBudget":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            scope=value.get("scope"),
            currency=value.get("currency"),
            amount_cents=value.get("amount_cents"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "scope": _dump(self.scope),
            "currency": _dump(self.currency),
            "amount_cents": _dump(self.amount_cents),
        }


@dataclass(kw_only=True)
class TripUserProfile:
    party_composition: Literal['solo', 'couple', 'family_kids', 'senior']
    pacing: Literal['relaxed', 'balanced', 'packed']
    interests: list[Literal['modern_skyline', 'history_culture', 'local_life', 'nature']] = field(default_factory=list)
    walking_speed_factor: float = 1.0  # 最终生效系数 = walking_speed_factor × party_walk_multiplier（见 mappings.json/weighting）。
    party_walk_multiplier: float = 1.0  # 由 party_composition 派生：family_kids/senior → 1.3，其余 1.0。PRD 只写了「1.3」没说作用对象与叠加方式。
    prefer_taxi: bool = False  # family_kids/senior 时为 true，对应「优先推荐打车模式」。

    @classmethod
    def from_dict(cls, value: dict) -> "TripUserProfile":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            party_composition=value.get("party_composition"),
            pacing=value.get("pacing"),
            interests=value.get("interests"),
            walking_speed_factor=value.get("walking_speed_factor"),
            party_walk_multiplier=value.get("party_walk_multiplier"),
            prefer_taxi=value.get("prefer_taxi"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "party_composition": _dump(self.party_composition),
            "pacing": _dump(self.pacing),
            **({} if self.interests is None else {"interests": _dump(self.interests)}),
            "walking_speed_factor": _dump(self.walking_speed_factor),
            **({} if self.party_walk_multiplier is None else {"party_walk_multiplier": _dump(self.party_walk_multiplier)}),
            **({} if self.prefer_taxi is None else {"prefer_taxi": _dump(self.prefer_taxi)}),
        }


@dataclass(kw_only=True)
class TripAnchorArrival:
    arrival_at: int  # UTC 秒（PRD 的 timestamp，与 date 矛盾的元凶）
    location_name: str
    coordinate: Point
    activity_start_at: int  # 服务端派生 = arrival_at + 90min；客户端只读
    border_buffer_minutes: int = 90

    @classmethod
    def from_dict(cls, value: dict) -> "TripAnchorArrival":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            arrival_at=value.get("arrival_at"),
            location_name=value.get("location_name"),
            coordinate=_build(Point, value.get("coordinate")),
            activity_start_at=value.get("activity_start_at"),
            border_buffer_minutes=value.get("border_buffer_minutes"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "arrival_at": _dump(self.arrival_at),
            "location_name": _dump(self.location_name),
            "coordinate": _dump(self.coordinate),
            "activity_start_at": _dump(self.activity_start_at),
            **({} if self.border_buffer_minutes is None else {"border_buffer_minutes": _dump(self.border_buffer_minutes)}),
        }


@dataclass(kw_only=True)
class TripAnchorDeparture:
    """PRD 缺离境锚点，导致 Day N 最后一段（酒店→机场）无法推演。"""

    departure_at: int
    location_name: str
    coordinate: Point
    is_international: bool = True
    hub_buffer_minutes: int = 180

    @classmethod
    def from_dict(cls, value: dict) -> "TripAnchorDeparture":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            departure_at=value.get("departure_at"),
            location_name=value.get("location_name"),
            coordinate=_build(Point, value.get("coordinate")),
            is_international=value.get("is_international"),
            hub_buffer_minutes=value.get("hub_buffer_minutes"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "departure_at": _dump(self.departure_at),
            "location_name": _dump(self.location_name),
            "coordinate": _dump(self.coordinate),
            **({} if self.is_international is None else {"is_international": _dump(self.is_international)}),
            "hub_buffer_minutes": _dump(self.hub_buffer_minutes),
        }


@dataclass(kw_only=True)
class TripAnchorHotel:
    name_en: str
    name_zh: str
    name_pinyin: str = None  # PRD 的 anchor_hotel 连拼音都没有
    coordinate: Point
    poi_id: str | None = None

    @classmethod
    def from_dict(cls, value: dict) -> "TripAnchorHotel":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            name_en=value.get("name_en"),
            name_zh=value.get("name_zh"),
            name_pinyin=value.get("name_pinyin"),
            coordinate=_build(Point, value.get("coordinate")),
            poi_id=value.get("poi_id"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "name_en": _dump(self.name_en),
            "name_zh": _dump(self.name_zh),
            **({} if self.name_pinyin is None else {"name_pinyin": _dump(self.name_pinyin)}),
            "coordinate": _dump(self.coordinate),
            **({} if self.poi_id is None else {"poi_id": _dump(self.poi_id)}),
        }


@dataclass(kw_only=True)
class TripDays:
    day_index: int
    date: str  # 上海本地日期
    day_status: Literal['empty', 'arrival_only', 'partial', 'fulfilled', 'locked']
    daily_start_local: str = '09:00'  # 每日独立出发时刻；Day 1 取配置时刻与 anchor_arrival.activity_start_at 的较晚值。
    poi_cap: int | None = None  # 由 pacing 派生：relaxed=2 / balanced=4 / packed=6
    start_anchor: DayAnchor | object = None  # 当日起点；null 时首日用抵达口岸，其余用前一日终点。
    end_anchor: DayAnchor | object = None  # 当日终点；null 时使用当前住宿，末日优先离境口岸。显式酒店终点成为后续默认住宿。
    ordered_stops: list[TripDaysOrderedStops] = field(default_factory=list)
    is_arrival_day: bool = None  # 服务端按抵达日期派生，独立于 day_status
    end_transit: Route | object = None

    @classmethod
    def from_dict(cls, value: dict) -> "TripDays":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            day_index=value.get("day_index"),
            date=value.get("date"),
            day_status=value.get("day_status"),
            daily_start_local=value.get("daily_start_local"),
            poi_cap=value.get("poi_cap"),
            start_anchor=_build(DayAnchor, value.get("start_anchor")),
            end_anchor=_build(DayAnchor, value.get("end_anchor")),
            ordered_stops=_build_list(TripDaysOrderedStops, value.get("ordered_stops")),
            is_arrival_day=value.get("is_arrival_day"),
            end_transit=_build(Route, value.get("end_transit")),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "day_index": _dump(self.day_index),
            "date": _dump(self.date),
            "day_status": _dump(self.day_status),
            "daily_start_local": _dump(self.daily_start_local),
            **({} if self.poi_cap is None else {"poi_cap": _dump(self.poi_cap)}),
            **({} if self.start_anchor is None else {"start_anchor": _dump(self.start_anchor)}),
            **({} if self.end_anchor is None else {"end_anchor": _dump(self.end_anchor)}),
            "ordered_stops": _dump(self.ordered_stops),
            **({} if self.is_arrival_day is None else {"is_arrival_day": _dump(self.is_arrival_day)}),
            **({} if self.end_transit is None else {"end_transit": _dump(self.end_transit)}),
        }


@dataclass(kw_only=True)
class TripDaysOrderedStops:
    stop_order: int
    stop_type: Literal['poi', 'hotel', 'arrival_anchor', 'departure_anchor']
    poi_id: str | None = None
    locked: bool = False  # 用户手动固定的点，Rule-02 的 Move to Evening 不得移动它。
    arrival_at: int | None = None  # 引擎推算，只读
    departure_at: int | None = None  # 引擎推算 = arrival_at + dwell
    user_preferred_arrival_local: str | None = None  # 用户意愿时刻。与引擎的 arrival_at 并存，不得互相覆盖（PRD 的 target_arrival_time 语义未定义）。
    planned_dwell_minutes: int
    transit_from_previous: Route | object = None
    rule_notices: list[Notice] = field(default_factory=list)
    stop_id: str = None  # 稳定停靠点标识；排序、移除、跨天移动使用
    name_zh: str = None
    name_en: str = None
    name_pinyin: str = None
    coordinate: Point = None
    hotel_stay_kind: Literal['rest', 'overnight'] = None  # 酒店停靠用途：rest 为途中休息，不改变后续住宿；overnight 为过夜或换酒店。旧数据缺字段沿用过夜继承。

    @classmethod
    def from_dict(cls, value: dict) -> "TripDaysOrderedStops":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            stop_order=value.get("stop_order"),
            stop_type=value.get("stop_type"),
            poi_id=value.get("poi_id"),
            locked=value.get("locked"),
            arrival_at=value.get("arrival_at"),
            departure_at=value.get("departure_at"),
            user_preferred_arrival_local=value.get("user_preferred_arrival_local"),
            planned_dwell_minutes=value.get("planned_dwell_minutes"),
            transit_from_previous=_build(Route, value.get("transit_from_previous")),
            rule_notices=_build_list(Notice, value.get("rule_notices")),
            stop_id=value.get("stop_id"),
            name_zh=value.get("name_zh"),
            name_en=value.get("name_en"),
            name_pinyin=value.get("name_pinyin"),
            coordinate=_build(Point, value.get("coordinate")),
            hotel_stay_kind=value.get("hotel_stay_kind"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "stop_order": _dump(self.stop_order),
            "stop_type": _dump(self.stop_type),
            **({} if self.poi_id is None else {"poi_id": _dump(self.poi_id)}),
            **({} if self.locked is None else {"locked": _dump(self.locked)}),
            **({} if self.arrival_at is None else {"arrival_at": _dump(self.arrival_at)}),
            **({} if self.departure_at is None else {"departure_at": _dump(self.departure_at)}),
            **({} if self.user_preferred_arrival_local is None else {"user_preferred_arrival_local": _dump(self.user_preferred_arrival_local)}),
            "planned_dwell_minutes": _dump(self.planned_dwell_minutes),
            **({} if self.transit_from_previous is None else {"transit_from_previous": _dump(self.transit_from_previous)}),
            **({} if self.rule_notices is None else {"rule_notices": _dump(self.rule_notices)}),
            **({} if self.stop_id is None else {"stop_id": _dump(self.stop_id)}),
            **({} if self.name_zh is None else {"name_zh": _dump(self.name_zh)}),
            **({} if self.name_en is None else {"name_en": _dump(self.name_en)}),
            **({} if self.name_pinyin is None else {"name_pinyin": _dump(self.name_pinyin)}),
            **({} if self.coordinate is None else {"coordinate": _dump(self.coordinate)}),
            **({} if self.hotel_stay_kind is None else {"hotel_stay_kind": _dump(self.hotel_stay_kind)}),
        }


@dataclass(kw_only=True)
class TripRevisionHistory:
    version: int
    changed_at: int
    operation: Literal['create', 'add_stop', 'remove_stop', 'reorder', 'move_to_evening', 'change_day', 'change_anchor', 'confirm_conflict', 'unlock_day', 'update_config']
    target: str = None

    @classmethod
    def from_dict(cls, value: dict) -> "TripRevisionHistory":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            version=value.get("version"),
            changed_at=value.get("changed_at"),
            operation=value.get("operation"),
            target=value.get("target"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "version": _dump(self.version),
            "changed_at": _dump(self.changed_at),
            "operation": _dump(self.operation),
            **({} if self.target is None else {"target": _dump(self.target)}),
        }


@dataclass(kw_only=True)
class TripCostInputs:
    intercity_cents: int | None = None
    meal_daily_cents: int | None = None
    extras_cents: int | None = None
    travelers: int | None = None
    lodging_rooms: int | None = None  # 自动住宿估算的房间数；未填写按1间参考估算。
    taxi_vehicles: int | None = None
    contingency_percent: int = None
    itinerary_key: str = None
    ticket_cents: dict[str, Any] = field(default_factory=dict)
    meal_overrides: dict[str, Any] = field(default_factory=dict)
    lodging_nights: list[TripCostInputsLodgingNights] = field(default_factory=list)

    @classmethod
    def from_dict(cls, value: dict) -> "TripCostInputs":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            intercity_cents=value.get("intercity_cents"),
            meal_daily_cents=value.get("meal_daily_cents"),
            extras_cents=value.get("extras_cents"),
            travelers=value.get("travelers"),
            lodging_rooms=value.get("lodging_rooms"),
            taxi_vehicles=value.get("taxi_vehicles"),
            contingency_percent=value.get("contingency_percent"),
            itinerary_key=value.get("itinerary_key"),
            ticket_cents=value.get("ticket_cents"),
            meal_overrides=value.get("meal_overrides"),
            lodging_nights=_build_list(TripCostInputsLodgingNights, value.get("lodging_nights")),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            **({} if self.intercity_cents is None else {"intercity_cents": _dump(self.intercity_cents)}),
            **({} if self.meal_daily_cents is None else {"meal_daily_cents": _dump(self.meal_daily_cents)}),
            **({} if self.extras_cents is None else {"extras_cents": _dump(self.extras_cents)}),
            **({} if self.travelers is None else {"travelers": _dump(self.travelers)}),
            **({} if self.lodging_rooms is None else {"lodging_rooms": _dump(self.lodging_rooms)}),
            **({} if self.taxi_vehicles is None else {"taxi_vehicles": _dump(self.taxi_vehicles)}),
            **({} if self.contingency_percent is None else {"contingency_percent": _dump(self.contingency_percent)}),
            **({} if self.itinerary_key is None else {"itinerary_key": _dump(self.itinerary_key)}),
            **({} if self.ticket_cents is None else {"ticket_cents": _dump(self.ticket_cents)}),
            **({} if self.meal_overrides is None else {"meal_overrides": _dump(self.meal_overrides)}),
            **({} if self.lodging_nights is None else {"lodging_nights": _dump(self.lodging_nights)}),
        }


@dataclass(kw_only=True)
class TripCostInputsLodgingNights:
    date: str
    hotel_name: str
    rooms: int | None
    room_price_cents: int | None

    @classmethod
    def from_dict(cls, value: dict) -> "TripCostInputsLodgingNights":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            date=value.get("date"),
            hotel_name=value.get("hotel_name"),
            rooms=value.get("rooms"),
            room_price_cents=value.get("room_price_cents"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "date": _dump(self.date),
            "hotel_name": _dump(self.hotel_name),
            "rooms": _dump(self.rooms),
            "room_price_cents": _dump(self.room_price_cents),
        }


@dataclass(kw_only=True)
class Trip:
    """C2 实体表。时间字段一律遵循 TIME_BASELINE.md：*_at=UTC 秒、date=上海本地日期、*_local=同日时刻。"""

    budget: TripBudget | None = None  # 每人整趟行程预算；null 表示未设置。金额使用整数分。
    trip_id: str
    user_id: str | None = None  # PRD 内嵌 user_profile 但无 user_id，无法做鉴权与越权校验。
    version: int  # 乐观锁 + 离线包过期判定，PRD 缺失。
    status: Literal['draft', 'confirmed', 'in_progress', 'completed', 'archived']
    timezone: Literal['Asia/Shanghai']
    created_at: int
    updated_at: int
    user_profile: TripUserProfile | None
    anchor_arrival: TripAnchorArrival | None
    anchor_departure: TripAnchorDeparture | None = None  # PRD 缺离境锚点，导致 Day N 最后一段（酒店→机场）无法推演。
    anchor_hotel: TripAnchorHotel | None
    unassigned_pois: list[str] = field(default_factory=list)  # PRD 选了 N 天却只选 M 个点时无「未装载」表示。
    days: list[TripDays] = field(default_factory=list)
    revision_history: list[TripRevisionHistory] = field(default_factory=list)
    resolved_day_points: dict[str, Any] = field(default_factory=dict)  # 服务端只读派生每日起终点快照，不持久化
    default_day_points: dict[str, Any] = field(default_factory=dict)  # 服务端只读派生每日起终点快照，不持久化
    cost_inputs: TripCostInputs | None = None
    budget_assessment: dict[str, Any] = field(default_factory=dict)  # 动态费用评估，不保存到行程文件；缺失费用不视为免费。

    @classmethod
    def from_dict(cls, value: dict) -> "Trip":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            budget=_build(TripBudget, value.get("budget")),
            trip_id=value.get("trip_id"),
            user_id=value.get("user_id"),
            version=value.get("version"),
            status=value.get("status"),
            timezone=value.get("timezone"),
            created_at=value.get("created_at"),
            updated_at=value.get("updated_at"),
            user_profile=_build(TripUserProfile, value.get("user_profile")),
            anchor_arrival=_build(TripAnchorArrival, value.get("anchor_arrival")),
            anchor_departure=_build(TripAnchorDeparture, value.get("anchor_departure")),
            anchor_hotel=_build(TripAnchorHotel, value.get("anchor_hotel")),
            unassigned_pois=value.get("unassigned_pois"),
            days=_build_list(TripDays, value.get("days")),
            revision_history=_build_list(TripRevisionHistory, value.get("revision_history")),
            resolved_day_points=value.get("resolved_day_points"),
            default_day_points=value.get("default_day_points"),
            cost_inputs=_build(TripCostInputs, value.get("cost_inputs")),
            budget_assessment=value.get("budget_assessment"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            **({} if self.budget is None else {"budget": _dump(self.budget)}),
            "trip_id": _dump(self.trip_id),
            **({} if self.user_id is None else {"user_id": _dump(self.user_id)}),
            "version": _dump(self.version),
            "status": _dump(self.status),
            "timezone": _dump(self.timezone),
            "created_at": _dump(self.created_at),
            "updated_at": _dump(self.updated_at),
            "user_profile": _dump(self.user_profile),
            "anchor_arrival": _dump(self.anchor_arrival),
            **({} if self.anchor_departure is None else {"anchor_departure": _dump(self.anchor_departure)}),
            "anchor_hotel": _dump(self.anchor_hotel),
            **({} if self.unassigned_pois is None else {"unassigned_pois": _dump(self.unassigned_pois)}),
            "days": _dump(self.days),
            **({} if self.revision_history is None else {"revision_history": _dump(self.revision_history)}),
            **({} if self.resolved_day_points is None else {"resolved_day_points": _dump(self.resolved_day_points)}),
            **({} if self.default_day_points is None else {"default_day_points": _dump(self.default_day_points)}),
            **({} if self.cost_inputs is None else {"cost_inputs": _dump(self.cost_inputs)}),
            **({} if self.budget_assessment is None else {"budget_assessment": _dump(self.budget_assessment)}),
        }


# ----------------------------------------------------------------------
# RouteSegment  (route.schema.json)
# ----------------------------------------------------------------------

@dataclass(kw_only=True)
class Endpoint:
    type: Literal['poi', 'hotel', 'arrival_anchor', 'departure_anchor']
    stop_id: str = None  # 实际停靠点稳定标识；每日隐式起终点可省略
    poi_id: str | None = None
    station_id: str | None = None
    name_zh: str | None = None
    name_en: str | None = None

    @classmethod
    def from_dict(cls, value: dict) -> "Endpoint":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            type=value.get("type"),
            stop_id=value.get("stop_id"),
            poi_id=value.get("poi_id"),
            station_id=value.get("station_id"),
            name_zh=value.get("name_zh"),
            name_en=value.get("name_en"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "type": _dump(self.type),
            **({} if self.stop_id is None else {"stop_id": _dump(self.stop_id)}),
            **({} if self.poi_id is None else {"poi_id": _dump(self.poi_id)}),
            **({} if self.station_id is None else {"station_id": _dump(self.station_id)}),
            **({} if self.name_zh is None else {"name_zh": _dump(self.name_zh)}),
            **({} if self.name_en is None else {"name_en": _dump(self.name_en)}),
        }


@dataclass(kw_only=True)
class Variant:
    mode: Literal['transit', 'taxi', 'walk', 'bike']
    duration_seconds: int | None
    distance_meters: int | None = None
    cost: dict[str, Any] | None = None
    congestion_level: Literal['unknown', 'low', 'medium', 'high', 'severe'] = None
    transfer_count: int | None = None
    walking_distance_meters: int | None = None
    estimated_steps: int | None = None
    highlight: bool = False  # 步行/骑行 ≤3km 时由服务端置位
    data_source: Literal['amap', 'tencent', 'baidu', 'curated', 'manual', 'degraded', 'mock']
    is_default_tab: bool = False  # prefer_taxi 为 true 时打车置位

    @classmethod
    def from_dict(cls, value: dict) -> "Variant":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            mode=value.get("mode"),
            duration_seconds=value.get("duration_seconds"),
            distance_meters=value.get("distance_meters"),
            cost=value.get("cost"),
            congestion_level=value.get("congestion_level"),
            transfer_count=value.get("transfer_count"),
            walking_distance_meters=value.get("walking_distance_meters"),
            estimated_steps=value.get("estimated_steps"),
            highlight=value.get("highlight"),
            data_source=value.get("data_source"),
            is_default_tab=value.get("is_default_tab"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "mode": _dump(self.mode),
            "duration_seconds": _dump(self.duration_seconds),
            **({} if self.distance_meters is None else {"distance_meters": _dump(self.distance_meters)}),
            **({} if self.cost is None else {"cost": _dump(self.cost)}),
            **({} if self.congestion_level is None else {"congestion_level": _dump(self.congestion_level)}),
            **({} if self.transfer_count is None else {"transfer_count": _dump(self.transfer_count)}),
            **({} if self.walking_distance_meters is None else {"walking_distance_meters": _dump(self.walking_distance_meters)}),
            **({} if self.estimated_steps is None else {"estimated_steps": _dump(self.estimated_steps)}),
            **({} if self.highlight is None else {"highlight": _dump(self.highlight)}),
            "data_source": _dump(self.data_source),
            **({} if self.is_default_tab is None else {"is_default_tab": _dump(self.is_default_tab)}),
        }


@dataclass(kw_only=True)
class Segment:
    kind: Literal['walk', 'ride', 'transfer']
    duration_seconds: int
    distance_meters: int | None = None
    line: SegmentLine | None = None
    direction: SegmentDirection | None = None
    board: AccessPoint = None
    alight: AccessPoint = None
    stops: int | None = None
    transfer: SegmentTransfer | None = None  # 仅 kind=transfer 时有值；source 决定前端是否可展示「2号口」这类人工数据。
    walk_note_en: str | None = None
    walk_note_zh: str | None = None

    @classmethod
    def from_dict(cls, value: dict) -> "Segment":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            kind=value.get("kind"),
            duration_seconds=value.get("duration_seconds"),
            distance_meters=value.get("distance_meters"),
            line=_build(SegmentLine, value.get("line")),
            direction=_build(SegmentDirection, value.get("direction")),
            board=_build(AccessPoint, value.get("board")),
            alight=_build(AccessPoint, value.get("alight")),
            stops=value.get("stops"),
            transfer=_build(SegmentTransfer, value.get("transfer")),
            walk_note_en=value.get("walk_note_en"),
            walk_note_zh=value.get("walk_note_zh"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "kind": _dump(self.kind),
            "duration_seconds": _dump(self.duration_seconds),
            **({} if self.distance_meters is None else {"distance_meters": _dump(self.distance_meters)}),
            **({} if self.line is None else {"line": _dump(self.line)}),
            **({} if self.direction is None else {"direction": _dump(self.direction)}),
            **({} if self.board is None else {"board": _dump(self.board)}),
            **({} if self.alight is None else {"alight": _dump(self.alight)}),
            **({} if self.stops is None else {"stops": _dump(self.stops)}),
            **({} if self.transfer is None else {"transfer": _dump(self.transfer)}),
            **({} if self.walk_note_en is None else {"walk_note_en": _dump(self.walk_note_en)}),
            **({} if self.walk_note_zh is None else {"walk_note_zh": _dump(self.walk_note_zh)}),
        }


@dataclass(kw_only=True)
class AccessPoint:
    station_id: str | None = None
    station_name_zh: str | None = None
    station_name_en: str | None = None
    access_no: str | None = None
    access_name_zh: str | None = None
    access_name_en: str | None = None
    landmark_desc_zh: str | None = None
    landmark_desc_en: str | None = None
    source: Literal['amap', 'tencent', 'baidu', 'curated', 'manual', 'degraded', 'mock'] = None  # curated=站台库；api=三方；缺失时前端隐藏该行而非显示占位

    @classmethod
    def from_dict(cls, value: dict) -> "AccessPoint":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            station_id=value.get("station_id"),
            station_name_zh=value.get("station_name_zh"),
            station_name_en=value.get("station_name_en"),
            access_no=value.get("access_no"),
            access_name_zh=value.get("access_name_zh"),
            access_name_en=value.get("access_name_en"),
            landmark_desc_zh=value.get("landmark_desc_zh"),
            landmark_desc_en=value.get("landmark_desc_en"),
            source=value.get("source"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            **({} if self.station_id is None else {"station_id": _dump(self.station_id)}),
            **({} if self.station_name_zh is None else {"station_name_zh": _dump(self.station_name_zh)}),
            **({} if self.station_name_en is None else {"station_name_en": _dump(self.station_name_en)}),
            **({} if self.access_no is None else {"access_no": _dump(self.access_no)}),
            **({} if self.access_name_zh is None else {"access_name_zh": _dump(self.access_name_zh)}),
            **({} if self.access_name_en is None else {"access_name_en": _dump(self.access_name_en)}),
            **({} if self.landmark_desc_zh is None else {"landmark_desc_zh": _dump(self.landmark_desc_zh)}),
            **({} if self.landmark_desc_en is None else {"landmark_desc_en": _dump(self.landmark_desc_en)}),
            **({} if self.source is None else {"source": _dump(self.source)}),
        }


@dataclass(kw_only=True)
class RouteTransferOverhead:
    """3.5 的「基础步行耗时上浮 30%」：只存系数不存改写后的值，保证多次重算幂等。"""

    applies_to: Literal['walking_segment', 'whole_transit', 'none'] = 'walking_segment'
    factor: float = 1.3
    counts_in_timeline: bool = True  # 是否计入时序推演；PRD 未定义会导致两套时间。

    @classmethod
    def from_dict(cls, value: dict) -> "RouteTransferOverhead":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            applies_to=value.get("applies_to"),
            factor=value.get("factor"),
            counts_in_timeline=value.get("counts_in_timeline"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "applies_to": _dump(self.applies_to),
            "factor": _dump(self.factor),
            **({} if self.counts_in_timeline is None else {"counts_in_timeline": _dump(self.counts_in_timeline)}),
        }


@dataclass(kw_only=True)
class RouteCost:
    min: float
    max: float
    currency: Literal['CNY'] = 'CNY'
    display_currency: str = 'CNY'  # 海外用户展示币种，换算口径见 mappings.json/currency_display

    @classmethod
    def from_dict(cls, value: dict) -> "RouteCost":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            min=value.get("min"),
            max=value.get("max"),
            currency=value.get("currency"),
            display_currency=value.get("display_currency"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "min": _dump(self.min),
            "max": _dump(self.max),
            "currency": _dump(self.currency),
            **({} if self.display_currency is None else {"display_currency": _dump(self.display_currency)}),
        }


@dataclass(kw_only=True)
class RouteDropOff:
    """3.5 打车下客点纠偏结果。source 用于区分「人工录入」与「三方推荐」。"""

    point: Point
    desc_zh: str
    desc_en: str
    source: Literal['amap', 'tencent', 'baidu', 'curated', 'manual', 'degraded', 'mock']
    selected_from: Literal['curated', 'api', 'poi_center_fallback'] = 'curated'

    @classmethod
    def from_dict(cls, value: dict) -> "RouteDropOff":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            point=_build(Point, value.get("point")),
            desc_zh=value.get("desc_zh"),
            desc_en=value.get("desc_en"),
            source=value.get("source"),
            selected_from=value.get("selected_from"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "point": _dump(self.point),
            "desc_zh": _dump(self.desc_zh),
            "desc_en": _dump(self.desc_en),
            "source": _dump(self.source),
            **({} if self.selected_from is None else {"selected_from": _dump(self.selected_from)}),
        }


@dataclass(kw_only=True)
class RouteCache:
    key: str = None  # 建议 geohash7:geohash7:mode，见 mappings.json/cache_keys
    ttl_seconds: int = 1800
    hit: bool = False

    @classmethod
    def from_dict(cls, value: dict) -> "RouteCache":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            key=value.get("key"),
            ttl_seconds=value.get("ttl_seconds"),
            hit=value.get("hit"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            **({} if self.key is None else {"key": _dump(self.key)}),
            **({} if self.ttl_seconds is None else {"ttl_seconds": _dump(self.ttl_seconds)}),
            **({} if self.hit is None else {"hit": _dump(self.hit)}),
        }


@dataclass(kw_only=True)
class SegmentLine:
    code: str = None
    name_en: str = None
    name_zh: str = None
    color_hex: str = None

    @classmethod
    def from_dict(cls, value: dict) -> "SegmentLine":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            code=value.get("code"),
            name_en=value.get("name_en"),
            name_zh=value.get("name_zh"),
            color_hex=value.get("color_hex"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            **({} if self.code is None else {"code": _dump(self.code)}),
            **({} if self.name_en is None else {"name_en": _dump(self.name_en)}),
            **({} if self.name_zh is None else {"name_zh": _dump(self.name_zh)}),
            **({} if self.color_hex is None else {"color_hex": _dump(self.color_hex)}),
        }


@dataclass(kw_only=True)
class SegmentDirection:
    name_en: str = None
    name_zh: str = None
    terminal_station_id: str | None = None

    @classmethod
    def from_dict(cls, value: dict) -> "SegmentDirection":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            name_en=value.get("name_en"),
            name_zh=value.get("name_zh"),
            terminal_station_id=value.get("terminal_station_id"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            **({} if self.name_en is None else {"name_en": _dump(self.name_en)}),
            **({} if self.name_zh is None else {"name_zh": _dump(self.name_zh)}),
            **({} if self.terminal_station_id is None else {"terminal_station_id": _dump(self.terminal_station_id)}),
        }


@dataclass(kw_only=True)
class SegmentTransfer:
    """仅 kind=transfer 时有值；source 决定前端是否可展示「2号口」这类人工数据。"""

    walking_distance_meters: int | None
    duration_min_minutes: float | None = None
    duration_max_minutes: float | None = None
    is_in_station: bool = True
    note_en: str | None = None
    note_zh: str | None = None
    vertical_gap_note_zh: str | None = None  # 枢纽立体高差提示（1.2 痛点之一）
    is_barrier_free: bool | None = None
    source: Literal['amap', 'tencent', 'baidu', 'curated', 'manual', 'degraded', 'mock']

    @classmethod
    def from_dict(cls, value: dict) -> "SegmentTransfer":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            walking_distance_meters=value.get("walking_distance_meters"),
            duration_min_minutes=value.get("duration_min_minutes"),
            duration_max_minutes=value.get("duration_max_minutes"),
            is_in_station=value.get("is_in_station"),
            note_en=value.get("note_en"),
            note_zh=value.get("note_zh"),
            vertical_gap_note_zh=value.get("vertical_gap_note_zh"),
            is_barrier_free=value.get("is_barrier_free"),
            source=value.get("source"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "walking_distance_meters": _dump(self.walking_distance_meters),
            **({} if self.duration_min_minutes is None else {"duration_min_minutes": _dump(self.duration_min_minutes)}),
            **({} if self.duration_max_minutes is None else {"duration_max_minutes": _dump(self.duration_max_minutes)}),
            **({} if self.is_in_station is None else {"is_in_station": _dump(self.is_in_station)}),
            **({} if self.note_en is None else {"note_en": _dump(self.note_en)}),
            **({} if self.note_zh is None else {"note_zh": _dump(self.note_zh)}),
            **({} if self.vertical_gap_note_zh is None else {"vertical_gap_note_zh": _dump(self.vertical_gap_note_zh)}),
            **({} if self.is_barrier_free is None else {"is_barrier_free": _dump(self.is_barrier_free)}),
            "source": _dump(self.source),
        }


@dataclass(kw_only=True)
class Route:
    """C5 Route Adapter 归一化契约。PRD 4.2 的 transit_from_previous 只有 5 个标量，导致「≤3km 高亮」「步行总长」「消耗步数」「换乘≥200m」全部无数据来源。本 schema 是 Adapter 的唯一输出格式。"""

    from_: Endpoint  # （JSON 字段名：from）
    to: Endpoint
    mode: Literal['transit', 'taxi', 'walk', 'bike']
    variants: list[Variant] = field(default_factory=list)  # 3.4 要求「同时展示三组」——三模态统一放在 variants 里，避免客户端为每种模式各写一套结构。
    distance_meters: int | None  # 3.4「距离 ≤3km 高亮」的判定依据，PRD 缺失。
    duration_seconds: int | None
    walking_distance_meters: int | None = None
    walking_duration_seconds: int | None = None
    estimated_steps: int | None = None
    transfer_count: int | None = None
    has_long_transfer: bool = False  # 派生布尔，保留原始值以便展示 「~X meters」。
    long_transfer_threshold_m: int = 200
    transfer_overhead: RouteTransferOverhead | None = None  # 3.5 的「基础步行耗时上浮 30%」：只存系数不存改写后的值，保证多次重算幂等。
    cost: RouteCost | None = None
    congestion_level: Literal['unknown', 'low', 'medium', 'high', 'severe'] = 'unknown'
    segments: list[Segment] = field(default_factory=list)  # 3.5 微观解析：进站→途中→换乘→出站→最后 300m。
    drop_off: RouteDropOff | None = None  # 3.5 打车下客点纠偏结果。source 用于区分「人工录入」与「三方推荐」。
    last_mile_walk_meters: int | None = None
    polyline: str | None = None  # lng,lat;lng,lat 格式折线；坐标系由 crs 声明。不完整轨迹为 null。
    crs: Literal['WGS84', 'GCJ-02', 'BD-09'] = 'WGS84'
    cache: RouteCache | None = None
    data_source: Literal['amap', 'tencent', 'baidu', 'curated', 'manual', 'degraded', 'mock']
    degraded_reason: Literal['none', 'timeout', 'rate_limited', 'no_route', 'unsupported_city', 'offline', 'partial_data']
    degraded_notice_key: str | None = None  # 降级文案键；直线粗算时为 'degraded.direct_orientation'
    partial: bool = False  # 部分成功语义：哪些字段为 null 必须能被前端识别
    fetched_at: int  # UTC 秒

    @classmethod
    def from_dict(cls, value: dict) -> "Route":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            from_=_build(Endpoint, value.get("from")),
            to=_build(Endpoint, value.get("to")),
            mode=value.get("mode"),
            variants=_build_list(Variant, value.get("variants")),
            distance_meters=value.get("distance_meters"),
            duration_seconds=value.get("duration_seconds"),
            walking_distance_meters=value.get("walking_distance_meters"),
            walking_duration_seconds=value.get("walking_duration_seconds"),
            estimated_steps=value.get("estimated_steps"),
            transfer_count=value.get("transfer_count"),
            has_long_transfer=value.get("has_long_transfer"),
            long_transfer_threshold_m=value.get("long_transfer_threshold_m"),
            transfer_overhead=_build(RouteTransferOverhead, value.get("transfer_overhead")),
            cost=_build(RouteCost, value.get("cost")),
            congestion_level=value.get("congestion_level"),
            segments=_build_list(Segment, value.get("segments")),
            drop_off=_build(RouteDropOff, value.get("drop_off")),
            last_mile_walk_meters=value.get("last_mile_walk_meters"),
            polyline=value.get("polyline"),
            crs=value.get("crs"),
            cache=_build(RouteCache, value.get("cache")),
            data_source=value.get("data_source"),
            degraded_reason=value.get("degraded_reason"),
            degraded_notice_key=value.get("degraded_notice_key"),
            partial=value.get("partial"),
            fetched_at=value.get("fetched_at"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "from": _dump(self.from_),
            "to": _dump(self.to),
            "mode": _dump(self.mode),
            **({} if self.variants is None else {"variants": _dump(self.variants)}),
            "distance_meters": _dump(self.distance_meters),
            "duration_seconds": _dump(self.duration_seconds),
            **({} if self.walking_distance_meters is None else {"walking_distance_meters": _dump(self.walking_distance_meters)}),
            **({} if self.walking_duration_seconds is None else {"walking_duration_seconds": _dump(self.walking_duration_seconds)}),
            **({} if self.estimated_steps is None else {"estimated_steps": _dump(self.estimated_steps)}),
            **({} if self.transfer_count is None else {"transfer_count": _dump(self.transfer_count)}),
            **({} if self.has_long_transfer is None else {"has_long_transfer": _dump(self.has_long_transfer)}),
            **({} if self.long_transfer_threshold_m is None else {"long_transfer_threshold_m": _dump(self.long_transfer_threshold_m)}),
            **({} if self.transfer_overhead is None else {"transfer_overhead": _dump(self.transfer_overhead)}),
            **({} if self.cost is None else {"cost": _dump(self.cost)}),
            **({} if self.congestion_level is None else {"congestion_level": _dump(self.congestion_level)}),
            **({} if self.segments is None else {"segments": _dump(self.segments)}),
            **({} if self.drop_off is None else {"drop_off": _dump(self.drop_off)}),
            **({} if self.last_mile_walk_meters is None else {"last_mile_walk_meters": _dump(self.last_mile_walk_meters)}),
            **({} if self.polyline is None else {"polyline": _dump(self.polyline)}),
            **({} if self.crs is None else {"crs": _dump(self.crs)}),
            **({} if self.cache is None else {"cache": _dump(self.cache)}),
            "data_source": _dump(self.data_source),
            "degraded_reason": _dump(self.degraded_reason),
            **({} if self.degraded_notice_key is None else {"degraded_notice_key": _dump(self.degraded_notice_key)}),
            **({} if self.partial is None else {"partial": _dump(self.partial)}),
            "fetched_at": _dump(self.fetched_at),
        }


# ----------------------------------------------------------------------
# CuratedStation  (station.schema.json)
# ----------------------------------------------------------------------

@dataclass(kw_only=True)
class StationNames:
    zh_Hans: str  # （JSON 字段名：zh-Hans）
    zh_Hant: str = None  # （JSON 字段名：zh-Hant）
    en: str
    ja: str = None
    ko: str = None

    @classmethod
    def from_dict(cls, value: dict) -> "StationNames":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            zh_Hans=value.get("zh-Hans"),
            zh_Hant=value.get("zh-Hant"),
            en=value.get("en"),
            ja=value.get("ja"),
            ko=value.get("ko"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "zh-Hans": _dump(self.zh_Hans),
            **({} if self.zh_Hant is None else {"zh-Hant": _dump(self.zh_Hant)}),
            "en": _dump(self.en),
            **({} if self.ja is None else {"ja": _dump(self.ja)}),
            **({} if self.ko is None else {"ko": _dump(self.ko)}),
        }


@dataclass(kw_only=True)
class StationRomanization:
    pinyin: str = None
    pinyin_plain: str = None

    @classmethod
    def from_dict(cls, value: dict) -> "StationRomanization":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            pinyin=value.get("pinyin"),
            pinyin_plain=value.get("pinyin_plain"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            **({} if self.pinyin is None else {"pinyin": _dump(self.pinyin)}),
            **({} if self.pinyin_plain is None else {"pinyin_plain": _dump(self.pinyin_plain)}),
        }


@dataclass(kw_only=True)
class StationLines:
    code: str
    name_en: str
    name_zh: str
    color_hex: str = None
    directions: list[StationLinesDirections] = field(default_factory=list)

    @classmethod
    def from_dict(cls, value: dict) -> "StationLines":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            code=value.get("code"),
            name_en=value.get("name_en"),
            name_zh=value.get("name_zh"),
            color_hex=value.get("color_hex"),
            directions=_build_list(StationLinesDirections, value.get("directions")),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "code": _dump(self.code),
            "name_en": _dump(self.name_en),
            "name_zh": _dump(self.name_zh),
            **({} if self.color_hex is None else {"color_hex": _dump(self.color_hex)}),
            **({} if self.directions is None else {"directions": _dump(self.directions)}),
        }


@dataclass(kw_only=True)
class StationLinesDirections:
    name_en: str
    name_zh: str
    terminal_station_id: str | None = None

    @classmethod
    def from_dict(cls, value: dict) -> "StationLinesDirections":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            name_en=value.get("name_en"),
            name_zh=value.get("name_zh"),
            terminal_station_id=value.get("terminal_station_id"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "name_en": _dump(self.name_en),
            "name_zh": _dump(self.name_zh),
            **({} if self.terminal_station_id is None else {"terminal_station_id": _dump(self.terminal_station_id)}),
        }


@dataclass(kw_only=True)
class StationAccessPoints:
    access_no: str
    kind: Literal['entrance', 'exit', 'both']
    name_zh: str
    name_en: str
    coordinate: Point = None
    landmark_desc_zh: str = None
    landmark_desc_en: str = None
    is_barrier_free: bool | None = None
    has_escalator: bool | None = None
    is_open: bool | None = None  # 临时关闭的出口；null=未知

    @classmethod
    def from_dict(cls, value: dict) -> "StationAccessPoints":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            access_no=value.get("access_no"),
            kind=value.get("kind"),
            name_zh=value.get("name_zh"),
            name_en=value.get("name_en"),
            coordinate=_build(Point, value.get("coordinate")),
            landmark_desc_zh=value.get("landmark_desc_zh"),
            landmark_desc_en=value.get("landmark_desc_en"),
            is_barrier_free=value.get("is_barrier_free"),
            has_escalator=value.get("has_escalator"),
            is_open=value.get("is_open"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "access_no": _dump(self.access_no),
            "kind": _dump(self.kind),
            "name_zh": _dump(self.name_zh),
            "name_en": _dump(self.name_en),
            **({} if self.coordinate is None else {"coordinate": _dump(self.coordinate)}),
            **({} if self.landmark_desc_zh is None else {"landmark_desc_zh": _dump(self.landmark_desc_zh)}),
            **({} if self.landmark_desc_en is None else {"landmark_desc_en": _dump(self.landmark_desc_en)}),
            **({} if self.is_barrier_free is None else {"is_barrier_free": _dump(self.is_barrier_free)}),
            **({} if self.has_escalator is None else {"has_escalator": _dump(self.has_escalator)}),
            **({} if self.is_open is None else {"is_open": _dump(self.is_open)}),
        }


@dataclass(kw_only=True)
class StationInteriorTransfers:
    from_line_code: str
    to_line_code: str
    walking_distance_meters: int
    minutes_min: float
    minutes_max: float
    is_in_station: bool = True
    note_zh: str | None = None
    note_en: str | None = None
    vertical_gap_note_zh: str | None = None
    is_barrier_free: bool | None = None

    @classmethod
    def from_dict(cls, value: dict) -> "StationInteriorTransfers":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            from_line_code=value.get("from_line_code"),
            to_line_code=value.get("to_line_code"),
            walking_distance_meters=value.get("walking_distance_meters"),
            minutes_min=value.get("minutes_min"),
            minutes_max=value.get("minutes_max"),
            is_in_station=value.get("is_in_station"),
            note_zh=value.get("note_zh"),
            note_en=value.get("note_en"),
            vertical_gap_note_zh=value.get("vertical_gap_note_zh"),
            is_barrier_free=value.get("is_barrier_free"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "from_line_code": _dump(self.from_line_code),
            "to_line_code": _dump(self.to_line_code),
            "walking_distance_meters": _dump(self.walking_distance_meters),
            "minutes_min": _dump(self.minutes_min),
            "minutes_max": _dump(self.minutes_max),
            **({} if self.is_in_station is None else {"is_in_station": _dump(self.is_in_station)}),
            **({} if self.note_zh is None else {"note_zh": _dump(self.note_zh)}),
            **({} if self.note_en is None else {"note_en": _dump(self.note_en)}),
            **({} if self.vertical_gap_note_zh is None else {"vertical_gap_note_zh": _dump(self.vertical_gap_note_zh)}),
            **({} if self.is_barrier_free is None else {"is_barrier_free": _dump(self.is_barrier_free)}),
        }


@dataclass(kw_only=True)
class StationCoverage:
    """PRD 未定义覆盖范围；没有它就无法回答「库里没有这个站怎么办」。"""

    tier: Literal['core_hub', 'major', 'standard'] = 'standard'
    completeness: Literal['full', 'partial', 'access_points_only', 'none'] = 'partial'  # 决定前端能展示到哪一层；none 时 3.5 的微观增强整体降级为纯文本。

    @classmethod
    def from_dict(cls, value: dict) -> "StationCoverage":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            tier=value.get("tier"),
            completeness=value.get("completeness"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "tier": _dump(self.tier),
            "completeness": _dump(self.completeness),
        }


@dataclass(kw_only=True)
class StationProvenance:
    source: Literal['amap', 'tencent', 'baidu', 'curated', 'manual', 'degraded', 'mock']
    updated_at: int
    reviewed_by: str = None
    field_verified_at: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: dict) -> "StationProvenance":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            source=value.get("source"),
            updated_at=value.get("updated_at"),
            reviewed_by=value.get("reviewed_by"),
            field_verified_at=value.get("field_verified_at"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "source": _dump(self.source),
            "updated_at": _dump(self.updated_at),
            **({} if self.reviewed_by is None else {"reviewed_by": _dump(self.reviewed_by)}),
            **({} if self.field_verified_at is None else {"field_verified_at": _dump(self.field_verified_at)}),
        }


@dataclass(kw_only=True)
class Station:
    """PRD 第 2 章架构图列出了「Curated Stations (核心站台库)」，但第 4 章没有实体；而 3.5/3.6/3.7 直接消费其内容（进出站口编号、站台方向、站内换乘步行距离、室内扶梯提示）。本 schema 是该库的最小可用实体。"""

    station_id: str
    names: StationNames | None
    romanization: StationRomanization | None = None
    coordinate: Point = None
    station_group_id: str | None = None  # 同站不同线（换乘站群）归组，避免把「中山公园 2 号线」与「中山公园 3 号线」当成两个车站。
    is_transfer_hub: bool = False
    vertical_complexity: Literal['flat', 'multi_level', 'deep_multi_level'] = 'flat'  # 对应 1.2 痛点「枢纽站立体高差大」。
    lines: list[StationLines] = field(default_factory=list)
    access_points: list[StationAccessPoints] = field(default_factory=list)  # 进出站口。这是「Enter via: Entrance 2 (2号口)」的唯一数据来源，三方 API 通常不返回。
    interior_transfers: list[StationInteriorTransfers] = field(default_factory=list)  # 站内换乘。支撑「Long Transfer Warning: Walking distance ~320m / 6-8 mins / Take indoor escalators」。
    coverage: StationCoverage | None = None  # PRD 未定义覆盖范围；没有它就无法回答「库里没有这个站怎么办」。
    provenance: StationProvenance | None

    @classmethod
    def from_dict(cls, value: dict) -> "Station":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            station_id=value.get("station_id"),
            names=_build(StationNames, value.get("names")),
            romanization=_build(StationRomanization, value.get("romanization")),
            coordinate=_build(Point, value.get("coordinate")),
            station_group_id=value.get("station_group_id"),
            is_transfer_hub=value.get("is_transfer_hub"),
            vertical_complexity=value.get("vertical_complexity"),
            lines=_build_list(StationLines, value.get("lines")),
            access_points=_build_list(StationAccessPoints, value.get("access_points")),
            interior_transfers=_build_list(StationInteriorTransfers, value.get("interior_transfers")),
            coverage=_build(StationCoverage, value.get("coverage")),
            provenance=_build(StationProvenance, value.get("provenance")),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "station_id": _dump(self.station_id),
            "names": _dump(self.names),
            **({} if self.romanization is None else {"romanization": _dump(self.romanization)}),
            **({} if self.coordinate is None else {"coordinate": _dump(self.coordinate)}),
            **({} if self.station_group_id is None else {"station_group_id": _dump(self.station_group_id)}),
            **({} if self.is_transfer_hub is None else {"is_transfer_hub": _dump(self.is_transfer_hub)}),
            **({} if self.vertical_complexity is None else {"vertical_complexity": _dump(self.vertical_complexity)}),
            "lines": _dump(self.lines),
            "access_points": _dump(self.access_points),
            **({} if self.interior_transfers is None else {"interior_transfers": _dump(self.interior_transfers)}),
            **({} if self.coverage is None else {"coverage": _dump(self.coverage)}),
            "provenance": _dump(self.provenance),
        }


# ----------------------------------------------------------------------
# Recommendation  (recommendation.schema.json)
# ----------------------------------------------------------------------

@dataclass(kw_only=True)
class Stop:
    poi_id: str
    planned_dwell_minutes: int

    @classmethod
    def from_dict(cls, value: dict) -> "Stop":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            poi_id=value.get("poi_id"),
            planned_dwell_minutes=value.get("planned_dwell_minutes"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "poi_id": _dump(self.poi_id),
            "planned_dwell_minutes": _dump(self.planned_dwell_minutes),
        }


@dataclass(kw_only=True)
class PlanDay:
    day_index: int
    stops: list[Stop] = field(default_factory=list)

    @classmethod
    def from_dict(cls, value: dict) -> "PlanDay":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            day_index=value.get("day_index"),
            stops=_build_list(Stop, value.get("stops")),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "day_index": _dump(self.day_index),
            "stops": _dump(self.stops),
        }


@dataclass(kw_only=True)
class Plan:
    days: list[PlanDay] = field(default_factory=list)

    @classmethod
    def from_dict(cls, value: dict) -> "Plan":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            days=_build_list(PlanDay, value.get("days")),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "days": _dump(self.days),
        }


@dataclass(kw_only=True)
class DetailStop:
    poi_id: str
    name_zh: str
    planned_dwell_minutes: int
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    estimated_arrival_local: str = None
    estimated_departure_local: str = None

    @classmethod
    def from_dict(cls, value: dict) -> "DetailStop":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            poi_id=value.get("poi_id"),
            name_zh=value.get("name_zh"),
            planned_dwell_minutes=value.get("planned_dwell_minutes"),
            reasons=value.get("reasons"),
            warnings=value.get("warnings"),
            estimated_arrival_local=value.get("estimated_arrival_local"),
            estimated_departure_local=value.get("estimated_departure_local"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "poi_id": _dump(self.poi_id),
            "name_zh": _dump(self.name_zh),
            "planned_dwell_minutes": _dump(self.planned_dwell_minutes),
            "reasons": _dump(self.reasons),
            "warnings": _dump(self.warnings),
            **({} if self.estimated_arrival_local is None else {"estimated_arrival_local": _dump(self.estimated_arrival_local)}),
            **({} if self.estimated_departure_local is None else {"estimated_departure_local": _dump(self.estimated_departure_local)}),
        }


@dataclass(kw_only=True)
class Setup:
    """沿用 POST /trips 的创建输入；完整业务约束由 trip_engine 校验。"""

    user_id: str | None = None
    user_profile: dict[str, Any] = field(default_factory=dict)
    duration_days: int
    start_date: str = None
    daily_start_local: str = None
    anchor_arrival: dict[str, Any] = field(default_factory=dict)
    anchor_hotel: dict[str, Any] = field(default_factory=dict)
    anchor_departure: dict[str, Any] | None = None
    budget: dict[str, Any] | None = None
    cost_inputs: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: dict) -> "Setup":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            user_id=value.get("user_id"),
            user_profile=value.get("user_profile"),
            duration_days=value.get("duration_days"),
            start_date=value.get("start_date"),
            daily_start_local=value.get("daily_start_local"),
            anchor_arrival=value.get("anchor_arrival"),
            anchor_hotel=value.get("anchor_hotel"),
            anchor_departure=value.get("anchor_departure"),
            budget=value.get("budget"),
            cost_inputs=value.get("cost_inputs"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            **({} if self.user_id is None else {"user_id": _dump(self.user_id)}),
            "user_profile": _dump(self.user_profile),
            "duration_days": _dump(self.duration_days),
            **({} if self.start_date is None else {"start_date": _dump(self.start_date)}),
            **({} if self.daily_start_local is None else {"daily_start_local": _dump(self.daily_start_local)}),
            "anchor_arrival": _dump(self.anchor_arrival),
            "anchor_hotel": _dump(self.anchor_hotel),
            **({} if self.anchor_departure is None else {"anchor_departure": _dump(self.anchor_departure)}),
            **({} if self.budget is None else {"budget": _dump(self.budget)}),
            **({} if self.cost_inputs is None else {"cost_inputs": _dump(self.cost_inputs)}),
        }


@dataclass(kw_only=True)
class GenerateRequest:
    trip_id: str = None
    setup: Setup = None
    day_indices: list[int] = field(default_factory=list)

    @classmethod
    def from_dict(cls, value: dict) -> "GenerateRequest":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            trip_id=value.get("trip_id"),
            setup=_build(Setup, value.get("setup")),
            day_indices=value.get("day_indices"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            **({} if self.trip_id is None else {"trip_id": _dump(self.trip_id)}),
            **({} if self.setup is None else {"setup": _dump(self.setup)}),
            "day_indices": _dump(self.day_indices),
        }


@dataclass(kw_only=True)
class CreateRequest:
    setup: Setup
    plan: Plan

    @classmethod
    def from_dict(cls, value: dict) -> "CreateRequest":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            setup=_build(Setup, value.get("setup")),
            plan=_build(Plan, value.get("plan")),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "setup": _dump(self.setup),
            "plan": _dump(self.plan),
        }


@dataclass(kw_only=True)
class ApplyRequest:
    plan: Plan

    @classmethod
    def from_dict(cls, value: dict) -> "ApplyRequest":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            plan=_build(Plan, value.get("plan")),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "plan": _dump(self.plan),
        }


@dataclass(kw_only=True)
class RecommendationDays:
    day_index: int
    date: str
    stops: list[DetailStop] = field(default_factory=list)

    @classmethod
    def from_dict(cls, value: dict) -> "RecommendationDays":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            day_index=value.get("day_index"),
            date=value.get("date"),
            stops=_build_list(DetailStop, value.get("stops")),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "day_index": _dump(self.day_index),
            "date": _dump(self.date),
            "stops": _dump(self.stops),
        }


@dataclass(kw_only=True)
class RecommendationSkippedDays:
    day_index: int
    reason: str

    @classmethod
    def from_dict(cls, value: dict) -> "RecommendationSkippedDays":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            day_index=value.get("day_index"),
            reason=value.get("reason"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "day_index": _dump(self.day_index),
            "reason": _dump(self.reason),
        }


@dataclass(kw_only=True)
class Recommendation:
    """只读推荐输出；估算信息与推荐理由不写入冻结行程字段。"""

    plan: Plan
    days: list[RecommendationDays] = field(default_factory=list)
    skipped_days: list[RecommendationSkippedDays] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    trip_id: str | None
    trip_version: int | None

    @classmethod
    def from_dict(cls, value: dict) -> "Recommendation":
        """从 dict 构造；忽略未知字段（契约演进时旧代码不会崩）。"""
        if not isinstance(value, dict):
            raise TypeError(f"{cls.__name__} 需要 dict，收到 {type(value).__name__}")
        return cls(
            plan=_build(Plan, value.get("plan")),
            days=_build_list(RecommendationDays, value.get("days")),
            skipped_days=_build_list(RecommendationSkippedDays, value.get("skipped_days")),
            warnings=value.get("warnings"),
            trip_id=value.get("trip_id"),
            trip_version=value.get("trip_version"),
        )

    def to_dict(self) -> dict:
        """输出为可 JSON 序列化的 dict：还原 JSON 字段名，跳过未设置的选填字段。"""
        return {
            "plan": _dump(self.plan),
            "days": _dump(self.days),
            "skipped_days": _dump(self.skipped_days),
            "warnings": _dump(self.warnings),
            "trip_id": _dump(self.trip_id),
            "trip_version": _dump(self.trip_version),
        }


# ---------------------------------------------------------------- 便捷入口

MODEL_BY_SCHEMA = {
    "poi.schema.json": Poi,
    "trip.schema.json": Trip,
    "route.schema.json": Route,
    "station.schema.json": Station,
    "recommendation.schema.json": Recommendation,
}


def build(schema_name: str, payload: dict):
    """按 schema 名构造模型；未知 schema 抛 KeyError。"""
    return MODEL_BY_SCHEMA[schema_name].from_dict(payload)

