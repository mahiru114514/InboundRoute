"""离线地名显示译名；只查已核录资料，不依赖网络，也不生成车站/出入口事实。"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

_HAN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U0002fa1f\U00030000-\U000323af]")
_DATA = Path(__file__).resolve().parent / "data"


def _text(value):
    return (value.strip() or None) if isinstance(value, str) else None


def has_chinese(value):
    return bool(isinstance(value, str) and _HAN.search(value))


@lru_cache(maxsize=1)
def place_reference():
    names = {}
    # 复用现有站名与景点主数据；新增译名表只保存显示名，不创建假站台记录。
    paths = [_DATA / "curated_stations.json",
             _DATA.parent.parent / "trip_engine/data/shanghai_pois_v1.json",
             _DATA.parent.parent / "trip_engine/data/shanghai_pois_v2.json"]
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            for row in data if isinstance(data, list) else []:
                pair = row.get("names") or {}
                zh, en = _text(pair.get("zh-Hans")), _text(pair.get("en"))
                if zh and en and not has_chinese(en):
                    names[zh] = en
        except (OSError, ValueError, TypeError, AttributeError):
            continue
    try:
        data = json.loads((_DATA / "curated_place_names.json").read_text(encoding="utf-8-sig"))
        for zh, row in data.get("places", {}).items():
            en = _text(row.get("en"))
            if _text(zh) and en and not has_chinese(en) and row.get("source") in data.get("sources", {}):
                names[zh] = en
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    # 全网地铁显示译名与住宿库：不创建站台/方向/出入口业务记录。
    try:
        metro = json.loads((_DATA / "metro_display_names.json").read_text(encoding="utf-8"))
        for zh, en in metro.get("places", {}).items():
            if _text(zh) and _text(en) and not has_chinese(en):
                names.setdefault(zh, en)
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    try:
        anchors = json.loads((_DATA.parent.parent / "trip_engine/data/anchors.json").read_text(encoding="utf-8"))
        for row in [*anchors.get("hotels", []), *anchors.get("hubs", [])]:
            zh, en = _text(row.get("name_zh")), _text(row.get("name_en"))
            if zh and en and not has_chinese(en):
                names.setdefault(zh, en)
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return names


def place_name_en(value):
    """完整地名匹配；辅路/括注/两条已知道路组成的公交站名按结构组合。未知名称留空。"""
    name = _text(value)
    if not name:
        return None
    if not has_chinese(name):
        return name
    names = place_reference()
    if name in names:
        return names[name]
    if name in ("北广场", "南广场", "东广场", "西广场"):
        return {"北":"North", "南":"South", "东":"East", "西":"West"}[name[0]] + " Square"
    if name.endswith("地铁站"):
        station = place_name_en(name[:-3])
        return station + " Metro Station" if station else None
    # 用户锚点可能已保存「中文 / English」合并名。
    for part in reversed(name.split(" / ")):
        if part.strip() and not has_chinese(part):
            return part.strip()
    if name.endswith("辅路"):
        road = names.get(name[:-2])
        return road + " service road" if road else None
    if name.endswith("步行街"):
        road = names.get(name[:-3])
        return road + " pedestrian street" if road else None
    annotation = re.fullmatch(r"(.+?)[（(](.+)[）)]", name)
    if annotation:
        base, detail = (place_name_en(part) for part in annotation.groups())
        if base and detail:
            return base + " (" + detail + ")"
    # 只有全文恰好等于两条已知道路才组合，防止把未知商家/同名地名误替换。
    for index in range(1, len(name)):
        left, right = name[:index], name[index:]
        if left in names and right in names and all(
                re.search(r"(?:路|大道|街)$", part) for part in (left, right)):
            return names[left] + " / " + names[right]
    return None


def translate_place_tokens(value):
    """补齐旧英文字段中的中文地名；整个中文片段未知则保留，不做子串猜译。"""
    text = _text(value)
    if not text:
        return None
    return re.sub(r"[\u3400-\u4dbf\u4e00-\u9fff0-9·]+(?:[（(][\u3400-\u4dbf\u4e00-\u9fff0-9·]+[）)])?",
                  lambda match: place_name_en(match.group()) or match.group(), text)


def english_place_name(name_zh, stored=None):
    """完整的既有英文优先；空值、重复中文、混合地名用核录译名补齐。"""
    english = _text(stored)
    if english and not has_chinese(english):
        return english
    translated = place_name_en(name_zh)
    if translated:
        return translated
    repaired = translate_place_tokens(english)
    return repaired if repaired and not has_chinese(repaired) else None


def localized_endpoint(point):
    if not isinstance(point, dict):
        return point
    return {**point, "name_en": english_place_name(point.get("name_zh"), point.get("name_en"))}
