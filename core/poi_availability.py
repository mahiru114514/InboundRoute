"""只读闭馆日期判定，供推荐与规则引擎共同使用。"""


def closure_rule_covers(rule: dict, date_str: str) -> bool:
    if rule.get('date') == date_str:
        return True
    date_from = rule.get('date_from')
    date_to = rule.get('date_to')
    if date_from and date_to:
        return date_from <= date_str <= date_to
    if date_from:
        return date_from <= date_str
    if date_to:
        return date_str <= date_to
    return False


def closure_hit(closure_rules: list[dict], date_str: str, weekday: int) -> tuple:
    """开放例外优先；其他闭馆规则保持契约中原有顺序。"""
    open_hit = None
    best = None
    for rule in closure_rules or []:
        kind = rule.get('kind')
        if kind == 'holiday_exception_open' and closure_rule_covers(rule, date_str):
            open_hit = rule
        elif kind == 'holiday_exception_closed' and closure_rule_covers(rule, date_str):
            if best is None:
                best = (kind, rule)
        elif kind in ('special_period', 'maintenance') and closure_rule_covers(rule, date_str):
            if best is None:
                best = (kind, rule)
        elif kind == 'weekly' and rule.get('weekday') == weekday:
            if best is None:
                best = (kind, rule)
    if open_hit is not None:
        return 'holiday_exception_open', open_hit
    return best if best is not None else (None, None)
