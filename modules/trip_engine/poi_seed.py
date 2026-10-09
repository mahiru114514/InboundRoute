"""上海 POI 主数据：原25条示例 + 第二批20条来源可追溯地点。

第一批位于 data/shanghai_pois_v1.json，第二批位于 data/shanghai_pois_v2.json。
第二批字段级审核记录见
data/shanghai_poi_reviews_v2.json。下文可信度说明只描述原有示例；
第二批未核对的开放、预约、入口精度不填默认结论，停留时长仅为规划参考。

来源：`contracts/examples/poi_bund.json`（契约样例）+ 补充数据，用于演示：
    · 周一闭馆 + 需预约的博物馆（Rule-01 硬冲突、预约制）
    · 无亮灯的自然类 POI（Rule-02 不触发）
    · 四条兴趣线齐全：modern_skyline / history_culture / local_life / nature
字段与 `contracts/schemas/poi.schema.json` 一致，时间戳为 UTC 秒。

坐标系统（重要，别改错）：
    按 `contracts/mappings.json#/crs_conversion`，内部主数据一律 **WGS84**，
    高德/腾讯瓦片是 **GCJ-02**，转换由客户端在画点时单向完成（WGS84 → GCJ-02）。
    因此数据文件里的坐标**必须是真正的 WGS84**。

    历史坑：这批坐标最初是直接从高德底图上量的（即已经是 GCJ-02），
    却被打上了 `crs: "WGS84"` 的标签，于是前端又转了一次，图钉整体偏移约 530 m
    （4 个点全部同方向偏移，正是"重复转换"的特征）。已用 `wgs84_from_gcj02`
    反解修正，回代误差 < 0.01 m。**不要把从国内地图/导航软件直接抄来的坐标填进来**，
    那些是 GCJ-02，要先反解。诊断脚本：`tools/check_poi_crs.py`。

    扩充记录（sh_poi_00120 起）同样取自高德底图标注点，经
    `modules/route_adapter/crs.py` 的 `gcj02_to_wgs84` 反解后写入，回代漂移 < 2.2 m
    （远小于 `mappings.json` 的 precision_requirement_m = 50）。

数据可信度（不要为了"好看"改高）：
    · `closure_data_status` = verified 只用于**开放式 24 小时街区/免费公园**
      —— 它们没有围墙与检票口，不存在固定闭馆日，这一条是可以确认的；
      它**不代表**开放时间已核实（收费公园的开闭园时间仍会随季节调整）。
    · 收费景区、寺庙、观景台统一 `unverified` + `tags` 里的「开放时间待复核」，
      因为官方开闭园时间与闭馆日未经人工复核；Rule-01 会按契约给软提示而非静默放行。
    · 亮灯时段只覆盖外滩、豫园、新天地与四座观景地标，且为**简化季节窗口**
      （真实亮灯时间随日落浮动），Rule-02 仅作兜底提醒。

注意：`romanization.pinyin` 是**人工审核字段**，不要由 name 自动生成（多音字必错）。
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
SEED_FILES = ("shanghai_pois_v1.json", "shanghai_pois_v2.json")

# 保留原有 POIS 列表接口和顺序；只改变主数据存放位置。
POIS = []
for filename in SEED_FILES:
    POIS.extend(json.loads((DATA_DIR / filename).read_text(encoding="utf-8")))
