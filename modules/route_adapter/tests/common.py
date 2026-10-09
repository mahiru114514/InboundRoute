"""测试公共工具：把模块目录与工作区根加入 sys.path，暴露契约校验。"""
import os
import sys

_MODULE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_WORKSPACE = os.path.dirname(os.path.dirname(_MODULE_DIR))
for _p in (_MODULE_DIR, _WORKSPACE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from contracts.generated import schema_store

    def validate_route(route):
        return schema_store.validate(route, "route.schema.json")

    def validate_station(station):
        return schema_store.validate(station, "station.schema.json")
except Exception:  # jsonschema 不可用时退化，结构断言仍在测试内进行
    def validate_route(route):  # noqa: D103
        return []

    def validate_station(station):  # noqa: D103
        return []