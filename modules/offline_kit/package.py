"""离线包生成（C8）：按 offline_package.must_include 裁剪，排除对比卡与实时公交。"""
from __future__ import annotations

import re
import time
import sys
from pathlib import Path
if str(Path(__file__).resolve().parents[2]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.trip_points import resolve_day_points
from modules.route_adapter.place_names import (english_place_name, has_chinese,
                                              localized_endpoint, place_name_en,
                                              translate_place_tokens)

try:
    from .ask_cards import card as _card
    from .ask_cards import transfer_card
except ImportError:  # 单模块独立测试时按顶层模块导入
    from ask_cards import card as _card
    from ask_cards import transfer_card

# 打包期补齐英文字段：老行程的路线快照是修复前算的，里面就没有 name_en / direction /
# walk_note_en。这里复用 route_adapter 同一套纯函数从中文派生，用户只要重新生成离线包
# 即可拿到英文，不必先重算交通（重算仍是最完整的路径，方向与出入口信息更全）。
# 完整英文以快照为准；旧字段若仍夹有中文地名，使用本地核录译名补齐。
try:
    from modules.route_adapter.normalize import (complete_line_name_en, derive_line_code, derive_line_name_en,
                                                 normalize_amap_transit_line,
                                                 parse_amap_access_name,
                                                 translate_amap_instructions)
    from modules.route_adapter.providers import rail_line_reference
except Exception:  # noqa: BLE001  route_adapter 缺失时降级为「只呈现快照里的字段」
    complete_line_name_en = derive_line_code = derive_line_name_en = normalize_amap_transit_line = None
    parse_amap_access_name = translate_amap_instructions = rail_line_reference = None

PACKAGE_VERSION = "0.3.0"
TTL_HOURS = 24
CAPACITY_MB = 5
FONT_SUBSET_MB = 1.5
# 契约里 line.code 是给人看的短线号；长数字是三方的内部主键，不进离线包。
_SHORT_CODE_RE = re.compile(r"^[0-9]{1,4}[A-Za-z]?$")


def _line_reference():
    if rail_line_reference is None:
        return {}
    try:
        return rail_line_reference()
    except Exception:  # noqa: BLE001
        return {}


def _clean_line_code(stored, name_zh):
    if isinstance(stored, str) and _SHORT_CODE_RE.match(stored.strip()):
        return stored.strip()
    if name_zh and derive_line_code:
        return derive_line_code(name_zh)
    return None


def _derive_line_and_direction(line, alight_name):
    """快照里没有方向时，用线路名括号里的起讫点 + 下车站名派生（推不出就不给）。"""
    name_zh = (line or {}).get("name_zh")
    if not name_zh or normalize_amap_transit_line is None:
        return None, None
    try:
        return normalize_amap_transit_line(
            name_zh, alight_name=alight_name, rail_reference=_line_reference())
    except Exception:  # noqa: BLE001
        return None, None


def is_stale(package_trip_version, current_trip_version, generated_at, now=None, ttl_hours=TTL_HOURS):
    """版本不匹配或超 TTL 时判定为过期。"""
    now = now if now is not None else time.time()
    if package_trip_version != current_trip_version:
        return True, "version_mismatch"
    if now - generated_at > ttl_hours * 3600:
        return True, "ttl_expired"
    return False, None


def _line_dict(line, direction=None, alight_name=None):
    line = line or {}
    # 行车方向单独带出：离线态里「往哪个方向」决定该上哪一趟车，不能只留在线路名的括号里。
    # 快照没有方向时用同一套规则派生；派生成功就把括号里的起讫点从线路名里摘掉（方向另起一行显示）。
    # 旧包没有这两个键，渲染层按「可缺失」处理。
    stored = dict(direction or {})
    derived_line, derived_direction = _derive_line_and_direction(line, alight_name)
    name_zh = (derived_line or {}).get("name_zh") or line.get("name_zh")
    name_en = line.get("name_en") or (derived_line or {}).get("name_en")
    if has_chinese(name_en):
        name_en = translate_place_tokens(name_en)
    if name_en and complete_line_name_en:
        name_en = complete_line_name_en(name_zh, name_en)
    if not name_en and name_zh and derive_line_name_en:
        try:
            name_en = derive_line_name_en(name_zh, _line_reference())
        except Exception:  # noqa: BLE001
            name_en = None
    out = {"code": _clean_line_code(line.get("code"), name_zh), "name_zh": name_zh,
           "name_en": name_en, "color_hex": line.get("color_hex")}
    direction = stored or derived_direction or {}
    if direction.get("name_zh") or direction.get("name_en"):
        out["direction_zh"] = direction.get("name_zh")
        direction_en = translate_place_tokens(direction.get("name_en"))
        if not direction_en:
            match = re.fullmatch(r"往(.+)方向", direction.get("name_zh") or "")
            target = place_name_en(match.group(1)) if match else None
            direction_en = "Towards " + target if target else None
        out["direction_en"] = direction_en
    return out


def _access_dict(ap, kind="entrance"):
    ap = ap or {}
    name_zh, name_en = ap.get("access_name_zh"), ap.get("access_name_en")
    access_no = ap.get("access_no")
    # 老快照只存了中文站口名（如「2号口」），没有编号也没有英文：
    # 打包时按固定句式补齐，补不出来就保持原样（渲染层只在有编号时才显示这一行）。
    if (not access_no or not name_en or has_chinese(name_en)) and name_zh and parse_amap_access_name:
        derived_no, derived_en = parse_amap_access_name(name_zh, kind)
        access_no = access_no or derived_no
        name_en = derived_en if has_chinese(name_en) else (name_en or derived_en)
    name_en = english_place_name(name_zh, name_en)
    return {"access_no": access_no, "kind": kind, "name_zh": name_zh, "name_en": name_en}


class OfflinePackager:
    def __init__(self):
        self.ttl_hours = TTL_HOURS

    def build(self, trip, station_provider=None, resolver=None):
        trip = trip or {}
        days_out = []
        points = resolve_day_points(trip)
        for day in trip.get("days") or []:
            stops_out = []
            for stop in day.get("ordered_stops") or []:
                stops_out.append(self._build_stop(stop, station_provider))
            endpoints = points[day['day_index']]
            end_route = day.get('end_transit')
            end = endpoints['end'] or {}
            final_transfer = self._build_stop({
                'stop_type':'day_end','type':end.get('type'),'coordinate':end.get('coordinate'),'poi_id':end.get('poi_id'),'name_zh':end.get('name_zh'),'name_en':english_place_name(end.get('name_zh'), end.get('name_en')),
                'departure_at':stops_out[-1]['departure_at'] if stops_out else None,
                'transit_from_previous':end_route}, station_provider) if end_route else None
            days_out.append({"day_index": day.get("day_index"), "date": day.get("date"),
                             "daily_start_local": day.get('daily_start_local'),
                             "start_anchor": localized_endpoint(points[day['day_index']]['start']),
                             "end_anchor": localized_endpoint(points[day['day_index']]['end']),
                             "end_transfer_required": bool(stops_out or endpoints['start'] != endpoints['end']) if end else None,
                             "end_transfer": final_transfer,
                             "stops": stops_out})
        from modules.offline_kit.place_translations import localize_payload
        from modules.route_adapter.place_resolver import PlaceNameResolver
        return localize_payload({"days": days_out}, resolver or PlaceNameResolver())

    def _build_stop(self, stop, station_provider):
        route = stop.get("transit_from_previous") or {}
        stations = self._stations_from_route(route, station_provider)
        walk_segments = self._walk_segments(route)
        ask_cards = self._ask_cards(route, stop)
        destination = route.get('to') or {}
        # 名称以当前停靠点为准；已有路线不是更改后的地点身份来源。
        current_name = stop.get('name_zh') or destination.get('name_zh')
        stored_english = stop.get('name_en') or (destination.get('name_en') if current_name == destination.get('name_zh') else None)
        return {
            "stop_order": stop.get("stop_order"),
            "stop_id": stop.get("stop_id"),
            "stop_type": stop.get("stop_type"),
            "poi_id": stop.get("poi_id"),
            "type": stop.get('type') or (destination.get('type') if stop.get('stop_type')=='day_end' else stop.get('stop_type')),
            "coordinate": stop.get('coordinate') or destination.get('coordinate'),
            "name_zh": current_name,
            "name_en": english_place_name(current_name, stored_english),
            "name_en_for_zh": stop.get("name_en_for_zh") or current_name,
            "data_source": route.get('data_source'),
            "arrival_at": stop.get("arrival_at"),
            "departure_at": stop.get("departure_at"),
            "planned_dwell_minutes": stop.get('planned_dwell_minutes'),
            "hotel_stay_kind": stop.get('hotel_stay_kind'),
            "mode": route.get('mode'),
            "duration_seconds": route.get('duration_seconds'),
            "distance_meters": route.get('distance_meters'),
            "from": localized_endpoint(route.get('from')),
            "to": localized_endpoint(route.get('to')),
            "stations": stations,
            "walk_segments": walk_segments,
            "ask_cards": ask_cards,
        }

    def _stations_from_route(self, route, station_provider):
        merged = {}
        for seg in route.get("segments") or []:
            for role, ap in (("entrance", seg.get("board")), ("exit", seg.get("alight"))):
                if not ap or not ap.get("station_id"):
                    continue
                sid = ap["station_id"]
                entry = merged.setdefault(sid, {
                    "station_id": sid, "name_zh": ap.get("station_name_zh"),
                    "name_en": english_place_name(ap.get("station_name_zh"), ap.get("station_name_en")),
                    "lines": [], "access_points": []})
                entry["name_en"] = english_place_name(entry["name_zh"],
                                                      ap.get("station_name_en") or entry["name_en"])
                if seg.get("line"):
                    line = _line_dict(seg["line"], seg.get("direction"),
                                      alight_name=(seg.get("alight") or {}).get("station_name_zh"))
                    if line not in entry["lines"]:
                        entry["lines"].append(line)
                access = _access_dict(ap, role)
                if access.get("access_no") and access not in entry["access_points"]:
                    entry["access_points"].append(access)
        # 用 route_adapter 的站台库补全线路与进出站口（可选，失败静默退回内嵌数据）
        if station_provider:
            for sid in list(merged):
                try:
                    enriched = station_provider(sid)
                    if enriched:
                        merged[sid] = self._enrich_station(merged[sid], enriched)
                except Exception:  # noqa: BLE001
                    continue
        return list(merged.values())

    def _enrich_station(self, entry, station):
        entry["name_zh"] = (station.get("names") or {}).get("zh-Hans") or entry["name_zh"]
        entry["name_en"] = (station.get("names") or {}).get("en") or entry["name_en"]
        for line in station.get("lines") or []:
            ld = _line_dict(line)
            if ld not in entry["lines"]:
                entry["lines"].append(ld)
        for ap in station.get("access_points") or []:
            ad = {"access_no": ap.get("access_no"), "kind": ap.get("kind", "entrance"),
                  "name_zh": ap.get("name_zh"), "name_en": ap.get("name_en")}
            if ad.get("access_no") and ad not in entry["access_points"]:
                entry["access_points"].append(ad)
        return entry

    @staticmethod
    def _note_en(note_zh, note_en):
        """保留完整英文；旧混合字段从中文指令重建或补齐已核录的地名。"""
        if note_en and not has_chinese(note_en):
            return note_en
        repaired = translate_place_tokens(note_en)
        if not note_zh or translate_amap_instructions is None:
            return repaired
        try:
            return translate_amap_instructions(str(note_zh).split("；")) or repaired
        except Exception:  # noqa: BLE001
            return repaired

    def _walk_segments(self, route):
        out = []
        for seg in route.get("segments") or []:
            if seg.get("kind") == "walk":
                out.append({"distance_meters": seg.get("distance_meters"),
                            "kind": "walk",
                            "note_zh": seg.get("walk_note_zh"),
                            "note_en": self._note_en(seg.get("walk_note_zh"), seg.get("walk_note_en"))})
            elif seg.get('kind') == 'transfer':
                transfer = seg.get('transfer') or {}
                out.append({'kind':'transfer',
                            'distance_meters':transfer.get('walking_distance_meters',seg.get('distance_meters')),
                            'note_zh':transfer.get('note_zh'),
                            'note_en':self._note_en(transfer.get('note_zh'), transfer.get('note_en'))})
        return out

    def _ask_cards(self, route, stop):
        cards = []
        segments = route.get("segments") or []
        for idx, seg in enumerate(segments):
            if seg.get("kind") == "ride" and seg.get("board"):
                access = _access_dict(seg["board"], "entrance")
                cards.append(_card("station_entrance", {
                    "access_name_zh": access["name_zh"],
                    "access_name_en": access["name_en"]}))
            if seg.get("kind") == "ride" and seg.get("alight"):
                access = _access_dict(seg["alight"], "exit")
                cards.append(_card("station_exit", {
                    "access_name_zh": access["name_zh"],
                    "access_name_en": access["name_en"]}))
            if seg.get("kind") == "transfer":
                line = seg.get("line") or {}
                if not line and idx + 1 < len(segments) and segments[idx + 1].get("kind") == "ride":
                    line = segments[idx + 1].get("line") or {}
                line = _line_dict(line)
                cards.append(transfer_card(
                    line_name_zh=line.get("name_zh"), line_name_en=line.get("name_en"),
                    direction_present=bool(line.get("name_zh") or line.get("name_en"))))
        if route.get("drop_off"):
            drop = route["drop_off"]
            cards.append(_card("drop_off", {"desc_zh": drop.get("desc_zh"),
                                            "desc_en": translate_place_tokens(drop.get("desc_en"))}))
        to_ep = route.get("to") or {}
        cards.append(_card("poi_arrival", {"poi_name_zh": to_ep.get("name_zh") or stop.get("name_zh"),
                                           "poi_name_en": english_place_name(to_ep.get("name_zh") or stop.get("name_zh"),
                                                                            to_ep.get("name_en") or stop.get("name_en"))}))
        return [c for c in cards if c]
