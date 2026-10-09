"""路线归一化与纯函数（C2/C3/C4/C6 展示项数据来源）。"""
from __future__ import annotations

import math
import re
try:
    from .place_names import place_name_en
except ImportError:
    from place_names import place_name_en

# step_estimation（mappings.json）：默认步长 0.7m，family_kids 0.55，senior 0.65。
_STRIDE = {"default": 0.7, "family_kids": 0.55, "senior": 0.65}
# walk_speed_mps（mappings.json）：默认 1.25，family_kids/senior 0.96。
_WALK_SPEED = {"default": 1.25, "family_kids": 0.96, "senior": 0.96}

LONG_TRANSFER_THRESHOLD_M = 200


def haversine_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371000.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def stride_for(party_composition: str) -> float:
    return _STRIDE.get(party_composition, _STRIDE["default"])


def walk_speed_for(party_composition: str) -> float:
    return _WALK_SPEED.get(party_composition, _WALK_SPEED["default"])


def estimate_steps(walking_distance_m, party_composition: str):
    if walking_distance_m is None:
        return None
    return int(round(walking_distance_m / stride_for(party_composition)))


def build_point(lat: float, lng: float, crs: str = "WGS84", precision_m: int = 50):
    return {"lat": round(float(lat), 6), "lng": round(float(lng), 6), "crs": crs, "precision_m": int(precision_m)}


def build_endpoint(stop_type: str, poi_id=None, station_id=None, name_zh=None, name_en=None):
    return {"type": stop_type, "poi_id": poi_id, "station_id": station_id,
            "name_zh": name_zh, "name_en": name_en}


def build_cost(min_value, max_value, currency="CNY", display_currency="CNY"):
    return {"min": float(min_value), "max": float(max_value),
            "currency": currency, "display_currency": display_currency}


def build_transfer_overhead(applies_to="walking_segment", factor=1.3, counts_in_timeline=True):
    return {"applies_to": applies_to, "factor": factor, "counts_in_timeline": counts_in_timeline}


# ------------------------------------------------------------------ 高德线路与步行指引
#
# 高德 buslines 只给中文线路名（形如「闵行18路(合川路虹泉路--金辉路保乐路)」）和一个内部 id。
# 契约里 line.code 是「给人看的短线号」（route.schema.json 的 examples 是 ["2"]），
# 所以内部 id 不能当线路号下发：丢弃它，从线路名派生可确证的短线号与英文名。
# 派生不出来就留空 —— 宁可只有中文，也不编造（同 C-铁律-1：缺失时隐藏，不显示占位）。
#
# 英文线路显示名来源：
#   1) 数字线路：'2号线' -> code '2' / 'Line 2'；'闵行18路' -> code '18' / 'Bus 18'（语言无关的编号，直接可译）；
#   2) 具名线路：查 data/curated_rail_lines.json 的官方译名表，查不到就保持中文。
#   3) 查地名显示译名表；拼音或描述性显示名在资料中单独标记，中文原名仍保留。
_RAIL_LINE_RE = re.compile(r"^(?:地铁|轨交|轻轨)?(?P<num>\d{1,3})号线$")
_BUS_LINE_RE = re.compile(r"^(?P<prefix>[^\d]{0,8}?)(?P<num>\d{1,4})路$")
_TERMINAL_SPLIT_RE = re.compile(r"\s*(?:--|—|–|－|~|～|至|到)\s*")
_ACCESS_NO_RE = re.compile(r"(?<!\d)(?P<num>\d{1,3})\s*号(?:口|出入口|出口|入口|门)")
_ACCESS_EN_RE = re.compile(r"^(?:Entrance|Exit|Gate)\s*(?P<num>\d{1,3})$", re.IGNORECASE)

# 高德步行指令的固定句式（动词/动作）。按长度降序排列，便于把「左转进入右侧道路」这类复合动作拆开。
_AMAP_WALK_ACTIONS = tuple(sorted((
    ("向右前方行走", "bear right and continue"),
    ("向左前方行走", "bear left and continue"),
    ("进入右转专用道", "enter the right-turn lane"),
    ("进入左转专用道", "enter the left-turn lane"),
    ("上过街天桥", "go up the pedestrian overpass"),
    ("下过街天桥", "go down the pedestrian overpass"),
    ("进入辅路", "enter the service road"),
    ("向右前方直行", "bear right and continue"),
    ("向左前方直行", "bear left and continue"),
    ("向右后方直行", "bear back-right and continue"),
    ("向左后方直行", "bear back-left and continue"),
    ("右转上阶梯", "turn right and take the stairs up"),
    ("左转上阶梯", "turn left and take the stairs up"),
    ("右转下阶梯", "turn right and take the stairs down"),
    ("左转下阶梯", "turn left and take the stairs down"),
    ("右转出阶梯", "turn right and exit the stairs"),
    ("左转出阶梯", "turn left and exit the stairs"),
    ("进入右侧道路", "enter the road on the right"),
    ("进入左侧道路", "enter the road on the left"),
    ("进入匝道", "enter the ramp"),
    ("到达目的地", "arrive at your destination"),
    ("出阶梯", "exit the stairs"),
    ("上阶梯", "take the stairs up"),
    ("下阶梯", "take the stairs down"),
    ("靠右", "keep right"),
    ("靠左", "keep left"),
    ("直行", "continue straight"),
    ("右转", "turn right"),
    ("左转", "turn left"),
), key=lambda item: -len(item[0])))
_DESTINATION_WORDS = ("目的地", "终点")
_COMPASS = {"东北":"northeast", "东南":"southeast", "西北":"northwest", "西南":"southwest",
            "东":"east", "南":"south", "西":"west", "北":"north"}
_COMPASS_RE = "|".join(_COMPASS)


def clean_text(value):
    """只接受非空字符串；三方常见的 [] / {} / None 占位一律视为无数据。"""
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def split_amap_line_name(raw_name):
    """把高德线路名拆成 (线路名, 起讫点串)。'闵行18路(A--B)' -> ('闵行18路', 'A--B')。"""
    name = clean_text(raw_name)
    if not name:
        return None, None
    # 从末尾找配对括号，避免环线附注或终点里的「(南广场)」被截错。
    value = name.replace("（", "(").replace("）", ")")
    if not value.endswith(")"):
        return name, None
    depth = 0
    for index in range(len(value) - 1, -1, -1):
        if value[index] == ")":
            depth += 1
        elif value[index] == "(":
            depth -= 1
            if depth == 0:
                return clean_text(name[:index]), clean_text(name[index + 1:-1])
    return name, None


def derive_line_code(name_zh):
    """可确证的短线号：'2号线' -> '2'，'闵行18路' -> '18'。否则 None（不猜）。"""
    name = clean_text(name_zh)
    if not name:
        return None
    base, annotation = split_amap_line_name(name)
    if annotation and base:
        return derive_line_code(base)
    for pattern in (_RAIL_LINE_RE, _BUS_LINE_RE):
        matched = pattern.match(name)
        if matched:
            return matched.group("num")
    return None


def derive_line_name_en(name_zh, rail_reference=None):
    """数字线路按编号译写；具名线路查已核录英文/拼音显示名，未知名称留空。"""
    name = clean_text(name_zh)
    if not name:
        return None
    base, annotation = split_amap_line_name(name)
    if annotation and base:
        base_en = derive_line_name_en(base, rail_reference)
        return complete_line_name_en(name, base_en) if base_en else None
    rail = _RAIL_LINE_RE.match(name)
    if rail:
        return "Line " + rail.group("num")
    bus = _BUS_LINE_RE.match(name)
    if bus:
        return "Bus " + bus.group("num")
    for key, value in (rail_reference or {}).items():
        if name == key or name.startswith(key):
            return clean_text(value)
    return place_name_en(name) if any(ch in name for ch in ("线", "铁路", "电车")) else None


def complete_line_name_en(name_zh, name_en):
    """给已有英文线路名补上中文名中保存的起讫站/环线说明，保持顺序，不推断乘车方向。"""
    english = clean_text(name_en)
    if not english:
        return None
    base, annotation = split_amap_line_name(name_zh)
    if not annotation:
        return english
    parts = [clean_text(part) for part in _TERMINAL_SPLIT_RE.split(annotation)]
    if len(parts) == 2 and all(parts):
        # 已保存完整英文起讫站时保留，不重复拼接。
        _, stored_annotation = split_amap_line_name(english)
        if stored_annotation and len(_TERMINAL_SPLIT_RE.split(stored_annotation)) == 2:
            return english
        if base and base.endswith(("(环线)", "（环线）")) and "(Loop)" not in english:
            english += " (Loop)"
        return english + " (" + " — ".join(place_name_en(part) or part for part in parts) + ")"
    if annotation == "环线" and "(Loop)" not in english:
        return english + " (Loop)"
    return english


def _terminal_matches(station_name, terminal):
    if not station_name or not terminal:
        return False
    return station_name == terminal or station_name in terminal or terminal in station_name


def build_amap_direction(raw_name, alight_name=None):
    """用「线路名括号里的起讫点」和「实际下车站名」推出行车方向。

    只有能确证「下车站就是其中一个终点」时才返回「往X方向」；两边都像或都不像一律返回 None，
    不用起讫点顺序去猜（猜错方向比不给方向更糟）。
    """
    _, terminals = split_amap_line_name(raw_name)
    alight = clean_text(alight_name)
    if not terminals or not alight:
        return None
    parts = [clean_text(piece) for piece in _TERMINAL_SPLIT_RE.split(terminals)]
    parts = [piece for piece in parts if piece]
    if len(parts) != 2:
        return None
    to_second = _terminal_matches(alight, parts[1])
    to_first = _terminal_matches(alight, parts[0])
    if to_second == to_first:
        return None
    target = parts[1] if to_second else parts[0]
    return {"name_zh": "往" + target + "方向", "name_en": "Towards " + (place_name_en(target) or target)}


def normalize_amap_transit_line(raw_name, alight_name=None, rail_reference=None):
    """返回 (line, direction)；line 只含有值的键（契约 additionalProperties=false，不许塞 null）。

    方向能确证时放进 direction；否则中文和英文线路名均保留起讫站，避免丢信息。
    """
    name = clean_text(raw_name)
    if not name:
        return None, None
    display, terminals = split_amap_line_name(name)
    clean_name = display or name
    direction = build_amap_direction(name, alight_name) if terminals else None
    line = {}
    code = derive_line_code(clean_name)
    if code:
        line["code"] = code
    name_en = derive_line_name_en(clean_name if direction else name, rail_reference)
    if name_en:
        line["name_en"] = name_en
    # 方向确证时才把起讫点摘进 direction；否则保留原始名（含括号），避免丢信息。
    line["name_zh"] = clean_name if direction else name
    return line, direction


def parse_amap_access_name(raw_name, kind="entrance"):
    """从高德的出入口名派生 (access_no, access_name_en)。

    '2号口' -> ('2', 'Entrance 2'/'Exit 2')；没有编号或不是编号式名称 -> (None, None)。
    """
    name = clean_text(raw_name)
    if not name:
        return None, None
    matched = _ACCESS_NO_RE.search(name) or _ACCESS_EN_RE.match(name)
    if not matched:
        directional = re.fullmatch(r"(" + _COMPASS_RE + r")(出入口|出口|入口|口)", name)
        if directional:
            direction, access_kind = directional.groups()
            label = "entrance / exit" if access_kind == "出入口" else (
                "exit" if access_kind == "出口" or (access_kind == "口" and kind == "exit") else "entrance")
            return None, _COMPASS[direction].capitalize() + " " + label
        return None, None
    number = matched.group("num")
    if kind == "exit":
        return number, "Exit " + number
    if kind == "entrance":
        return number, "Entrance " + number
    return number, "Gate " + number


def _walk_action_en(text):
    """动作片段的英文：整段认识就直译；复合动作（左转进入右侧道路）拆成已知片段再连起来。"""
    value = clean_text(text)
    if not value:
        return None
    value = value.strip("。.;；,，、 ")
    if not value:
        return None
    if value.startswith("到达"):
        destination = value[len("到达"):].strip()
        if destination in _DESTINATION_WORDS:
            return "arrive at your destination"
        return "reach " + (place_name_en(destination) or destination) if destination else "arrive"
    for zh, en in _AMAP_WALK_ACTIONS:
        if value == zh:
            return en
    pieces, index = [], 0
    while index < len(value):
        for zh, en in _AMAP_WALK_ACTIONS:
            if value.startswith(zh, index):
                pieces.append(en)
                index += len(zh)
                break
        else:
            return None          # 有一段不认识就整段不翻，不猜义
    return " and ".join(pieces) if pieces else None


def _arrival_phrase(action):
    """「到达X」的英文说法；不是到达句式返回 None。"""
    value = clean_text(action)
    if not value or not value.startswith("到达"):
        return None
    destination = value[len("到达"):].strip()
    if destination in _DESTINATION_WORDS or not destination:
        return "arrive at your destination"
    return "reach " + (place_name_en(destination) or destination)


def translate_amap_instruction(text):
    """把一条高德中文步行指令翻成英文句式；句式不认识就返回 None（不猜义）。

    固定句式、距离及已核录地名翻译；未知地名保留原文，中文指令始终独立保留。
    """
    value = clean_text(text)
    if not value:
        return None
    value = value.strip("。.;；,，、 ")
    if not value:
        return None
    along_compass = re.fullmatch(r"沿(.+?)向(" + _COMPASS_RE + r")步行(\d+)米(.*)", value)
    if along_compass:
        road, direction, distance, action = along_compass.groups()
        translated = translate_amap_instruction("沿" + road + "步行" + distance + "米" + action)
        return translated.replace("Walk " + distance + " m", "Walk " + distance + " m " + _COMPASS[direction], 1) if translated else None
    compass_walk = re.fullmatch(r"向(" + _COMPASS_RE + r")步行(\d+)米(.*)", value)
    if compass_walk:
        direction, distance, action = compass_walk.groups()
        translated = _walk_action_en(action) if action else None
        if action and not translated:
            return None
        return "Walk " + distance + " m " + _COMPASS[direction] + (", " + translated if translated else "")
    matched = re.match(r"^沿(?P<road>.+?)步行(?P<distance>\d+)米(?P<action>.+)$", value)
    if matched:
        road, distance = matched.group("road"), matched.group("distance")
        road = place_name_en(road) or road
        arrival = _arrival_phrase(matched.group("action"))
        if arrival:
            return "Walk {distance} m along {road} to {arrival}".format(
                distance=distance, road=road, arrival=arrival)
        action = _walk_action_en(matched.group("action"))
        if not action:
            return None
        return "Walk {distance} m along {road}, {action}".format(
            distance=distance, road=road, action=action)
    matched = re.match(r"^沿(?P<road>.+?)步行(?P<distance>\d+)米$", value)
    if matched:
        return "Walk {distance} m along {road}".format(
            distance=matched.group("distance"), road=place_name_en(matched.group("road")) or matched.group("road"))
    matched = re.match(r"^步行(?P<distance>\d+)米到达(?P<destination>.+)$", value)
    if matched:
        destination = matched.group("destination").strip()
        if destination in _DESTINATION_WORDS:
            return "Walk {distance} m to arrive at your destination".format(distance=matched.group("distance"))
        return "Walk {distance} m to reach {destination}".format(
            distance=matched.group("distance"), destination=place_name_en(destination) or destination)
    matched = re.match(r"^步行(?P<distance>\d+)米$", value)
    if matched:
        return "Walk {distance} m".format(distance=matched.group("distance"))
    matched = re.match(r"^步行(?P<distance>\d+)米(?P<action>.+)$", value)
    if matched:
        action = _walk_action_en(matched.group("action"))
        if not action:
            return None
        return "Walk {distance} m, {action}".format(distance=matched.group("distance"), action=action)
    return _walk_action_en(value)


def translate_amap_instructions(values):
    """按顺序翻译一组指令。

    能翻的片段翻成英文，翻不出的片段**原样保留**（不猜义、不丢信息）；
    整条指令一条都翻不出来时才返回 None（避免英文行退化成中文的重复）。
    """
    pieces = [clean_text(value) for value in (values or [])]
    pieces = [piece for piece in pieces if piece]
    if not pieces:
        return None
    translated, any_english = [], False
    for piece in pieces:
        english = translate_amap_instruction(piece)
        if english:
            translated.append(english)
            any_english = True
        else:
            translated.append(piece)
    return "; ".join(translated) if any_english else None
