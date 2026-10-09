"""解析每日实际起终点；缺省字段兼容旧行程，酒店变更按日继承。"""
from copy import deepcopy


def _endpoint(anchor, kind):
    if not anchor or not anchor.get('coordinate'):
        return None
    return {'type': anchor.get('type', kind), 'poi_id': anchor.get('poi_id'),
            'station_id': None, 'name_zh': anchor.get('name_zh') or anchor.get('location_name'),
            'name_en': anchor.get('name_en') or anchor.get('location_name'),
            'coordinate': deepcopy(anchor['coordinate'])}


def resolve_day_points(trip):
    days = sorted(trip.get('days') or [], key=lambda day: day['day_index'])
    hotel = _endpoint(trip.get('anchor_hotel'), 'hotel')
    previous_end = None
    result = {}
    for position, day in enumerate(days):
        start = _endpoint(day.get('start_anchor'), 'hotel')
        if start is None:
            start = (_endpoint(trip.get('anchor_arrival'), 'arrival_anchor') if position == 0 else previous_end) or hotel
        if start and start['type'] == 'hotel':
            hotel = start
        for stop in day.get('ordered_stops') or []:
            if stop.get('stop_type') == 'hotel' and stop.get('hotel_stay_kind', 'overnight') == 'overnight':
                hotel = _endpoint(stop, 'hotel') or hotel
        end = _endpoint(day.get('end_anchor'), 'hotel')
        if end is None:
            end = (_endpoint(trip.get('anchor_departure'), 'departure_anchor') if position == len(days)-1 else None) or hotel
        if end and end['type'] == 'hotel':
            hotel = end
        result[day['day_index']] = {'start': deepcopy(start), 'end': deepcopy(end)}
        previous_end = end
    return result


def enrich_trip_points(trip):
    """只读派生快照；浏览器使用它，默认规则只在本模块实现。"""
    trip['resolved_day_points'] = resolve_day_points(trip)
    defaults = {}
    for day in trip.get('days') or []:
        defaults[day['day_index']] = {}
        for field, key in (('start_anchor', 'start'), ('end_anchor', 'end')):
            preview = {**trip, 'days': [{**d, field: None} if d is day else d for d in trip['days']]}
            defaults[day['day_index']][key] = resolve_day_points(preview)[day['day_index']][key]
    trip['default_day_points'] = defaults
    return trip
