"""行程应用服务：创建、预校验、读取、修改、复制、删除与统一提交。"""
from __future__ import annotations

import json
import re
import threading
import uuid
from datetime import date, timedelta

from core.trip_points import resolve_day_points
from .errors import EngineError
from .store import TripStore
from .validation import TripValidation
from .stops import StopOperations
from .catalog import CatalogueQueries
from .recommendations import RecommendationOperations
from .domain import (
    CONTRACT_VERSION,
    PACING_CAP,
    PARTY_WALK_MULTIPLIER,
    PARTY_COMPOSITIONS,
    PACINGS,
    INTERESTS,
    BORDER_BUFFER_DEFAULT,
    DEFAULT_DAILY_START,
    now_seconds,
    local_date_of,
    _require,
    _as_float,
    _trip_transaction,
)


class TripService(TripValidation, StopOperations, CatalogueQueries, RecommendationOperations):
    """行程生命周期与提交；统一持有存储、时钟和事务锁。"""

    def __init__(self, data_dir, poi_path=None, wall_clock=None):
        self.store = TripStore(data_dir, poi_path)
        self.contract_version = CONTRACT_VERSION
        self._wall_clock = wall_clock or now_seconds
        self._trip_locks = [threading.RLock() for _ in range(64)]

    def create_trip(self, payload: dict) -> dict:
        """校验 + 落盘。校验全部集中在 _build_trip，创建与「预校验」共用同一段逻辑。"""
        return self.store.save(self._build_trip(payload))

    def validate_trip(self, payload: dict) -> dict:
        """只校验、不落盘（POST /trips:validate）。

        为什么需要它：工作台原来一提交就直接 POST /trips 建行程，非法输入或后续规则求值
        失败时行程已经存下来了（要么留下半成品，要么用户得手动删）。现在前端先打这个接口，
        校验通过才真正创建。「合法但不落盘」也顺便让用户能先看到派生出来的天数与单日建议上限。
        """
        trip = self._build_trip(payload)
        return {
            "valid": True,
            "duration_days": len(trip["days"]),
            "dates": [day["date"] for day in trip["days"]],
            "day_status": [day["day_status"] for day in trip["days"]],
            "poi_cap": trip["days"][0]["poi_cap"],
            "activity_start_at": trip["anchor_arrival"]["activity_start_at"],
            "has_departure": trip["anchor_departure"] is not None,
        }

    def _build_trip(self, payload: dict) -> dict:
        _require(isinstance(payload, dict), "请求体必须是 JSON 对象")
        budget = self._validate_budget(payload.get('budget'))

        profile = payload.get("user_profile")
        _require(isinstance(profile, dict), "user_profile 必填")
        party = profile.get("party_composition")
        pacing = profile.get("pacing")
        _require(party in PARTY_COMPOSITIONS, f"party_composition 必须是 {sorted(PARTY_COMPOSITIONS)} 之一")
        _require(pacing in PACINGS, f"pacing 必须是 {sorted(PACINGS)} 之一")
        interests = profile.get("interests", [])
        _require(isinstance(interests, list) and len(interests) <= 4, "interests 必须是最多 4 项的数组")
        bad = [item for item in interests if item not in INTERESTS]
        _require(not bad, f"interests 含未知取值：{bad}")
        speed = profile.get("walking_speed_factor", 1.0)
        _require(isinstance(speed, (int, float)) and not isinstance(speed, bool) and 0.5 <= speed <= 2.0,
                 "walking_speed_factor 必须在 0.5~2.0 之间")

        duration = payload.get("duration_days")
        _require(isinstance(duration, int) and not isinstance(duration, bool), "duration_days 必填且必须是整数")
        _require(1 <= duration <= 15, "duration_days 必须在 1~15 之间")

        arrival = self._validate_anchor(payload.get("anchor_arrival"), "anchor_arrival", "border_buffer_minutes", (0, 300, BORDER_BUFFER_DEFAULT))
        hotel = payload.get("anchor_hotel")
        _require(isinstance(hotel, dict), "anchor_hotel 必填")
        for field in ("name_en", "name_zh"):
            _require(isinstance(hotel.get(field), str) and hotel[field].strip(), f"anchor_hotel.{field} 必填")
        coordinate = hotel.get("coordinate")
        _require(isinstance(coordinate, dict) and isinstance(coordinate.get("crs"), str), "anchor_hotel.coordinate 必填")
        departure = payload.get("anchor_departure")
        if departure is not None:
            # 注意顺序：_validate_anchor 只保留它的白名单字段（at / location_name /
            # coordinate / <buffer_field>），is_international 会被丢掉。原来先校验再读，
            # 于是 departure.get("is_international", True) 永远取默认值 True ——
            # 「国内段」被静默当成国际段。必须先从原始 payload 取值。
            _require(isinstance(departure, dict), "anchor_departure 必须是对象")
            is_international = departure.get("is_international", True)
            _require(isinstance(is_international, bool), "anchor_departure.is_international 必须是布尔值")
            departure = self._validate_anchor(departure, "anchor_departure", "hub_buffer_minutes", (60, 300, 180))
            departure["is_international"] = is_international

        start_date = payload.get("start_date") or local_date_of(arrival["at"])
        _require(isinstance(start_date, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", start_date),
                 "start_date 必须是 YYYY-MM-DD")
        daily_start = payload.get("daily_start_local") or DEFAULT_DAILY_START
        _require(isinstance(daily_start, str) and re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", daily_start),
                 "daily_start_local 必须是 HH:mm")

        timestamp = self._wall_clock()
        trip_id = f"trip_{uuid.uuid4().hex[:12]}"
        arrival_day = local_date_of(arrival["at"])
        day_one = date.fromisoformat(start_date)
        days = []
        for index in range(duration):
            current = (day_one + timedelta(days=index)).isoformat()
            days.append({
                "day_index": index + 1,
                "date": current,
                "day_status": "arrival_only" if current == arrival_day else "empty",
                "is_arrival_day": current == arrival_day,
                "daily_start_local": daily_start,
                "poi_cap": PACING_CAP[pacing],
                "ordered_stops": [],
            })

        trip = {
            "trip_id": trip_id,
            "user_id": payload.get("user_id"),
            "version": 1,
            "status": "draft",
            "budget": budget,
            "timezone": "Asia/Shanghai",
            "created_at": timestamp,
            "updated_at": timestamp,
            "user_profile": {
                "party_composition": party,
                "pacing": pacing,
                "interests": list(interests),
                "walking_speed_factor": float(speed),
                "party_walk_multiplier": PARTY_WALK_MULTIPLIER[party],
                "prefer_taxi": party in ("family_kids", "senior"),
            },
            "anchor_arrival": {
                **arrival,
                "activity_start_at": arrival["at"] + arrival["border_buffer_minutes"] * 60,
            },
            "anchor_departure": departure,
            "anchor_hotel": {
                "name_en": hotel["name_en"].strip(),
                "name_zh": hotel["name_zh"].strip(),
                "coordinate": coordinate,
                **({"name_pinyin": hotel["name_pinyin"]} if hotel.get("name_pinyin") else {}),
                "poi_id": hotel.get("poi_id"),
            },
            "unassigned_pois": [],
            "days": days,
            "revision_history": [{"version": 1, "changed_at": timestamp, "operation": "create", "target": trip_id}],
        }
        trip['cost_inputs'] = self._validate_cost_inputs(payload.get('cost_inputs'), trip)
        return trip

    def get_trip(self, trip_id: str) -> dict:
        trip = self.store.get(trip_id)
        self._retag_arrival_day(trip)
        return trip

    @_trip_transaction
    def delete_trip(self, trip_id: str) -> dict:
        """删除一份历史行程（② 的历史列表以前只能选，不能删）。"""
        self.store.get(trip_id)      # 不存在时先报 TRIP_NOT_FOUND，不能静默成功
        self.store.delete(trip_id)
        return {"trip_id": trip_id, "deleted": True}

    @_trip_transaction
    def duplicate_trip(self, trip_id: str) -> dict:
        """复制一份行程为新草稿：想在同一套设定上再排一版时不用从头填。"""
        source = self.store.get(trip_id)
        timestamp = self._wall_clock()
        copy = json.loads(json.dumps(source))     # 深拷贝，避免与原件共享嵌套对象
        copy["trip_id"] = f"trip_{uuid.uuid4().hex[:12]}"
        copy["version"] = 1
        copy["status"] = "draft"
        copy["created_at"] = timestamp
        copy["updated_at"] = timestamp
        copy["revision_history"] = [{"version": 1, "changed_at": timestamp,
                                     "operation": "create", "target": copy["trip_id"]}]
        return self.store.save(copy)

    @_trip_transaction
    def patch_trip(self, trip_id: str, payload: dict, expected_version=None) -> dict:
        _require(isinstance(payload, dict), "请求体必须是 JSON 对象")
        trip = self.store.get(trip_id)
        if expected_version is not None and int(expected_version) != trip["version"]:
            raise EngineError(409, "VERSION_CONFLICT", "行程已被其他操作修改，请刷新后重试",
                              {"expected": int(expected_version), "actual": trip["version"]})

        points_before = resolve_day_points(trip)
        changed: list[str] = []
        if 'budget' in payload:
            trip['budget'] = self._validate_budget(payload['budget'])
            changed.append('budget')
        if 'cost_inputs' in payload:
            trip['cost_inputs'] = self._validate_cost_inputs(payload['cost_inputs'], trip)
            changed.append('cost_inputs')
        profile = payload.get("user_profile")
        if profile is not None:
            _require(isinstance(profile, dict), "user_profile 必须是对象")
            target = trip["user_profile"]
            if "pacing" in profile:
                _require(profile["pacing"] in PACINGS, "pacing 取值非法")
                target["pacing"] = profile["pacing"]
                for day in trip["days"]:
                    day["poi_cap"] = PACING_CAP[profile["pacing"]]
                changed.append("pacing")
            if "party_composition" in profile:
                _require(profile["party_composition"] in PARTY_COMPOSITIONS, "party_composition 取值非法")
                target["party_composition"] = profile["party_composition"]
                target["party_walk_multiplier"] = PARTY_WALK_MULTIPLIER[profile["party_composition"]]
                target["prefer_taxi"] = profile["party_composition"] in ("family_kids", "senior")
                changed.append("party_composition")
            if "interests" in profile:
                interests = profile["interests"]
                _require(isinstance(interests, list) and len(interests) <= 4, "interests 必须是最多 4 项的数组")
                bad = [item for item in interests if item not in INTERESTS]
                _require(not bad, f"interests 含未知取值：{bad}")
                target["interests"] = list(interests)
                changed.append("interests")
            if "walking_speed_factor" in profile:
                speed = _as_float(profile["walking_speed_factor"], "walking_speed_factor")
                _require(0.5 <= speed <= 2.0, "walking_speed_factor 必须在 0.5~2.0 之间")
                target["walking_speed_factor"] = speed
                changed.append("walking_speed_factor")

        if "daily_start_local" in payload:
            value = payload["daily_start_local"]
            _require(isinstance(value, str) and re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", value),
                     "daily_start_local 必须是 HH:mm")
            for day in trip["days"]:
                day["daily_start_local"] = value
            changed.append("daily_start_local")

        if "anchor_arrival" in payload:
            arrival = self._validate_anchor(payload["anchor_arrival"], "anchor_arrival", "border_buffer_minutes", (0, 300, BORDER_BUFFER_DEFAULT))
            trip["anchor_arrival"] = {**arrival, "activity_start_at": arrival["at"] + arrival["border_buffer_minutes"] * 60}
            self._retag_arrival_day(trip)      # 抵达时刻变了，「抵达日」可能换一天
            changed.append("anchor_arrival")

        if "anchor_departure" in payload:
            # 显式传 null = 取消离境安排；传对象 = 设置/替换。以前这条只能创建时给一次。
            departure = payload["anchor_departure"]
            if departure is None:
                trip["anchor_departure"] = None
            else:
                _require(isinstance(departure, dict), "anchor_departure 必须是对象或 null")
                is_international = departure.get("is_international", True)
                _require(isinstance(is_international, bool), "anchor_departure.is_international 必须是布尔值")
                built = self._validate_anchor(departure, "anchor_departure", "hub_buffer_minutes", (60, 300, 180))
                built["is_international"] = is_international
                trip["anchor_departure"] = built
            changed.append("anchor_departure")

        if "start_date" in payload:
            start = payload["start_date"]
            _require(isinstance(start, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", start),
                     "start_date 必须是 YYYY-MM-DD")
            first = date.fromisoformat(start)
            for offset, day in enumerate(trip["days"]):
                day["date"] = (first + timedelta(days=offset)).isoformat()
            self._retag_arrival_day(trip)
            changed.append("start_date")

        if "duration_days" in payload:
            duration = payload["duration_days"]
            _require(isinstance(duration, int) and not isinstance(duration, bool), "duration_days 必须是整数")
            _require(1 <= duration <= 15, "duration_days 必须在 1~15 之间")
            days = trip["days"]
            if duration < len(days):
                # 缩短天数会直接删掉整天：有已排点位时必须拒绝，不能静默丢数据。
                doomed = [day for day in days[duration:] if day["ordered_stops"]]
                _require(not doomed,
                         "缩短天数会丢掉已排的点位："
                         + "、".join(f"Day {day['day_index']}（{len(day['ordered_stops'])} 个）" for day in doomed)
                         + "；请先移除这些点位")
                del days[duration:]
            elif duration > len(days):
                first = date.fromisoformat(days[0]["date"])
                for offset in range(len(days), duration):
                    days.append({
                        "day_index": offset + 1,
                        "date": (first + timedelta(days=offset)).isoformat(),
                        "day_status": "empty",
                        "daily_start_local": days[0]["daily_start_local"],
                        "poi_cap": PACING_CAP[trip["user_profile"]["pacing"]],
                        "ordered_stops": [],
                    })
            for index, day in enumerate(days, start=1):
                day["day_index"] = index
            self._retag_arrival_day(trip)
            changed.append("duration_days")

        if "anchor_hotel" in payload:
            hotel = payload["anchor_hotel"]
            _require(isinstance(hotel, dict), "anchor_hotel 必须是对象")
            for field in ("name_en", "name_zh"):
                _require(isinstance(hotel.get(field), str) and hotel[field].strip(), f"anchor_hotel.{field} 必填")
            trip["anchor_hotel"] = {
                "name_en": hotel["name_en"].strip(),
                "name_zh": hotel["name_zh"].strip(),
                "coordinate": hotel["coordinate"],
                **({"name_pinyin": hotel["name_pinyin"]} if hotel.get("name_pinyin") else {}),
                "poi_id": hotel.get("poi_id"),
            }
            changed.append("anchor_hotel")

        departure_days: set[int] = set()
        confirm_targets: list[str] = []
        if "days" in payload:
            days_payload = payload["days"]
            _require(isinstance(days_payload, list) and days_payload, "days 必须是非空数组")
            for day_patch in days_payload:
                _require(isinstance(day_patch, dict), "days[] 必须是对象")
                day = self._day(trip, day_patch.get("day_index"))
                if 'end_transit' in day_patch:
                    route = day_patch['end_transit']
                    _require(route is None or isinstance(route, dict), 'end_transit 必须是路线对象或 null')
                    if route is not None:
                        expected = resolve_day_points(trip)[day['day_index']]['end'] or {}
                        destination = route.get('to') or {}
                        _require(destination.get('type') == expected.get('type') and
                                 destination.get('poi_id') == expected.get('poi_id') and
                                 destination.get('name_zh') == expected.get('name_zh'), '返程路线终点与当日终止点不匹配')
                    day['end_transit'] = route
                for field in ('start_anchor', 'end_anchor'):
                    if field in day_patch:
                        day[field] = self._validate_day_anchor(day_patch[field], field)
                if "daily_start_local" in day_patch:
                    value = day_patch["daily_start_local"]
                    _require(isinstance(value, str) and re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", value),
                             "days[].daily_start_local 必须是 HH:mm")
                    day["daily_start_local"] = value
                    departure_days.add(day["day_index"])
                if "ordered_stops" not in day_patch:
                    _require(any(field in day_patch for field in ('daily_start_local', 'start_anchor', 'end_anchor', 'end_transit')),
                             "days[] 需要 daily_start_local、start_anchor、end_anchor 或 ordered_stops")
                    continue
                stops_patch = day_patch.get("ordered_stops")
                _require(isinstance(stops_patch, list) and stops_patch, "days[].ordered_stops 必须是非空数组")
                for stop_patch in stops_patch:
                    _require(isinstance(stop_patch, dict), "ordered_stops[] 必须是对象")
                    order = stop_patch.get("stop_order")
                    _require(isinstance(order, int) and not isinstance(order, bool), "stop_order 必须是整数")
                    stop = next((item for item in day["ordered_stops"] if item.get("stop_order") == order), None)
                    _require(stop is not None, f"Day {day['day_index']} 没有 stop_order={order}")
                    if "locked" in stop_patch:
                        _require(isinstance(stop_patch["locked"], bool), "locked 必须是布尔值")
                        stop["locked"] = stop_patch["locked"]
                    if "transit_from_previous" in stop_patch:
                        route = stop_patch["transit_from_previous"]
                        _require(route is None or isinstance(route, dict), "路线必须是对象或 null")
                        if route is not None:
                            _require((route.get("to") or {}).get("poi_id") == stop.get("poi_id"), "路线终点与景点不匹配")
                            if stop.get('stop_type', 'poi') != 'poi':
                                destination = route.get('to') or {}
                                _require(destination.get('stop_id') == stop['stop_id'] if destination.get('stop_id') else
                                         destination.get('type') == stop['stop_type'] and destination.get('name_zh') == stop.get('name_zh'),
                                         '路线终点与住宿/口岸不匹配')
                        stop["transit_from_previous"] = route
                        for following in day["ordered_stops"]:
                            following["arrival_at"] = None
                            following["departure_at"] = None
                    if "arrival_at" in stop_patch:
                        stop["arrival_at"] = stop_patch["arrival_at"]
                    if "departure_at" in stop_patch:
                        stop["departure_at"] = stop_patch["departure_at"]
                    if "rule_notices" in stop_patch:
                        _require(isinstance(stop_patch["rule_notices"], list), "rule_notices 必须是数组")
                        stop["rule_notices"] = stop_patch["rule_notices"]
                    confirm_targets.append(stop.get("poi_id") or str(order))
            changed.append("days")

        _require(changed, "没有可更新的字段（支持 user_profile / daily_start_local / anchor_arrival / "
                          "anchor_departure / anchor_hotel / start_date / duration_days / days / budget / cost_inputs）")
        if 'cost_inputs' in payload:
            trip['cost_inputs'] = self._validate_cost_inputs(payload['cost_inputs'], trip)
        points_after = resolve_day_points(trip)
        departure_days.update(index for index, points in points_after.items() if points_before.get(index) != points)
        if confirm_targets:
            for day in trip["days"]:
                if day["day_index"] in departure_days:
                    self._invalidate_route_data(day)
            if departure_days:
                return self._commit(trip, "update_config", ", ".join(changed))
            return self._commit(trip, "confirm_conflict", ", ".join(confirm_targets))
        for day in trip["days"]:
            if not set(payload).issubset({'days', 'anchor_hotel', 'budget', 'cost_inputs'}) or day["day_index"] in departure_days:
                self._invalidate_route_data(day)
        return self._commit(trip, "update_config", ", ".join(changed))

    def _commit(self, trip: dict, operation: str, target: str) -> dict:
        # 显式首站抵达口岸包含入境缓冲，不能因加入/排序时给了零停留而丢失。
        for day in trip['days']:
            first = next(iter(day['ordered_stops']), None)
            if (day['day_index'] == 1 and first and first.get('stop_type') == 'arrival_anchor'
                    and first.get('coordinate') == trip['anchor_arrival']['coordinate']):
                first['planned_dwell_minutes'] = max(first['planned_dwell_minutes'],
                    trip['anchor_arrival'].get('border_buffer_minutes', 90))
        before = resolve_day_points(self.store.get(trip['trip_id']))
        after = resolve_day_points(trip)
        for day in trip['days']:
            if before.get(day['day_index']) != after.get(day['day_index']):
                self._invalidate_route_data(day)
        self._retag_arrival_day(trip)
        timestamp = self._wall_clock()
        trip["version"] += 1
        trip["updated_at"] = timestamp
        trip["revision_history"].append({
            "version": trip["version"], "changed_at": timestamp, "operation": operation, "target": target,
        })
        return self.store.save(trip)
