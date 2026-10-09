"""锚点、预算与费用输入校验。"""
from __future__ import annotations

import math

from core.budget_assessment import validate_cost_inputs, itinerary_key
from .errors import EngineError
from .domain import (
    _require,
)


class TripValidation:
    """行程输入校验；由 TripService 复用，不读写行程文件。"""

    def _validate_anchor(self, anchor, name, buffer_field, buffer_range):
        _require(isinstance(anchor, dict), f"{name} 必须是对象")
        moment = anchor.get("at")
        _require(isinstance(moment, int) and not isinstance(moment, bool),
                 f"{name}.at 必须是 UTC 秒级整数")
        _require(1700000000 <= moment <= 2000000000, f"{name}.at 超出合理范围（2023-2033）")
        _require(isinstance(anchor.get("location_name"), str) and anchor["location_name"].strip(),
                 f"{name}.location_name 必填")
        coordinate = anchor.get("coordinate")
        _require(isinstance(coordinate, dict), f"{name}.coordinate 必填")
        _require(isinstance(coordinate.get("crs"), str), f"{name}.coordinate.crs 必填（WGS84 / GCJ-02 / BD-09）")
        _require(isinstance(coordinate.get("lat"), (int, float)) and not isinstance(coordinate.get("lat"), bool),
                 f"{name}.coordinate.lat 必须是数字")
        _require(isinstance(coordinate.get("lng"), (int, float)) and not isinstance(coordinate.get("lng"), bool),
                 f"{name}.coordinate.lng 必须是数字")
        buffer_value = anchor.get("buffer_minutes", buffer_range[2])
        _require(isinstance(buffer_value, int) and not isinstance(buffer_value, bool),
                 f"{name}.buffer_minutes 必须是整数")
        _require(buffer_range[0] <= buffer_value <= buffer_range[1],
                 f"{name}.buffer_minutes 必须在 {buffer_range[0]}~{buffer_range[1]} 之间")
        return {
            "at": moment,
            "location_name": anchor["location_name"].strip(),
            "coordinate": {key: coordinate[key] for key in ("lat", "lng", "crs") if key in coordinate},
            buffer_field: buffer_value,
        }

    def _validate_budget(self, budget):
        if budget is None:
            return None
        _require(isinstance(budget, dict), 'budget 必须是对象或 null')
        _require(set(budget) == {'scope', 'currency', 'amount_cents'}, 'budget 需要 scope、currency、amount_cents')
        _require(budget['scope'] == 'per_person', 'budget.scope 必须是 per_person（每人整趟行程）')
        _require(budget['currency'] == 'CNY', 'budget.currency 必须是 CNY')
        amount = budget['amount_cents']
        _require(isinstance(amount, int) and not isinstance(amount, bool) and 0 <= amount <= 999999999999,
                 'budget.amount_cents 必须是 0~999999999999 的整数分')
        return dict(budget)

    def _validate_cost_inputs(self, value, trip):
        try:
            inputs = validate_cost_inputs(value)
        except ValueError as exc:
            raise EngineError(400, 'BAD_REQUEST', str(exc)) from exc
        if inputs is not None:
            inputs['itinerary_key'] = itinerary_key(trip)
        return inputs

    def _validate_day_anchor(self, value, field):
        if value is None:
            return None
        _require(isinstance(value, dict), f'{field} 必须是地点对象或 null')
        _require(not set(value) - {'type', 'name_zh', 'name_en', 'name_pinyin', 'poi_id', 'coordinate'},
                 f'{field} 含未知字段')
        _require(value.get('type') in {'hotel', 'poi', 'arrival_anchor', 'departure_anchor'}, f'{field}.type 非法')
        for name in ('name_zh', 'name_en'):
            _require(isinstance(value.get(name), str) and bool(value[name].strip()), f'{field}.{name} 必填')
        coordinate = value.get('coordinate')
        _require(isinstance(coordinate, dict), f'{field}.coordinate 必填')
        _require(not set(coordinate) - {'lat', 'lng', 'crs', 'precision_m'}, f'{field}.coordinate 含未知字段')
        for key, limit in (('lat', 90), ('lng', 180)):
            number = coordinate.get(key)
            _require(isinstance(number, (int, float)) and not isinstance(number, bool)
                     and -limit <= number <= limit and math.isfinite(number), f'{field}.coordinate.{key} 非法')
        _require(coordinate.get('crs') in {'WGS84', 'GCJ-02', 'BD-09'}, f'{field}.coordinate.crs 非法')
        if 'precision_m' in coordinate:
            precision = coordinate['precision_m']
            _require(isinstance(precision, (int, float)) and not isinstance(precision, bool)
                     and (isinstance(precision, int) or math.isfinite(precision)) and precision >= 0, f'{field}.coordinate.precision_m 非法')
        _require(value.get('poi_id') is None or isinstance(value['poi_id'], str), f'{field}.poi_id 非法')
        _require('name_pinyin' not in value or isinstance(value['name_pinyin'], str), f'{field}.name_pinyin 非法')
        return {**value, 'name_zh': value['name_zh'].strip(), 'name_en': value['name_en'].strip()}
