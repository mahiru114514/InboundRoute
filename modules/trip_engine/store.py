"""trip_engine 的持久化层：行程单文件存储 + POI 主数据加载。

设计约束（见 contracts/devtools 需求文档）：
    · 行程数据只落在本模块的 data_dir 下，写入用「临时文件 + 原子替换」；
    · 每次写入递增 trip.version（乐观锁）；
    · POI 主数据只读，支持 config["poi_path"] 覆盖（便于测试与后续换成真实数据源）。
"""
from __future__ import annotations

import json
import os
import tempfile
import uuid
from pathlib import Path

from core.trip_points import enrich_trip_points
from core.budget_assessment import assess_trip

from .poi_seed import POIS
from .errors import EngineError


def _atomic_write(path: Path, payload) -> None:
    """原子写：先写同目录临时文件，再 os.replace 覆盖。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(prefix=f".{path.name}-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
        os.replace(temp_name, path)
    except OSError:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


class TripStore:
    def __init__(self, data_dir: Path, poi_path: Path | str | None = None):
        self.data_dir = Path(data_dir)
        self.trips_dir = self.data_dir / "trips"
        self.trips_dir.mkdir(parents=True, exist_ok=True)
        self.poi_path = Path(poi_path) if poi_path else None
        self._pois: dict[str, dict] | None = None
        self._poi_stamp: tuple[float, int] | None = None

    # ------------------------------------------------------------ POI 主数据

    def _load_pois(self) -> dict[str, dict]:
        source = self.poi_path
        if source is not None and source.is_file():
            stamp = (source.stat().st_mtime, source.stat().st_size)
            if self._pois is None or self._poi_stamp != stamp:
                payload = json.loads(source.read_text(encoding="utf-8"))
                records = payload.get("pois", payload) if isinstance(payload, dict) else payload
                self._pois = {item["poi_id"]: item for item in records}
                self._poi_stamp = stamp
            return self._pois
        if self._pois is None:
            self._pois = {item["poi_id"]: item for item in POIS}
        return self._pois

    @property
    def poi_source(self) -> str:
        return str(self.poi_path) if self.poi_path and self.poi_path.is_file() else "内置种子数据(poi_seed.py)"

    def poi(self, poi_id: str) -> dict:
        record = self._load_pois().get(poi_id)
        if record is None:
            raise EngineError(404, "POI_NOT_FOUND", f"POI 不存在：{poi_id}")
        return record

    def list_pois(self, interest: str | None = None, category_level1: str | None = None) -> list[dict]:
        records = list(self._load_pois().values())
        if category_level1:
            records = [item for item in records if item["category"]["level1"] == category_level1]
        if interest:
            records = [item for item in records if item["category"]["level1"] == interest]
        return records

    # ------------------------------------------------------------ 行程存储

    def _path(self, trip_id: str) -> Path:
        if not trip_id or "/" in trip_id or "\\" in trip_id or ".." in trip_id:
            raise EngineError(400, "BAD_REQUEST", "行程 ID 非法")
        return self.trips_dir / f"{trip_id}.json"

    def get(self, trip_id: str) -> dict:
        path = self._path(trip_id)
        if not path.is_file():
            raise EngineError(404, "TRIP_NOT_FOUND", f"行程不存在：{trip_id}")
        try:
            trip = json.loads(path.read_text(encoding="utf-8"))
            # 旧数据使用确定性 ID：读操作不写盘，重读仍得到同一个标识。
            for day in trip.get('days') or []:
                for index, stop in enumerate(day.get('ordered_stops') or []):
                    stop.setdefault('stop_id', 'stop_' + uuid.uuid5(uuid.NAMESPACE_URL,
                        f"{trip_id}/{day['day_index']}/{index}").hex[:20])
            return self._enrich(trip)
        except (OSError, json.JSONDecodeError) as exc:
            raise EngineError(500, "INTERNAL", f"行程数据损坏：{exc}") from exc

    def save(self, trip: dict) -> dict:
        _atomic_write(self._path(trip["trip_id"]), {k: v for k, v in trip.items()
            if k not in {'resolved_day_points', 'default_day_points', 'budget_assessment'}})
        return self._enrich(trip)

    def _enrich(self, trip):
        enrich_trip_points(trip)
        trip['budget_assessment'] = assess_trip(trip, self._load_pois())
        return trip

    def list_trips(self) -> list[str]:
        return sorted(path.stem for path in self.trips_dir.glob("*.json"))

    def delete(self, trip_id: str) -> None:
        try:
            self._path(trip_id).unlink()
        except FileNotFoundError:
            raise EngineError(404, "TRIP_NOT_FOUND", f"行程不存在：{trip_id}")
