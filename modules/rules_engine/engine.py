"""rules_engine 的业务实现与 HTTP 服务。

端点：GET /health、POST /trips/{id}/rules:evaluate、POST /trips/{id}/rules:precheck、
      POST /trips/{id}/conflicts/{notice_id}/confirm
鉴权：除 /health 外必须带 X-Module-Token（见 contracts/MODULE_RUNTIME.md §4）。
行程数据唯一持久化方是 trip_engine，本模块只读上游并通过 HTTP 写回（confirm）。
"""
from __future__ import annotations

import json
import secrets
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    from .client import TripEngineClient, UpstreamError
    from .rules import (
        RULE_IDS, SEVERITY_ORDER,
        evaluate_day, build_timeline, load_contracts, parse_notice_id, rule_01_closure, split_render,
    )
except ImportError:  # pragma: no cover
    from client import TripEngineClient, UpstreamError  # type: ignore
    from rules import (  # type: ignore
        RULE_IDS, SEVERITY_ORDER,
        evaluate_day, build_timeline, load_contracts, parse_notice_id, rule_01_closure, split_render,
    )

CONTRACT_VERSION = "0.3.3"
MODULE_ID = "rules_engine"
MAX_BODY = 64 * 1024
DEFAULT_TRIGGER = "load_trip"
TRIGGER_EVENTS = {
    "add_stop", "remove_stop", "reorder", "move_to_evening",
    "change_day", "change_anchor", "change_config", "load_trip",
}


class ServiceError(Exception):
    def __init__(self, status: int, code: str, message: str, details=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details or {}


def _require(condition, message):
    if not condition:
        raise ServiceError(400, "BAD_REQUEST", message)


def _now() -> int:
    return int(time.time())


class RulesService:
    def __init__(self, workspace, client: TripEngineClient | None = None,
                 rules: dict | None = None, mappings: dict | None = None, wall_clock=None):
        self.workspace = workspace
        self.client = client
        if rules is None or mappings is None:
            rules, mappings = load_contracts(workspace)
        self.rules = rules
        self.mappings = mappings
        self._wall_clock = wall_clock or _now
        self.contract_version = CONTRACT_VERSION
        self.started_at = self._wall_clock()

    # ------------------------------------------------------------ 上游与健康

    def upstream_health(self) -> dict | None:
        if self.client is None:
            return None
        return self.client.health()

    def health(self) -> dict:
        healthy = self.upstream_health()
        status = "ok" if healthy else "degraded"
        return {
            "module_id": MODULE_ID,
            "status": status,
            "contract_version": self.contract_version,
            "ready": True,
            "started_at": self.started_at,
            "degraded": status != "ok",
            "degraded_reason": "none" if healthy else "upstream_down",
        }

    def _require_client(self) -> TripEngineClient:
        if self.client is None or self.upstream_health() is None:
            raise ServiceError(503, "UPSTREAM_TIMEOUT",
                               "上游 trip_engine 不可达，请先在管理页面运行它", {"retryable": True})
        return self.client

    # ------------------------------------------------------------ POI 读取

    def _poi_lookup(self, trip: dict) -> dict[str, dict | None]:
        client = self._require_client()
        poi_ids: set[str] = set()
        for day in trip.get("days", []):
            for stop in day.get("ordered_stops", []):
                poi_id = stop.get("poi_id")
                if poi_id and stop.get("stop_type", "poi") == "poi":
                    poi_ids.add(poi_id)
        lookup: dict[str, dict | None] = {}
        for poi_id in poi_ids:
            try:
                lookup[poi_id] = client.get_poi(poi_id)
            except UpstreamError:
                lookup[poi_id] = None
        return lookup

    def _days_for(self, trip: dict, day_index) -> list[dict]:
        if day_index is None:
            return list(trip.get("days", []))
        try:
            index = int(day_index)
        except (TypeError, ValueError):
            raise ServiceError(400, "BAD_REQUEST", "day_index 必须是整数")
        for day in trip.get("days", []):
            if day.get("day_index") == index:
                return [day]
        raise ServiceError(404, "BAD_REQUEST", f"Day {index} 不存在")

    # ------------------------------------------------------------ 求值

    def evaluate(self, trip_id: str, day_index=None, trigger: str = DEFAULT_TRIGGER, persist=False) -> dict:
        _require(trigger in TRIGGER_EVENTS, f"trigger 必须是 {sorted(TRIGGER_EVENTS)} 之一")
        return self._evaluate_trip(self._require_client().get_trip(trip_id), day_index, persist)

    def _evaluate_trip(self, trip: dict, day_index, persist: bool) -> dict:
        """对一份**已经取到的**行程求值。

        这样拆分是为了预检：预检在内存副本里插入候选点后调用本方法，
        既不复用不到的网络往返，也保证不可能误落盘。
        """
        client = self._require_client()
        poi_lookup = self._poi_lookup(trip)

        notices: list[dict] = []
        skips: list[dict] = []
        timelines = []
        patches = []
        now = self._wall_clock()
        for day in self._days_for(trip, day_index):
            result = evaluate_day(trip, day, poi_lookup, self.rules, self.mappings, now)
            times = build_timeline(trip, day)
            complete = True
            stop_patches = []
            for stop, timing in zip(day["ordered_stops"], times):
                route = stop.get("transit_from_previous") or {}
                complete = complete and route.get("duration_seconds") is not None
                if not complete:
                    timing = {"arrival_at": None, "departure_at": None}
                own = []
                for notice in result["notices"]:
                    args = notice.get("message_args", {})
                    notice_id = args.get("notice_id", "")
                    if not notice_id.endswith(":" + str(stop.get("poi_id"))):
                        continue
                    old = next((n for n in stop.get("rule_notices", [])
                                if n.get("message_args") == args and n.get("outcome") == "confirmed_proceed"), None)
                    if old:
                        notice.update(outcome=old["outcome"], confirmed_at=old.get("confirmed_at"))
                    own.append(notice)
                stop_patches.append({"stop_order": stop["stop_order"], "arrival_at": timing["arrival_at"],
                                     "departure_at": timing["departure_at"], "rule_notices": own})
            if not complete:
                # 不能以省略交通时间的估算触发亮灯建议。
                result["notices"] = [n for n in result["notices"] if n["rule_id"] != "rule_02_lightup"]
                skips.append({"rule_id": "rule_02_lightup", "reason": "missing_route_duration"})
                for patch in stop_patches:
                    patch["rule_notices"] = [n for n in patch["rule_notices"] if n["rule_id"] != "rule_02_lightup"]
            timelines.append({"day_index": day["day_index"], "complete": complete, "stops": stop_patches})
            if stop_patches:
                patches.append({"day_index": day["day_index"], "ordered_stops": stop_patches})
            notices.extend(result["notices"])
            skips.extend(result["skipped_rules"])

        notices.sort(key=lambda notice: SEVERITY_ORDER.get(notice["severity"], 9))
        rendered, overflow_items = split_render(notices)
        overflow = len(overflow_items)
        seen: set[tuple[str, str]] = set()
        deduped: list[dict] = []
        for item in skips:
            key = (item["rule_id"], item["reason"])
            if key not in seen:
                seen.add(key)
                deduped.append(item)
        # 相同结果不写回，刷新页面不应让版本递增、离线包立即过期。
        changed = any(any(any(stop.get(key) != patch[key] for key in ("arrival_at", "departure_at"))
                              or self._notice_signature(stop.get("rule_notices", [])) != self._notice_signature(patch["rule_notices"])
                              for stop, patch in zip(next(d for d in trip["days"] if d["day_index"] == day_patch["day_index"])["ordered_stops"], day_patch["ordered_stops"]))
                      for day_patch in patches)
        if persist and patches and changed:
            # 拆分出 _evaluate_trip 后 trip_id 不在作用域里了：行程对象自带 trip_id。
            trip = client.patch_trip(trip["trip_id"], {"days": patches}, expected_version=trip.get("version"))
        return {"notices": rendered, "overflow": overflow,
                # 被 channel 承载位裁掉的建议一并回传：前端才能「展开全部」，
                # 而不是只留一句「还有 N 条建议」把信息丢掉。
                "overflow_notices": overflow_items,
                "timeline": timelines, "trip": trip,
                "evaluated_rules": list(RULE_IDS), "skipped_rules": deduped}

    def precheck(self, trip_id: str, payload: dict) -> dict:
        """加入景点**之前**的预检：在内存副本里插入候选点求值一次，绝不落盘。

        原来硬冲突要等「景点已经加进行程」之后才提示，用户只能事后二选一
        （仍然保留 / 移除此景点）。预检让他在点「加入行程」之前就看到结论。
        """
        _require(isinstance(payload, dict), "请求体必须是 JSON 对象")
        day_index = payload.get("day_index")
        poi_id = payload.get("poi_id")
        _require(day_index is not None, "day_index 必填")
        _require(isinstance(poi_id, str) and poi_id.strip(), "poi_id 必填")

        client = self._require_client()
        trip = client.get_trip(trip_id)
        day = next((item for item in trip.get("days", [])
                    if str(item.get("day_index")) == str(day_index)), None)
        if day is None:
            # 与 _days_for 保持一致：Day 不存在是「找不到」，用 404 而不是 400。
            raise ServiceError(404, "BAD_REQUEST", f"Day {day_index} 不存在")
        _require(not any(stop.get("poi_id") == poi_id for stop in day.get("ordered_stops", [])),
                 f"{poi_id} 已经在 Day {day_index} 里")
        poi = client.get_poi(poi_id)

        # 候选停靠点与 trip_engine.add_stop 同口径，保证预检结论和真正加入后的结论一致。
        day["ordered_stops"] = list(day.get("ordered_stops", [])) + [{
            "stop_order": len(day.get("ordered_stops", [])) + 1,
            "stop_type": "poi",
            "poi_id": poi_id,
            "locked": False,
            "arrival_at": None,
            "departure_at": None,
            "user_preferred_arrival_local": None,
            "planned_dwell_minutes": self._dwell_minutes(poi),
            "transit_from_previous": None,
            "rule_notices": [],
        }]
        result = self._evaluate_trip(trip, day["day_index"], persist=False)
        hard = [notice for notice in result["notices"] if notice.get("severity") == "hard"]
        return {
            "poi_id": poi_id,
            "day_index": day["day_index"],
            "poi_name": (poi.get("names") or {}).get("zh-Hans"),
            "would_block": bool(hard),
            "hard_conflicts": hard,
            "notices": result["notices"],
            "timeline": result["timeline"],
            "skipped_rules": result["skipped_rules"],
        }

    @staticmethod
    def _dwell_minutes(poi: dict) -> int:
        """与 trip_engine.dwell_minutes_of 同口径：区间取下界，缺失按 90 分钟。"""
        dwell = (poi.get("operating_rules") or {}).get("dwell_time") or {}
        if dwell.get("kind") == "range":
            return int(dwell.get("minutes_min") or 90)
        return int(dwell.get("minutes") or 90)

    @staticmethod
    def _notice_signature(notices):
        return [{k: v for k, v in n.items() if k != "raised_at"} for n in notices]

    # ------------------------------------------------------------ 冲突确认

    def confirm(self, trip_id: str, notice_id: str, decision: str) -> dict:
        _require(decision in ("proceed_anyway", "reject"),
                 "decision 必须是 proceed_anyway 或 reject")
        client = self._require_client()
        trip = client.get_trip(trip_id)
        try:
            rule_id, day_index, poi_id = parse_notice_id(notice_id)
        except ValueError as exc:
            raise ServiceError(400, "BAD_REQUEST", str(exc)) from exc

        day = next((item for item in trip.get("days", []) if item.get("day_index") == day_index), None)
        _require(day is not None, f"Day {day_index} 不存在")
        stop = next((item for item in day.get("ordered_stops", [])
                     if item.get("poi_id") == poi_id), None)
        _require(stop is not None, f"这一天没有 {poi_id}")

        poi = client.get_poi(poi_id)
        now = self._wall_clock()
        # 以 Rule-01 的纯函数重算，拿到 message_key / args / severity / channel。
        pending_notices, _ = rule_01_closure(day, poi, now)
        notice = next((item for item in pending_notices
                       if item.get("rule_id") == rule_id and item.get("severity") == "hard"), None)
        _require(notice is not None, "该 notice 不是可确认的硬冲突")

        desired_outcome = "confirmed_proceed" if decision == "proceed_anyway" else "rejected"
        existing = next((item for item in stop.get("rule_notices", [])
                         if item.get("rule_id") == rule_id
                         and item.get("outcome") == desired_outcome), None)
        if existing is not None:
            return {"trip": trip, "notice": existing}

        if decision == "proceed_anyway":
            notice["outcome"] = "confirmed_proceed"
        else:
            notice["outcome"] = "rejected"
        notice["confirmed_at"] = now

        payload = {"days": [{"day_index": day_index, "ordered_stops": [
            {"stop_order": stop.get("stop_order"), "rule_notices": [notice]}]}]}
        updated = client.patch_trip(trip_id, payload, expected_version=trip.get("version"))
        return {"trip": updated, "notice": notice}


# ---------------------------------------------------------------- HTTP 层

def build_handler(service: RulesService, token: str):
    class Handler(BaseHTTPRequestHandler):
        server_version = "rules_engine/0.1"
        protocol_version = "HTTP/1.1"

        def setup(self):
            super().setup()
            self.connection.settimeout(20)

        def log_message(self, *_):
            pass

        def reply(self, status, payload):
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def ok(self, data, status=200):
            self.reply(status, {"ok": True, "data": data,
                                "meta": {"contract_version": service.contract_version,
                                         "server_time": _now()}})

        def fail(self, status, code, message, details=None):
            self.reply(status, {"ok": False, "error": {"code": code, "message": message,
                                                       "details": details or {},
                                                       "retryable": status >= 500}})

        def _host_allowed(self) -> bool:
            allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            return self.headers.get("Host") in allowed

        def _authorized(self) -> bool:
            return self._host_allowed() and secrets.compare_digest(
                self.headers.get("X-Module-Token", ""), token)

        def _body(self) -> dict:
            length = int(self.headers.get("Content-Length", "0") or 0)
            if length > MAX_BODY:
                raise ServiceError(413, "BAD_REQUEST", f"请求体超过 {MAX_BODY} 字节")
            raw = self.rfile.read(length) if length else b""
            if not raw:
                return {}
            try:
                return json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ServiceError(400, "BAD_REQUEST", f"请求体必须是 JSON：{exc}") from exc

        def _dispatch(self, method):
            path = urllib.parse.urlsplit(self.path).path
            if path == "/health":
                return self.ok(service.health())
            if not self._authorized():
                return self.fail(403, "FORBIDDEN", "缺少或错误的 X-Module-Token")
            parts = [segment for segment in path.strip("/").split("/") if segment]
            try:
                return self._route(method, parts)
            except ServiceError as exc:
                return self.fail(exc.status, exc.code, exc.message, exc.details)
            except UpstreamError as exc:
                return self.fail(exc.status, exc.code, exc.message, {"upstream": "trip_engine"})
            except (ValueError, OSError, RuntimeError) as exc:
                return self.fail(500, "INTERNAL", str(exc))

        def _route(self, method, parts):
            if method == "POST" and len(parts) == 3 and parts[0] == "trips" and parts[2] == "rules:evaluate":
                body = self._body()
                return self.ok(service.evaluate(parts[1], body.get("day_index"),
                                                body.get("trigger", DEFAULT_TRIGGER), body.get("persist", False)))
            if method == "POST" and len(parts) == 3 and parts[0] == "trips" and parts[2] == "rules:precheck":
                # 加入景点之前的预检：只算不写。
                return self.ok(service.precheck(parts[1], self._body()))
            if (method == "POST" and len(parts) == 5 and parts[0] == "trips"
                    and parts[2] == "conflicts" and parts[4] == "confirm"):
                body = self._body()
                return self.ok(service.confirm(parts[1], urllib.parse.unquote(parts[3]), body.get("decision")))
            raise ServiceError(404, "BAD_REQUEST", f"操作不存在：{method} /{'/'.join(parts)}")

        def do_GET(self):
            self._dispatch("GET")

        def do_POST(self):
            self._dispatch("POST")

    return Handler


def build_server(service: RulesService, token: str, port: int = 0, host: str = "127.0.0.1") -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), build_handler(service, token))
    server.daemon_threads = True
    return server
