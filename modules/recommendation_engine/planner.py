"""纯推荐排程；距离仅用于规划余量，不生成导航或真实交通数据。"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from core.poi_availability import closure_hit
from core.trip_points import resolve_day_points

SHANGHAI = timezone(timedelta(hours=8))
PACING_CAP = {'relaxed': 2, 'balanced': 4, 'packed': 6}
INTERESTS = {'modern_skyline', 'history_culture', 'local_life', 'nature'}


def validate_day_indices(day_indices, days=None):
    if (not isinstance(day_indices, list) or not day_indices
            or any(type(index) is not int or index < 1 for index in day_indices)):
        raise ValueError('day_indices 必须是非空正整数数组')
    if len(set(day_indices)) != len(day_indices):
        raise ValueError('day_indices 不得重复')
    if days is not None and not set(day_indices).issubset({day['day_index'] for day in days}):
        raise ValueError('day_indices 含不存在的日期')


def _local_time(day, hhmm):
    return int(datetime.fromisoformat(f'{day}T{hhmm}').replace(tzinfo=SHANGHAI).timestamp())


def _distance(first, second):
    if not first or not second or first.get('crs', 'WGS84') != second.get('crs', 'WGS84'):
        return None
    try:
        values = [float(first['lat']), float(first['lng']), float(second['lat']), float(second['lng'])]
        if not all(math.isfinite(value) for value in values):
            return None
        lat1, lng1, lat2, lng2 = values
        dlat, dlng = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
        value = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
        return 6371 * 2 * math.asin(min(1, math.sqrt(value)))
    except (ValueError, TypeError, KeyError):
        return None


def _transit_minutes(first, second, slower=False):
    distance = _distance(first, second)
    # 道路绕行、换乘与等候的保守规划余量；未知坐标不能按零距离处理。
    return 45 if distance is None else math.ceil(15 + distance * (4 if slower else 3))


def _season_matches(window, date):
    lower, upper, mmdd = window.get('date_from'), window.get('date_to'), date[5:]
    if lower and upper:
        return lower <= mmdd <= upper if lower <= upper else mmdd >= lower or mmdd <= upper
    return (not lower or mmdd >= lower) and (not upper or mmdd <= upper)


def _fit_window(operating, date, earliest, dwell_seconds, holiday_open=False):
    windows = operating.get('opening_hours') or []
    weekday = datetime.fromisoformat(date).isoweekday()
    eligible = [window for window in windows if (holiday_open or weekday in window.get('weekdays', range(1, 8)))
                and _season_matches(window, date)]
    if windows and not eligible:
        return None
    last_entry = operating.get('last_entry_time')
    last_entry_at = _local_time(date, last_entry) if last_entry else None
    light = operating.get('light_up') or {}
    light_windows = [window for window in light.get('windows') or [] if _season_matches(window, date)] if light.get('required') else []
    if light.get('required') and light.get('windows') and not light_windows:
        return None
    intervals = []
    for light_window in light_windows:
        light_start = _local_time(date, light_window['start'])
        if light.get('T_light_rule', 'window_start_minus_30') == 'window_start_minus_30':
            light_start -= 30 * 60
        intervals.append((max(earliest, light_start), _local_time(date, light_window['close'])))
    if not intervals:
        intervals = [(earliest, _local_time(date, '23:59'))]
    if not windows:
        starts = [start for start, end in intervals if start + dwell_seconds <= end
                  and start == earliest
                  and (last_entry_at is None or start <= last_entry_at)]
        return min(starts) if starts else None
    starts = []
    for window in eligible:
        opened = _local_time(date, window['open'])
        closed = _local_time(date, window['close']) + (86400 if window.get('close_next_day') else 0)
        window_last_entry = last_entry_at
        if window.get('close_next_day') and window_last_entry is not None and window_last_entry < opened:
            window_last_entry += 86400
        for earliest_start, interval_close in intervals:
            start = max(earliest_start, opened)
            # plan 只保存 POI 与停留，不能保存等待；只接受即到即开始的窗口。
            if (start == earliest and start + dwell_seconds <= min(closed, interval_close)
                    and (window_last_entry is None or start <= window_last_entry)):
                starts.append(start)
    return min(starts) if starts else None


def _dwell(operating, slower, warnings):
    dwell = operating.get('dwell_time') or {}
    value = dwell.get('minutes_min') if dwell.get('kind') == 'range' else dwell.get('minutes')
    if type(value) is not int or not 15 <= value <= 720:
        value = 90
        warnings.append('建议停留资料缺失，暂按 90 分钟规划，需核验。')
    if slower and dwell.get('kind') == 'range':
        maximum = dwell.get('minutes_max')
        if type(maximum) is int and value <= maximum <= 720:
            value = maximum
    return value


def _boundaries(trip, day):
    date = day['date']
    start = _local_time(date, day.get('daily_start_local') or '09:00')
    finish = _local_time(date, '22:00')
    arrival = trip.get('anchor_arrival') or {}
    arrival_at = arrival.get('activity_start_at')
    if arrival_at is None:
        anchor_at = arrival.get('at', arrival.get('arrival_at'))
        if anchor_at is not None:
            arrival_at = anchor_at + arrival.get('border_buffer_minutes', 90) * 60
    if arrival_at is not None:
        start = max(start, arrival_at)
    departure = trip.get('anchor_departure') or {}
    departure_at = departure.get('at', departure.get('departure_at'))
    if departure_at is not None:
        finish = min(finish, departure_at - departure.get('hub_buffer_minutes', 180) * 60)
    return start, finish


def generate_plan(trip: dict, pois: list[dict], day_indices: list[int]) -> dict:
    """按选中空白日返回建议，不修改行程、候选或用户偏好。"""
    days = trip.get('days') or []
    validate_day_indices(day_indices, days)
    profile = trip.get('user_profile') or {}
    cap = PACING_CAP.get(profile.get('pacing'), 4)
    interests = set(profile.get('interests') or [])
    slower = profile.get('party_composition') in ('family_kids', 'senior')
    rest_minutes = 25 if slower or profile.get('pacing') == 'relaxed' else 15
    used = {stop.get('poi_id') for day in days for stop in day.get('ordered_stops') or [] if stop.get('poi_id')}
    points = resolve_day_points(trip)
    result = {'plan': {'days': []}, 'days': [], 'skipped_days': [],
              'warnings': ['交通仅为地理距离估算并预留休息余量；真实路线需由路线模块核验。',
                           '每日活动暂以 22:00 为规划上限，数量为上限，不保证全部填满。',
                           '推荐未核算整趟预算，住宿、机票与预约费用需另行评估。'],
              'trip_id': trip.get('trip_id'), 'trip_version': trip.get('version')}
    candidates = {item['poi_id']: item for item in pois
                  if item.get('poi_id') and (item.get('category') or {}).get('level1') in INTERESTS}
    selected = set(day_indices)
    for day in sorted(days, key=lambda value: value['day_index']):
        index, date = day['day_index'], day['date']
        if index not in selected:
            continue
        if day.get('ordered_stops') or day.get('day_status') == 'locked' or day.get('locked'):
            result['skipped_days'].append({'day_index': index, 'reason': '该日已有安排或已锁定，保留用户内容。'})
            continue
        now, end = _boundaries(trip, day)
        endpoints = points[index]
        current = (endpoints.get('start') or {}).get('coordinate')
        target = (endpoints.get('end') or {}).get('coordinate')
        stops = []
        exclusions = set()
        while len(stops) < cap:
            options = []
            for poi_id, item in candidates.items():
                if poi_id in used:
                    continue
                operating = item.get('operating_rules') or {}
                hit, _ = closure_hit(operating.get('closure_rules') or [], date, datetime.fromisoformat(date).isoweekday())
                if hit not in (None, 'holiday_exception_open'):
                    exclusions.add('已知闭馆')
                    continue
                warnings = []
                if operating.get('closure_data_status') != 'verified' or operating.get('is_enclosed_attraction') is None:
                    warnings.append('开放与闭馆资料待核验，不能保证入场。')
                if not operating.get('opening_hours'):
                    warnings.append('开放时段缺失，请出发前核验。')
                if hit == 'holiday_exception_open':
                    warnings.append('节假日开放例外暂参考常规开放时段，实际时段需核验。')
                if operating.get('reservation_required'):
                    warnings.append('此景点需要预约，请自行核验预约资格及名额。')
                coordinate = item.get('coordinate')
                distance = _distance(current, coordinate)
                if distance is None or _distance(coordinate, target) is None:
                    warnings.append('位置缺失或坐标系不同，交通余量与顺序需核验。')
                dwell = _dwell(operating, slower, warnings)
                earliest = now + _transit_minutes(current, coordinate, slower) * 60
                light = operating.get('light_up') or {}
                if light.get('required') and (not light.get('windows') or light.get('T_light_rule') == 'sunset'):
                    warnings.append('亮灯时段或日落资料待核验，不能保证看到夜景。')
                start = _fit_window(operating, date, earliest, dwell * 60, hit == 'holiday_exception_open')
                if start is None or start + (dwell + rest_minutes + _transit_minutes(coordinate, target, slower)) * 60 > end:
                    exclusions.add('开放时段、停留或出行时间不足')
                    continue
                category = (item.get('category') or {}).get('level1')
                # 兴趣优先，同时惩罚跨区距离；未到开放时段的候选在后续插入时重试。
                score = (30 if category in interests else 0) - (distance if distance is not None else 15) * 3
                reasons = ['匹配所选兴趣' if category in interests else '补充游玩类型', '按每日起终点及区域距离安排顺序', '已预留停留、交通估算及休息时间']
                if light.get('required') and light.get('windows'):
                    reasons.append('参考亮灯窗口安排晚间游玩')
                options.append((score, poi_id, item, start, dwell, reasons, warnings))
            if not options:
                break
            _, poi_id, item, start, dwell, reasons, warnings = sorted(options, key=lambda item: (-item[0], item[1]))[0]
            stops.append({'poi_id': poi_id, 'name_zh': (item.get('names') or {}).get('zh-Hans') or poi_id,
                          'planned_dwell_minutes': dwell, 'reasons': reasons, 'warnings': warnings})
            used.add(poi_id)
            now = start + (dwell + rest_minutes) * 60
            current = item.get('coordinate')
        if stops:
            result['days'].append({'day_index': index, 'date': date, 'stops': stops})
            result['plan']['days'].append({'day_index': index, 'stops': [
                {'poi_id': stop['poi_id'], 'planned_dwell_minutes': stop['planned_dwell_minutes']} for stop in stops]})
            if len(stops) < cap:
                reason = '、'.join(sorted(exclusions)) or '可用且未重复的候选不足'
                result['warnings'].append(f'第 {index} 天安排 {len(stops)} 个景点：{reason}，未为填满数量重复添加。')
        else:
            reason = '、'.join(sorted(exclusions)) or '可用且未重复的候选不足'
            result['skipped_days'].append({'day_index': index, 'reason': f'未安排：{reason}。'})
    return result
