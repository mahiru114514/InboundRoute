"""规则引擎（rules_engine）—— 时序推演 + Rule-01~04 求值。

负责人：开发者 B　需求文档：contracts/devdocs/开发者B-开发需求文档.md
依赖：trip_engine（只读行程/POI，确认冲突时通过 HTTP 写回）。
"""
import sys
import threading
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))
MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from contracts.runtime import registry  # noqa: E402
from client import TripEngineClient  # noqa: E402
from engine import MODULE_ID, RulesService, build_server  # noqa: E402

ENDPOINTS = [
    "/health",
    "/trips/{trip_id}/rules:evaluate",
    "/trips/{trip_id}/rules:precheck",
    "/trips/{trip_id}/conflicts/{notice_id}/confirm",
]


def run(context):
    config = context.config or {}
    # 端口粘性：没有显式配置时复用上一次登记的端口，书签/深链在重启后依然有效
    port = registry.resolve_port(config, MODULE_ID, WORKSPACE)
    token = registry.new_token()
    registry.check_no_live_instance(WORKSPACE, MODULE_ID)

    # 等待上游时**每轮重读注册表**：
    #   · 上一轮遗留的注册文件可能指向已死端口，新实例会换端口登记；
    #   · 被依赖方比我们晚几百毫秒登记也是常态（launcher 分层并发启动）。
    # 固定 base_url 会让我们对着死端口白等 30s，见 logs/rules_engine.log 2026-09-29 22:52。
    context.log("等待上游 trip_engine 就绪（最长 30s，会跟随它重启后的新端口）")
    try:
        upstream, health = registry.wait_for_registration(WORKSPACE, "trip_engine", timeout=30.0)
    except registry.RegistryError as exc:
        context.log(f"启动失败：{exc}")
        raise
    context.log(f"上游 trip_engine 已就绪（status={health.get('status')}）：{upstream.base_url}")

    # resolver：trip_engine 重启后端口与令牌都会变，每个请求前重新解析一次注册表。
    client = TripEngineClient(upstream.base_url, upstream.token,
                              resolver=lambda: registry.try_read(WORKSPACE, "trip_engine"))
    service = RulesService(WORKSPACE, client=client)
    server = build_server(service, token, port)
    actual_port = server.server_port
    registration = registry.build_registration(
        MODULE_ID, actual_port, token, depends_on=["trip_engine"], endpoints=ENDPOINTS)

    try:
        registry.write(registration, WORKSPACE)
        context.log(f"规则引擎监听 {registration.base_url}")
        threading.Thread(target=server.serve_forever, daemon=True).start()
        while not context.wait(0.5):
            pass
    finally:
        server.shutdown()
        server.server_close()
        registry.remove(WORKSPACE, MODULE_ID)
        context.log("规则引擎已停止，端口与注册文件已释放")
