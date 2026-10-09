"""推荐方案的事务写入；推荐计算在独立插件中，本文件只校验和保存。"""
from __future__ import annotations

import re
import uuid

from .domain import _require, _trip_transaction, dwell_minutes_of
from .errors import EngineError


class RecommendationOperations:
    """宿主提供存储、行程构造、日状态工具与统一提交。"""

    def preview_trip(self, payload: dict) -> dict:
        return self._build_trip(payload)

    def _recommendation_days(self, trip: dict, plan: dict) -> list[int]:
        _require(isinstance(plan, dict) and set(plan) == {'days'}, 'plan 必须只包含 days')
        proposals = plan['days']
        _require(isinstance(proposals, list) and 1 <= len(proposals) <= 15,
                 '推荐计划须包含 1~15 个日期')
        used = {stop.get('poi_id') for day in trip['days'] for stop in day['ordered_stops']
                if stop.get('stop_type', 'poi') == 'poi'}
        selected = set()
        prepared = []
        total = 0
        for proposal in proposals:
            _require(isinstance(proposal, dict) and set(proposal) == {'day_index', 'stops'},
                     '推荐日期需要 day_index 和 stops')
            index = proposal['day_index']
            _require(isinstance(index, int) and not isinstance(index, bool), '推荐日期必须是整数')
            _require(index not in selected, '推荐日期不能重复')
            selected.add(index)
            day = self._day(trip, index)
            _require(not day['ordered_stops'], f'Day {index} 已有安排，请选择空白日')
            _require(day.get('day_status') != 'locked', f'Day {index} 已锁定，请先解锁')
            stops = proposal['stops']
            _require(isinstance(stops, list) and len(stops) <= 6, '推荐日期最多包含 6 个景点')
            new_stops = []
            for item in stops:
                _require(isinstance(item, dict) and 'poi_id' in item
                         and not set(item) - {'poi_id', 'planned_dwell_minutes'}, '推荐点位字段非法')
                poi_id = item['poi_id']
                _require(isinstance(poi_id, str) and bool(poi_id.strip()), 'poi_id 必填')
                _require(poi_id not in used, '推荐景点不能与行程其他日期重复')
                poi = self.store.poi(poi_id)
                dwell = item.get('planned_dwell_minutes', dwell_minutes_of(poi))
                _require(isinstance(dwell, int) and not isinstance(dwell, bool)
                         and 1 <= dwell <= 720, '推荐停留须为 1~720 的整数分钟')
                used.add(poi_id)
                new_stops.append({
                    'stop_order': len(new_stops) + 1, 'stop_type': 'poi',
                    'stop_id': 'stop_' + uuid.uuid4().hex[:20], 'poi_id': poi_id,
                    'locked': False, 'arrival_at': None, 'departure_at': None,
                    'user_preferred_arrival_local': None, 'planned_dwell_minutes': dwell,
                    'transit_from_previous': None, 'rule_notices': [],
                })
            total += len(new_stops)
            prepared.append((day, new_stops))
        _require(total > 0, '没有可应用的推荐景点，请调整日期或偏好')
        # 全部候选校验通过之后才改变内存副本，最后由调用方一次落盘。
        applied = []
        for day, stops in prepared:
            if stops:
                day['ordered_stops'] = stops
                self._invalidate_route_data(day)
                self._refresh_day_status(day)
                applied.append(day['day_index'])
        return applied

    def create_recommended_trip(self, payload: dict) -> dict:
        _require(isinstance(payload, dict) and set(payload) == {'setup', 'plan'},
                 '创建推荐行程需要 setup 和 plan')
        trip = self._build_trip(payload['setup'])
        self._recommendation_days(trip, payload['plan'])
        self._retag_arrival_day(trip)
        return self.store.save(trip)

    @_trip_transaction
    def apply_recommendations(self, trip_id: str, payload: dict, expected_version=None) -> dict:
        _require(not isinstance(expected_version, bool)
                 and isinstance(expected_version, (int, str))
                 and re.fullmatch(r'[1-9][0-9]*', str(expected_version)),
                 '应用推荐必须携带有效的 If-Match 行程版本')
        trip = self.store.get(trip_id)
        if int(expected_version) != trip['version']:
            raise EngineError(409, 'VERSION_CONFLICT', '行程已改变，请刷新后重新生成推荐',
                              {'expected': int(expected_version), 'actual': trip['version']})
        _require(isinstance(payload, dict) and set(payload) == {'plan'}, '应用推荐需要 plan')
        days = self._recommendation_days(trip, payload['plan'])
        return self._commit(trip, 'add_stop', '推荐日期：' + ','.join(map(str, days)))
