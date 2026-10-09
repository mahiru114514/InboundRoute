"""独立推荐服务入口，注册/清理由共享运行时负责。"""
import sys
import threading
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from contracts.runtime import registry
from .client import TripEngineClient
from .http_api import build_server
from .service import MODULE_ID, RecommendationService

ENDPOINTS = ['/health', '/recommendations:generate']


def run(context):
    config = context.config or {}
    registry.check_no_live_instance(WORKSPACE, MODULE_ID)
    port = registry.resolve_port(config, MODULE_ID, WORKSPACE)
    token = registry.new_token()
    context.log('等待 trip_engine 就绪（最长 30s，跟随注册表刷新）')
    upstream, health = registry.wait_for_registration(WORKSPACE, 'trip_engine', timeout=30.0)
    context.log(f'trip_engine 已就绪（{health.get("status")}）：{upstream.base_url}')
    client = TripEngineClient(upstream.base_url, upstream.token,
                              resolver=lambda: registry.try_read(WORKSPACE, 'trip_engine'))
    server = build_server(RecommendationService(client), token, port)
    registration = registry.build_registration(MODULE_ID, server.server_port, token,
                                                depends_on=['trip_engine'], endpoints=ENDPOINTS)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    registered = False
    started = False
    try:
        registry.write(registration, WORKSPACE)
        registered = True
        thread.start()
        started = True
        context.log(f'推荐行程服务监听 {registration.base_url}')
        while not context.wait(0.5):
            pass
    finally:
        if started:
            server.shutdown()
            thread.join(timeout=2)
        server.server_close()
        if registered:
            registry.remove(WORKSPACE, MODULE_ID)
        context.log('推荐服务已停止，端口与注册文件已释放')
