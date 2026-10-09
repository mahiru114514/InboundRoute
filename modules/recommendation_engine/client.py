"""只读调用 trip_engine；驻留客户端每次请求重新解析注册表。"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from urllib.parse import quote


class UpstreamError(Exception):
    def __init__(self, status, code, message, details=None):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message
        self.details = details or {}


class TripEngineClient:
    def __init__(self, base_url, token, timeout=20.0, resolver=None):
        self.base_url, self.token = base_url.rstrip('/'), token
        self.timeout, self.resolver = timeout, resolver

    def _connection(self):
        # 返回请求私有快照，避免线程并发导致地址与令牌混用。
        if self.resolver is None:
            return self.base_url, self.token
        try:
            record = self.resolver()
        except (OSError, ValueError, RuntimeError) as exc:
            raise UpstreamError(503, 'UPSTREAM_TIMEOUT', f'trip_engine 注册信息不可用：{exc}') from exc
        if record is None:
            raise UpstreamError(503, 'UPSTREAM_TIMEOUT', 'trip_engine 未运行，请先启动行程引擎。')
        return record.base_url.rstrip('/'), record.token

    def _request(self, method, path, payload=None, authenticated=True):
        base_url, token = self._connection()
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode('utf-8')
        request = urllib.request.Request(base_url + path, data=body, method=method)
        request.add_header('Content-Type', 'application/json; charset=utf-8')
        if authenticated:
            request.add_header('X-Module-Token', token)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout if authenticated else min(self.timeout, 2)) as response:
                status, raw = response.status, response.read()
        except urllib.error.HTTPError as exc:
            status, raw = exc.code, exc.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise UpstreamError(503, 'UPSTREAM_TIMEOUT', f'trip_engine 不可达：{exc}') from exc
        try:
            envelope = json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise UpstreamError(502, 'UPSTREAM_BAD_RESPONSE', 'trip_engine 响应不是有效 JSON') from exc
        if not isinstance(envelope, dict) or type(envelope.get('ok')) is not bool:
            raise UpstreamError(502, 'UPSTREAM_BAD_RESPONSE', 'trip_engine 响应信封无效')
        if envelope['ok'] is False:
            error = envelope.get('error')
            if not isinstance(error, dict):
                raise UpstreamError(502, 'UPSTREAM_BAD_RESPONSE', 'trip_engine 错误信封无效')
            raise UpstreamError(status if status >= 400 else 502, error.get('code', 'UPSTREAM_BAD_RESPONSE'),
                                error.get('message', 'trip_engine 请求失败'), error.get('details'))
        if status >= 400 or not isinstance(envelope.get('data'), dict):
            raise UpstreamError(502, 'UPSTREAM_BAD_RESPONSE', 'trip_engine 响应数据无效')
        return envelope['data']

    def get_trip(self, trip_id):
        return self._request('GET', '/trips/' + quote(trip_id, safe=''))

    def preview_trip(self, setup):
        return self._request('POST', '/trips:preview', setup)

    def list_pois(self):
        return self._request('GET', '/pois')

    def health(self):
        try:
            data = self._request('GET', '/health', authenticated=False)
            return {'ok': True, 'data': data}
        except UpstreamError:
            return None
