"""行程引擎（trip_engine）—— 已实现：行程数据的创建、读写、POI 查询与 HTTP 服务。

负责人：开发者 A　需求文档：contracts/devdocs/开发者A-开发需求文档.md
契约依据：
    contracts/MODULE_RUNTIME.md          模块怎么跑（端口 / 注册表 / 令牌 / 依赖等待）
    contracts/schemas/trip.schema.json   行程数据结构
    contracts/schemas/poi.schema.json    POI 数据结构
    contracts/schemas/api.schema.json    端点定义
    contracts/errors.json                错误信封与错误码
实现文件：
    engine.py     旧接口兼容导出
    service.py    行程生命周期与统一提交
    domain.py / validation.py / stops.py / catalog.py  领域定义、校验、停靠点与候选查询
    http_api.py   HTTP 请求适配与服务器生命周期
    store.py      行程单文件持久化（原子写）+ POI 主数据加载
    poi_seed.py   上海 POI 种子与补充数据加载
    anchors_seed.py 抵达 / 离境口岸与住宿候选（不再写死在前端）

本模块 dependencies 为空：它是最上游，只被调用，不调用别人。
"""
import sys
import threading
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from contracts.runtime import registry  # noqa: E402
from .service import TripService
from .http_api import build_server  # noqa: E402

ENDPOINTS = [
    "/health",
    "/trips",
    "/trips/{trip_id}",
    "/trips/{trip_id}/days/{day_index}/stops",
    "/trips/{trip_id}/days/{day_index}/stops/{poi_id}",
    "/pois",
    "/pois/{poi_id}",
    "/anchors",
    "/trips:validate",
    "/trips:preview",
    "/trips:recommended",
    "/trips/{trip_id}/recommendations:apply",
    "/trips/{trip_id}:duplicate",
    "/trips/{trip_id}/days/{day_index}/stops/{poi_id}/move",
]


def run(context):
    config = context.config or {}
    # 端口粘性：没有显式配置时复用上一次登记的端口，书签/深链在重启后依然有效
    port = registry.resolve_port(config, "trip_engine", WORKSPACE)
    token = registry.new_token()
    registry.check_no_live_instance(WORKSPACE, "trip_engine")

    service = TripService(context.data_dir, config.get("poi_path"))
    server = build_server(service, token, port)
    actual_port = server.server_port
    registration = registry.build_registration(
        "trip_engine", actual_port, token, depends_on=[], endpoints=ENDPOINTS)

    try:
        registry.write(registration, WORKSPACE)
        context.log(f"行程引擎监听 {registration.base_url}")
        context.log(f"POI 数据源：{service.store.poi_source}")
        context.log(f"注册文件：{WORKSPACE / 'data' / '_registry' / 'trip_engine.json'}")
        threading.Thread(target=server.serve_forever, daemon=True).start()
        while not context.wait(0.5):
            pass
    finally:
        server.shutdown()
        server.server_close()
        registry.remove(WORKSPACE, "trip_engine")
        context.log("行程引擎已停止，端口与注册文件已释放")
