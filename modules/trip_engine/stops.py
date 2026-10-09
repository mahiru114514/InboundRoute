"""每日停靠点操作、日状态与路线失效管理。"""
from __future__ import annotations

import re
import uuid

from .errors import EngineError
from .domain import (
    PACING_CAP,
    STOP_TYPES,
    local_date_of,
    minutes_to_seconds,
    dwell_minutes_of,
    _require,
    _trip_transaction,
)


class StopOperations:
    """停靠点操作；宿主提供 store、事务锁、校验与 _commit。"""

    def _day(self, trip: dict, day_index) -> dict:
        try:
            index = int(day_index)
        except (TypeError, ValueError):
            raise EngineError(400, "BAD_REQUEST", "day_index 必须是整数")
        for day in trip["days"]:
            if day["day_index"] == index:
                return day
        raise EngineError(404, "BAD_REQUEST", f"Day {index} 不存在（行程共 {len(trip['days'])} 天）")

    def _poi_options(self) -> dict:
        return {item["poi_id"]: item for item in self.store.list_pois()}

    @_trip_transaction
    def add_stop(self, trip_id: str, day_index, payload: dict) -> dict:
        _require(isinstance(payload, dict), "请求体必须是 JSON 对象")
        kind = payload.get('stop_type', 'poi')
        _require(kind in STOP_TYPES, 'stop_type 非法')
        stay_kind = payload.get('hotel_stay_kind')
        if 'hotel_stay_kind' in payload:
            _require(kind == 'hotel' and stay_kind in ('rest', 'overnight'),
                     'hotel_stay_kind 仅用于酒店，须为 rest 或 overnight')
        poi_id = payload.get("poi_id")
        trip = self.store.get(trip_id)
        day = self._day(trip, day_index)
        anchor = None
        if kind == 'poi':
            _require(isinstance(poi_id, str) and poi_id.strip(), "poi_id 必填")
            poi = self.store.poi(poi_id)
        else:
            value = payload.get('anchor')
            if value is None:
                value = trip.get({'hotel': 'anchor_hotel', 'arrival_anchor': 'anchor_arrival',
                                  'departure_anchor': 'anchor_departure'}[kind])
                _require(value is not None, '请先设置该口岸或住宿')
                value = {k: v for k, v in value.items() if k in
                         {'name_zh', 'name_en', 'name_pinyin', 'poi_id', 'coordinate'}} | {
                    'type': kind, 'name_zh': value.get('name_zh') or value.get('location_name'),
                    'name_en': value.get('name_en') or value.get('location_name')}
            anchor = self._validate_day_anchor(value, 'anchor')
            _require(anchor is not None and anchor['type'] == kind, 'anchor.type 与 stop_type 不一致')
            poi_id = anchor.get('poi_id')
            poi = {'names': {'zh-Hans': anchor['name_zh']}}

        existing = [stop for stop in day["ordered_stops"] if kind == "poi" and stop.get("stop_type", "poi") == "poi" and stop.get("poi_id") == poi_id]
        _require(not existing, f"{poi['names']['zh-Hans']} 已在这一天里")

        if payload.get("planned_dwell_minutes") is not None:
            dwell = minutes_to_seconds(payload["planned_dwell_minutes"]) // 60
        else:
            dwell = dwell_minutes_of(poi) if kind == 'poi' else 0
            if (kind == 'arrival_anchor' and day['day_index'] == 1
                    and not day['ordered_stops'] and anchor['coordinate'] == trip['anchor_arrival']['coordinate']):
                dwell = trip['anchor_arrival'].get('border_buffer_minutes', 90)
        _require(0 <= dwell <= 720, '停留时长必须在 0~720 分钟之间')

        order = len(day["ordered_stops"]) + 1
        if payload.get("stop_order") is not None:
            try:
                order = int(payload["stop_order"])
            except (TypeError, ValueError):
                raise EngineError(400, "BAD_REQUEST", "stop_order 必须是整数")
            _require(1 <= order <= len(day["ordered_stops"]) + 1, "stop_order 超出范围")

        preferred = payload.get("user_preferred_arrival_local")
        if preferred is not None:
            _require(isinstance(preferred, str) and re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", preferred),
                     "user_preferred_arrival_local 必须是 HH:mm")

        stop = {
            "stop_order": order,
            "stop_type": kind,
            "stop_id": "stop_" + uuid.uuid4().hex[:20],
            "poi_id": poi_id,
            "locked": bool(payload.get("locked", False)),
            "arrival_at": None,
            "departure_at": None,
            "user_preferred_arrival_local": preferred,
            "planned_dwell_minutes": dwell,
            "transit_from_previous": None,
            "rule_notices": [],
        }
        if anchor:
            stop.update({k: v for k, v in anchor.items() if k != 'type'})
        if stay_kind is not None:
            stop['hotel_stay_kind'] = stay_kind
        day["ordered_stops"].insert(order - 1, stop)
        self._renumber(day)
        self._refresh_day_status(day)
        self._invalidate_route_data(day)
        result = self._commit(trip, "add_stop", stop["stop_id"])

        warning = self._cap_warning(day, trip)
        response = {"trip": result}
        if warning:
            response["pacing_warning"] = warning
        return response

    @_trip_transaction
    def reorder_stops(self, trip_id: str, day_index, payload: dict) -> dict:
        _require(isinstance(payload, dict), "请求体必须是 JSON 对象")
        order = payload.get("stop_order")
        _require(isinstance(order, list) and order, "stop_order 必须是非空数组（按新顺序列出 stop_id）")
        _require(all(isinstance(item, str) for item in order), '排序标识必须是字符串')
        trip = self.store.get(trip_id)
        day = self._day(trip, day_index)

        key = 'stop_id' if all(item in {s['stop_id'] for s in day['ordered_stops']} for item in order) else 'poi_id'
        current = [stop.get(key) for stop in day["ordered_stops"]]
        _require(len(set(current)) == len(current) and None not in current,
                 '请使用 stop_id 排序；poi_id 不能唯一标识这些停靠点')
        _require(len(order) == len(current) and set(order) == set(current), f"新顺序必须与当日停靠点集合一致（当前：{current}）")
        # locked 语义：点不能被挪到**其他 locked 点之前/之后**，即它们的相对顺序必须保持；
        # 未锁定的点可以绕过它移动，因此 locked 点的绝对位置允许变化。
        locked_in_current = [item for item in current if item in
                             {stop.get(key) for stop in day["ordered_stops"] if stop.get("locked")}]
        locked_in_new = [item for item in order if item in set(locked_in_current)]
        if locked_in_new != locked_in_current:
            raise EngineError(400, "BAD_REQUEST",
                              f"已固定（locked）的点的相对顺序不能改变：{locked_in_current} → {locked_in_new}")

        by_id = {stop.get(key): stop for stop in day["ordered_stops"]}
        day["ordered_stops"] = [by_id[item] for item in order]
        self._renumber(day)
        self._invalidate_route_data(day)
        return {"trip": self._commit(trip, "reorder", ",".join(order))}

    @_trip_transaction
    def remove_stop(self, trip_id: str, day_index, poi_id: str) -> dict:
        trip = self.store.get(trip_id)
        day = self._day(trip, day_index)
        moving = self._find_stop(day, poi_id)
        remaining = [stop for stop in day["ordered_stops"] if stop is not moving]
        _require(len(remaining) != len(day["ordered_stops"]), f"这一天没有 {poi_id}")
        day["ordered_stops"] = remaining
        self._renumber(day)
        self._refresh_day_status(day)
        self._invalidate_route_data(day)
        return {"trip": self._commit(trip, "remove_stop", poi_id)}

    @_trip_transaction
    def move_stop_to_evening(self, trip_id: str, day_index, poi_id: str) -> dict:
        """方案 A 的唯一改单入口（由用户显式触发）：插到末尾连续 locked 点之前。"""
        trip = self.store.get(trip_id)
        day = self._day(trip, day_index)
        stops = day["ordered_stops"]
        moving = self._find_stop(day, poi_id)
        _require(moving is not None, f"这一天没有 {poi_id}")
        _require(not moving.get("locked"), "该点已被固定（locked），不能移动")

        others = [stop for stop in stops if stop is not moving]
        insert_at = len(others)
        while insert_at > 0 and others[insert_at - 1].get("locked"):
            insert_at -= 1
        if insert_at == len(others) and stops[-1] is moving:
            raise EngineError(400, "BAD_REQUEST", "该点已经在当天最后位置")
        others.insert(insert_at, moving)
        day["ordered_stops"] = others
        self._renumber(day)
        self._invalidate_route_data(day)
        return {"trip": self._commit(trip, "move_to_evening", poi_id)}

    @_trip_transaction
    def move_stop(self, trip_id: str, from_day_index, poi_id: str, payload: dict) -> dict:
        """把景点移到另一天（② 原来只能同一天内上下移动 / 拖拽）。

        payload：{"to_day_index": int, "stop_order": int?}，省略 stop_order 时追加到目标日末尾。
        约束与同日移动一致：locked 的点不能移动；目标日已有同一个 POI 时拒绝（避免重复占位）。
        跨天会同时作废来源日与目标日的时间轴（两端的时间都要重算）。
        """
        _require(isinstance(payload, dict), "请求体必须是 JSON 对象")
        target_index = payload.get("to_day_index")
        _require(target_index is not None, "to_day_index 必填")
        trip = self.store.get(trip_id)
        source = self._day(trip, from_day_index)
        target = self._day(trip, target_index)
        _require(source is not target, "目标日与来源日相同；同一天内请用排序接口")

        moving = self._find_stop(source, poi_id)
        _require(moving is not None, f"Day {source['day_index']} 里没有 {poi_id}")
        _require(not moving.get("locked"), "该点已被固定（locked），不能跨天移动")
        _require(moving.get("stop_type", "poi") != "poi" or not any(stop.get("stop_type", "poi") == "poi" and stop.get("poi_id") == moving.get("poi_id") for stop in target["ordered_stops"]),
                 f"{poi_id} 已经在 Day {target['day_index']} 里")

        order = len(target["ordered_stops"]) + 1
        if payload.get("stop_order") is not None:
            try:
                order = int(payload["stop_order"])
            except (TypeError, ValueError):
                raise EngineError(400, "BAD_REQUEST", "stop_order 必须是整数")
            _require(1 <= order <= len(target["ordered_stops"]) + 1, "stop_order 超出范围")

        source["ordered_stops"] = [stop for stop in source["ordered_stops"] if stop is not moving]
        target["ordered_stops"].insert(order - 1, moving)
        for day in (source, target):
            self._renumber(day)
            self._refresh_day_status(day)
            self._invalidate_route_data(day)
        result = self._commit(trip, "change_day", poi_id)
        warning = self._cap_warning(target, trip)
        response = {"trip": result}
        if warning:
            response["pacing_warning"] = warning
        return response

    def _renumber(self, day: dict) -> None:
        for index, stop in enumerate(day["ordered_stops"], start=1):
            stop["stop_order"] = index

    def _find_stop(self, day, identifier):
        matches = [s for s in day['ordered_stops'] if s.get('stop_id') == identifier]
        if not matches:
            matches = [s for s in day['ordered_stops'] if s.get('poi_id') == identifier]
        _require(len(matches) <= 1, '该 poi_id 对应多个停靠点，请使用 stop_id')
        return matches[0] if matches else None

    def _refresh_day_status(self, day: dict) -> None:
        stops = day['ordered_stops']
        count = sum(s.get('stop_type', 'poi') == 'poi' for s in stops)
        if stops and all(s.get('locked') for s in stops):
            day['day_status'] = 'locked'
        elif not count:
            day['day_status'] = 'arrival_only' if day.get('is_arrival_day', day.get('day_status') == 'arrival_only') else ('partial' if stops else 'empty')
        elif count >= (day.get('poi_cap') or PACING_CAP['balanced']):
            day['day_status'] = 'fulfilled'
        else:
            day['day_status'] = 'partial'

    def _retag_arrival_day(self, trip: dict) -> None:
        arrival_day = local_date_of(trip['anchor_arrival']['at'])
        for day in trip['days']:
            day['is_arrival_day'] = day['date'] == arrival_day
            # 空白日也可以由外部行程明确标记锁定；读取或编辑其他日期不能解锁它。
            if day.get('day_status') == 'locked' and not day['ordered_stops']:
                continue
            self._refresh_day_status(day)

    def _invalidate_route_data(self, day: dict) -> None:
        """顺序变化后，逐点时间与区段数据必须重算（由 rules_engine / route_adapter 填充）。"""
        day['end_transit'] = None
        for stop in day["ordered_stops"]:
            stop["arrival_at"] = None
            stop["departure_at"] = None
            stop["transit_from_previous"] = None
            stop["rule_notices"] = [n for n in stop.get("rule_notices", []) if not n.get("expires_on_reorder", True)]

    def _cap_warning(self, day: dict, trip: dict) -> str:
        cap = day.get("poi_cap")
        used = sum(s.get("stop_type", "poi") == "poi" for s in day["ordered_stops"])
        if cap and used > cap:
            pacing = trip["user_profile"]["pacing"]
            return f"今天的点位已超过 {pacing} 的建议上限（{cap} 个）"
        return ""
