"""上游引擎发现与调用（web_workbench 专用）。

它是唯一可以代表用户调用其他模块的模块，因此：
    · 从 data/_registry/<id>.json 读上游的 base_url 与 token；
    · 令牌只在本进程内使用，绝不下发浏览器；
    · 上游缺失/未就绪不抛异常崩掉，而是记录状态供前端展示。
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

UPSTREAMS = ("trip_engine", "rules_engine", "route_adapter", "offline_kit", "recommendation_engine")
PROBE_TIMEOUT = 1.0
CALL_TIMEOUT = 20.0
READY_TTL = 5.0      # 就绪状态的缓存时长
NOT_READY_TTL = 0.5  # 未就绪时短缓存：避免 3 秒轮询打爆上游，同时能快速发现「刚起来」


class UpstreamError(Exception):
    """转发上游失败：保留上游的错误码与状态，便于前端按契约处理。"""

    def __init__(self, status: int, code: str, message: str, details=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details or {}


class ServiceRegistry:
    def __init__(self, workspace_root: Path | str, ready_ttl: float = READY_TTL,
                 not_ready_ttl: float = NOT_READY_TTL):
        self.root = Path(workspace_root)
        self.registry_dir = self.root / "data" / "_registry"
        self.ready_ttl = ready_ttl
        self.not_ready_ttl = not_ready_ttl
        self._cache: dict[str, tuple[float, dict]] = {}

    # ------------------------------------------------------------ 发现

    def record(self, module_id: str) -> dict | None:
        path = self.registry_dir / f"{module_id}.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if isinstance(payload, dict) and payload.get("base_url") and payload.get("token"):
            return payload
        return None

    def status_of(self, module_id: str) -> dict:
        """返回 {ready, base_url, health, detail}。

        缓存策略：就绪结果缓存久一点（READY_TTL），未就绪结果只缓存很短时间。
        否则「模块刚启动」这一刻的失败结果会被反复续期，界面永远显示未就绪。
        """
        now = time.monotonic()
        cached = self._cache.get(module_id)
        if cached:
            ttl = self.ready_ttl if cached[1]["ready"] else self.not_ready_ttl
            if now - cached[0] < ttl:
                return cached[1]
        record = self.record(module_id)
        info = {"module_id": module_id, "ready": False, "base_url": "", "health": "not_running",
                "detail": "未运行（无注册文件）"}
        if record:
            info["base_url"] = record["base_url"]
            health = self._probe(record["base_url"])
            if health is None:
                info.update(health="unreachable", detail="已注册端口但服务无响应")
            else:
                detail = "就绪" if health.get("ready", True) else "已启动但未就绪"
                if module_id == "route_adapter" and health.get("degraded_reason") == "provider_not_configured":
                    detail = "路线服务未读取 API Key；使用高德时，请在设置 AMAP_WEB_KEY 的终端重新启动整个软件"
                info.update(ready=bool(health.get("ready", True)),
                            health=str(health.get("status", "ok")),
                            detail=detail)
        self._cache[module_id] = (now, info)
        return info

    def snapshot(self) -> dict:
        """给前端的依赖概览：哪些引擎可用、缺哪个、缺了会影响什么。"""
        items = {module_id: self.status_of(module_id) for module_id in UPSTREAMS}
        notes = {
            "trip_engine": "行程数据的读写（必需）",
            "rules_engine": "时序推演与 Rule-01~04（未接入时编排页只显示数据、不做冲突提示）",
            "route_adapter": "门到门路线与三模态对比卡（未接入时无法显示区间耗时）",
            "offline_kit": "离线包与问路卡（未接入时无此功能）",
            "recommendation_engine": "按兴趣与日期生成推荐游玩安排（未接入时仍可手动规划）",
        }
        return {
            "services": [dict(info, purpose=notes.get(module_id, "")) for module_id, info in items.items()],
            "ready": {module_id: info["ready"] for module_id, info in items.items()},
        }

    @staticmethod
    def _probe(base_url: str) -> dict | None:
        try:
            with urllib.request.urlopen(base_url.rstrip("/") + "/health", timeout=PROBE_TIMEOUT) as response:
                payload = json.loads(response.read(4096).decode("utf-8"))
        except (urllib.error.URLError, OSError, ValueError):
            return None
        if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
            return payload["data"]
        return payload if isinstance(payload, dict) else None

    # ------------------------------------------------------------ 调用

    def call(self, module_id: str, method: str, path: str, payload=None, headers=None) -> dict:
        """转发到上游并解开响应信封；上游不可用或返回错误时抛 UpstreamError。"""
        record = self.record(module_id)
        if record is None:
            raise UpstreamError(503, "UPSTREAM_DOWN", f"{module_id} 未运行，无法完成该操作",
                                {"module_id": module_id})
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(record["base_url"].rstrip("/") + path, data=body,
                                         method=method.upper())
        request.add_header("X-Module-Token", record["token"])
        request.add_header("Content-Type", "application/json; charset=utf-8")
        for key, value in (headers or {}).items():
            if value is not None:
                request.add_header(key, str(value))
        try:
            with urllib.request.urlopen(request, timeout=CALL_TIMEOUT) as response:
                envelope = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                detail = json.loads(raw).get("error", {})
            except (ValueError, AttributeError):
                detail = {}
            raise UpstreamError(exc.code, detail.get("code", "UPSTREAM_ERROR"),
                                detail.get("message", f"{module_id} 返回 HTTP {exc.code}"),
                                detail.get("details")) from exc
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise UpstreamError(504, "UPSTREAM_TIMEOUT", f"无法连接 {module_id}：{exc}",
                                {"module_id": module_id}) from exc
        if not envelope.get("ok"):
            error = envelope.get("error") or {}
            raise UpstreamError(502, error.get("code", "UPSTREAM_ERROR"),
                                error.get("message", f"{module_id} 返回失败"), error.get("details"))
        return envelope.get("data")
