"""景点、口岸与住宿候选查询。"""
from __future__ import annotations

from .anchors_seed import load_anchors


class CatalogueQueries:
    """只读候选查询；宿主提供 POI store。"""

    def list_pois(self, query: dict) -> dict:
        source = self.store.poi_source
        records = self.store.list_pois(
            interest=(query.get("interest") or [None])[0],
            category_level1=(query.get("category_level1") or [None])[0],
        )
        keyword = (query.get("keyword") or [""])[0].strip().lower()
        if keyword:
            def haystack(poi):
                names = poi["names"]
                roman = poi.get("romanization") or {}
                return " ".join([names.get("zh-Hans", ""), names.get("en", ""), roman.get("pinyin", ""),
                                 roman.get("pinyin_plain", ""), *poi.get("search_aliases", [])]).lower()
            records = [item for item in records if keyword in haystack(item)]
        return {"pois": records, "total": len(records), "source": source}

    def get_poi(self, poi_id: str) -> dict:
        return self.store.poi(poi_id)

    def list_anchors(self, query: dict) -> dict:
        """抵达 / 离境口岸与住宿候选。

        口径与 ``list_pois`` 一致：``keyword`` 同时匹配中文名 / 英文名 / 拼音
        （含去空格连写）/ 别名，便于前端做「中文、英文、拼音都能搜」的联想。
        """
        catalogue = load_anchors()
        keyword = (query.get("keyword") or [""])[0].strip().lower()

        def matches(anchor: dict) -> bool:
            if not keyword:
                return True
            pinyin = anchor.get("name_pinyin", "")
            haystack = " ".join([anchor.get("name_zh", ""), anchor.get("name_en", ""),
                                 pinyin, pinyin.replace(" ", ""),
                                 *(anchor.get("aliases") or [])]).lower()
            return keyword in haystack

        return {
            "hubs": [item for item in catalogue["hubs"] if matches(item)],
            "hotels": [item for item in catalogue["hotels"] if matches(item)],
            "total": {"hubs": len(catalogue["hubs"]), "hotels": len(catalogue["hotels"])},
            "coordinate_system": "WGS84",
            "source": "anchors_seed",
        }
