"""推荐应用服务，不提供任何落盘或修改行程入口。"""
from __future__ import annotations

import re

from contracts.runtime.registry import CONTRACT_VERSION
from .client import UpstreamError
from .planner import generate_plan, validate_day_indices

MODULE_ID = 'recommendation_engine'


class RecommendationService:
    contract_version = CONTRACT_VERSION

    def __init__(self, client):
        self.client = client

    def generate(self, payload):
        if not isinstance(payload, dict) or set(payload) not in (
                {'trip_id', 'day_indices'}, {'setup', 'day_indices'}):
            raise ValueError('请求恰好包含 trip_id 或 setup 之一，以及 day_indices')
        validate_day_indices(payload['day_indices'])
        existing = 'trip_id' in payload
        if existing:
            trip_id = payload['trip_id']
            if not isinstance(trip_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,120}', trip_id):
                raise ValueError('trip_id 必须是有效行程标识')
            trip = self.client.get_trip(trip_id)
        else:
            if not isinstance(payload['setup'], dict):
                raise ValueError('setup 必须是 JSON 对象')
            trip = self.client.preview_trip(payload['setup'])
        if (not isinstance(trip, dict) or not isinstance(trip.get('days'), list)
                or not all(isinstance(day, dict) and type(day.get('day_index')) is int and isinstance(day.get('date'), str)
                           for day in trip['days'])):
            raise UpstreamError(502, 'UPSTREAM_BAD_RESPONSE', 'trip_engine 行程骨架无效')
        validate_day_indices(payload['day_indices'], trip['days'])
        catalogue = self.client.list_pois()
        if (not isinstance(catalogue, dict) or not isinstance(catalogue.get('pois'), list)
                or not all(isinstance(poi, dict) for poi in catalogue['pois'])):
            raise UpstreamError(502, 'UPSTREAM_BAD_RESPONSE', 'trip_engine 景点列表无效')
        result = generate_plan(trip, catalogue['pois'], payload['day_indices'])
        if not existing:
            result['trip_id'], result['trip_version'] = None, None
        return result

    def health(self):
        health = self.client.health()
        data = health.get('data') if isinstance(health, dict) and health.get('ok') else None
        ready = isinstance(data, dict) and data.get('ready') is True
        return {'module_id': MODULE_ID, 'status': 'ok' if ready else 'degraded', 'ready': ready,
                'contract_version': self.contract_version,
                'upstream': {'trip_engine': 'ok' if ready else 'unavailable'}}
