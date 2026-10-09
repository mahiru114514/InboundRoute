"""三方数据源与 Mock 数据源（C1/C2）。

Mock 与真实 Provider 返回相同签名，切换只改 config.provider，调用方零改动。
真实 Provider 只做「取数 + 单向坐标归一化」，字段映射遵循 mappings.provider_field_map。
"""
from __future__ import annotations

import json
import math
import os
import socket
import ssl
import urllib.parse
import urllib.error
import urllib.request
from pathlib import Path

try:
    from .place_names import english_place_name
    from .crs import to_wgs84, wgs84_to_gcj02
    from .normalize import (build_cost, clean_text, estimate_steps, haversine_meters,
                            normalize_amap_transit_line, parse_amap_access_name,
                            translate_amap_instructions, walk_speed_for)
except ImportError:  # 单模块独立测试时按顶层模块导入
    from place_names import english_place_name
    from crs import to_wgs84, wgs84_to_gcj02
    from normalize import (build_cost, clean_text, estimate_steps, haversine_meters,
                           normalize_amap_transit_line, parse_amap_access_name,
                           translate_amap_instructions, walk_speed_for)

# 具名线路的官方英文译名表（高德只给中文名，查不到就保持中文，不做机器翻译）。
_RAIL_LINE_REFERENCE_PATH = Path(__file__).resolve().parent / "data" / "curated_rail_lines.json"
_RAIL_LINE_REFERENCE = None


def rail_line_reference():
    """懒加载官方译名表；文件缺失或损坏时返回空表（功能降级为「只有中文」，不报错）。"""
    global _RAIL_LINE_REFERENCE
    if _RAIL_LINE_REFERENCE is None:
        lines = {}
        try:
            data = json.loads(_RAIL_LINE_REFERENCE_PATH.read_text(encoding="utf-8-sig"))
            raw = data.get("lines") if isinstance(data, dict) else None
            lines = {key: value for key, value in (raw or {}).items()
                     if isinstance(key, str) and isinstance(value, str) and value.strip()}
        except Exception:  # noqa: BLE001
            lines = {}
        _RAIL_LINE_REFERENCE = lines
    return _RAIL_LINE_REFERENCE


class ProviderError(RuntimeError):
    """三方失败原因：timeout / rate_limited / no_route / unsupported_city。"""

    def __init__(self, reason: str, detail: str = "", *, diagnostic: dict | None = None):
        super().__init__(detail or reason)
        self.reason = reason
        self.detail = detail
        # Only fixed categories and numeric codes are safe to show in diagnostics.
        # Never forward provider info, request URLs or raw exception text.
        diagnostic = diagnostic or {}
        self.diagnostic = {}
        if diagnostic.get("category") in {
            "service_error", "http_error", "timeout", "certificate_error",
            "dns_error", "network_error", "invalid_json", "invalid_response",
            "missing_route_fields", "no_route",
            "walking_duration_missing", "ride_duration_missing",
            "unsupported_transit_segment", "transit_segments_missing",
        }:
            self.diagnostic["category"] = diagnostic["category"]
        code = diagnostic.get("provider_code")
        if isinstance(code, str) and len(code) == 5 and code.isascii() and code.isdigit():
            self.diagnostic["provider_code"] = code
        http_status = diagnostic.get("http_status")
        if type(http_status) is int and 100 <= http_status <= 599:
            self.diagnostic["http_status"] = http_status


class ProviderNotConfigured(ProviderError):
    def __init__(self, provider: str):
        super().__init__("unsupported_city", f"{provider} 未配置 API key")


def _pick_nearest(station_lib, lat, lng):
    best = None
    best_d = None
    for station in getattr(station_lib, "_stations", {}).values():
        coord = station.get("coordinate") or {}
        if "lat" not in coord or "lng" not in coord:
            continue
        d = haversine_meters(lat, lng, coord["lat"], coord["lng"])
        if best_d is None or d < best_d:
            best_d = d
            best = station
    return best


class BaseProvider:
    name = "base"
    source = "mock"
    output_crs = "WGS84"

    def compute(self, from_point, to_point, mode, party_composition, options):
        raise NotImplementedError


class MockProvider(BaseProvider):
    """不访问外网，返回与真实 Provider 同签名的归一化结果。data_source=mock。"""

    name = "mock"
    source = "mock"

    def __init__(self, station_lib):
        self.station_lib = station_lib

    def compute(self, from_point, to_point, mode, party_composition, options):
        lat1, lng1 = float(from_point["lat"]), float(from_point["lng"])
        lat2, lng2 = float(to_point["lat"]), float(to_point["lng"])
        straight = haversine_meters(lat1, lng1, lat2, lng2)
        speed = walk_speed_for(party_composition)
        if mode in ("walk", "bike"):
            distance = int(round(straight))
            duration = int(round(distance / speed))
            return {
                "mode": mode,
                "duration_seconds": duration,
                "distance_meters": distance,
                "cost": None,
                "congestion_level": "unknown",
                "transfer_count": 0,
                "walking_distance_meters": distance,
                "walking_duration_seconds": duration,
                "estimated_steps": estimate_steps(distance, party_composition),
                "segments": None,
                "data_source": self.source,
            }
        if mode == "taxi":
            distance = int(round(straight * 1.25))
            duration = int(round(distance / 9.0))
            cost_min = 14 + distance / 1000.0 * 2.4
            cost_max = 14 + distance / 1000.0 * 3.4
            walk = 90
            return {
                "mode": mode,
                "duration_seconds": duration,
                "distance_meters": distance,
                "cost": build_cost(round(cost_min, 1), round(cost_max, 1)),
                "congestion_level": "low" if distance < 5000 else "medium",
                "transfer_count": 0,
                "walking_distance_meters": walk,
                "walking_duration_seconds": int(round(walk / speed)),
                "estimated_steps": estimate_steps(walk, party_composition),
                "segments": None,
                "data_source": self.source,
            }
        # transit
        board_station = _pick_nearest(self.station_lib, lat1, lng1)
        alight_station = _pick_nearest(self.station_lib, lat2, lng2)
        transfer_count = 1 if straight >= 3000 else 0
        transfer_walk = 320 if transfer_count else 0
        walk_to_station = min(int(straight * 0.25), 800)
        walk_from_station = min(int(straight * 0.2), 700)
        walking_distance = walk_to_station + transfer_walk + walk_from_station
        ride_distance = max(int(straight * 1.1), 500)
        ride_duration = int(ride_distance / 11.0)
        walk_duration = int(walking_distance / speed)
        duration = ride_duration + (390 if transfer_count else 0) + walk_duration
        distance = int(round(straight * 1.3))

        segments = []
        if walk_to_station > 0:
            segments.append({
                "kind": "walk", "duration_seconds": int(walk_to_station / speed),
                "distance_meters": walk_to_station,
                "line": None, "direction": None, "board": None, "alight": None,
                "stops": None, "transfer": None,
                "walk_note_en": f"Walk {walk_to_station}m to the station.",
                "walk_note_zh": f"步行 {walk_to_station} 米至地铁站。",
            })
        line_code = "2"
        if board_station:
            board = self.station_lib.access_point(board_station["station_id"], kind="entrance")
            board["access_name_zh"] = "2号口"
            board["access_name_en"] = "Entrance 2"
            board["access_no"] = "2"
            board["landmark_desc_zh"] = "进站方向"
            board["landmark_desc_en"] = "Towards station entrance"
        else:
            board = None
        if alight_station:
            alight = self.station_lib.access_point(alight_station["station_id"], kind="exit")
            alight["access_name_zh"] = "7号口"
            alight["access_name_en"] = "Exit 7"
            alight["access_no"] = "7"
        else:
            alight = None
        segments.append({
            "kind": "ride", "duration_seconds": ride_duration, "distance_meters": ride_distance,
            "line": {"code": line_code, "name_en": "Line 2 (Green)", "name_zh": "2 号线", "color_hex": "#00A650"},
            "direction": {"name_en": "Towards Pudong Int'l Airport", "name_zh": "往浦东国际机场方向", "terminal_station_id": "sh_stn_00002"},
            "board": board, "alight": alight, "stops": 2, "transfer": None,
            "walk_note_en": None, "walk_note_zh": None,
        })
        if transfer_count:
            segments.append({
                "kind": "transfer", "duration_seconds": 390, "distance_meters": transfer_walk,
                "line": None, "direction": None, "board": None, "alight": None, "stops": None,
                "transfer": {
                    "walking_distance_meters": transfer_walk,
                    "duration_min_minutes": 5, "duration_max_minutes": 7,
                    "is_in_station": True, "note_en": "Take indoor escalators",
                    "note_zh": "建议走站内扶梯", "vertical_gap_note_zh": "站厅到站台高差较大",
                    "is_barrier_free": True, "source": "curated",
                },
                "walk_note_en": None, "walk_note_zh": None,
            })
        if walk_from_station > 0:
            segments.append({
                "kind": "walk", "duration_seconds": int(walk_from_station / speed),
                "distance_meters": walk_from_station,
                "line": None, "direction": None, "board": None, "alight": None,
                "stops": None, "transfer": None,
                "walk_note_en": f"Walk {walk_from_station}m to the destination.",
                "walk_note_zh": f"步行 {walk_from_station} 米至目的地。",
            })

        return {
            "mode": "transit",
            "duration_seconds": duration,
            "distance_meters": distance,
            "cost": build_cost(3, 4),
            "congestion_level": "unknown",
            "transfer_count": transfer_count,
            "walking_distance_meters": walking_distance,
            "walking_duration_seconds": walk_duration,
            "estimated_steps": estimate_steps(walking_distance, party_composition),
            "segments": segments,
            "data_source": self.source,
        }


class HttpProvider(BaseProvider):
    """真实三方 Provider 骨架：仅做取数与单向坐标归一化，不落日志/不下发 key。"""

    def __init__(self, name, source, config):
        self.name = name
        self.source = source
        self.config = config or {}
        self.api_key = self.config.get("api_key") or self.config.get("key") or ""

    def _require_key(self):
        if not self.api_key:
            raise ProviderNotConfigured(self.name)

    def _request_json(self, url, timeout=2.0):
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "inboundroute-route-adapter/0.1")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _normalize_direction(self, payload, from_point, to_point, mode, party_composition):
        # 三方字段映射：duration/cost/transfer_count/walking_distance（provider_field_map）
        duration = payload.get("duration")
        distance = payload.get("distance") or payload.get("distance_meters")
        if distance is None:
            distance = int(round(haversine_meters(from_point["lat"], from_point["lng"],
                                                  to_point["lat"], to_point["lng"]) * 1.3))
        cost = payload.get("cost")
        walking = payload.get("walking_distance") or payload.get("walking_distance_meters") or 0
        return {
            "mode": mode,
            "duration_seconds": int(duration) if duration is not None else None,
            "distance_meters": int(distance) if distance is not None else None,
            "cost": build_cost(float(cost), float(cost)) if isinstance(cost, (int, float)) else None,
            "congestion_level": payload.get("congestion_level", "unknown"),
            "transfer_count": payload.get("transfer_count"),
            "walking_distance_meters": int(walking) if walking else None,
            "walking_duration_seconds": None,
            "estimated_steps": estimate_steps(int(walking), party_composition) if walking else None,
            "segments": None,
            "data_source": self.source,
        }

    def compute(self, from_point, to_point, mode, party_composition, options):
        self._require_key()
        base = self.config.get("base_url", "").rstrip("/")
        if not base:
            raise ProviderNotConfigured(self.name)
        from_lat, from_lng = to_wgs84(float(from_point["lat"]), float(from_point["lng"]),
                                      from_point.get("crs", self.provider_crs))
        # 此处只演示取数与归一化路径；真实 endpoint 需按各家文档替换。
        url = f"{base}/direction?origin={from_lat},{from_lng}&destination={to_point['lat']},{to_point['lng']}&mode={mode}&key={self.api_key}"
        payload = self._request_json(url)
        return self._normalize_direction(payload, from_point, to_point, mode, party_composition)


class AmapProvider(HttpProvider):
    """高德 Web 服务 v3；请求 GCJ-02，经度在前，输出遵循路线契约。"""

    name = "amap"
    source = "amap"
    provider_crs = "GCJ-02"

    def __init__(self, config):
        super().__init__("amap", "amap", config)
        self.api_key = self.api_key or os.environ.get("AMAP_WEB_KEY", "")

    @staticmethod
    def _number(value, integer=True):
        try:
            number = float(value)
            if not math.isfinite(number) or number < 0:
                return None
            return int(round(number)) if integer else number
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _has_data(value, depth=0):
        """Amap may return nonempty objects whose fields are all empty placeholders.

        Numeric zero is still data. Match the smoke diagnostics and conservatively
        treat deeply nested nonempty containers as data.
        """
        if depth > 4:
            return bool(value)
        if isinstance(value, dict):
            return any(AmapProvider._has_data(item, depth + 1) for item in value.values())
        if isinstance(value, list):
            return any(AmapProvider._has_data(item, depth + 1) for item in value)
        return value is not None and value != ""

    @staticmethod
    def _coordinate(point):
        lat, lng = to_wgs84(float(point["lat"]), float(point["lng"]), point.get("crs", "WGS84"))
        lat, lng = wgs84_to_gcj02(lat, lng)
        return f"{lng:.6f},{lat:.6f}"

    @staticmethod
    def _access(stop, access, kind="entrance"):
        stop = stop if isinstance(stop, dict) else {}
        access = access if isinstance(access, dict) else {}
        if not stop and not access:
            return None
        # 高德把出入口名（如「2号口」）放在 entrance/exit 里，没有单独的编号字段：
        # 编号与英文名从名称里按固定句式派生，派生不出来就留空（占位不编造）。
        name = clean_text(access.get("name"))
        access_no, access_name_en = parse_amap_access_name(name, kind)
        return {"station_id": stop.get("id") or None,
                "station_name_zh": clean_text(stop.get("name")),
                "station_name_en": english_place_name(stop.get("name"), stop.get("name_en")),
                "access_no": access_no, "access_name_zh": name,
                "access_name_en": access_name_en, "landmark_desc_zh": None,
                "landmark_desc_en": None, "source": "amap"}

    def _segment(self, raw, kind):
        duration = self._number(raw.get("duration"))
        if duration is None:
            raise ProviderError("partial_data", "高德路段缺少有效耗时",
                                diagnostic={"category": "walking_duration_missing" if kind == "walk" else "ride_duration_missing"})
        return {"kind": kind, "duration_seconds": duration,
                "distance_meters": self._number(raw.get("distance")),
                "line": None, "direction": None, "board": None, "alight": None,
                "stops": None, "transfer": None, "walk_note_en": None, "walk_note_zh": None}

    @staticmethod
    def _walk_notes(segment, instructions):
        """保留中文，英文按固定句式与本地地名资料翻译；未知片段原样保留。"""
        kept = [instruction for instruction in instructions if clean_text(instruction)]
        segment["walk_note_zh"] = "；".join(kept) or None
        segment["walk_note_en"] = translate_amap_instructions(kept)

    def _transit_segments(self, path):
        segments = []
        for item in path.get("segments") or []:
            walking = item.get("walking")
            if isinstance(walking, dict) and walking:
                segment = self._segment(walking, "walk")
                instructions = [step.get("instruction") for step in walking.get("steps", []) if isinstance(step, dict) and step.get("instruction")]
                self._walk_notes(segment, instructions)
                segments.append(segment)
            bus = item.get("bus") or {}
            lines = bus.get("buslines") or [] if isinstance(bus, dict) else []
            # buslines are alternatives for the same leg, not successive rides.
            if lines:
                line = lines[0]
                segment = self._segment(line, "ride")
                # 高德 id 是内部主键，不是给人看的线路号，故不写入契约。
                segment["board"] = self._access(line.get("departure_stop"), item.get("entrance"), "entrance")
                segment["alight"] = self._access(line.get("arrival_stop"), item.get("exit"), "exit")
                line_names, direction = normalize_amap_transit_line(
                    line.get("name"),
                    alight_name=(segment["alight"] or {}).get("station_name_zh"),
                    rail_reference=rail_line_reference())
                if line_names:
                    segment["line"] = line_names
                segment["direction"] = direction
                via = self._number(line.get("via_num"))
                segment["stops"] = via + 1 if via is not None else None
                segments.append(segment)
            if self._has_data(item.get("railway")) or self._has_data(item.get("taxi")):
                raise ProviderError("partial_data", "当前暂不支持此公交方案中的火车或出租车路段",
                                    diagnostic={"category": "unsupported_transit_segment"})
        if not segments:
            raise ProviderError("partial_data", "高德公交方案缺少路段",
                                diagnostic={"category": "transit_segments_missing"})
        return segments

    @staticmethod
    def _path_polyline(path, mode):
        chunks = []
        def add_steps(raw):
            if raw.get('polyline'):
                chunks.append(raw['polyline'])
                return True
            steps = raw.get('steps') or []
            if not steps or any(not isinstance(step, dict) or not step.get('polyline') for step in steps):
                return False
            chunks.extend(step['polyline'] for step in steps)
            return True
        if mode == 'transit':
            for item in path.get('segments') or []:
                walking = item.get('walking') or {}
                if walking and AmapProvider._number(walking.get('distance')) != 0 and not add_steps(walking):
                    return None
                lines = (item.get('bus') or {}).get('buslines') or []
                if lines:
                    if not lines[0].get('polyline'):
                        return None
                    chunks.append(lines[0]['polyline'])
        elif not add_steps(path):
            return None
        points = []
        try:
            for chunk in chunks:
                if not isinstance(chunk, str):
                    return None
                for item in chunk.split(';'):
                    pair = item.split(',')
                    if len(pair) != 2 or not all(value.strip() for value in pair):
                        return None
                    lng, lat = map(float, pair)
                    if not (math.isfinite(lat) and math.isfinite(lng) and -90 <= lat <= 90 and -180 <= lng <= 180):
                        return None
                    lat, lng = to_wgs84(lat, lng, 'GCJ-02')
                    point = f'{lng:.6f},{lat:.6f}'
                    if not points or points[-1] != point:
                        points.append(point)
                    if len(points) > 10000:
                        return None
        except (ValueError, TypeError):
            return None
        return ';'.join(points) if len(points) >= 2 else None

    def compute(self, from_point, to_point, mode, party_composition, options):
        self._require_key()
        endpoints = {"walk": "walking", "taxi": "driving", "transit": "transit/integrated"}
        if mode not in endpoints:
            raise ProviderError("no_route", "高德当前未接入此交通方式")
        options = options or {}
        params = {"key": self.api_key, "origin": self._coordinate(from_point),
                  "destination": self._coordinate(to_point), "output": "JSON"}
        if mode in ("transit", "taxi"):
            params["extensions"] = "all"
        if mode == "transit":
            city = options.get("city") or self.config.get("city")
            if not city:
                raise ProviderError("unsupported_city", "高德公交需要配置 city")
            params["city"] = city
            for key in ("cityd", "strategy", "date", "time", "nightflag"):
                value = options.get(key, self.config.get(key))
                if value is not None:
                    params[key] = value
        base = (self.config.get("base_url") or "https://restapi.amap.com").rstrip("/")
        if base.endswith("/v3"):
            base = base[:-3]
        url = base + "/v3/direction/" + endpoints[mode] + "?" + urllib.parse.urlencode(params)
        try:
            payload = self._request_json(url, timeout=float(self.config.get("timeout_seconds", 5)))
        except urllib.error.HTTPError as exc:
            raise ProviderError("rate_limited" if exc.code == 429 else "partial_data", "高德 HTTP 请求失败",
                                diagnostic={"category": "http_error", "http_status": exc.code}) from None
        except (TimeoutError, urllib.error.URLError) as exc:
            cause = exc.reason if isinstance(exc, urllib.error.URLError) else exc
            category = ("timeout" if isinstance(cause, TimeoutError) else
                        "certificate_error" if isinstance(cause, ssl.SSLCertVerificationError) else
                        "dns_error" if isinstance(cause, socket.gaierror) else "network_error")
            raise ProviderError("timeout" if category == "timeout" else "partial_data", "高德网络请求失败",
                                diagnostic={"category": category}) from None
        except ValueError:
            raise ProviderError("partial_data", "高德响应无法解析", diagnostic={"category": "invalid_json"}) from None
        except OSError as exc:
            category = ("certificate_error" if isinstance(exc, ssl.SSLCertVerificationError) else
                        "dns_error" if isinstance(exc, socket.gaierror) else "network_error")
            raise ProviderError("partial_data", "高德网络请求失败", diagnostic={"category": category}) from None
        if not isinstance(payload, dict):
            raise ProviderError("partial_data", "高德响应格式无效", diagnostic={"category": "invalid_response"})
        if str(payload.get("status")) != "1":
            code = str(payload.get("infocode", ""))
            reason = "rate_limited" if code in {"10003", "10004", "10014", "10019", "10020", "10021", "10029", "10044"} else "partial_data"
            raise ProviderError(reason, "高德服务未返回成功结果",
                                diagnostic={"category": "service_error", "provider_code": code})
        route = payload.get("route")
        if not isinstance(route, dict):
            raise ProviderError("no_route", "高德未返回路线", diagnostic={"category": "no_route"})
        paths = route.get("transits" if mode == "transit" else "paths")
        if not isinstance(paths, list) or not paths:
            raise ProviderError("no_route", "高德未找到可用路线", diagnostic={"category": "no_route"})
        path = paths[0]
        if not isinstance(path, dict):
            raise ProviderError("partial_data", "高德路线格式无效", diagnostic={"category": "invalid_response"})
        segments = self._transit_segments(path) if mode == "transit" else []
        duration = self._number(path.get("duration"))
        distance = self._number(path.get("distance"))
        if mode == "transit" and distance is None and all(s["distance_meters"] is not None for s in segments):
            distance = sum(s["distance_meters"] for s in segments)
        if duration is None or distance is None:
            raise ProviderError("partial_data", "高德路线缺少距离或耗时", diagnostic={"category": "missing_route_fields"})
        if mode == 'walk':
            segment = self._segment(path, 'walk')
            self._walk_notes(segment, [step.get('instruction') for step in (path.get('steps') or [])
                                       if isinstance(step, dict)])
            segments = [segment]
        walking = self._number(path.get("walking_distance")) if mode == "transit" else distance if mode == "walk" else None
        walking_duration = sum(s["duration_seconds"] for s in segments if s["kind"] == "walk") if mode == "transit" else duration if mode == "walk" else None
        cost = self._number(path.get("cost") if mode == "transit" else route.get("taxi_cost") if mode == "taxi" else None, integer=False)
        return {"mode": mode, "duration_seconds": duration, "distance_meters": distance,
                "cost": build_cost(cost, cost) if cost is not None else None,
                "congestion_level": "unknown",
                "transfer_count": max(0, sum(s["kind"] == "ride" for s in segments) - 1),
                "walking_distance_meters": walking, "walking_duration_seconds": walking_duration,
                "estimated_steps": estimate_steps(walking, party_composition),
                "segments": segments, "polyline": self._path_polyline(path, mode), "data_source": self.source}


class TencentProvider(HttpProvider):
    name = "tencent"
    source = "tencent"
    provider_crs = "GCJ-02"

    def __init__(self, config):
        super().__init__("tencent", "tencent", config)


class BaiduProvider(HttpProvider):
    name = "baidu"
    source = "baidu"
    provider_crs = "BD-09"

    def __init__(self, config):
        super().__init__("baidu", "baidu", config)


def build_provider(provider_name: str, config: dict, station_lib):
    provider_name = (provider_name or "mock").lower()
    if provider_name == "mock":
        return MockProvider(station_lib)
    if provider_name == "amap":
        return AmapProvider(config or {})
    if provider_name == "tencent":
        return TencentProvider(config or {})
    if provider_name == "baidu":
        return BaiduProvider(config or {})
    raise ValueError("未知的 provider：" + str(provider_name))
