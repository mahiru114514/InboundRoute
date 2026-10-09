"""验证 R-1/R-2：生成模型（models.py）+ 运行时公共库（runtime/registry.py）的可用性。

用法：
    python scripts/check_runtime.py     # 全部通过时退出码 0

约定：本脚本用**真实示例数据**驱动，断言的是「开发者实际会怎么用」，
因此它同时充当两份产物的契约测试。改了 schema 后必须重跑。
"""
import json
import os
import pathlib
import shutil
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from contracts.generated.models import Poi, Route, Station, Trip
from contracts.generated.schema_store import is_valid, validate
from contracts.runtime import registry

FAILURES = []


def check(label, condition, detail=""):
    print(("PASS  " if condition else "FAIL  ") + label + (" :: " + str(detail) if detail else ""))
    if not condition:
        FAILURES.append(label)


def _has_jsonschema():
    try:
        import jsonschema  # noqa: F401
        return True
    except ImportError:
        return False


HAS_JSONSCHEMA = _has_jsonschema()
if not HAS_JSONSCHEMA:
    print("提示：未安装 jsonschema，跳过结构校验（pip install jsonschema）")


def check_schema(label, payload, schema_name):
    """结构校验。

    jsonschema 是可选依赖（generated/schema_store.py 有它才真正校验）。没装时应当像
    validate.py 一样「跳过并说明」，而不是让整个自检脚本崩在中间 —— 否则它后面的
    注册表 / 端口检查根本跑不到，读者会以为整个契约都坏了。
    """
    if not HAS_JSONSCHEMA:
        check(label + "（跳过：未安装 jsonschema）", True)
        return
    errors = validate(payload, schema_name)
    check(label, not errors, "; ".join(error.message for error in errors[:2]))


def payload_of(data):
    """剥离文档级元数据键（$schema_target、$comment 等）——与 validate.py 同一约定。"""
    return {key: value for key, value in data.items() if not key.startswith("$")}


def example(name):
    return payload_of(json.loads((ROOT / "contracts" / "examples" / name).read_text(encoding="utf-8")))


# ---------------------------------------------------------------- 模型往返
route_payload = example("route_transit_transfer.json")
route = Route.from_dict(route_payload)
check("Route.from_dict 保留 from/to（关键字字段）", route.from_.type == "poi" and route.to.type == "poi",
      f"{route.from_.type} -> {route.to.type}")
check("Route 数组字段已构造", len(route.variants) == 2 and len(route.segments) == 3,
      f"variants={len(route.variants)} segments={len(route.segments)}")
check("Route 嵌套换乘段已构造为对象", route.segments[1].transfer.walking_distance_meters == 280 and
      route.segments[1].transfer.source == "curated", type(route.segments[1].transfer).__name__)
check("Route 嵌套 array-of-object 已构造", route.segments[0].line.code == "2" and
      route.segments[0].board.access_name_zh == "2号口", type(route.segments[0].line).__name__)
check("Route 数字字段类型正确", isinstance(route.distance_meters, int), type(route.distance_meters).__name__)
dumped = route.to_dict()
check("to_dict 还原 JSON 字段名", "from" in dumped and "to" in dumped, list(dumped)[:6])
check("to_dict 未输出 None 选填字段", "last_mile_walk_meters" not in dumped or
      dumped["last_mile_walk_meters"] is not None)
check_schema("to_dict 结构可再校验", dumped, "route.schema.json")

poi = Poi.from_dict(example("poi_bund.json"))
check("Poi 的多语言字段已标识符化", poi.names.zh_Hans == "外滩" and poi.names.en == "The Bund",
      f"{poi.names.zh_Hans} / {poi.names.en}")
check("Poi.to_dict 还原 zh-Hans", poi.to_dict()["names"]["zh-Hans"] == "外滩")
check("Poi 嵌套 operating_rules 已构造", poi.operating_rules.closure_data_status == "verified",
      poi.operating_rules.closure_data_status)
check("Poi 数组元素为对象（含内联对象）", poi.drop_off_locations[0].source == "curated" and
      poi.drop_off_locations[0].point.crs == "WGS84", type(poi.drop_off_locations[0]).__name__)
check("Poi 亮灯窗口已构造", len(poi.operating_rules.light_up.windows) == 2,
      len(poi.operating_rules.light_up.windows))
check_schema("Poi 往返后仍合法", poi.to_dict(), "poi.schema.json")

trip_payload = example("trip_shanghai_2d.json")
trip = Trip.from_dict(trip_payload)
check("Trip 顶层标量", trip.timezone == "Asia/Shanghai" and trip.version == 7)
check("Trip 天数与停靠点", len(trip.days) == 2 and len(trip.days[1].ordered_stops) == 2, f"days={len(trip.days)}")
stop = trip.days[1].ordered_stops[1]
check("停靠点的区段已构造为对象", stop.transit_from_previous is not None and
      stop.transit_from_previous.distance_meters == 3200, type(stop.transit_from_previous).__name__)
check("notices 已构造", trip.days[1].ordered_stops[1].rule_notices[0].rule_id == "rule_01_closure")
check_schema("Trip 往返后仍合法", trip.to_dict(), "trip.schema.json")
check("未知字段被忽略（前向兼容）", Trip.from_dict({**trip_payload, "未来字段": 1}).trip_id == "trip_982341")

station = Station.from_dict(example("station_nanjing_east.json"))
check("Station 出入口与站内换乘", len(station.access_points) == 2 and len(station.interior_transfers) == 1,
      f"{len(station.access_points)}/{len(station.interior_transfers)}")

# ---------------------------------------------------------------- schema_store
check_schema("schema_store 可校验合法数据", route_payload, "route.schema.json")
bad_trip = example("invalid_trip_time_conflict.invalid.json")
if HAS_JSONSCHEMA:
    check("schema_store 能拦住非法数据", not is_valid(bad_trip, "trip.schema.json"))
else:
    check("schema_store 能拦住非法数据（跳过：未安装 jsonschema）", True)
check("schema_store 覆盖六个 schema", set(__import__("contracts.generated.schema_store",
      fromlist=["SCHEMAS"]).SCHEMAS) == {"poi.schema.json", "trip.schema.json", "route.schema.json",
      "station.schema.json", "api.schema.json", "recommendation.schema.json"})

# ---------------------------------------------------------------- 注册表
# 探针目录放进系统临时目录，而不是项目根：自检脚本不该往交付目录里写东西
# （既污染工程，也会在只读/受限环境下直接把脚本卡死）。
temp = pathlib.Path(tempfile.mkdtemp(prefix="inboundroute-registry-"))
try:
    (temp / "data" / "_registry").mkdir(parents=True, exist_ok=True)
    token = registry.new_token()
    check("令牌是 urlsafe 且足够长", len(token) >= 32 and " " not in token, token[:12] + "…")
    check("端口缺省为自动分配", registry.resolve_port(None) == 0 and registry.resolve_port({"port": "0"}) == 0)
    check("非法端口回落到自动分配", registry.resolve_port({"port": "abc"}) == 0)

    check("未运行模块的注册文件不存在", registry.try_read(temp, "trip_engine") is None)
    try:
        registry.read(temp, "trip_engine")
        check("read 缺失注册文件应报错", False, "未抛错")
    except registry.RegistryError as exc:
        check("read 缺失注册文件应报错", "未找到" in str(exc), str(exc)[:40])

    registration = registry.build_registration("trip_engine", 51234, token, endpoints=["/health", "/trips"])
    path = registry.write(registration, temp)
    check("注册文件写入路径正确", path == temp / "data" / "_registry" / "trip_engine.json", str(path))
    raw = json.loads(path.read_text(encoding="utf-8"))
    check("注册文件字段完整（C7 §2）",
          set(raw) == {"module_id", "port", "base_url", "token", "pid", "contract_version",
                       "started_at", "depends_on", "endpoints"}, sorted(raw))
    check("base_url 由 host+port 组装", raw["base_url"] == "http://127.0.0.1:51234")
    check("contract_version 取常量", raw["contract_version"] == registry.CONTRACT_VERSION)

    loaded = registry.read(temp, "trip_engine")
    check("往返一致", loaded.token == token and loaded.port == 51234)
    check("health_url 正确", loaded.health_url == "http://127.0.0.1:51234/health")

    registry.check_no_live_instance(temp, "trip_engine")
    check("残留注册文件（进程已死）不阻止启动", True)

    try:
        registry.discover(temp, ["trip_engine", "route_adapter"])
        check("discover 缺依赖应报错", False, "未抛错")
    except registry.RegistryError as exc:
        check("discover 缺依赖应报错", "route_adapter" in str(exc), str(exc)[:60])
    check("discover 返回可用实例", registry.discover(temp, ["trip_engine"])["trip_engine"].port == 51234)

    # 真起一个 HTTP 服务，验证 socket 绑定 + /health 探测 + 双实例保护
    import http.server
    import threading

    class Health(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps({"module_id": "probe", "status": "ok", "ready": True}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server_socket = registry.bind_socket(port=0)
    port = server_socket.getsockname()[1]
    check("bind_socket 返回真实端口", 0 < port < 65536, port)
    httpd = http.server.HTTPServer(("127.0.0.1", port), Health, bind_and_activate=False)
    httpd.socket = server_socket
    httpd.server_address = ("127.0.0.1", port)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    probe = registry.probe_health(f"http://127.0.0.1:{port}")
    check("probe_health 能读到 /health", probe is not None and probe["status"] == "ok", probe)
    registry.write(registry.build_registration("probe", port, token), temp)
    try:
        registry.check_no_live_instance(temp, "probe")
        check("存活实例应阻止双实例", False, "未抛错")
    except registry.RegistryError as exc:
        check("存活实例应阻止双实例", "另一个运行实例" in str(exc), str(exc)[:50])
    try:
        registry.wait_for_dependency(registry.build_registration("probe", port, token), timeout=2)
        check("wait_for_dependency 就绪即返回", True)
    except registry.RegistryError as exc:
        check("wait_for_dependency 就绪即返回", False, str(exc)[:60])
    try:
        registry.wait_for_dependency(registry.build_registration("ghost", 1, token), timeout=1)
        check("依赖超时应抛错（不静默）", False, "未抛错")
    except registry.RegistryError as exc:
        check("依赖超时应抛错（不静默）", "未就绪" in str(exc), str(exc)[:40])

    # wait_for_registration：等待期间必须重读注册文件（模块重启会换端口）
    registry.write(registry.build_registration("probe", 9, token), temp)   # 9 端口连不上
    settled: dict = {}

    def rewrite_registration():
        import time
        time.sleep(0.4)
        registry.write(registry.build_registration("probe", port, token), temp)

    threading.Thread(target=rewrite_registration, daemon=True).start()
    try:
        registration, health = registry.wait_for_registration(temp, "probe", timeout=5)
        settled = {"port": registration.port, "status": health.get("status")}
    except registry.RegistryError as exc:
        settled = {"error": str(exc)[:60]}
    check("wait_for_registration 跟随重新注册的新端口",
          settled.get("port") == port and settled.get("status") == "ok", settled)

    try:
        registry.wait_for_registration(temp, "never_registered", timeout=1,
                                       initial_interval=0.05, max_interval=0.1)
        check("wait_for_registration 超时应抛错", False, "未抛错")
    except registry.RegistryError as exc:
        check("wait_for_registration 超时应抛错",
              "never_registered" in str(exc) and "管理页面" in str(exc), str(exc)[:60])

    httpd.shutdown()
    httpd.server_close()

    registry.remove(temp, "trip_engine")
    check("remove 删除注册文件", not (temp / "data" / "_registry" / "trip_engine.json").exists())
    registry.remove(temp, "trip_engine")
    check("重复 remove 不报错", True)
finally:
    shutil.rmtree(temp, ignore_errors=True)

print("\n" + ("全部通过" if not FAILURES else f"失败 {len(FAILURES)} 项：{FAILURES}"))
sys.exit(1 if FAILURES else 0)
