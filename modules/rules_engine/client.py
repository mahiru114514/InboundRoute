"""rules_engine 的上游客户端：只通过本地 HTTP 调 trip_engine，不 import 其代码。"""
from __future__ import annotations

import json
import urllib.error
import urllib.request


class UpstreamError(Exception):
    """上游调用失败。code 对齐 contracts/errors.json 的 UPSTREAM_*。"""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class TripEngineClient:
    """trip_engine 的 HTTP 客户端。

    `resolver` 可选：每次请求前用它重新解析上游注册信息。
    trip_engine 重启会换端口和令牌，如果抱着启动时读到的那份不放，
    之后每个请求都会打到一个已死端口上（表现为「上游不可达」但对方其实在正常运行）。
    传 `None` 表示地址固定——只有测试和一次性脚本才应该这么做。
    """

    def __init__(self, base_url: str, token: str, timeout: float = 20.0, resolver=None):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.resolver = resolver

    def refresh(self) -> bool:
        """重新解析上游地址与令牌；拿到新注册信息返回 True。

        拿不到（注册文件被删/不可读）时保留上一次的值并返回 False：
        让调用方去撞真实的连接错误，而不是把「上游没了」伪装成别的问题。
        """
        if self.resolver is None:
            return True
        record = self.resolver()
        if record is None:
            return False
        self.base_url = str(record.base_url).rstrip("/")
        self.token = record.token
        return True

    def _request(self, method: str, path: str, payload: dict | None = None,
                 headers: dict | None = None) -> dict:
        self.refresh()
        url = self.base_url + path
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(url, data=body, method=method.upper())
        request.add_header("X-Module-Token", self.token)
        request.add_header("Content-Type", "application/json; charset=utf-8")
        for key, value in (headers or {}).items():
            request.add_header(key, value)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                status = response.status
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            status = exc.code
            raw = exc.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, OSError) as exc:
            raise UpstreamError(503, "UPSTREAM_TIMEOUT", f"trip_engine 不可达：{exc}") from exc

        try:
            envelope = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise UpstreamError(502, "UPSTREAM_BAD_RESPONSE", f"上游响应不是 JSON：{exc}") from exc
        if not isinstance(envelope, dict) or not envelope.get("ok"):
            error = (envelope or {}).get("error") or {}
            # 透传上游原始错误码（如 TRIP_NOT_FOUND / VERSION_CONFLICT），网络层失败才用 UPSTREAM_*。
            raise UpstreamError(
                status, error.get("code", "UPSTREAM_ERROR"), error.get("message", "上游请求失败"))
        return envelope.get("data")

    def get_trip(self, trip_id: str) -> dict:
        return self._request("GET", f"/trips/{trip_id}")

    def get_poi(self, poi_id: str) -> dict:
        return self._request("GET", f"/pois/{poi_id}")

    def patch_trip(self, trip_id: str, payload: dict, expected_version: int | None = None) -> dict:
        headers = {"If-Match": str(expected_version)} if expected_version is not None else None
        return self._request("PATCH", f"/trips/{trip_id}", payload, headers=headers)

    def health(self) -> dict | None:
        """探测上游 /health（无需令牌）；失败返回 None。"""
        self.refresh()
        request = urllib.request.Request(self.base_url + "/health", method="GET")
        try:
            with urllib.request.urlopen(request, timeout=min(self.timeout, 2.0)) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
            return None
