"""离线与问路卡（offline_kit）—— 开发者 C 交付。

宿主是「模块工作台」：本模块是独立进程，通过本地 HTTP 提供服务。
契约：contracts/MODULE_RUNTIME.md、contracts/mappings.json#/offline_package、
      contracts/mappings.json#/ask_card_templates。
"""
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from .service import OfflineKitService  # noqa: E402


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
    service = OfflineKitService(config, context.data_dir, WORKSPACE, _ContextLogger(context))
    try:
        service.start()
    except Exception as exc:  # noqa: BLE001
        context.log(f"offline_kit 启动失败：{exc}")
        return
    try:
        while not context.wait(1):
            pass
    finally:
        service.stop()