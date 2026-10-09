"""核心站台库（C7 CuratedStation）。进出站口/站内换乘的唯一可信来源。"""
from __future__ import annotations

import json
from pathlib import Path


class CuratedStationLibrary:
    def __init__(self, data_path: Path):
        self._data_path = Path(data_path)
        self._stations = {}
        self._load()

    def _load(self):
        if not self._data_path.is_file():
            self._stations = {}
            return
        raw = json.loads(self._data_path.read_text(encoding="utf-8-sig"))
        # 允许单个对象或对象列表
        items = raw if isinstance(raw, list) else [raw]
        for item in items:
            sid = item.get("station_id")
            if sid:
                self._stations[sid] = item

    def get(self, station_id: str):
        return self._stations.get(station_id)

    def access_point(self, station_id: str, access_no: str = None, kind: str = None):
        """按编号/类型查找进出站口，返回 route.schema 的 access_point 结构（source=curated）。"""
        station = self.get(station_id)
        if not station:
            return None
        points = station.get("access_points") or []
        chosen = None
        for ap in points:
            if access_no is not None and ap.get("access_no") == access_no:
                chosen = ap
                break
        if chosen is None:
            for ap in points:
                if kind is not None and ap.get("kind") == kind:
                    chosen = ap
                    break
        if chosen is None and points:
            chosen = points[0]
        if chosen is None:
            return None
        names = station.get("names") or {}
        return {
            "station_id": station.get("station_id"),
            "station_name_zh": names.get("zh-Hans"),
            "station_name_en": names.get("en"),
            "access_no": chosen.get("access_no"),
            "access_name_zh": chosen.get("name_zh"),
            "access_name_en": chosen.get("name_en"),
            "landmark_desc_zh": chosen.get("landmark_desc_zh"),
            "landmark_desc_en": chosen.get("landmark_desc_en"),
            "source": "curated",
        }

    def interior_transfer(self, station_id: str, from_line_code: str, to_line_code: str):
        station = self.get(station_id)
        if not station:
            return None
        for t in station.get("interior_transfers") or []:
            if t.get("from_line_code") == from_line_code and t.get("to_line_code") == to_line_code:
                return t
        return None