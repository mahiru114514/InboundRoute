"""在独立进程中运行插件。进程隔离用于生命周期管理，不是安全沙箱。"""
import importlib.util
import json
import logging
import os
import sys
import time
import traceback
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path


@dataclass
class Context:
    config: dict
    data_dir: Path
    _stop_event: object
    _logger: object

    def log(self, message):
        self._logger.info(str(message))

    def should_stop(self):
        return self._stop_event.is_set()

    def wait(self, seconds):
        """等待秒数；收到停止请求时立即返回 True。"""
        return self._stop_event.wait(seconds)


class LogStream:
    def __init__(self, logger):
        self.logger = logger

    def write(self, text):
        if text.strip():
            self.logger.info(text.rstrip())
        return len(text)

    def flush(self):
        pass


def _marker_path(data: Path, module_id: str) -> Path:
    return data.parent / "_registry" / f"{module_id}.run"


def _write_run_marker(data: Path, module_id: str) -> None:
    """写下「这个模块正在运行」的标记（带 pid）。

    服务型模块会写注册文件（含端口），宿主据此知道它在跑；但**非服务型**模块
    （heartbeat / greeting / test_demo）什么也不写，宿主就无从判断它是否已经在运行，
    于是重复执行 `--all` 会把 heartbeat 起成两份，而且没有任何地方能停掉多余的那份。
    标记里带 pid：宿主用 pid 存活来判定，崩溃残留下来的标记不会被误判成「在运行」。
    """
    try:
        path = _marker_path(data, module_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"module_id": module_id, "pid": os.getpid(),
                                    "started_at": int(time.time())}), encoding="utf-8")
    except OSError:
        pass    # 标记只是宿主判活用的优化，写不下不能影响模块本身


def _clear_run_marker(data: Path, module_id: str) -> None:
    try:
        _marker_path(data, module_id).unlink()
    except OSError:
        pass


def run_worker(module_dir, config, data_dir, log_path, event):
    logger = logging.getLogger("plugin")
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(log_path, maxBytes=1024 * 1024, backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%Y-%m-%d %H:%M:%S"))
    logger.addHandler(handler)
    sys.stdout = sys.stderr = LogStream(logger)
    folder = Path(module_dir)
    data = Path(data_dir)
    try:
        data.mkdir(parents=True, exist_ok=True)
        _write_run_marker(data, folder.name)
        # plugin.py 同时作为包入口，允许 from .helper import ...。
        spec = importlib.util.spec_from_file_location("user_plugin", folder / "plugin.py", submodule_search_locations=[str(folder)])
        plugin = importlib.util.module_from_spec(spec)
        sys.modules["user_plugin"] = plugin
        spec.loader.exec_module(plugin)
        if not callable(getattr(plugin, "run", None)):
            raise ValueError("plugin.py 必须导出 run(context) 函数")
        logger.info("模块开始运行")
        plugin.run(Context(config, data, event, logger))
        logger.info("模块运行结束")
    except KeyboardInterrupt:
        # Windows 上模块子进程与启动器共用控制台，Ctrl+C 会直接打断主循环。
        # 这是正常的停止路径，不该在日志里留 traceback（否则日志会被噪音淹没）。
        logger.info("模块被中断（Ctrl+C），按正常停止处理")
    except BaseException:
        logger.error(traceback.format_exc())
        raise
    finally:
        _clear_run_marker(data, folder.name)
        handler.close()
