"""路线适配器（route_adapter）—— 开发者 C 交付。

宿主是「模块工作台」：本模块是独立进程，通过本地 HTTP 提供服务。
契约：contracts/MODULE_RUNTIME.md、contracts/schemas/route.schema.json、
      contracts/schemas/station.schema.json、contracts/mappings.json、contracts/errors.json。
"""
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent.parent
MODULE_DIR = Path(__file__).resolve().parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from .service import RouteAdapterService  # noqa: E402


class _ContextLogger:
    def __init__(self, context):
        self._context = context

    def info(self, message):
        try:
            self._context.log(str(message))
        except Exception:  # noqa: BLE001
            pass


def run(context):
    config = context.config or {}
    service = RouteAdapterService(config, context.data_dir, WORKSPACE, _ContextLogger(context), MODULE_DIR)
    try:
        service.start()
    except Exception as exc:  # noqa: BLE001
        context.log(f"route_adapter 启动失败：{exc}")
        return
    try:
        while not context.wait(1):
            pass
    finally:
        service.stop()