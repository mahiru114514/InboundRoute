"""行程工作台（web_workbench）—— 前端页面 + 到各引擎的代理。

负责人：开发者 A　需求文档：contracts/devdocs/开发者A-开发需求文档.md
职责：初始化看板 / POI 选点与详情 / 行程概览；**唯一可以代表用户调用其他模块的模块**。
契约依据：
    contracts/MODULE_RUNTIME.md          依赖发现与令牌传递
    contracts/generated/domain.ts        前端类型来源（本项目为纯 JS + JSDoc，不做构建）
    contracts/mappings.json              drawer_field_map / pacing_cap / weighting / interests_weight
实现文件：
    engine.py     静态资源服务 + /api/* 代理路由（浏览器不接触引擎令牌）
    map_config.py 地图配置与 CSP
    proxy.py      上游发现与调用（读 data/_registry/<id>.json）
    web/          按功能拆分的原生脚本；app.js 仅启动装配（零构建）

依赖 trip_engine（必需）、rules_engine / route_adapter / offline_kit（可选，未就绪时降级展示）。
"""
import sys
import threading
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from contracts.runtime import registry  # noqa: E402
from .engine import WEB_DIR, build_server
from .map_config import map_config  # noqa: E402
from .proxy import ServiceRegistry  # noqa: E402

ENDPOINTS = ["/health", "/api/session", "/api/services", "/api/pois", "/api/trips"]


def run(context):
    config = context.config or {}
    # 端口粘性：没有显式配置时复用上一次登记的端口，书签/深链在重启后依然有效
    port = registry.resolve_port(config, "web_workbench", WORKSPACE)
    token = registry.new_token()
    registry.check_no_live_instance(WORKSPACE, "web_workbench")

    services = ServiceRegistry(WORKSPACE)
    maps = map_config(config)
    server = build_server(services, token, port, maps=maps)
    actual_port = server.server_port
    registration = registry.build_registration(
        "web_workbench", actual_port, token,
        depends_on=["trip_engine"], endpoints=ENDPOINTS)

    try:
        registry.write(registration, WORKSPACE)
        context.log(f"行程工作台监听 {registration.base_url}")
        context.log(f"前端目录：{WEB_DIR}（零构建，由本模块直接伺服）")
        if maps["ready"]:
            if maps["provider"] == "amap":
                context.log(f"地图：高德 JS API v{maps['version']}；安全密钥"
                            f"{'已配置' if maps['security_code'] else '**未配置**（高德可能拒绝请求）'}")
            else:
                context.log(f"地图：Leaflet + 免费瓦片（无需 key）；瓦片 {maps['tile_url'][:60]}…")
        else:
            context.log(f"地图：未使用底图 —— {maps['hint']}")
        for module_id, note in (("trip_engine", "必需"), ("rules_engine", "可选"),
                                ("route_adapter", "可选"), ("offline_kit", "可选")):
            status = services.status_of(module_id)
            context.log(f"依赖 {module_id}（{note}）：{status['detail']}"
                        + (f" {status['base_url']}" if status["base_url"] else ""))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        while not context.wait(0.5):
            pass
    finally:
        server.shutdown()
        server.server_close()
        registry.remove(WORKSPACE, "web_workbench")
        context.log("行程工作台已停止")
