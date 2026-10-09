"""人均费用评估：用户费用输入与已选路线统一汇总，未知费用不视为免费。"""
from datetime import date
from decimal import Decimal, ROUND_FLOOR, ROUND_CEILING
from hashlib import sha256
import json
from .trip_points import resolve_day_points
from .reference_prices import hotel_reference, ticket_reference, ticket_notices

MAX_CENTS = 999999999999
CATEGORY_NAMES = {'intercity': '往返大交通', 'lodging': '住宿', 'transport': '当地交通',
                  'tickets': '景点门票', 'meals': '餐饮', 'extras': '购物及其他', 'contingency': '机动费用'}


def itinerary_key(trip):
    """不包含交通计算时间/费用；增删点位、酒店或日期改变才要求核对手填费用。"""
    points = resolve_day_points(trip)
    payload = [(d['date'], points[d['day_index']],
                [(s.get('stop_id'), s.get('poi_id'), s.get('stop_type'), s.get('coordinate'))
                 for s in d.get('ordered_stops') or []]) for d in trip.get('days') or []]
    payload = [payload, (trip.get('anchor_arrival') or {}).get('at'), (trip.get('anchor_departure') or {}).get('at')]
    return sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:24]


def validate_cost_inputs(value):
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError('cost_inputs 必须是对象或 null')
    allowed = {'travelers', 'taxi_vehicles', 'lodging_rooms', 'intercity_cents', 'lodging_nights', 'ticket_cents',
               'meal_daily_cents', 'meal_overrides', 'extras_cents', 'contingency_percent', 'itinerary_key'}
    if set(value) - allowed:
        raise ValueError('cost_inputs 含未知字段')

    def number(v, label, minimum=0, maximum=MAX_CENTS, nullable=True):
        if v is None and nullable:
            return v
        if isinstance(v, bool) or not isinstance(v, int) or not minimum <= v <= maximum:
            raise ValueError(f'cost_inputs.{label} 必须是 {minimum}~{maximum} 的整数')
        return v

    def day(v):
        if not isinstance(v, str):
            raise ValueError('cost_inputs 住宿/餐饮日期必须是 YYYY-MM-DD')
        try:
            parsed = date.fromisoformat(v)
        except ValueError:
            raise ValueError('cost_inputs 住宿/餐饮日期非法') from None
        if parsed.isoformat() != v or not 2023 <= parsed.year <= 2033:
            raise ValueError('cost_inputs 住宿/餐饮日期非法')

    result = dict(value)
    for key in ('travelers', 'taxi_vehicles', 'lodging_rooms'):
        result[key] = number(value.get(key), key, 1, 100)
    for key in ('intercity_cents', 'meal_daily_cents', 'extras_cents'):
        result[key] = number(value.get(key), key)
    result['contingency_percent'] = number(value.get('contingency_percent', 0), 'contingency_percent', 0, 100, False)
    for key in ('ticket_cents', 'meal_overrides'):
        items = value.get(key, {})
        if not isinstance(items, dict) or len(items) > 240:
            raise ValueError(f'cost_inputs.{key} 必须是金额映射，最多 240 项')
        for k, v in items.items():
            if not isinstance(k, str) or not 1 <= len(k) <= 128:
                raise ValueError(f'cost_inputs.{key} 标识非法')
            if key == 'meal_overrides':
                day(k)
            number(v, key)
        result[key] = dict(items)
    nights = value.get('lodging_nights')
    if nights is not None:
        if not isinstance(nights, list) or len(nights) > 60:
            raise ValueError('cost_inputs.lodging_nights 最多 60 项')
        copied = []
        for night in nights:
            if not isinstance(night, dict) or set(night) - {'date', 'hotel_name', 'rooms', 'room_price_cents'}:
                raise ValueError('cost_inputs.lodging_nights 字段非法')
            day(night.get('date'))
            name = night.get('hotel_name', '')
            if not isinstance(name, str) or len(name) > 160:
                raise ValueError('cost_inputs.hotel_name 非法')
            copied.append({'date': night['date'], 'hotel_name': name,
                           'rooms': number(night.get('rooms'), 'rooms', 1, 100),
                           'room_price_cents': number(night.get('room_price_cents'), 'room_price_cents')})
        result['lodging_nights'] = copied
    else:
        result['lodging_nights'] = None
    if 'itinerary_key' in value and (not isinstance(value['itinerary_key'], str) or len(value['itinerary_key']) > 128):
        raise ValueError('cost_inputs.itinerary_key 非法')
    return result


def _same_place(a, b):
    a, b = (a or {}).get('coordinate'), (b or {}).get('coordinate')
    return bool(a and b and all(a.get(k) == b.get(k) for k in ('lat', 'lng', 'crs')))


def _range(low, high=None):
    return {'min_cents': int(low), 'max_cents': int(low if high is None else high)}


def _quote(route, travelers, vehicles):
    if not route or route.get('data_source') not in {'amap', 'tencent', 'baidu', 'curated', 'manual'}:
        return None
    if route.get('duration_seconds') is None:
        return None
    if route.get('mode') == 'walk':
        return _range(0)
    cost = route.get('cost') or {}
    if cost.get('currency') != 'CNY':
        return None
    try:
        low, high = Decimal(str(cost['min'])) * 100, Decimal(str(cost['max'])) * 100
        if not low.is_finite() or not high.is_finite() or not 0 <= low <= high <= MAX_CENTS:
            return None
    except (KeyError, ValueError, TypeError, ArithmeticError):
        return None
    if route.get('mode') == 'taxi':
        if not travelers or not vehicles:
            return None
        low, high = low * vehicles / travelers, high * vehicles / travelers
    return _range(low.to_integral_value(rounding=ROUND_FLOOR), high.to_integral_value(rounding=ROUND_CEILING))


def assess_trip(trip, poi_lookup=None):
    inputs = trip.get('cost_inputs') or {}
    days = sorted(trip.get('days') or [], key=lambda d: d['day_index'])
    points = resolve_day_points(trip)
    key = itinerary_key(trip)
    categories = {k: {**_range(0), 'label': label, 'complete': True} for k, label in CATEGORY_NAMES.items()}
    missing, lines, suggestions = [], [], []
    notices, assumptions, ticket_prices = [], [], {}
    travelers, vehicles = inputs.get('travelers'), inputs.get('taxi_vehicles')

    def unknown(category, identifier, message):
        categories[category]['complete'] = False
        missing.append({'category': category, 'id': identifier, 'message': message})

    def add(category, identifier, label, amount, source='user'):
        categories[category]['min_cents'] += amount['min_cents']
        categories[category]['max_cents'] += amount['max_cents']
        lines.append({'category': category, 'id': identifier, 'label': label, 'source': source, **amount})

    def money_input(category, identifier, label, value, multiplier=1):
        if value is None:
            unknown(category, identifier, label + '费用待补充（免费或不发生请明确填写 0）')
        else:
            add(category, identifier, label, _range(value * multiplier))

    money_input('intercity', 'intercity', '每人往返大交通', inputs.get('intercity_cents'))
    money_input('extras', 'extras', '每人购物及其他', inputs.get('extras_cents'))
    defaults = []
    automatic_lodging = inputs.get('lodging_nights') is None
    auto_rooms, auto_travelers = inputs.get('lodging_rooms') or 1, travelers or 1
    if automatic_lodging and len(days) > 1:
        assumptions.append(f'住宿按行程前 {len(days)-1} 晚、{auto_travelers} 人、{auto_rooms} 间房估算；跨零点、提前入住或延住请切换手动房晚。')
    for d in days[:-1]:
        end = points[d['day_index']]['end']
        reference = hotel_reference(end, d['date'])
        defaults.append({'date': d['date'], 'hotel_name': end['name_zh'] if end and end.get('type') == 'hotel' else '住宿（请确认）',
                         'rooms': auto_rooms, 'room_price_cents': None, 'reference_price': reference})
    nights = inputs.get('lodging_nights')
    if nights is None:
        nights = defaults
    for i, night in enumerate(nights):
        label = f"{night['date']} {night.get('hotel_name') or '住宿'}"
        if automatic_lodging:
            reference = night['reference_price']
            if reference is None:
                unknown('lodging', f'night:{i}', label + '：酒店价格待核实（自选位置或酒店实体冲突请手填）')
            else:
                low, high = reference['min_cents'] * auto_rooms, reference['max_cents'] * auto_rooms
                add('lodging', f'night:{i}', label, {**reference,
                    **_range(low // auto_travelers, (high + auto_travelers - 1) // auto_travelers)}, 'reference_price')
            continue
        price, rooms = night.get('room_price_cents'), night.get('rooms')
        if price is None or rooms is None or (price and not travelers):
            unknown('lodging', f'night:{i}', label + '：每间房价、房间数或实际同行人数待补充')
        else:
            total = price * rooms
            count = travelers or 1
            add('lodging', f'night:{i}', label, _range(total // count, (total + count - 1) // count))

    for d in days:
        index = d['day_index']
        stops = d.get('ordered_stops') or []
        for stop in stops:
            if stop.get('stop_type', 'poi') == 'poi':
                sid = stop.get('stop_id') or f"legacy:{index}:{stop.get('stop_order')}"
                poi = (poi_lookup or {}).get(stop.get('poi_id')) or {}
                name = stop.get('name_zh') or (poi.get('names') or {}).get('zh-Hans') or stop.get('poi_id') or '景点'
                value = (inputs.get('ticket_cents') or {}).get(sid)
                reference = ticket_reference(stop.get('poi_id'), d['date'])
                ticket_prices[sid] = reference
                notices.extend({**n, 'id': sid, 'day_index':index} for n in ticket_notices(stop.get('poi_id'), d['date']))
                label = f'Day {index} {name}门票'
                if value is None and reference is not None:
                    add('tickets', sid, label, reference, 'reference_price')
                else:
                    money_input('tickets', sid, label, value)
                savings = _range(value) if value is not None else reference
                if savings and savings['max_cents']:
                    suggestions.append({'kind': 'ticket', 'title': f'评估减少 {name} 的付费游览',
                        'body': '若取消这次付费游览，每人可减少这次计入的门票估算；请在当天行程自行调整。',
                        'savings_min_cents': savings['min_cents'], 'savings_max_cents': savings['max_cents'], 'day_index': index})
        meals = (inputs.get('meal_overrides') or {}).get(d['date'], inputs.get('meal_daily_cents'))
        money_input('meals', d['date'], d['date'] + '每人餐饮', meals)
        routes = [s.get('transit_from_previous') for s in stops]
        route_points = [points[index]['start']]
        for stop in stops:
            poi = (poi_lookup or {}).get(stop.get('poi_id')) or {}
            route_points.append(stop if stop.get('coordinate') else poi)
        route_points.append(points[index]['end'])
        routes.append(d.get('end_transit'))
        for segment, route in enumerate(routes):
            label = f'Day {index} 第 {segment+1} 段交通' + ('（返程 / 终点）' if segment == len(stops) else '')
            if route is None and _same_place(route_points[segment], route_points[segment+1]):
                add('transport', f'{index}:{segment}', label, _range(0), 'same_place')
                continue
            amount = _quote(route, travelers, vehicles)
            if amount is None:
                reason = '演示路线不能计入真实费用' if (route or {}).get('data_source') == 'mock' else (
                    '实际同行人数和打车车辆数待补充' if (route or {}).get('mode') == 'taxi' and (not travelers or not vehicles)
                    else '已选路线或人民币费用待补充')
                unknown('transport', f'{index}:{segment}', label + '：' + reason)
                continue
            add('transport', f'{index}:{segment}', label, amount, route.get('data_source'))
            if route.get('mode') == 'taxi':
                for variant in route.get('variants') or []:
                    if variant.get('mode') != 'transit':
                        continue
                    alternative = _quote(variant, travelers, vehicles)
                    if not alternative:
                        continue
                    save_min = amount['min_cents'] - alternative['max_cents']
                    if save_min <= 0:
                        continue
                    extra = (variant['duration_seconds'] - route['duration_seconds']) / 60
                    suggestions.append({'kind': 'transit', 'title': label + '可考虑公共交通',
                        'body': '到当天交通卡选择公共交通；切换后重新计算行程时间。费用来自当前可用方案。',
                        'day_index': index, 'segment_index': segment, 'extra_minutes': round(extra, 1),
                        'savings_min_cents': save_min,
                        'savings_max_cents': amount['max_cents'] - alternative['min_cents']})

    stale = bool(inputs and inputs.get('itinerary_key') != key)
    if stale:
        unknown('extras', 'stale', '行程已变更，请核对房晚、门票和餐饮后重新保存费用设置')
    percent = inputs.get('contingency_percent', 0)
    base_low = sum(c['min_cents'] for c in categories.values())
    base_high = sum(c['max_cents'] for c in categories.values())
    add('contingency', 'contingency', f'机动费用 {percent}%', _range(base_low * percent // 100,
        (base_high * percent + 99) // 100), 'user_percentage')
    if missing:
        categories['contingency']['complete'] = False
    total = _range(sum(c['min_cents'] for c in categories.values()), sum(c['max_cents'] for c in categories.values()))
    budget = (trip.get('budget') or {}).get('amount_cents')
    complete = not missing
    status = 'no_budget' if budget is None else ('over_budget' if total['min_cents'] > budget else
             'incomplete' if not complete else 'at_risk' if total['max_cents'] > budget else 'within_budget')
    if budget is not None and complete and total['max_cents'] > budget:
        # 以保守上界反推额度，机动比例先从总预算中扣除。
        base_budget = budget * 100 // (100 + percent)
        for category, count, title in [('lodging', len(nights), '住宿每晚人均目标'), ('meals', len(days), '餐饮每日人均目标')]:
            if count:
                fixed = base_high - categories[category]['max_cents']
                available = max(0, base_budget - fixed)
                target = available // count
                saving = max(0, categories[category]['min_cents'] - target * count)
                suggestions.append({'kind': category, 'title': title, 'target_cents': target,
                    'body': '其他支出已超过预算，即使此项降至 0 仍需同时压缩其他费用；这不是可单独达成的目标。' if fixed > base_budget else
                    '这是在其他支出保持不变时的预算目标；请核实实际可选价格。住宿目标按每人分摊后的费用计算。' if category == 'lodging'
                    else '这是其他支出保持不变时的每日餐饮预算目标，可在费用设置中按天调整。',
                    'savings_min_cents': saving, 'savings_max_cents': max(saving, categories[category]['max_cents'] - target * count)})
        suggestions.append({'kind': 'budget', 'title': '需要压缩支出或调整每人预算',
            'body': '若保留当前安排，可参考完整费用估算区间调整每人预算。',
            'required_reduction_cents': max(0, total['max_cents'] - budget), 'estimate': total})
    suggestions.sort(key=lambda s: -s.get('savings_min_cents', 0))
    return {'currency': 'CNY', 'scope': 'per_person', 'categories': categories, 'lines': lines,
            'total': total, 'complete': complete, 'status': status, 'budget_cents': budget,
            'remaining': None if budget is None else _range(budget-total['max_cents'], budget-total['min_cents']),
            'missing': missing, 'suggestions': suggestions, 'itinerary_key': key,
            'defaults': {'lodging_nights': defaults, 'dates': [d['date'] for d in days], 'ticket_prices': ticket_prices},
            'price_notices': notices, 'assumptions': assumptions, 'automatic_lodging': automatic_lodging,
            'stale': stale}
