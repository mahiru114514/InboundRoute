"""契约运行时公共库。

业务模块这样使用（在 plugin.py 里把 workspace 根加入 sys.path 之后）：

    from contracts.runtime import registry

    root = registry.workspace_root_from_module_dir(context.data_dir.parent.parent)  # 或自行传入 workspace 根
    registration = registry.read(root, "trip_engine")
    data = registry.call_json(registration, "GET", "/trips/trip_982341")

约定：本包只依赖标准库；不 import contracts/generated/（避免循环依赖）。
"""

from . import registry  # noqa: F401

__all__ = ["registry"]
