"""抵达 / 离境口岸与住宿候选清单（trip_engine 主数据）。

为什么放在后端而不是前端：
    这两份清单原来是写死在 ``web_workbench/web/app.js`` 里的（各 6 条），
    于是「加一个口岸」必须改前端代码，而且浏览器缓存旧 JS 时会继续用旧清单。
    现在由 ``GET /anchors`` 统一供给，前端只负责渲染与检索。

数据放在同目录的 ``data/anchors.json``，而不是写在 Python 里：
    这样前端接线回归测试（``tests/workbench_wiring.test.js``）可以直接读同一份文件当桩数据，
    不需要在测试里再维护一份「和真实数据差不多」的副本 —— 那种副本迟早会跟真实数据脱节。

坐标约定（与 poi_seed.py 同一条注意事项）：
    一律 **WGS84**。从国内地图直接抄来的坐标是 GCJ-02，填错会让锚点整体偏移几百米；
    ``coordinate_source`` 如实标注来源：
      · curated      —— 人工整理并核对过，暂未在真实底图上实测
      · approximate  —— 近似值。页面会提示「近似值，建议点选校正」，
                        并允许用「在地图上点选住宿位置」覆盖。
    新增条目一律先标 approximate，避免把没核过的坐标说成可信值。
"""
import json
from pathlib import Path

ANCHORS_PATH = Path(__file__).resolve().parent / "data" / "anchors.json"

# 清单一期只有几十条，读一次即可；按 mtime 失效，改 JSON 后不用重启模块也能生效。
_cache: tuple[float, dict] | None = None


def load_anchors() -> dict:
    """读取口岸 / 住宿候选；返回深拷贝，避免调用方改到缓存。"""
    global _cache
    try:
        stamp = ANCHORS_PATH.stat().st_mtime
    except OSError as exc:
        raise RuntimeError(f"锚点清单不可读：{ANCHORS_PATH}（{exc}）") from exc
    if _cache is None or _cache[0] != stamp:
        raw = json.loads(ANCHORS_PATH.read_text(encoding="utf-8"))
        hubs = raw.get("hubs")
        hotels = raw.get("hotels")
        if not isinstance(hubs, list) or not isinstance(hotels, list):
            raise RuntimeError(f"锚点清单格式无效：{ANCHORS_PATH} 需要 hubs / hotels 两个数组")
        _cache = (stamp, {"hubs": hubs, "hotels": hotels})
    return {"hubs": [dict(item) for item in _cache[1]["hubs"]],
            "hotels": [dict(item) for item in _cache[1]["hotels"]]}
