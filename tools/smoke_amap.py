"""Check real Amap directions without modifying module config or saved trips.

Key comes only from AMAP_WEB_KEY. Output intentionally excludes credentials,
request URLs, station access details and full provider exception messages.
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modules.route_adapter.providers import AmapProvider, ProviderError
from modules.trip_engine.poi_seed import POIS

# Meanings from https://developer.amap.com/api/webservice/guide/tools/info.
# Use our own fixed text, never the provider's raw info or exception message.
CODE_HINTS = {
    '10001': 'Key 不正确或已过期；核对复制的是完整的 Web服务 Key。',
    '10002': '服务权限或接口路径有误；核对控制台的路径规划权限。',
    '10003': '调用量超过限制；核对控制台的当前额度。',
    '10004': '请求过于频繁；稍后重试并核对调用频率。',
    '10005': '请求出口 IP 不在白名单中；核对控制台的 IP 白名单。',
    '10006': '绑定域名无效；核对控制台配置。',
    '10007': '数字签名校验失败；当前接入未实现 sig，需核对 Key 的签名配置。',
    '10009': 'Key 平台不匹配；使用 Web服务 Key，不能使用 Web端(JS API) Key。',
    '10012': '服务权限不足；核对控制台的服务授权。',
    '10013': 'Key 已被删除；核对控制台中该 Key 是否仍有效。',
}
CATEGORY_HINTS = {
    'service_error': '高德返回失败；按 provider_code 核对官方错误码和控制台配置。',
    'http_error': 'HTTP 请求失败；根据 http_status 检查网络、代理或服务状态。',
    'timeout': '请求超时；检查网络连接后重试。',
    'certificate_error': 'HTTPS 证书校验失败；检查系统时间、Python 信任证书及代理证书配置。',
    'dns_error': '域名解析失败；检查 DNS 和网络连接。',
    'network_error': '网络连接失败；检查网络及代理配置。',
    'invalid_json': '响应不是有效 JSON；检查代理拦截或服务响应。',
    'invalid_response': '响应结构不符合预期；需要检查提供方数据格式。',
    'missing_route_fields': '路线返回了不完整的距离或耗时；需要检查提供方数据格式。',
    'no_route': '高德没有返回可用路线；检查起终点和路线条件。',
    'walking_duration_missing': '公交方案的步行路段缺少有效耗时；用 --diagnose 查看步行 steps 的字段状态。',
    'ride_duration_missing': '公交方案的乘车路段缺少有效耗时；用 --diagnose 查看 buslines 的字段状态。',
    'unsupported_transit_segment': '公交方案包含当前解析器不支持的火车或出租车字段；用 --diagnose 区分实际路段与空占位字段。',
    'transit_segments_missing': '公交方案未解析出路段；用 --diagnose 查看返回结构。',
}


def _field_state(value):
    if value is None:
        return 'missing'
    if value in ('', [], {}):
        return 'empty'
    return 'valid' if AmapProvider._number(value) is not None else 'invalid'


def _has_data(value):
    return AmapProvider._has_data(value)


def summarize_transit(payload):
    """Only field states and counts; never raw values, names, coordinates or URLs."""
    route = payload.get('route') if isinstance(payload, dict) else None
    plans = route.get('transits') if isinstance(route, dict) else None
    if not isinstance(plans, list):
        return None
    summary = {'plan_count': len(plans), 'plans': []}
    for path in plans[:3]:
        if not isinstance(path, dict):
            summary['plans'].append({'structure': 'invalid'})
            continue
        raw_segments = path.get('segments')
        segments = raw_segments if isinstance(raw_segments, list) else []
        plan = {'duration': _field_state(path.get('duration')),
                'distance': _field_state(path.get('distance')),
                'segment_count': len(segments), 'segments': []}
        for item in segments[:12]:
            if not isinstance(item, dict):
                plan['segments'].append({'structure': 'invalid'})
                continue
            walking = item.get('walking')
            walking = walking if isinstance(walking, dict) else {}
            steps = walking.get('steps')
            steps = steps if isinstance(steps, list) else []
            bus = item.get('bus')
            lines = bus.get('buslines') if isinstance(bus, dict) else None
            lines = lines if isinstance(lines, list) else []
            plan['segments'].append({
                'walking': {'has_data': _has_data(walking),
                            'duration': _field_state(walking.get('duration')),
                            'distance': _field_state(walking.get('distance')),
                            'step_count': len(steps),
                            'timed_step_count': sum(isinstance(step, dict) and
                                _field_state(step.get('duration')) == 'valid' for step in steps)},
                'busline_count': len(lines),
                'buslines': [{'duration': _field_state(line.get('duration')),
                              'distance': _field_state(line.get('distance'))}
                             for line in lines[:3] if isinstance(line, dict)],
                'railway_has_data': _has_data(item.get('railway')),
                'taxi_has_data': _has_data(item.get('taxi')),
            })
        summary['plans'].append(plan)
    return summary


class DiagnosticAmapProvider(AmapProvider):
    def _request_json(self, url, timeout=2.0):
        payload = super()._request_json(url, timeout=timeout)
        self.response_summary = summarize_transit(payload)
        return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--modes', default='walk,taxi,transit', help='walk,taxi,transit 的逗号分隔子集；每种方式调用一次')
    parser.add_argument('--require-key', action='store_true', help='缺 key 时以退出码2失败，供CI使用')
    parser.add_argument('--diagnose', action='store_true', help='显示公交返回的字段状态和数量，不输出原始响应或个人信息')
    args = parser.parse_args()
    modes = list(dict.fromkeys(args.modes.split(',')))
    if not modes or any(m not in {'walk', 'taxi', 'transit'} for m in modes):
        parser.error('modes 只能包含 walk,taxi,transit')
    if not os.environ.get('AMAP_WEB_KEY'):
        print(json.dumps({'status':'skipped', 'reason':'未设置 AMAP_WEB_KEY（Web服务 key）；未发出真实请求'}, ensure_ascii=False))
        return 2 if args.require_key else 0
    pois = {p['poi_id']:p for p in POIS}
    start, end = (pois[p]['coordinate'] for p in ('sh_poi_00042','sh_poi_00088'))
    provider_class = DiagnosticAmapProvider if args.diagnose else AmapProvider
    provider = provider_class({'city':'上海', 'timeout_seconds':8})
    rows = []
    for mode in modes:
        provider.response_summary = None
        try:
            result = provider.compute(start, end, mode, 'solo', {})
            valid = result.get('data_source') == 'amap' and result.get('duration_seconds', 0) > 0 and result.get('distance_meters', 0) > 0
            if mode == 'transit':
                valid = valid and bool(result.get('segments'))
            rows.append({'mode':mode,'status':'passed' if valid else 'failed', 'data_source':result.get('data_source'),
                         'duration_seconds':result.get('duration_seconds'), 'distance_meters':result.get('distance_meters'),
                         'segment_count':len(result.get('segments') or [])})
        except ProviderError as error:
            diagnostic = error.diagnostic
            hint = CODE_HINTS.get(diagnostic.get('provider_code')) or CATEGORY_HINTS.get(
                diagnostic.get('category'), '未取得可用路线；需要进一步检查请求配置或返回格式。')
            rows.append({'mode':mode,'status':'failed','reason':error.reason,
                         'diagnostic':diagnostic,'hint':hint})
        except Exception:
            rows.append({'mode':mode,'status':'failed','reason':'unexpected_provider_error'})
        if args.diagnose and provider.response_summary is not None:
            rows[-1]['response_summary'] = provider.response_summary
    passed = all(row['status'] == 'passed' for row in rows)
    print(json.dumps({'status':'passed' if passed else 'failed','routes':rows},ensure_ascii=False,indent=2))
    return 0 if passed else 1

if __name__ == '__main__':
    raise SystemExit(main())
