"""问路卡模板（C9）：5 类节点 + 方向缺失降级。只固化模板键与参数，不固化最终文案（多语言）。"""
from __future__ import annotations

# 模板文案冻结自 contracts/mappings.json#/ask_card_templates
ASK_CARD_TEMPLATES = {
    "station_entrance": {"zh": "请问去往 {access_name_zh} 怎么走？", "en": "Excuse me, which way is {access_name_en}?", "ja": "すみません、{access_name_en} へはどう行けばよいですか？", "ko": "실례합니다, {access_name_en}에는 어떻게 가나요?"},
    "transfer": {"zh": "请问换乘 {line_name_zh} 怎么走？", "en": "Excuse me, how do I transfer to {line_name_en}?", "ja": "すみません、{line_name_en} へはどう乗り換えればよいですか？", "ko": "실례합니다, {line_name_en}으로 어떻게 환승하나요?"},
    "station_exit": {"zh": "请问 {access_name_zh} 在哪个方向？", "en": "Excuse me, which way is {access_name_en}?", "ja": "すみません、{access_name_en} はどちらですか？", "ko": "실례합니다, {access_name_en}은 어느 방향인가요?"},
    "drop_off": {"zh": "请把我送到 {desc_zh}。", "en": "Please drop me off at {desc_en}.", "ja": "{desc_en} で降ろしてください。", "ko": "{desc_en}에서 내려 주세요."},
    "poi_arrival": {"zh": "请问 {poi_name_zh} 怎么走？", "en": "Excuse me, how do I get to {poi_name_en}?", "ja": "すみません、{poi_name_en} へはどう行けばよいですか？", "ko": "실례합니다, {poi_name_en}에는 어떻게 가나요?"},
    "direction_fallback": {"zh": "请问 {line_name_zh} 怎么走？", "en": "Excuse me, which way is {line_name_en}?", "ja": "すみません、{line_name_en} はどちらですか？", "ko": "실례합니다, {line_name_en}은 어느 방향인가요?"},
}

ASK_CARD_NODES = ("station_entrance", "transfer", "station_exit", "drop_off", "poi_arrival")


def card(node_type, args):
    """返回问路卡（模板键 + 参数）。方向缺失时对 transfer 走 direction_fallback。"""
    if node_type == "transfer" and not args.get("line_name_zh") and not args.get("line_name_en"):
        return None
    if node_type not in ASK_CARD_NODES:
        raise ValueError("未知问路卡节点：" + str(node_type))
    return {"node_type": node_type, "template_key": node_type, "args": dict(args)}


def transfer_card(line_name_zh=None, line_name_en=None, direction_present=True):
    """换乘问路卡：方向字段缺失时退回 direction_fallback。"""
    template_key = "transfer" if direction_present else "direction_fallback"
    return {"node_type": "transfer", "template_key": template_key,
            "args": {"line_name_zh": line_name_zh, "line_name_en": line_name_en}}


def render(card, lang="zh"):
    template = ASK_CARD_TEMPLATES.get(card["template_key"], {})
    text = template.get(lang) or template.get("en", "")
    try:
        return text.format(**card.get("args", {}))
    except (KeyError, IndexError):
        return text
